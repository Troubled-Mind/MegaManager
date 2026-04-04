import os
import json
import subprocess
import threading
import time
from database import get_db
from models import File, MegaAccount
from utils.config import cmd, settings

def run(args=None):
    if not args or ":" not in args:
        return {"status": 400, "message": "Usage: upload-local-file:<file_id>:<mega_account_id>"}

    try:
        file_id_str, account_id_str = args.split(":")
        file_id = int(file_id_str)
        account_id = int(account_id_str)
    except ValueError:
        return {"status": 400, "message": "Invalid file or account ID."}

    with get_db() as session:
        file = session.query(File).filter(File.id == file_id).first()
        if not file:
            return {"status": 404, "message": f"No file found with ID {file_id}"}

        if not file.l_path or not file.l_folder_name:
            return {"status": 400, "message": "Missing local path or folder name"}

        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        if not account:
            return {"status": 404, "message": f"No MEGA account found with ID {account_id}"}

        local_full_path = os.path.join(file.l_path, file.l_folder_name)

        if not os.path.exists(local_full_path):
            return {"status": 404, "message": f"Local folder does not exist: {local_full_path}"}

        # Get the base paths from settings
        local_paths = settings.get("local_paths", [])
        if isinstance(local_paths, str):
            try:
                local_paths = json.loads(local_paths)
            except Exception as e:
                print(f"ERROR Failed to parse local_paths: {e}")
                return {"status": 400, "message": "local_paths must be a valid JSON list string"}
        
        if not isinstance(local_paths, list):
            print(f"ERROR Invalid local_paths format, expected a list but got {type(local_paths)}")
            return {"status": 400, "message": "local_paths should be a list"}

        # Map local path to mega path structure
        mega_target_path = local_full_path
        for local_base in local_paths:
            if local_full_path.startswith(local_base):
                mega_target_path = "/" + local_full_path[len(local_base):].lstrip(os.sep)
                break
        else:
            print(f"WARNING No matching base path found for {local_full_path}. Using full local path.")

        # Desired remote location: e.g. /Musicals/TickBOOM/Video
        # We should upload to the PARENT of this path so MEGA creates the 'Video' folder inside the parent.
        mega_remote_parent = os.path.dirname(mega_target_path)
        if not mega_remote_parent:
            mega_remote_parent = "/"

        print(f"INFO Upload target parent on MEGA: {mega_remote_parent} (mapped from {mega_target_path})")

        # Mark the file as 'In Progress' immediately
        file.upload_status = 'In Progress'
        file.upload_progress = 0
        session.commit()

        # Perform the upload in a separate thread
        upload_thread = threading.Thread(target=upload_file_in_thread, args=(file_id, account_id, mega_remote_parent, local_full_path))
        upload_thread.start()

    return {"status": 200, "message": "Upload started in background."}

def upload_file_in_thread(file_id, account_id, mega_remote_parent, local_full_path):
    """Function to run the upload process in a separate thread."""
    try:
        with get_db() as session:
            account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
            if not account:
                print(f"ERROR No MEGA account found with ID {account_id}")
                return

            # Persistent Session Management
            print(f"INFO Ensuring session for {account.email}...")
            
            # Check current login
            whoami = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True)
            current_user = whoami.stdout.strip() if whoami.returncode == 0 else ""
            
            if account.email.lower() not in current_user.lower():
                if "not logged in" not in current_user.lower() and current_user:
                    print(f"INFO Switching from {current_user} to {account.email}...")
                    subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Perform fresh login
                login_res = subprocess.run([cmd("mega-login"), account.email, account.password], capture_output=True, text=True)
                if login_res.returncode != 0:
                    raise Exception(f"Failed to authenticate session for {account.email}. Error: {login_res.stderr.strip() or login_res.stdout.strip()}")
            
            print(f"INFO Session active for {account.email}")

            # Sanity check local path
            if not os.path.exists(local_full_path):
                raise Exception(f"Local path not found: {local_full_path}")
            
            # Ensure the cloud directory structure exists recursively
            print(f"INFO Ensuring cloud directory exists: {mega_remote_parent}")
            subprocess.run([cmd("mega-mkdir"), "-p", mega_remote_parent], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Start the upload process
            print(f"INFO Starting mega-put: {local_full_path} -> {mega_remote_parent}")
            # We use -c to continue if partial, and let mega-cmd-server handle the heavy lifting.
            process = subprocess.Popen([cmd("mega-put"), "-c", local_full_path, mega_remote_parent], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            stderr_output = []

            def monitor_stdout(pipe):
                for line in pipe:
                    if line:
                        msg = line.strip()
                        if "MB" in msg or "TRANSFERRING" in msg or "%" in msg:
                            update_file_progress(file_id, msg)
                        else:
                            print(f"MSG {msg}")

            def monitor_stderr(pipe):
                for line in pipe:
                    if line:
                        msg = line.strip()
                        stderr_output.append(msg)
                        if "access denied" in msg.lower():
                            print(f"CRITICAL REJECTED: {msg}")
                        print(f"WARNING {msg}")

            stdout_thread = threading.Thread(target=monitor_stdout, args=(process.stdout,))
            stderr_thread = threading.Thread(target=monitor_stderr, args=(process.stderr,))

            stdout_thread.start()
            stderr_thread.start()

            return_code = process.wait()
            stdout_thread.join()
            stderr_thread.join()

            if return_code != 0:
                error_summary = "\n".join(stderr_output)
                if return_code == 11 or "access denied" in error_summary.lower():
                    raise Exception("MEGA Transfer Quota (Bandwidth) likely reached. Try again later.")
                if return_code == 51:
                    raise Exception("Already exists on MEGA. Clear remote folder/file to retry.")
                raise Exception(f"mega-put error {return_code}: {error_summary}")

            print(f"INFO Upload execution final for {local_full_path}.")

            # Update DB
            with get_db() as final_session:
                file = final_session.query(File).filter(File.id == file_id).first()
                if file:
                    file.m_path = mega_remote_parent
                    file.m_folder_name = os.path.basename(local_full_path)
                    file.m_account_id = account.id
                    file.upload_progress = 100
                    file.upload_status = 'Completed'
                    final_session.commit()

                    # Trigger automatic refreshes
                    print(f"INFO Post-upload sync for file {file_id}...")
                    from utils.commands.accounts.account_login import process_account
                    from utils.commands.files.file_details import run as fetch_file_details
                    
                    try:
                        # 1. Update Account Quota
                        process_account(account_id)
                        # 2. Update File Size and Link
                        fetch_file_details(str(file_id))
                        print(f"INFO Auto-sync completed for file {file_id}")
                    except Exception as sync_err:
                        print(f"WARNING Non-critical post-sync error for file {file_id}: {sync_err}")

    except Exception as e:
        print(f"ERROR Error in upload thread: {e}")
        with get_db() as err_session:
            file = err_session.query(File).filter(File.id == file_id).first()
            if file:
                file.upload_status = 'Failed'
                err_session.commit()
    # Note: NO LOGOUT in finally. Let the session persist for performance and background resilience.

def update_file_progress(file_id, output):
    """Parses output and updates progress, speed, and ETA in a fresh session."""
    if "TRANSFERRING" in output:
        try:
            import re
            
            # 1. Parse Progress Percentage (Handles XX.XX% or XX%)
            progress = None
            progress_match = re.search(r"(\d+(?:\.\d+)?)\s*%", output)
            if progress_match:
                progress = float(progress_match.group(1))
            
            # 2. Parse Speed (e.g., '122 KB/s', '1.1 MB/s', or '1GB/s')
            speed = None
            speed_match = re.search(r"(\d+(?:\.\d+)?\s*[KMGT]B/s)", output, re.IGNORECASE)
            if speed_match:
                speed = speed_match.group(1)
            
            # 3. Parse ETA (e.g., '00:00:31' or '(00:00:31)')
            eta = None
            eta_match = re.search(r"\(?(\d{1,2}:\d{2}:\d{2})\)?", output)
            if eta_match:
                eta = eta_match.group(1)

            if progress is not None:
                with get_db() as session:
                    file = session.query(File).filter(File.id == file_id).first()
                    if file:
                        file.upload_progress = int(progress)
                        if speed: file.upload_speed = speed
                        if eta: file.upload_eta = eta
                        
                        if progress < 100:
                            file.upload_status = 'In Progress'
                        session.commit()
                        
        except (ValueError, Exception) as e:
            # Don't spam logs for every unparseable line, but log real errors
            pass

def calculate_folder_size(path):
    """Return folder size in bytes."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            fp = os.path.join(dirpath, filename)
            try:
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
            except Exception as e:
                print(f"WARNING Skipped file {fp}: {e}")
    return total_size

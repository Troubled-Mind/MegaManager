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

    session = next(get_db())

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
            print(f"❌ Failed to parse local_paths: {e}")
            return {"status": 400, "message": "local_paths must be a valid JSON list string"}
    
    if not isinstance(local_paths, list):
        print(f"❌ Invalid local_paths format, expected a list but got {type(local_paths)}")
        return {"status": 400, "message": "local_paths should be a list"}

    # Initialize mega_target_path as the full local path
    mega_target_path = local_full_path

    for local_base in local_paths:
        if local_full_path.startswith(local_base):
            # Remove the base path and prepend the relative path with "/"
            mega_target_path = "/" + local_full_path[len(local_base):].lstrip(os.sep)
            break
    else:
        # If no base path matches, print a warning
        print(f"⚠️ No matching base path found for {local_full_path}. Using the full local path.")

    print(f"☁️ Upload target path on MEGA: {mega_target_path}")

    # Perform the upload in a separate thread to allow UI updates
    upload_thread = threading.Thread(target=upload_file_in_thread, args=(file_id, account_id, session, mega_target_path, local_full_path))
    upload_thread.start()

    return {"status": 200, "message": "Upload started in background."}

def upload_file_in_thread(file_id, account_id, session, mega_target_path, local_full_path):
    """Function to run the upload process in a separate thread."""
    try:
        file = session.query(File).filter(File.id == file_id).first()
        if not file:
            print(f"❌ No file found with ID {file_id}")
            return {"status": 404, "message": f"No file found with ID {file_id}"}

        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        if not account:
            print(f"❌ No MEGA account found with ID {account_id}")
            return {"status": 404, "message": f"No MEGA account found with ID {account_id}"}

        # Login to MEGA
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run([cmd("mega-login"), account.email, account.password], check=True, text=True)
        print(f"✅ Logged in as {account.email}")

        # Start the upload process
        process = subprocess.Popen([cmd("mega-put"), '-c', local_full_path, mega_target_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Function to read stdout
        def read_stdout():
            while True:
                stdout_line = process.stdout.readline()
                if stdout_line == '' and process.poll() is not None:
                    break
                if stdout_line:
                    process_output(stdout_line.strip(), file, session)
                time.sleep(0.5)

        # Function to read stderr
        def read_stderr():
            while True:
                stderr_line = process.stderr.readline()
                if stderr_line == '' and process.poll() is not None:
                    break
                if stderr_line:
                    process_output(stderr_line.strip(), file, session)  # Update progress when reading stderr
                time.sleep(0.5)

        # Start the threads
        stdout_thread = threading.Thread(target=read_stdout)
        stderr_thread = threading.Thread(target=read_stderr)

        stdout_thread.start()
        stderr_thread.start()

        process.communicate()  # Wait for the process to finish

        stdout_thread.join()
        stderr_thread.join()

        print(f"☁️ Upload completed: {local_full_path} → {mega_target_path}")

        # After the upload is done, update the record in the database
        existing_record = session.query(File).filter(File.id == file_id).first()
        if existing_record:
            existing_record.m_path = os.path.dirname(mega_target_path)
            existing_record.m_folder_name = file.l_folder_name
            existing_record.m_account_id = account.id
            existing_record.upload_progress = 100
            existing_record.upload_status = 'Completed'
            session.add(existing_record)
        session.commit()

    except subprocess.CalledProcessError as e:
        print(f"❌ Upload failed: {e.stderr or e.stdout}")
        file.upload_status = 'Failed'  # Mark as failed if there's an error
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"❌ Error during upload: {str(e)}")
        file.upload_status = 'Failed'  # Mark as failed if there's an exception
        session.commit()
    finally:
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def process_output(output, file, session):
    """Handle the output from the mega-put command."""
    if "TRANSFERRING" in output:
        progress_line = output.split("||")[-1].strip()
        
        # Clean up the string to extract the percentage (after 'MB:')
        if "MB:" in progress_line:
            # Split by 'MB:' and take the second part
            parts = progress_line.split("MB:")[-1].strip()
            
            # Now split by spaces and take the part that is the percentage
            if "%" in parts:
                progress_str = parts.split()[0].replace('%', '').strip()  # Extract the percentage value
                
                try:
                    # Convert the cleaned string to a float
                    progress = float(progress_str)
                    print(f"✅ Progress: {progress}%")

                    # Update progress in the database
                    file.upload_progress = progress
                    if progress < 100:
                        file.upload_status = 'In Progress'
                    else:
                        file.upload_status = 'Completed'
                    session.commit()  # Commit the changes to the database

                except ValueError as e:
                    print(f"❌ Error parsing progress value: {e}")


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
                print(f"⚠️ Skipped file {fp}: {e}")
    return total_size

import os
import json
import subprocess
from database import get_db
from models import File, MegaAccount
from utils.config import cmd, settings

def run(args=None):
    print(f"📥 Raw args: {args} ({type(args)})")
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

    # Initialize mega_target_path to be the same as local_full_path initially
    mega_target_path = local_full_path

    # Iterate through all base paths and remove the matching base path from local_full_path
    for local_base in local_paths:
        # Ensure to match base_path and remove it from local_full_path
        if local_full_path.startswith(local_base):
            # Remove the base path and prepend the resulting relative path with "/"
            mega_target_path = "/" + local_full_path[len(local_base):].lstrip(os.sep)
            break
    else:
        print(f"⚠️ No matching base path found in {local_paths}. Using the full local path.")

    print(f"☁️ Upload target path on MEGA: {mega_target_path}")

    input()
    try:
        # Login to MEGA
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run([cmd("mega-login"), account.email, account.password], check=True, text=True)
        print(f"✅ Logged in as {account.email}")

        # Upload the folder to MEGA, using -c to preserve folder structure
        subprocess.run([cmd("mega-put"), '-c', local_full_path, mega_target_path], check=True, text=True)
        print(f"☁️ Uploaded: {local_full_path} → {mega_target_path}")

        # Update the file record with MEGA info
        file.m_path = mega_target_path
        file.m_folder_name = file.l_folder_name
        file.m_account_id = account.id
        session.commit()

        return {
            "status": 200,
            "message": f"Successfully uploaded {file.l_folder_name} to MEGA",
            "file_id": file.id
        }

    except subprocess.CalledProcessError as e:
        return {"status": 500, "message": f"Upload failed: {e.stderr or e.stdout}"}
    except Exception as e:
        session.rollback()
        return {"status": 500, "message": f"Error during upload: {str(e)}"}
    finally:
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

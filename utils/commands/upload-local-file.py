import os
import subprocess
from database import get_db
from models import File, MegaAccount
from utils.config import cmd

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

    full_path = os.path.join(file.l_path, file.l_folder_name)

    if not os.path.exists(full_path):
        return {"status": 404, "message": f"Local folder does not exist: {full_path}"}

    try:
        # Login to MEGA
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run([cmd("mega-login"), account.email, account.password], check=True, text=True)
        print(f"✅ Logged in as {account.email}")

        # Upload the folder
        subprocess.run([cmd("mega-put"), full_path, "/"], check=True, text=True)
        print(f"☁️ Uploaded: {full_path}")

        # Update the file record with MEGA info
        file.m_path = "/"
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

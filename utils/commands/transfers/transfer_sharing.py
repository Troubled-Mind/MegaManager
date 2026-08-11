import subprocess
import re
from database import get_db
from models import File, MegaAccount
from utils.config import cmd
from utils.mega_session import mega_session

def run(args=None, expiry=None):
    # Parse args if passed as string "file_id", "file_id:expiry", int, dict, or list
    file_id = None
    if isinstance(args, dict):
        file_id = args.get("file_id") or args.get("id")
        expiry = expiry or args.get("expiry")
    elif isinstance(args, (list, tuple)):
        if len(args) > 0:
            file_id = args[0]
        if len(args) > 1:
            expiry = expiry or args[1]
    elif isinstance(args, str):
        if ":" in args:
            parts = args.split(":", 1)
            file_id = parts[0]
            expiry = expiry or parts[1]
        else:
            file_id = args
    elif isinstance(args, int):
        file_id = args

    try:
        file_id = int(file_id)
    except (ValueError, TypeError):
        print(f"[ERROR] Invalid file ID format: {file_id}. Must be an integer.")
        return {"status": 400, "message": "Invalid file ID format. Must be an integer."}

    with get_db() as session:
        file_obj = session.query(File).filter(File.id == file_id).first()
        if not file_obj:
            print(f"[WARNING] File #{file_id} not found.")
            return {"status": 404, "message": f"File #{file_id} not found."}

        if not file_obj.m_account_id:
            print(f"[WARNING] File #{file_id} is not associated with any MEGA account.")
            return {"status": 400, "message": f"File #{file_id} is not associated with any MEGA cloud account."}

        account = session.query(MegaAccount).filter(MegaAccount.id == file_obj.m_account_id).first()
        if not account:
            print(f"[WARNING] Account #{file_obj.m_account_id} not found for file #{file_id}.")
            return {"status": 404, "message": f"MEGA account #{file_obj.m_account_id} not found."}

        path = (file_obj.m_path or "").rstrip('/')
        folder_name = file_obj.m_folder_name or ""
        if not path and not folder_name:
            return {"status": 400, "message": f"File #{file_id} does not have a cloud path set."}

        full_path = f"{path}/{folder_name}" if folder_name else path

        # Holds the process-wide MEGAcmd session lock for the login + export
        # below, so a concurrent upload/sync job can't log in as a different
        # account in between and redirect the export to the wrong place.
        with mega_session(account.email, account.password) as logged_in:
            if not logged_in:
                return {"status": 500, "message": f"Login failed for {account.email}"}

            try:
                export_cmd = [cmd("mega-export"), "-af", full_path.strip()]
                if expiry:
                    export_cmd += ["--expire", str(expiry)]

                export_result = subprocess.run(export_cmd, capture_output=True, text=True)
                if export_result.returncode != 0:
                    return {"status": 500, "message": f"Export failed: {export_result.stderr.strip()}"}

                match = re.search(r'https://mega\.nz/\S+', export_result.stdout)
                if not match:
                    print("[ERROR] Export succeeded but no link was found.")
                    return {"status": 500, "message": "Export succeeded but no link was found in output."}

                sharing_link = match.group(0)
                print(f"[INFO] Sharing link generated: {sharing_link}")

                file_obj.m_sharing_link = sharing_link
                session.commit()

                return {"status": 200, "link": sharing_link, "message": "Sharing link generated successfully"}
            except Exception as e:
                session.rollback()
                return {"status": 500, "message": f"Failed to generate sharing link: {str(e)}"}

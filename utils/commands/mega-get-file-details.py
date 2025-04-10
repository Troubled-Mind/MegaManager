import re
import subprocess
from database import get_db
from models import MegaFile, MegaAccount
from utils.config import cmd

def run(args=None):
    """Get the size and link of a MEGA file."""
    try:
        mega_file_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid MEGA file ID"}
    
    session = next(get_db())
    mega_file = session.query(MegaFile).filter(MegaFile.id == mega_file_id).first()
    if not mega_file:
        return {"status": 404, "message": f"No MEGA file found with ID {mega_file_id}"}
    full_path = mega_file.path + "/" + mega_file.folder_name
    account_id = mega_file.mega_account_id

    try:
        # Get mega account
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        if not account:
            return {"status": 404, "message": f"No MEGA account found with ID {account_id}"}
        
        # Login
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run([cmd("mega-login"), account.email, account.password], check=True, text=True)
        print(f"✅ Logged in: {account.email}")

        # Fetch file/folder size
        du_result = subprocess.run([cmd("mega-du"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        storage = parse_mega_du(du_result.stdout.strip())
        mega_file.folder_size = storage
        print(f"💾 Size: {storage}")

        # Fetch file link
        # Need to handle expiry dates
        export_result = subprocess.run([cmd("mega-export"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        link = parse_mega_export(export_result.stdout.strip())
        if link:
            mega_file.mega_sharing_link = link
            print(f"🔗 Link: {link}")

        # Logout
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Save changes to the database
        session.commit()
        return {
            "status": 200,
            "message": f"File details updated successfully for {mega_file.folder_name}",
            "folder_size": storage,
            "link": link
        }
    
    except subprocess.CalledProcessError as e:
        session.rollback()

        stdout = e.stdout.strip() if e.stdout else ""
        stderr = e.stderr.strip() if e.stderr else ""
        error_msg = stderr or stdout or f"Unknown error (code {e.returncode})"
        return {"status": 500, 
                "message": f"Error fetching file details: {error_msg}"}
    
    except Exception as e:
        session.rollback()
        return {"status": 500, "message": f"Error fetching file details: {str(e)}"}

def parse_mega_du(output):
    for line in output.splitlines():
        if "Total storage used:" in line:
            # Line is e.g. Total storage used:    60441276
            storage = line.strip().split()[-1]
            return int(storage)
    return 0

def parse_mega_export(output):
    match = re.search(r'https://mega\.nz/folder/[^\s)]+', output)
    if match:
        return match.group(0)
    else:
        return None

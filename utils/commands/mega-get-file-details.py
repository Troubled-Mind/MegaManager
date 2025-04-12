import re
import subprocess
from database import get_db
from models import File, MegaAccount
from utils.config import cmd

def run(args=None):
    """Get the size and link of a MEGA file."""
    try:
        file_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid MEGA file ID"}

    session = next(get_db())
    mega_file = session.query(File).filter(File.id == file_id).first()
    if not mega_file:
        return {"status": 404, "message": f"No MEGA file found with ID {file_id}"}

    if not mega_file.m_path or not mega_file.m_folder_name:
        return {"status": 400, "message": "Cloud path or folder name missing"}

    full_path = mega_file.m_path + "/" + mega_file.m_folder_name
    account_id = mega_file.m_account_id
    storage = 0
    link = None

    try:
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        if not account:
            return {"status": 404, "message": f"No MEGA account found with ID {account_id}"}

        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run([cmd("mega-login"), account.email, account.password], check=True, text=True)
        print(f"✅ Logged in: {account.email}")

        # Fetch file/folder size
        du_result = subprocess.run([cmd("mega-du"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        storage = parse_mega_du(du_result.stdout.strip())
        mega_file.m_folder_size = str(storage)  # ⬅️ Save as string, matching your DB expectations
        print(f"💾 Size: {storage}")

        # Fetch file link
        export_result = subprocess.run([cmd("mega-export"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        link = parse_mega_export(export_result.stdout.strip())
        mega_file.m_sharing_link = link
        print(f"🔗 Link: {link}")

        session.commit()
        return {
            "status": 200,
            "message": f"File details updated successfully for {mega_file.m_folder_name}",
            "file": {
                "id": mega_file.id,
                "m_path": mega_file.m_path,
                "m_folder_name": mega_file.m_folder_name,
                "m_folder_size": str(storage),
                "is_cloud": True,
                "cloud_email": account.email,
                "m_sharing_link": link,
            },
        }

    except subprocess.CalledProcessError as e:
        stdout = e.stdout.strip() if e.stdout else ""
        stderr = e.stderr.strip() if e.stderr else ""

        if "not exported" in stdout.lower():
            mega_file.m_folder_size = str(storage)
            mega_file.m_sharing_link = None
            session.commit()
            return {
                "status": 200,
                "message": f"File details updated (no link) for {mega_file.m_folder_name}",
                "file": {
                    "id": mega_file.id,
                    "m_path": mega_file.m_path,
                    "m_folder_name": mega_file.m_folder_name,
                    "m_folder_size": str(storage),
                    "is_cloud": True,
                    "cloud_email": account.email,
                },
                "m_sharing_link": None
            }

        return {
            "status": 500,
            "message": f"Error fetching file details: {stderr or stdout or f'Unknown error (code {e.returncode})'}"
        }

    except Exception as e:
        session.rollback()
        return {"status": 500, "message": f"Error fetching file details: {str(e)}"}

    finally:
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def parse_mega_du(output):
    for line in output.splitlines():
        if "Total storage used:" in line:
            try:
                return int(line.strip().split()[-1])
            except ValueError:
                return 0
    return 0


def parse_mega_export(output):
    match = re.search(r'https://mega\.nz/folder/[^\s)]+', output)
    return match.group(0) if match else None

import csv
import io
from database import get_db
from models import File, MegaAccount
from utils.config import cmd

FILENAME = "mega_accounts.csv"

def run(args=None):
    """Export data to a CSV file."""
    if not args:
        return {"status": 400, "message": "No arguments provided."}
    elif args == "accounts":
        return export_mega_accounts()
    elif args == "local_files":
        return export_local_files()
    elif args == "cloud_files":
        return export_cloud_files()
    else:
        return {"status": 400, "message": "Invalid argument provided."}

def export_mega_accounts():
    """Export all MEGA accounts to a CSV file."""
    session = next(get_db())
    accounts = session.query(MegaAccount).all()

    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["email", "password"]
    writer.writerow(headers)

    for account in accounts:
        writer.writerow([getattr(account, header) for header in headers])

    # Return file to be downloaded
    output.seek(0)
    return {
        "status": 200,
        "body": output.read()
    }

def export_local_files():
    """Export all local files to a CSV file."""
    session = next(get_db())
    files = session.query(File).filter(File.l_folder_name != None).all()

    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["l_path", "l_folder_name", "l_folder_size",]
    writer.writerow(headers)

    for file in files:
        writer.writerow([getattr(file, header) for header in headers])

    # Return file to be downloaded
    output.seek(0)
    return {
        "status": 200,
        "body": output.read()
    }

def export_cloud_files():
    """Export all cloud files to a CSV file."""
    session = next(get_db())
    files = session.query(File).filter(File.m_folder_name != None).all()

    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["MEGA Path", "Folder Name", "Folder Size", "Sharing Link", "Account Email"]
    writer.writerow(headers)

    for file in files:
        writer.writerow([
            file.m_path,
            file.m_folder_name,
            file.m_folder_size,
            file.m_sharing_link,
            file.account.email if file.account else None
        ])
    
    # Return file to be downloaded
    output.seek(0)
    return {
        "status": 200,
        "body": output.read()
    }

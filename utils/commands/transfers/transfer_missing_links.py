import re
import subprocess
from collections import defaultdict
import threading
from database import get_db
from models import File, MegaAccount
from utils.config import cmd
from utils.mega_session import mega_session

def run(args=None):
    """Generate missing MEGA sharing links in a background thread."""
    indexing_thread = threading.Thread(target=generate_missing_links_in_background)
    indexing_thread.start()

    return {
        "status": 200,
        "message": "Missing sharing links generation started in background."
    }

def generate_missing_links_in_background():
    """Wait for threads and perform the link generation."""
    print("Starting background generation of missing links...")

    try:
        with get_db() as session:
            # Get all files with no sharing link, but that have MEGA data
            files_to_export = session.query(File, MegaAccount).join(MegaAccount, File.m_account_id == MegaAccount.id).filter(
                File.m_path != None,
                (File.m_sharing_link == None) | (File.m_sharing_link == '')
            ).all()

            files_by_account = defaultdict(list)
            for f, acc in files_to_export:
                files_by_account[acc].append(f)

            for account, files in files_by_account.items():
                try:
                    # Holds the process-wide MEGAcmd session lock for this
                    # account's whole batch of exports, so a concurrent
                    # upload/sync job can't log in as a different account
                    # mid-loop and redirect these exports to the wrong place.
                    with mega_session(account.email, account.password) as logged_in:
                        if not logged_in:
                            print(f"Login failed for {account.email}")
                            continue

                        for file in files:
                            folder_name = file.m_folder_name or ""
                            path = (file.m_path or "").rstrip('/')
                            full_path = f"{path}/{folder_name}" if folder_name else path
                            export_cmd = [cmd("mega-export"), "-af", full_path]
                            export = subprocess.run(export_cmd, capture_output=True, text=True)

                            if export.returncode == 0:
                                match = re.search(r'https://mega\.nz/\S+', export.stdout)
                                if match:
                                    sharing_link = match.group(0)
                                    file.m_sharing_link = sharing_link
                                    print(f"Generated link for: {folder_name or full_path}")

                        session.commit()
                        print(f"Committed links for account: {account.email}")

                except Exception as e:
                    print(f"Error generating links for account {account.id}: {e}")

        print("Background link generation done.")
    except Exception as e:
        print(f"Unhandled error in background link generation: {e}")

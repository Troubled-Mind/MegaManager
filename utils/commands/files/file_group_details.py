import re
import subprocess
from collections import defaultdict
from database import get_db
from models import File, MegaAccount
from utils.config import cmd
from utils.mega_session import mega_session

import threading

def run(args=None):
    """Batch update MEGA file sizes and links grouped by account in a background thread."""
    indexing_thread = threading.Thread(target=grouped_details_in_background)
    indexing_thread.start()

    return {
        "status": 200,
        "message": "MEGA file details update started in the background."
    }

def grouped_details_in_background():
    """Wait for threads and perform the details update."""
    print("Starting background MEGA grouped file details update...")

    with get_db() as session:
        all_files = session.query(File).filter(File.m_path != None).all()
        files_by_account = defaultdict(list)
        for f in all_files:
            files_by_account[f.m_account_id].append(f)

        for account_id, files in files_by_account.items():
            account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
            if not account:
                continue

            try:
                # Holds the process-wide MEGAcmd session lock for this account's
                # whole batch of mega-du/mega-export calls, so a concurrent
                # upload/quota-refresh/other sync job can't log in as a
                # different account mid-loop and silently redirect these calls
                # (which previously left folder sizes stuck at 0/null).
                with mega_session(account.email, account.password) as logged_in:
                    if not logged_in:
                        print(f"Failed to log into {account.email}, skipping {len(files)} file(s)")
                        continue

                    print(f"Logged in: {account.email}")

                    for file in files:
                        full_path = f"{file.m_path}/{file.m_folder_name}"
                        try:
                            du_result = subprocess.run([cmd("mega-du"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                            storage = parse_mega_du(du_result.stdout.strip())
                            file.m_folder_size = storage

                            export_result = subprocess.run([cmd("mega-export"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                            link = parse_mega_export(export_result.stdout.strip())
                            file.m_sharing_link = link
                            print(f"Updated details for: {file.m_folder_name}")

                        except subprocess.CalledProcessError:
                            pass

                    session.commit()
                    print(f"Committed updates for account: {account.email}")

            except Exception as e:
                print(f"Error during account {account_id} update: {e}")

    print("Background MEGA details update done.")

def parse_mega_du(output):
    for line in output.splitlines():
        if "Total storage used:" in line:
            return int(line.strip().split()[-1])
    return 0

def parse_mega_export(output):
    match = re.search(r'https://mega\.nz/folder/[^\s)]+', output)
    return match.group(0) if match else None
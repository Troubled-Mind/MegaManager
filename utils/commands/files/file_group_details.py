import re
import subprocess
from collections import defaultdict
from database import get_db
from models import File, MegaAccount
from utils.config import cmd

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
    print("☁️ Starting background MEGA grouped file details update...")
    
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
                subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run([cmd("mega-login"), account.email, account.password], check=True, text=True)
                print(f"✅ Logged in: {account.email}")

                for file in files:
                    # Refresh file object within the loop to avoid stale session issues
                    # Actually, we are using the same session here, which is fine since we are in one thread
                    full_path = f"{file.m_path}/{file.m_folder_name}"
                    try:
                        du_result = subprocess.run([cmd("mega-du"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                        storage = parse_mega_du(du_result.stdout.strip())
                        file.m_folder_size = storage

                        export_result = subprocess.run([cmd("mega-export"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                        link = parse_mega_export(export_result.stdout.strip())
                        file.m_sharing_link = link
                        print(f"✅ Updated details for: {file.m_folder_name}")

                    except subprocess.CalledProcessError:
                        # Silently handle or mark error
                        pass
                
                session.commit()
                print(f"✅ Committed updates for account: {account.email}")

            except Exception as e:
                print(f"❌ Error during account {account_id} update: {e}")
            finally:
                subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    print("✅ Background MEGA details update done.")

def parse_mega_du(output):
    for line in output.splitlines():
        if "Total storage used:" in line:
            return int(line.strip().split()[-1])
    return 0

def parse_mega_export(output):
    match = re.search(r'https://mega\.nz/folder/[^\s)]+', output)
    return match.group(0) if match else None
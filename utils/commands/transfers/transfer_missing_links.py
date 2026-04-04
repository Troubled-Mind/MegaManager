import re
import sqlite3
import subprocess
from collections import defaultdict
from utils.config import cmd

import threading

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
    print("🔗 Starting background generation of missing links...")
    
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
                subprocess.run([cmd("mega-logout")], capture_output=True, text=True)
                login = subprocess.run([cmd("mega-login"), account.email, account.password], capture_output=True, text=True)

                if login.returncode != 0:
                    print(f"❌ Login failed for {account.email}: {login.stderr.strip()}")
                    continue

                for file in files:
                    full_path = f"{file.m_path.rstrip('/')}/{file.m_folder_name}"
                    export_cmd = [cmd("mega-export"), "-af", full_path]
                    export = subprocess.run(export_cmd, capture_output=True, text=True)

                    if export.returncode == 0:
                        match = re.search(r'https://mega\.nz/\S+', export.stdout)
                        if match:
                            sharing_link = match.group(0)
                            file.m_sharing_link = sharing_link
                            print(f"✅ Generated link for: {file.m_folder_name}")
                
                session.commit()
                print(f"✅ Committed links for account: {account.email}")

            except Exception as e:
                print(f"❌ Error generating links for account {account.id}: {e}")
            finally:
                subprocess.run([cmd("mega-logout")], capture_output=True, text=True)

    print("✅ Background link generation done.")

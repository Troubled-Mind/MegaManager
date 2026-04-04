import os
from socketserver import ThreadingMixIn
from http.server import HTTPServer
from database import create_database
from utils.config import settings, check_for_update, state
from utils.http_handler import CustomHandler 

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for better responsiveness."""
    daemon_threads = True

import threading
import time
import subprocess
from utils.config import cmd

def maintenance_worker():
    """Background worker to keep the state in sync."""
    print("INFO Maintenance service started.")
    is_first_run = True
    while True:
        try:
            from database import get_db
            from models import File, MegaAccount
            from utils.commands.accounts.account_login import process_account
            from utils.commands.files.file_details import run as fetch_file_details

            with get_db() as session:
                # 1. Check for active uploads
                active_uploads = session.query(File).filter(File.upload_status == "In Progress").count()
                state["uploads_active"] = active_uploads > 0

                # 2. Refresh Accounts every 30 mins (OR on boot)
                if is_first_run or (int(time.time()) % 1800 < 30):
                    accounts = session.query(MegaAccount).all()
                    for acc in accounts:
                        print(f"INFO Auto-syncing account: {acc.email}")
                        process_account(acc.id)

                # 3. Verify 'In Progress' uploads actually have a process
                # If a file is 'In Progress' but no mega-put is running, mark as Failed
                stalled_files = session.query(File).filter(File.upload_status == "In Progress").all()
                if stalled_files:
                    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                    for f in stalled_files:
                        if f.l_folder_name not in ps.stdout:
                           print(f"WARNING Detected stalled upload for {f.l_folder_name}. Marking as Failed.")
                           f.upload_status = "Failed"
                
                session.commit()

        except Exception as e:
            print(f"ERROR Maintenance service error: {e}")
        
        is_first_run = False
        state["booting"] = False
        time.sleep(1800) # Run every 30 minutes

def run_server():
    os.chdir(os.getcwd())  
    create_database()  # Ensure the database and schema are created
    check_for_update()  
    
    # Start Maintenance Thread
    threading.Thread(target=maintenance_worker, daemon=True).start()

    server_address = ("0.0.0.0", 6342)
    httpd = ThreadingHTTPServer(server_address, CustomHandler)
    settings.load()  # Load settings from the database
    print("Server running at http://localhost:6342/")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()

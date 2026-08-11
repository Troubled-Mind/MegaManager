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

CACHE_REFRESH_INTERVAL = 120

def maintenance_worker():
    """Background worker to keep state in sync and resume queued uploads."""
    print("INFO Maintenance service started.")
    is_first_run = True
    last_quota_refresh = 0
    last_cache_refresh = 0

    while True:
        try:
            from database import get_db
            from models import File, MegaAccount
            from utils.commands.accounts.account_login import process_account
            from utils.commands.transfers.transfer_upload import ensure_upload_worker

            now = time.time()
            with get_db() as session:
                active_uploads = session.query(File).filter(File.upload_status.in_(["In Progress", "Queued"])).count()
                state["uploads_active"] = active_uploads > 0
                state["booting"] = False

                if active_uploads > 0:
                    ensure_upload_worker()

                # Refresh Account Quotas on boot or every 30 minutes (only when no uploads active)
                if (is_first_run or (now - last_quota_refresh >= 1800)) and active_uploads == 0:
                    accounts = session.query(MegaAccount).all()
                    for acc in accounts:
                        print(f"INFO Auto-syncing account: {acc.email}")
                        process_account(acc.id)
                    last_quota_refresh = now

                session.commit()

            # Keep the files/accounts/stats caches warm so the web UI loads
            # instantly instead of re-querying the DB on every page visit.
            # This is gated on its own (longer) timer, separate from the 30s
            # health-check tick above - on large libraries a full recompute
            # can itself take a while, so refreshing every 30s would just
            # pile up DB load without any benefit. Explicit user actions
            # (uploads, imports, deletes, etc.) already trigger an immediate
            # refresh via invalidate_and_refresh_async(), so this loop is
            # just a freshness safety net, not the primary update path.
            if is_first_run or (now - last_cache_refresh >= CACHE_REFRESH_INTERVAL):
                from utils.stats_cache import refresh_all_caches
                refresh_all_caches()
                last_cache_refresh = time.time()

        except Exception as e:
            print(f"ERROR Maintenance service error: {e}")

        is_first_run = False
        state["booting"] = False
        time.sleep(30)

def run_server():
    os.chdir(os.getcwd())
    create_database()
    check_for_update()

    from utils.stats_cache import invalidate_and_refresh_async
    invalidate_and_refresh_async()

    threading.Thread(target=maintenance_worker, daemon=True).start()

    server_address = ("0.0.0.0", 6342)
    httpd = ThreadingHTTPServer(server_address, CustomHandler)
    settings.load()
    print("Server running at http://localhost:6342/")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()

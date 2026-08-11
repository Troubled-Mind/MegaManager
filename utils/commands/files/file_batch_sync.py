import os
import threading
import time
import subprocess
from datetime import datetime
from database import get_db
from models import File, MegaAccount
from utils.commands.transfers.transfer_upload import ensure_upload_worker
from utils.commands.shared import size_to_bytes
from utils.config import state, cmd

def run(args=None):
    """
    Triggers a batch upload process in the background.
    """
    state["batch_calculating"] = True
    state["batch_status"] = "Calculating file allocation and analyzing free storage..."

    thread = threading.Thread(target=process_batch_upload)
    thread.daemon = True
    thread.start()
    return {"status": 200, "message": "Batch upload initiated in the background."}

def process_batch_upload():
    """
    Streaming Batch Upload Engine:
    1. Scan candidate files once (largest first).
    2. For each account: login, get live quota, assign as many files as fit.
    3. Immediately enqueue & start the upload worker - don't wait for other accounts.
    This means uploading begins as soon as the FIRST account is checked.
    """
    print("INFO Batch Upload: Starting streaming background processor...")
    state["batch_calculating"] = True
    state["batch_status"] = "Scanning local files for upload candidates..."

    SAFETY_BUFFER_BYTES = 10 * 1024 * 1024  # 10 MB overhead margin
    MAX_ACCOUNT_QUOTA_BYTES = 20 * 1024 * 1024 * 1024  # 20 GB free account cap

    # Ensure rclone config is up to date before starting
    try:
        from utils.rclone_config import rebuild_all_accounts
        rebuild_all_accounts()
    except Exception as e:
        print(f"WARNING Could not rebuild rclone config: {e}")

    try:
        with get_db() as db:
            # --- PHASE 1: Build candidate file list once ---
            print("INFO Phase 1: Scanning local files for candidates...")
            from sqlalchemy import or_
            candidates = db.query(File).filter(
                File.l_path != None,
                or_(File.m_path == None, File.m_path == ""),
                or_(File.m_sharing_link == None, File.m_sharing_link == ""),
                or_(
                    File.upload_status == None,
                    File.upload_status.notin_(["In Progress", "Completed"]),
                )
            ).all()

            if not candidates:
                print("DONE Batch Upload: No more files to upload.")
                return

            def get_size(f):
                if f.l_folder_size:
                    try:
                        return size_to_bytes(f.l_folder_size)
                    except: pass
                local_path = os.path.join(f.l_path, f.l_folder_name)
                total = 0
                if os.path.exists(local_path):
                    try:
                        for r, d, files in os.walk(local_path):
                            for file_item in files:
                                total += os.path.getsize(os.path.join(r, file_item))
                    except: pass
                return total

            # Build and sort the file list once (Largest First for best-fit)
            file_list = []
            for f in candidates:
                sz = get_size(f)
                if sz > 0:
                    file_list.append({"model": f, "size_bytes": sz, "assigned": False})
            file_list.sort(key=lambda x: x["size_bytes"], reverse=True)
            print(f"INFO Found {len(file_list)} candidate files. Streaming allocation starting...")

            # --- PHASE 2: Per-account streaming allocation ---
            all_accounts = db.query(MegaAccount).filter(MegaAccount.status == "Active").all()
            if not all_accounts:
                all_accounts = db.query(MegaAccount).all()

            total_enqueued = 0
            worker_started = False

            for acc in all_accounts:
                remaining = [x for x in file_list if not x["assigned"]]
                if not remaining:
                    print("INFO All files assigned - stopping early.")
                    break

                state["batch_status"] = f"Checking quota for {acc.email}..."
                print(f"INFO Checking account: {acc.email}")

                # Get live quota via rclone about (no session switching needed!)
                used_raw, total_raw = acc.used_quota, acc.total_quota
                try:
                    from utils.rclone_config import get_account_quota
                    u, t = get_account_quota(acc.id)
                    if u is not None and t is not None:
                        acc.used_quota = str(u)
                        acc.total_quota = str(t)
                        acc.last_login = datetime.utcnow()
                        db.commit()
                        used_raw, total_raw = str(u), str(t)
                except Exception as e:
                    print(f"rclone quota check failed for {acc.email}: {e}")

                try:
                    used = size_to_bytes(used_raw)
                    total = size_to_bytes(total_raw)

                    if not acc.is_pro_account:
                        if total <= 0 or total > MAX_ACCOUNT_QUOTA_BYTES:
                            print(f"INFO Capping {acc.email} to 20 GB (reported: {total/(1024**3):.2f} GB)")
                            total = MAX_ACCOUNT_QUOTA_BYTES
                    else:
                        if total <= 0:
                            print(f"WARNING {acc.email} is pro but mega-df returned 0 - skipping.")
                            continue

                    free = total - used - SAFETY_BUFFER_BYTES
                    if free <= 1024 * 1024:
                        print(f"INFO Skipping {acc.email}: insufficient free space ({max(0,free)/(1024**3):.2f} GB)")
                        continue
                except Exception:
                    continue

                acc_enqueued = 0
                for item in file_list:
                    if item["assigned"]:
                        continue
                    if item["size_bytes"] <= free:
                        f_model = item["model"]
                        f_model.m_account_id = acc.id
                        f_model.upload_status = "Queued"
                        f_model.upload_progress = 0
                        f_model.upload_speed = None
                        f_model.upload_eta = None
                        db.commit()

                        free -= item["size_bytes"]
                        item["assigned"] = True
                        acc_enqueued += 1
                        total_enqueued += 1
                        print(f"[Queued] {f_model.l_folder_name} ({item['size_bytes']/(1024**3):.2f} GB) -> {acc.email}")

                if acc_enqueued > 0:
                    print(f"INFO Enqueued {acc_enqueued} files for {acc.email}. Starting upload worker...")
                    ensure_upload_worker()
                    worker_started = True

            if total_enqueued == 0:
                print("ERROR Batch Upload: No files could be assigned to any account.")
            else:
                print(f"DONE Batch Upload: {total_enqueued} files enqueued across accounts.")

    except Exception as e:
        print(f"Batch upload calculation error: {e}")
    finally:
        state["batch_calculating"] = False
        state["batch_status"] = ""

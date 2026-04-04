import os
import threading
import time
from database import get_db
from models import File, MegaAccount
from utils.commands.transfers.transfer_upload import upload_file_in_thread
from utils.commands.shared import size_to_bytes

def run(args=None):
    """
    Triggers a batch upload process in the background.
    """
    thread = threading.Thread(target=process_batch_upload)
    thread.daemon = True
    thread.start()
    return {"status": 200, "message": "Batch upload initiated in the background."}

def process_batch_upload():
    """
    Automated Batch Upload Engine:
    1. Scan/Refresh all MEGA accounts for accurate quota.
    2. Sort candidate files (Largest to Smallest).
    3. Map files to accounts in-memory (using tracked free space).
    4. Execute uploads sequentially.
    """
    print("INFO Batch Upload: Starting background processor...")
    
    with get_db() as db:
        # --- PHASE 1: Account Refresh ---
        print("INFO Phase 1: Refreshing all MEGA account quotas...")
        all_accounts = db.query(MegaAccount).all()
        from utils.commands.accounts.account_login import process_account
        
        account_pool = []
        for acc in all_accounts:
            # We refresh EVERY account to ensure our in-memory math is 100% accurate
            print(f"   - Refreshing {acc.email}...")
            process_account(acc.id)
            db.refresh(acc)
            
            try:
                used = size_to_bytes(acc.used_quota)
                total = size_to_bytes(acc.total_quota)
                free = total - used
                if total > 0:
                    account_pool.append({
                        "id": acc.id,
                        "email": acc.email,
                        "free_bytes": free,
                        "model": acc
                    })
            except:
                continue

        if not account_pool:
            print("❌ Batch Upload: Stop. No usable MEGA accounts found.")
            return

        # --- PHASE 2: Candidate Discovery & Sorting ---
        print("INFO Phase 2: Scanning local files for candidates...")
        from sqlalchemy import or_
        candidates = db.query(File).filter(
            File.l_path != None,
            or_(File.m_path == None, File.m_path == ""),
            or_(File.m_sharing_link == None, File.m_sharing_link == ""),
            or_(
                File.upload_status == None,
                File.upload_status == "",
                File.upload_status.notin_(['In Progress', 'Completed'])
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

        file_list = []
        for f in candidates:
            sz = get_size(f)
            if sz > 0:
                file_list.append({"model": f, "size_bytes": sz})
        
        # Sort Largest First
        file_list.sort(key=lambda x: x["size_bytes"], reverse=True)
        print(f"INFO Batch Upload: Found {len(file_list)} files. Sorting complete (Largest First).")

        # --- PHASE 3: In-Memory Assignment (Bin Packing) ---
        print("INFO Phase 3: Planning distribution...")
        upload_queue = []
        
        for item in file_list:
            f_model = item["model"]
            f_size = item["size_bytes"]
            
            # Find best-fit account in our tracked pool
            best_acc = None
            max_remaining = -1
            
            for acc_data in account_pool:
                if acc_data["free_bytes"] >= f_size:
                    if acc_data["free_bytes"] > max_remaining:
                        max_remaining = acc_data["free_bytes"]
                        best_acc = acc_data
            
            if best_acc:
                # Assign in-memory and in-database
                f_model.m_account_id = best_acc["id"]
                f_model.upload_status = 'Queued'
                db.commit()

                upload_queue.append({
                    "file": f_model,
                    "account": best_acc["model"],
                    "size_bytes": f_size
                })
                # Subtract from tracked space so next file doesn't overfill it
                best_acc["free_bytes"] -= f_size
                print(f"   [Mapped] {f_model.l_folder_name} ({(f_size/1024/1024/1024):.2f} GB) -> {best_acc['email']}")

        if not upload_queue:
            print("ERROR Batch Upload: Stop. No files could fit into remaining account space.")
            return

        print(f"INFO Phase 4: Executing {len(upload_queue)} assigned uploads...")
        
        # --- PHASE 4: Sequential Execution ---
        for task in upload_queue:
            f = task["file"]
            acc = task["account"]
            size = task["size_bytes"]
            
            # Final database health check/refresh
            db.refresh(f)
            if f.upload_status in ['In Progress', 'Completed']:
                continue

            print(f"INFO Processing: {f.l_folder_name} to {acc.email}...")
            
            # Map path logic
            from utils.config import settings
            import json
            local_full_path = os.path.join(f.l_path, f.l_folder_name)
            
            # Properly parse local_paths from settings
            local_paths_setting = settings.get("local_paths", "[]")
            try:
                local_paths = json.loads(local_paths_setting) if isinstance(local_paths_setting, str) else local_paths_setting
            except:
                local_paths = []
            
            mega_target_path = local_full_path
            for local_base in local_paths:
                if local_full_path.startswith(local_base):
                    # Strip the local base to get the relative path for cloud
                    mega_target_path = "/" + local_full_path[len(local_base):].lstrip(os.sep)
                    break
            
            mega_remote_parent = os.path.dirname(mega_target_path) or "/"

            # Mark state
            f.m_account_id = acc.id
            f.upload_status = 'In Progress'
            db.commit()

            # Execute blocking upload
            try:
                upload_file_in_thread(f.id, acc.id, mega_remote_parent, local_full_path)
            except Exception as e:
                print(f"ERROR Batch Upload: Failed {f.l_folder_name}: {e}")
            
            print(f"INFO Cooling down after {f.l_folder_name}...")
            time.sleep(5)

    print("DONE Batch Upload: Finished all assigned tasks.")

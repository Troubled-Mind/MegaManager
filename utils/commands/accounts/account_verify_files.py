import subprocess
import os
import json
import threading
from database import get_db
from models import MegaAccount, File
from utils.rclone_config import rclone_cmd, RCLONE_CONF_PATH, _section_name
from utils.config import state

def run(args=None):
    if not args:
        return {"status": 400, "message": "Missing account_id"}
    # Normalise: HTTP handler may pass a raw string e.g. "all" or "1"
    if isinstance(args, str):
        args = [args]
    try:
        account_ids = []
        if args[0] == "all":
            with get_db() as db:
                account_ids = [acc.id for acc in db.query(MegaAccount).all()]
        else:
            account_ids = [int(args[0]) if isinstance(args, list) else int(args)]
    except Exception:
        return {"status": 400, "message": "Invalid account ID format"}

    if state.get("verify_running"):
        return {"status": 400, "message": "A verification process is already running."}

    state["verify_running"] = True
    state["verify_progress"] = {"current": 0, "total": 0, "message": "Starting verification...", "done": False}

    def _verify_worker():
        try:
            total_files = 0
            with get_db() as db:
                for account_id in account_ids:
                    total_files += db.query(File).filter(File.m_account_id == account_id, File.upload_status == "Completed").count()

            state["verify_progress"]["total"] = total_files
            if total_files == 0:
                state["verify_progress"]["message"] = "No files to verify."
                state["verify_progress"]["done"] = True
                state["verify_running"] = False
                return

            total_checked = 0
            total_bad = 0

            for account_id in account_ids:
                try:
                    with get_db() as db:
                        account = db.query(MegaAccount).filter(MegaAccount.id == account_id).first()
                        if not account:
                            continue

                        email = account.email
                        section = _section_name(account_id)

                        files = db.query(File).filter(
                            File.m_account_id == account_id,
                            File.upload_status == "Completed"
                        ).all()

                        if not files:
                            continue

                        bad_count = 0
                        # Cache the account's full recursive directory listing the first
                        # time a mismatch needs it, and reuse it for every other mismatched
                        # file in this account instead of re-listing the whole remote tree
                        # per file (an expensive operation on accounts with many folders).
                        account_dirs_cache = None
                        for f in files:
                            total_checked += 1
                            state["verify_progress"]["current"] = total_checked
                            state["verify_progress"]["message"] = f"Checking {email}: {f.m_folder_name}"

                            if not f.m_path or not f.m_folder_name:
                                continue

                            remote_path = f"{f.m_path}/{f.m_folder_name}".replace("//", "/")
                            remote_target = f"{section}:{remote_path}"

                            r_cmd = [rclone_cmd(), "size", "--config", RCLONE_CONF_PATH, remote_target, "--json"]
                            p = subprocess.run(r_cmd, capture_output=True, text=True)
                            remote_size = -1
                            if p.returncode == 0:
                                try:
                                    remote_size = json.loads(p.stdout).get("bytes", 0)
                                except Exception:
                                    pass

                            try:
                                local_size = int(f.l_folder_size or 0)
                            except (ValueError, TypeError):
                                local_size = 0
                            if remote_size != local_size or remote_size == -1:
                                state["verify_progress"]["message"] = f"Searching for misplaced {f.m_folder_name}..."
                                found_misplaced_path = None

                                if account_dirs_cache is None:
                                    ls_cmd = [rclone_cmd(), "lsjson", "-R", "--dirs-only", "--config", RCLONE_CONF_PATH, f"{section}:/"]
                                    p_ls = subprocess.run(ls_cmd, capture_output=True, text=True)
                                    if p_ls.returncode == 0:
                                        try:
                                            account_dirs_cache = json.loads(p_ls.stdout)
                                        except Exception:
                                            account_dirs_cache = []
                                    else:
                                        account_dirs_cache = []

                                for d in account_dirs_cache:
                                    if d.get("Name") == f.m_folder_name:
                                        cand_path = d.get("Path")
                                        s_cmd = [rclone_cmd(), "size", "--config", RCLONE_CONF_PATH, f"{section}:/{cand_path}", "--json"]
                                        p_s = subprocess.run(s_cmd, capture_output=True, text=True)
                                        if p_s.returncode == 0:
                                            try:
                                                cand_size = json.loads(p_s.stdout).get("bytes", -1)
                                            except Exception:
                                                cand_size = -1
                                            if cand_size == local_size:
                                                found_misplaced_path = cand_path
                                                break

                                if found_misplaced_path:
                                    state["verify_progress"]["message"] = f"Relocating misplaced {f.m_folder_name}..."
                                    copy_cmd = [
                                        rclone_cmd(), "copy", "--config", RCLONE_CONF_PATH,
                                        f"{section}:/{found_misplaced_path}",
                                        remote_target
                                    ]
                                    cp = subprocess.run(copy_cmd, capture_output=True)
                                    if cp.returncode == 0:
                                        subprocess.run([rclone_cmd(), "purge", "--config", RCLONE_CONF_PATH, f"{section}:/{found_misplaced_path}"], capture_output=True)
                                        state["verify_progress"]["message"] = f"Relocated {f.m_folder_name}"
                                    else:
                                        state["verify_progress"]["message"] = f"Relocation failed, will re-upload {f.m_folder_name}"
                                        subprocess.run([rclone_cmd(), "purge", "--config", RCLONE_CONF_PATH, f"{section}:/{found_misplaced_path}"], capture_output=True)
                                        f.upload_status = None
                                        f.upload_progress = 0
                                        f.m_account_id = None
                                        f.upload_speed = None
                                        f.upload_eta = None
                                        bad_count += 1
                                    continue

                                # Tier 3: check for loose files dumped in the parent dir.
                                # This happens when the old mega-put bug fired: files were copied
                                # into the parent folder rather than into the named subfolder.
                                parent_remote = f"{section}:{f.m_path}"
                                ls_parent_cmd = [rclone_cmd(), "lsjson", "--config", RCLONE_CONF_PATH, parent_remote]
                                p_parent = subprocess.run(ls_parent_cmd, capture_output=True, text=True)
                                found_loose = False
                                if p_parent.returncode == 0:
                                    try:
                                        parent_items = json.loads(p_parent.stdout)
                                        # Sum size of all loose files (not dirs) in parent
                                        loose_files = [i for i in parent_items if not i.get("IsDir")]
                                        loose_size = sum(i.get("Size", 0) for i in loose_files)
                                        if loose_size == local_size and loose_files:
                                            state["verify_progress"]["message"] = f"Found loose files in parent, moving into {f.m_folder_name}..."
                                            all_ok = True
                                            for item in loose_files:
                                                fname = item["Name"]
                                                cp = subprocess.run([
                                                    rclone_cmd(), "copyto", "--config", RCLONE_CONF_PATH,
                                                    f"{parent_remote}/{fname}",
                                                    f"{remote_target}/{fname}"
                                                ], capture_output=True)
                                                if cp.returncode == 0:
                                                    subprocess.run([rclone_cmd(), "deletefile", "--config", RCLONE_CONF_PATH,
                                                                    f"{parent_remote}/{fname}"], capture_output=True)
                                                else:
                                                    all_ok = False
                                            if all_ok:
                                                state["verify_progress"]["message"] = f"Recovered loose files into {f.m_folder_name}"
                                                found_loose = True
                                    except Exception:
                                        pass

                                if found_loose:
                                    continue

                                # Tier 4: truly missing - purge and re-upload.
                                state["verify_progress"]["message"] = f"Mismatched/Missing. Purging {f.m_folder_name}..."
                                subprocess.run([rclone_cmd(), "purge", "--config", RCLONE_CONF_PATH, remote_target], capture_output=True)
                                f.upload_status = None
                                f.upload_progress = 0
                                f.m_account_id = None
                                f.upload_speed = None
                                f.upload_eta = None
                                bad_count += 1

                        if bad_count > 0:
                            state["verify_progress"]["message"] = f"Cleaning trash for {email}..."
                            subprocess.run([rclone_cmd(), "cleanup", "--config", RCLONE_CONF_PATH, f"{section}:"], capture_output=True)
                            db.commit()
                            total_bad += bad_count

                except Exception as e:
                    state["verify_progress"]["message"] = f"Error verifying account #{account_id}: {e}"
                    continue
            if total_bad > 0:
                from utils.stats_cache import invalidate_and_refresh_async
                invalidate_and_refresh_async()
                state["verify_progress"]["message"] = f"Verified {total_checked} files. {total_bad} mismatches purged."
            else:
                state["verify_progress"]["message"] = f"Verified {total_checked} files. Perfect match!"

        except Exception as e:
            state["verify_progress"]["message"] = f"Error: {e}"
        finally:
            state["verify_progress"]["done"] = True
            state["verify_running"] = False

    threading.Thread(target=_verify_worker, daemon=True).start()
    return {"status": 200, "message": "Verification started in the background."}

import os
import re
import json
import subprocess
import threading
import time
from database import get_db
from models import File, MegaAccount
from utils.config import cmd, state, add_transfer_log

# How many different accounts may have an upload actively running at once. MEGA
# throttles bandwidth per account/connection, so running independent accounts in
# parallel (rather than one global sequential queue) multiplies real throughput
# instead of leaving every other account idle behind a single throttled connection.
MAX_CONCURRENT_UPLOADS = 5

# Module-level worker lock and state
_worker_lock = threading.Lock()     # guards _active_workers bookkeeping
_claim_lock = threading.Lock()      # serializes "pick the next file to upload" so two
                                     # worker threads can never claim the same file or
                                     # start a second concurrent upload for one account
_active_workers = 0
_files_in_flight = set()            # file IDs currently being uploaded by a live thread
_accounts_in_flight = set()         # account IDs currently having an active upload
_last_progress_update = {}

def ensure_upload_worker():
    """Tops up the pool of worker threads (up to MAX_CONCURRENT_UPLOADS) so queued
    uploads for different accounts can run in parallel.

    Only spawns as many new workers as there are distinct claimable accounts right
    now (queued/in-progress work whose account isn't already owned by a live
    worker). Blindly topping up to MAX_CONCURRENT_UPLOADS regardless of that would
    spin up a thread that immediately finds nothing to claim, exits, and - since
    _worker_loop's finally block calls this again whenever any work remains
    anywhere - respawns forever in a tight busy loop the moment fewer than
    MAX_CONCURRENT_UPLOADS distinct accounts have work in flight.
    """
    global _active_workers
    with _worker_lock:
        capacity = MAX_CONCURRENT_UPLOADS - _active_workers
        if capacity <= 0:
            return

        with get_db() as session:
            queued_accounts = {
                row[0] for row in session.query(File.m_account_id).filter(
                    File.upload_status.in_(["Queued", "In Progress"]),
                    File.m_account_id.isnot(None)
                ).distinct().all()
            }
        claimable = queued_accounts - _accounts_in_flight

        to_start = min(capacity, len(claimable))
        for _ in range(max(0, to_start)):
            _active_workers += 1
            thread = threading.Thread(target=_worker_loop, daemon=True)
            thread.start()

def run(args=None):
    if not args or ":" not in args:
        return {"status": 400, "message": "Usage: transfer_upload:<file_id>:<mega_account_id>"}

    try:
        file_id_str, account_id_str = args.split(":")
        file_id = int(file_id_str)
        account_id = int(account_id_str)
    except ValueError:
        return {"status": 400, "message": "Invalid file or account ID."}

    with get_db() as session:
        file = session.query(File).filter(File.id == file_id).first()
        if not file:
            return {"status": 404, "message": f"No file found with ID {file_id}"}

        if not file.l_path or not file.l_folder_name:
            return {"status": 400, "message": "Missing local path or folder name"}

        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        if not account:
            return {"status": 404, "message": f"No MEGA account found with ID {account_id}"}

        local_full_path = os.path.join(file.l_path, file.l_folder_name)
        if not os.path.exists(local_full_path):
            return {"status": 404, "message": f"Local folder does not exist: {local_full_path}"}

        # Queue the file for upload
        file.m_account_id = account.id
        file.upload_status = 'Queued'
        file.upload_progress = 0
        file.upload_speed = None
        file.upload_eta = None
        session.commit()
        add_transfer_log(f"Queued #{file_id} ({file.l_folder_name}) -> {account.email}", "QUEUE")

    state["uploads_active"] = True
    ensure_upload_worker()

    return {"status": 200, "message": f"Upload queued for file #{file_id}"}

def _claim_next_task():
    """Atomically pick and claim the next uploadable file, skipping any account that
    already has an upload actively running on another worker thread in this process."""
    with _claim_lock:
        with get_db() as session:
            # Resume a leftover "In Progress" row first (e.g. left behind by a crash/
            # restart) - but only if no live worker already owns that account, and only
            # if no live worker already claimed this exact file.
            file = session.query(File).filter(
                File.upload_status == "In Progress",
                ~File.id.in_(_files_in_flight) if _files_in_flight else True
            ).order_by(File.id.asc()).first()

            if file and file.m_account_id in _accounts_in_flight:
                file = None

            if not file:
                q = session.query(File).filter(File.upload_status == "Queued")
                if _accounts_in_flight:
                    q = q.filter(~File.m_account_id.in_(_accounts_in_flight))
                file = q.order_by(File.id.asc()).first()

            if not file or not file.m_account_id:
                return None

            task = {
                "file_id": file.id,
                "account_id": file.m_account_id,
                "l_path": file.l_path,
                "l_folder_name": file.l_folder_name
            }
            file.upload_status = "In Progress"
            session.commit()

            _files_in_flight.add(file.id)
            _accounts_in_flight.add(file.m_account_id)
            return task

def _worker_loop():
    """Worker loop - one of up to MAX_CONCURRENT_UPLOADS running concurrently, each
    processing files for accounts no other live worker currently owns."""
    global _active_workers
    print("INFO Upload worker thread started.")
    add_transfer_log("Upload worker thread started", "INFO")

    try:
        while True:
            task = _claim_next_task()
            if not task:
                break

            state["uploads_active"] = True
            try:
                _execute_single_upload(task["file_id"], task["account_id"], task["l_path"], task["l_folder_name"])
            finally:
                _files_in_flight.discard(task["file_id"])
                _accounts_in_flight.discard(task["account_id"])
            time.sleep(1)

    except Exception as e:
        print(f"ERROR Upload worker thread encountered error: {e}")
        add_transfer_log(f"Upload worker thread error: {e}", "ERROR")
    finally:
        with _worker_lock:
            _active_workers -= 1
            still_running = _active_workers > 0
        with get_db() as session:
            remaining = session.query(File).filter(File.upload_status.in_(["In Progress", "Queued"])).count()
            if remaining > 0:
                ensure_upload_worker()
            elif not still_running:
                state["uploads_active"] = False
        print("INFO Upload worker thread stopped.")

def _execute_single_upload(file_id, account_id, l_path, l_folder_name):
    """Executes a single file upload using rclone copy (parallel, no shared daemon)."""
    local_full_path = os.path.join(l_path, l_folder_name)
    # Outer loop handles full process crashes (e.g. OOM, hard network drop).
    # rclone itself handles chunk/file-level retries internally (--retries 5).
    # Defined up-front (not just before the retry loop) so the except block below can
    # always reference them, even if an exception is raised earlier during setup
    # (e.g. the account lookup) before the retry loop itself ever starts.
    max_attempts = 2
    attempt = 0

    try:
        with get_db() as session:
            account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
            if not account:
                raise Exception(f"Account ID #{account_id} not found.")

            account_email = account.email
            account_password = account.password

        # Map local path to mega target path
        from utils.commands.shared import get_local_paths, strip_local_base
        local_paths = get_local_paths()

        mega_target_path = strip_local_base(local_full_path, local_paths)
        if not mega_target_path:
            raise Exception(
                f"Local path {local_full_path} does not match any configured local_paths entry "
                f"- refusing to upload to an unpredictable destination. Check Settings > Local Paths."
            )

        mega_remote_parent = os.path.dirname(mega_target_path) or "/"
        success = False
        last_error = None

        while attempt < max_attempts:
            attempt += 1
            print(f"INFO rclone upload #{file_id} ({l_folder_name}) - Attempt {attempt}/{max_attempts}")
            add_transfer_log(f"Starting #{file_id} ({l_folder_name}) -> {account_email} (Attempt {attempt}/{max_attempts})", "TRANSFER")

            try:
                if not os.path.exists(local_full_path):
                    raise Exception(f"Local path not found: {local_full_path}")

                from utils.rclone_config import rclone_cmd, RCLONE_CONF_PATH, _section_name
                section = _section_name(account_id)
                # rclone copy transfers contents of the source dir to the destination dir.
                # So we must use mega_target_path to ensure the folder itself is created on the remote.
                remote_dest = f"{section}:{mega_target_path}"

                # --- Pre-flight quota check via rclone about ---
                file_size_bytes = 0
                try:
                    for root, dirs, files in os.walk(local_full_path):
                        for fn in files:
                            file_size_bytes += os.path.getsize(os.path.join(root, fn))
                except Exception:
                    file_size_bytes = 0

                if file_size_bytes > 0:
                    try:
                        # This may be a resume (a prior attempt already landed some of
                        # this folder on the remote) - rclone copy only transfers what's
                        # missing or different, so what actually needs to fit in free
                        # space is file_size_bytes minus whatever's already there, not
                        # the full local size. Checking against the full size here would
                        # reject resumes that only need a fraction of that space.
                        already_on_remote = 0
                        try:
                            size_res = subprocess.run(
                                [rclone_cmd(), "size", "--config", RCLONE_CONF_PATH, remote_dest, "--json"],
                                capture_output=True, text=True, timeout=30
                            )
                            if size_res.returncode == 0:
                                already_on_remote = json.loads(size_res.stdout).get("bytes", 0) or 0
                        except Exception:
                            already_on_remote = 0

                        bytes_still_needed = max(0, file_size_bytes - already_on_remote)

                        from utils.rclone_config import get_account_quota
                        used_b, total_b = get_account_quota(account_id)
                        if used_b is not None and total_b is not None:
                            free_b = total_b - used_b
                            MARGIN = 10 * 1024 * 1024  # 10 MB
                            if bytes_still_needed > (free_b - MARGIN):
                                raise Exception(
                                    f"Quota pre-flight failed: need {bytes_still_needed/(1024**3):.2f} GB "
                                    f"but only {free_b/(1024**3):.2f} GB free on {account_email}."
                                )
                            already_note = f" ({already_on_remote/(1024**3):.2f} GB already there)" if already_on_remote > 0 else ""
                            add_transfer_log(
                                f"Quota OK #{file_id}: {bytes_still_needed/(1024**3):.2f} GB needed{already_note}, "
                                f"{free_b/(1024**3):.2f} GB free on {account_email}", "TRANSFER"
                            )
                    except Exception as quota_err:
                        if "Quota pre-flight failed" in str(quota_err):
                            raise
                        print(f"WARNING rclone quota pre-flight skipped for #{file_id}: {quota_err}")

                # --- Launch rclone copy ---
                rclone_command = [
                    rclone_cmd(),
                    "copy",
                    "--config", RCLONE_CONF_PATH,
                    local_full_path,
                    remote_dest,
                    "--transfers", "4",
                    "--checkers", "8",
                    "--retries", "5",           # rclone retries each file up to 5 times
                    "--retries-sleep", "10s",   # wait 10s between retries (avoids rate limiting)
                    "--low-level-retries", "10",# retry low-level errors (e.g. connection reset)
                    "--stats", "3s",
                    "--log-level", "INFO",
                    "-P",                       # progress to stderr
                ]

                process = subprocess.Popen(
                    rclone_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )

                def _format_eta(seconds):
                    if not seconds or seconds < 0 or seconds > 86400 * 30:
                        return None
                    seconds = int(seconds)
                    if seconds < 60: return f"{seconds}s"
                    elif seconds < 3600:
                        return f"{seconds//60}m {seconds%60}s"
                    else:
                        h = seconds // 3600
                        return f"{h}h {(seconds%3600)//60}m"

                # Parse rclone progress lines:
                # e.g. "Transferred: 1.234 GiB / 5.678 GiB, 22%, 50.000 MiB/s, ETA 30s"
                PROGRESS_RE = re.compile(
                    r'Transferred:\s+([\d.]+)\s+(\S+)\s*/\s*([\d.]+)\s+(\S+),\s*(\d+)%,\s*([\d.]+)\s+(\S+)/s,\s*ETA\s+(\S+)',
                    re.IGNORECASE
                )
                last_logged_pct = [-1]

                for line in process.stdout:
                    line = line.rstrip()
                    m = PROGRESS_RE.search(line)
                    if m:
                        up_val, up_unit, tot_val, tot_unit, pct, spd_val, spd_unit, eta_raw = m.groups()
                        pct_int = int(pct)
                        speed_str = f"{spd_val} {spd_unit}/s"
                        # Parse ETA string (rclone gives e.g. "30s", "1m30s", "1h2m3s")
                        eta_str = eta_raw if eta_raw != "-" else None

                        update_file_progress_rclone(file_id, pct_int, speed_str, eta_str)

                        if last_logged_pct[0] == -1 or pct_int >= last_logged_pct[0] + 10:
                            last_logged_pct[0] = pct_int
                            add_transfer_log(
                                f"#{file_id} {pct_int}% ({up_val} {up_unit} / {tot_val} {tot_unit}) @ {speed_str}",
                                "PROGRESS"
                            )

                return_code = process.wait()

                # If the user explicitly stopped this upload (transfer_stop_all) while
                # rclone was running, respect that instead of overwriting it below -
                # regardless of whether rclone happened to exit 0 or non-zero.
                with get_db() as session_stop_check:
                    f_stop_check = session_stop_check.query(File).filter(File.id == file_id).first()
                    if f_stop_check and f_stop_check.upload_status == "Stopped":
                        add_transfer_log(f"Upload for #{file_id} ({l_folder_name}) was stopped by user - not marking completed/failed", "INFO")
                        success = True
                        break

                if return_code != 0:
                    raise Exception(f"rclone exited with code {return_code}")

                # Mark completed in DB
                with get_db() as session_c:
                    f = session_c.query(File).filter(File.id == file_id).first()
                    if f and f.upload_status != "Stopped":
                        f.m_path = mega_remote_parent
                        f.m_folder_name = os.path.basename(local_full_path)
                        f.m_account_id = account_id
                        f.upload_progress = 100
                        f.upload_speed = None
                        f.upload_eta = None
                        f.upload_status = "Completed"
                        session_c.commit()

                add_transfer_log(f"Upload completed for #{file_id} ({l_folder_name})", "SUCCESS")
                print(f"INFO Upload completed for #{file_id} ({l_folder_name})")

                # Async post-upload stats refresh
                def _async_post_sync(acc_id, f_id, expected_bytes, remote_target):
                    try:
                        # 1. Update the account's quota in the DB via rclone
                        from utils.rclone_config import get_account_quota, rclone_cmd, RCLONE_CONF_PATH
                        from database import get_db
                        from models import MegaAccount

                        r_used, r_total = get_account_quota(acc_id)
                        if r_used is not None and r_total is not None:
                            with get_db() as session_q:
                                acc = session_q.query(MegaAccount).filter(MegaAccount.id == acc_id).first()
                                if acc:
                                    acc.used_quota = r_used
                                    acc.total_quota = r_total
                                    session_q.commit()

                        # 2. Record the folder's cloud size now, instead of leaving it
                        #    unset until someone runs "Sync All" - verify the remote
                        #    size actually matches what we uploaded before trusting it,
                        #    since rclone reporting success doesn't rule out e.g. a
                        #    concurrent external change to the same path.
                        if expected_bytes and expected_bytes > 0:
                            try:
                                size_res = subprocess.run(
                                    [rclone_cmd(), "size", "--config", RCLONE_CONF_PATH, remote_target, "--json"],
                                    capture_output=True, text=True, timeout=30
                                )
                                if size_res.returncode == 0:
                                    remote_bytes = json.loads(size_res.stdout).get("bytes", -1)
                                    if remote_bytes == expected_bytes:
                                        with get_db() as session_sz:
                                            f_sz = session_sz.query(File).filter(File.id == f_id).first()
                                            if f_sz:
                                                f_sz.m_folder_size = str(remote_bytes)
                                                session_sz.commit()
                                    else:
                                        print(f"WARNING Post-upload size mismatch for #{f_id}: remote={remote_bytes} local={expected_bytes} - leaving for Cloud Verification to reconcile")
                            except Exception as size_err:
                                print(f"WARNING Post-upload size check failed for #{f_id}: {size_err}")

                        # 3. Rebuild the global stats/files/accounts caches
                        from utils.stats_cache import refresh_all_caches
                        refresh_all_caches()
                    except Exception as sync_err:
                        print(f"WARNING Post-upload sync warning for #{f_id}: {sync_err}")

                threading.Thread(
                    target=_async_post_sync,
                    args=(account_id, file_id, file_size_bytes, remote_dest),
                    daemon=True
                ).start()
                success = True
                break

            except Exception as attempt_err:
                last_error = attempt_err
                print(f"ERROR Upload attempt {attempt}/{max_attempts} failed for #{file_id}: {attempt_err}")
                add_transfer_log(f"Upload attempt {attempt}/{max_attempts} failed for #{file_id}: {attempt_err}", "WARNING")
                try:
                    process.terminate()
                except Exception:
                    pass

                # A quota pre-flight failure won't come out differently on an
                # identical retry a few seconds later against the same account -
                # stop wasting an attempt (and the 5s backoff) and fail fast.
                if "Quota pre-flight failed" in str(attempt_err):
                    break

                if attempt < max_attempts:
                    time.sleep(5)

        if not success:
            raise Exception(f"Failed after {attempt} attempt(s). Last error: {last_error}")

    except Exception as e:
        print(f"ERROR Upload failed for #{file_id}: {e}")
        add_transfer_log(f"Upload failed for #{file_id}: {e}", "ERROR")
        with get_db() as err_session:
            f = err_session.query(File).filter(File.id == file_id).first()
            if f:
                f.upload_status = f"Failed after {attempt} attempt(s)"
                f.upload_speed = None
                f.upload_eta = None
                err_session.commit()
    finally:
        state["current_upload_speed_bps"] = 0


def update_file_progress_rclone(file_id, pct_int, speed_str, eta_str):
    """Write rclone parsed progress to the DB (throttled)."""
    global _last_progress_update
    try:
        now = time.time()
        last_time, last_pct = _last_progress_update.get(file_id, (0, -1))
        if (now - last_time >= 0.5) or (pct_int != last_pct):
            _last_progress_update[file_id] = (now, pct_int)
            with get_db() as session:
                f = session.query(File).filter(File.id == file_id).first()
                if f and f.upload_status in ("In Progress", "Queued"):
                    f.upload_progress = pct_int
                    f.upload_speed = speed_str
                    f.upload_eta = eta_str
                    f.upload_status = "In Progress"
                    session.commit()
    except Exception:
        pass

def update_file_progress(file_id, output):
    """Parses output and throttles progress updates to avoid SQLite database locks."""
    global _last_progress_update

    # Check if this line looks like transfer progress
    if not any(token in output for token in ("%", "TRANSFERRING", "MB/s", "KB/s", "GB/s", "ETA")):
        return

    try:
        # 1. Parse Progress Percentage
        progress = None
        progress_match = re.search(r"(\d+(?:\.\d+)?)\s*%", output)
        if progress_match:
            progress = float(progress_match.group(1))

        # 2. Parse Speed
        speed = None
        speed_match = re.search(r"(\d+(?:\.\d+)?\s*[KMGT]B/s)", output, re.IGNORECASE)
        if speed_match:
            speed = speed_match.group(1)

        # 3. Parse ETA
        eta = None
        eta_match = re.search(r"\(?(\d{1,2}:\d{2}:\d{2})\)?", output)
        if eta_match:
            eta = eta_match.group(1)

        if progress is not None:
            now = time.time()
            last_time, last_pct = _last_progress_update.get(file_id, (0, -1))

            # Throttle writes: commit if > 500ms elapsed or progress changed by >= 1%
            if (now - last_time >= 0.5) or (int(progress) != last_pct):
                _last_progress_update[file_id] = (now, int(progress))
                with get_db() as session:
                    file = session.query(File).filter(File.id == file_id).first()
                    if file and file.upload_status in ("In Progress", "Queued"):
                        file.upload_progress = int(progress)
                        if speed: file.upload_speed = speed
                        if eta: file.upload_eta = eta
                        file.upload_status = 'In Progress'
                        session.commit()
    except Exception:
        pass

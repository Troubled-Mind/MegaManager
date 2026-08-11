import json
import subprocess
from database import get_db
from models import File, MegaAccount
from utils.config import add_transfer_log
from utils.rclone_config import rclone_cmd, RCLONE_CONF_PATH, _section_name, get_account_quota

# Safety margin so a re-upload doesn't land an account exactly at 0 bytes free
# (matches the pre-flight check transfer_upload.py already uses).
MARGIN_BYTES = 10 * 1024 * 1024


def run(args=None):
    """Smart re-upload for a partial/mismatched cloud folder:

    1. If the account the file is already linked to has enough free space to
       cover what's still missing (local size minus whatever's on the cloud),
       just re-queue the upload against that same account. rclone only
       transfers files that are missing or differ, so this naturally resumes
       rather than re-transferring what's already there.
    2. Otherwise, purge whatever partial/mismatched content (and same-release
       sidecar files) sit on that account's remote, and queue a full
       re-upload on a different account that has room for the whole thing.
    """
    try:
        file_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid file ID"}

    with get_db() as session:
        file = session.query(File).filter(File.id == file_id).first()
        if not file:
            return {"status": 404, "message": f"No file found with ID {file_id}"}

        if not file.l_path or not file.l_folder_name:
            return {"status": 400, "message": "Missing local path or folder name - nothing to re-upload"}

        try:
            local_size = int(file.l_folder_size or 0)
        except (ValueError, TypeError):
            local_size = 0
        try:
            cloud_size = int(file.m_folder_size or 0)
        except (ValueError, TypeError):
            cloud_size = 0

        current_account_id = file.m_account_id
        current_account = (
            session.query(MegaAccount).filter(MegaAccount.id == current_account_id).first()
            if current_account_id else None
        )
        m_path = file.m_path
        m_folder_name = file.m_folder_name

    if local_size <= 0:
        return {"status": 400, "message": "Local size unknown - run a local scan before re-uploading"}

    gap_bytes = max(0, local_size - cloud_size)
    if gap_bytes == 0:
        return {"status": 200, "message": f"#{file_id} already matches locally recorded size - nothing to upload"}

    from utils.commands.transfers.transfer_upload import run as run_upload

    # --- Step 1: try resuming on the currently-linked account ---
    if current_account:
        free_b = _account_free_bytes(current_account)
        if free_b is not None and free_b - MARGIN_BYTES >= gap_bytes:
            add_transfer_log(
                f"Reupload #{file_id}: {current_account.email} has room for the remaining "
                f"{gap_bytes/(1024**3):.2f} GB - resuming",
                "INFO"
            )
            return run_upload(f"{file_id}:{current_account_id}")

        add_transfer_log(
            f"Reupload #{file_id}: {current_account.email} doesn't have room for the remaining "
            f"{gap_bytes/(1024**3):.2f} GB - clearing remote and moving accounts",
            "WARNING"
        )

        # --- Step 2: not enough room - clear whatever's on the remote first ---
        if m_path and m_folder_name:
            _purge_remote_folder_and_sidecars(current_account_id, m_path, m_folder_name)

    # Find a fresh account (excluding the current one) with room for the FULL local
    # size. Uses each account's last-known (DB-cached) quota to pick a candidate
    # without a live rclone round-trip per account - transfer_upload.py's own
    # pre-flight check re-verifies with a live quota lookup right before it
    # actually starts moving bytes.
    best_account = None
    best_available = None
    with get_db() as session:
        candidates = session.query(MegaAccount).filter(MegaAccount.id != (current_account_id or -1)).all()
        for acc in candidates:
            if acc.total_quota is None or acc.used_quota is None:
                continue
            try:
                available = int(acc.total_quota) - int(acc.used_quota)
            except (ValueError, TypeError):
                continue
            if available - MARGIN_BYTES < local_size:
                continue
            if best_available is None or available < best_available:
                best_account = acc
                best_available = available

    if not best_account:
        return {
            "status": 400,
            "message": f"No other account has enough free space ({local_size/(1024**3):.2f} GB needed) to re-upload #{file_id}"
        }

    add_transfer_log(f"Reupload #{file_id}: moving to {best_account.email} ({best_available/(1024**3):.2f} GB free)", "INFO")
    return run_upload(f"{file_id}:{best_account.id}")


def _account_free_bytes(account):
    """Prefer a live rclone quota check; fall back to the DB's last-known quota."""
    used_b, total_b = get_account_quota(account.id)
    if used_b is None or total_b is None:
        if account.total_quota is None or account.used_quota is None:
            return None
        try:
            used_b, total_b = int(account.used_quota), int(account.total_quota)
        except (ValueError, TypeError):
            return None
    return total_b - used_b


def _purge_remote_folder_and_sidecars(account_id, m_path, m_folder_name):
    """Delete the (possibly partial) release folder, plus any loose sidecar
    files left in the parent directory sharing its release date-token."""
    section = _section_name(account_id)
    full_path = f"{m_path}/{m_folder_name}".replace("//", "/")
    remote_target = f"{section}:{full_path}"

    subprocess.run([rclone_cmd(), "purge", "--config", RCLONE_CONF_PATH, remote_target], capture_output=True)

    try:
        from utils.commands.transfers.transfer_reorg_cloud import _date_token
        token = _date_token(m_folder_name)
        if not token:
            return

        ls_res = subprocess.run(
            [rclone_cmd(), "lsjson", "--config", RCLONE_CONF_PATH, f"{section}:{m_path}"],
            capture_output=True, text=True
        )
        if ls_res.returncode != 0:
            return

        items = json.loads(ls_res.stdout)
        for item in items:
            name = item.get("Name", "")
            if not item.get("IsDir") and name != m_folder_name and token in name:
                subprocess.run(
                    [rclone_cmd(), "deletefile", "--config", RCLONE_CONF_PATH, f"{section}:{m_path}/{name}"],
                    capture_output=True
                )
    except Exception as e:
        print(f"WARNING Sidecar sweep failed while clearing #{m_folder_name}: {e}")

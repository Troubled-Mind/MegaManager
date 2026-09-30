from database import get_db
from models import MegaAccount, File

def run(args=None):
    """Bulk-delete accounts by comma-separated IDs.

    Mirrors the cleanup logic in account_delete.py for each account:
    cloud-only File rows are dropped, rows with a local counterpart have
    their cloud columns cleared.  rclone config entries are removed and
    the stats cache is invalidated once after all deletions.
    """
    if not args:
        return {"status": 400, "message": "No account IDs provided."}

    try:
        ids = [int(i.strip()) for i in str(args).split(",") if i.strip()]
    except ValueError:
        return {"status": 400, "message": "Invalid account ID list — must be comma-separated integers."}

    if not ids:
        return {"status": 400, "message": "No valid account IDs provided."}

    deleted = []
    not_found = []
    errors = []

    with get_db() as session:
        for account_id in ids:
            account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
            if not account:
                not_found.append(account_id)
                continue

            try:
                # Drop cloud-only File rows (no local counterpart).
                session.query(File).filter(
                    File.m_account_id == account_id,
                    File.l_path.is_(None)
                ).delete(synchronize_session=False)

                # Revert mixed rows to local-only.
                session.query(File).filter(
                    File.m_account_id == account_id
                ).update({
                    File.m_account_id: None,
                    File.m_path: None,
                    File.m_folder_name: None,
                    File.m_folder_size: None,
                    File.m_sharing_link: None,
                    File.m_sharing_link_expiry: None,
                    File.upload_status: None,
                    File.upload_progress: 0,
                    File.upload_speed: None,
                    File.upload_eta: None,
                }, synchronize_session=False)

                session.delete(account)
                deleted.append(account_id)
            except Exception as e:
                errors.append({"id": account_id, "error": str(e)})

        session.commit()

    # Remove rclone config entries outside the DB session.
    for account_id in deleted:
        try:
            from utils.rclone_config import remove_account
            remove_account(account_id)
        except Exception as e:
            print(f"WARNING: rclone config removal failed for account {account_id}: {e}")

    if deleted:
        from utils.stats_cache import invalidate_and_refresh_async
        invalidate_and_refresh_async()

    return {
        "status": 200,
        "deleted": deleted,
        "not_found": not_found,
        "errors": errors,
        "message": (
            f"Deleted {len(deleted)} account(s)."
            + (f" {len(not_found)} not found." if not_found else "")
            + (f" {len(errors)} error(s)." if errors else "")
        ),
    }

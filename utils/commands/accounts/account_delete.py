from database import get_db
from models import MegaAccount, File

def run(args=None):
    try:
        account_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}

    with get_db() as session:
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()

        if not account:
            return {"status": 404, "message": f"No account found with ID {account_id}"}

        # The UI promises deleting an account removes "all references to
        # [its files] from Mega Manager" - without this, File rows kept a
        # dangling m_account_id forever (orphaned FK, since nothing enforces
        # it at the DB level), showing up as a "synced" file with no account
        # attached and still counted in cloud-size stats.
        #
        # Cloud-only rows (no local counterpart) become meaningless once the
        # account link is gone, so drop them outright. Rows with a local
        # counterpart just revert to "local-only, unsynced".
        session.query(File).filter(
            File.m_account_id == account_id,
            File.l_path.is_(None)
        ).delete(synchronize_session=False)

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
        session.commit()

        try:
            from utils.rclone_config import remove_account
            remove_account(account_id)
        except Exception as rclone_err:
            print(f"WARNING rclone config removal failed for account {account_id}: {rclone_err}")

        from utils.stats_cache import invalidate_and_refresh_async
        invalidate_and_refresh_async()

        return {"status": 200, "message": f"Account {account_id} deleted successfully"}

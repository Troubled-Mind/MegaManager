from database import get_db
from models import MegaAccount

def run(args=None):
    try:
        if not args or len(args) < 1:
            return {"status": 400, "message": "Invalid CSV data"}, 400

        with get_db() as db:
            account_ids = []

            for row in args:
                parts = row.strip().split(',')
                if len(parts) != 2:
                    print(f"Invalid row format: {row}")
                    continue
                email, password = parts
                email = email.strip()
                password = password.strip()

                account = db.query(MegaAccount).filter(MegaAccount.email == email).first()
                if account:
                    print(f"Account already exists: {email}")
                    continue
                else:
                    new_account = MegaAccount(email=email, password=password)
                    db.add(new_account)
                    db.flush()
                    account_ids.append(new_account.id)
                    db.commit()
                    print(f"Added account: {email}")

                    try:
                        from utils.rclone_config import add_or_update_account
                        add_or_update_account(new_account.id, email, password)
                    except Exception as rclone_err:
                        print(f"WARNING rclone config update failed for {email}: {rclone_err}")

            from utils.stats_cache import invalidate_and_refresh_async
            invalidate_and_refresh_async()

            return {
                "status": 200,
                "account_ids": account_ids
            }, 200

    except Exception as e:
        print(f"Error while processing CSV data: {e}")
        return {"status": 500, "message": "Internal server error"}, 500

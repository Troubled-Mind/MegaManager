import re
import subprocess
from datetime import datetime
from database import get_db
from models import MegaAccount
from utils.commands.shared import get_account_files, size_to_bytes
from utils.config import cmd

def run(args=None):
    try:
        with get_db() as session:
            print(f"args = {args!r} (type = {type(args).__name__})")

            if args == "all" or args is None:
                account_ids = [acc.id for acc in session.query(MegaAccount).all()]
            elif isinstance(args, list):
                account_ids = [int(id) for id in args]
            else:
                account_ids = [int(args)]
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}
    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}

    overall_status = 200
    results = []

    for account_id in account_ids:
        print(f"\nINFO Processing account ID {account_id}")
        result = process_account(account_id)
        results.append(f"Account {account_id}: {result['message']}")

        if result.get("status") != 200:
            overall_status = 500

    # Invalidate stats cache so total quota updates
    from utils.stats_cache import invalidate_and_refresh_async
    invalidate_and_refresh_async()

    return {
        "status": overall_status,
        "account_ids": account_ids,
        "message": "\n\n".join(results)
    }


def format_command(exe, *args):
    return f"{exe} {' '.join(args)}"


def process_account(account_id):
    with get_db() as session:
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()

        if not account:
            return {"status": 404, "message": f"No account found with ID {account_id}"}

        email = account.email
        password = account.password

        try:
            # Skip synchronization for accounts awaiting manual verification
            if account.status == "Pending Verification":
                return {"status": 202, "message": f"Account {email} is pending verification. Please verify before syncing."}

            # Holds the process-wide MEGAcmd session lock from login through
            # the mega-whoami/mega-find calls below, so a concurrent
            # upload/sync job can't log in as a different account mid-way
            # and redirect these commands to the wrong account.
            from utils.mega_session import mega_session
            with mega_session(email, password) as logged_in:
                if not logged_in:
                    return {"status": 500, "message": f"Login failed for {email} after 3 attempts - check server log for the MEGA error detail (wrong password, unverified account, or session conflict)"}

                # Optional info retrieval
                is_pro = False
                used_quota = account.used_quota or "0"
                total_quota = account.total_quota or "0"

                try:
                    whoami_output = subprocess.run([cmd("mega-whoami"), "-l"], capture_output=True, text=True)
                    if pro_level_match := re.search(r"Pro level:\s+(\d+)", whoami_output.stdout):
                        pro_level = int(pro_level_match.group(1))
                        is_pro = pro_level > 0

                    # Fetch quota via rclone - ensure the account has an rclone.conf
                    # entry first. Accounts registered/confirmed through the app
                    # only ever get one via CSV import today; without this,
                    # get_account_quota() silently fails forever for any account
                    # that arrived any other way, and it never contributes to the
                    # Total Cloud Pool figure no matter how often it's refreshed.
                    from utils.rclone_config import get_account_quota, add_or_update_account
                    add_or_update_account(account_id, email, password)
                    r_used, r_total = get_account_quota(account_id)
                    if r_used is not None and r_total is not None:
                        used_quota, total_quota = r_used, r_total
                    else:
                        print(f"WARNING Could not fetch quota for {email} via rclone (check rclone.conf)")

                except Exception as e:
                    print(f"WARNING Non-critical error fetching account info for {email}: {e}")

                now = datetime.utcnow()
                account.is_pro_account = 1 if is_pro else 0
                account.used_quota = used_quota
                account.total_quota = total_quota
                account.storage_quota_updated = now
                account.last_login = now
                session.commit()

                # Index account files
                print("INFO Indexing account files...")
                result = get_account_files(account_id)
                if result.get("status") != 200:
                    print(f"WARNING Indexing failed: {result.get('message')}")

            return {"status": 200, "message": f"Login and sync successful for {email}"}

        except Exception as e:
            print(f"ERROR Account sync failed for {email}: {e}")
            return {"status": 500, "message": str(e)}

def parse_pro_level(output):
    for line in output.splitlines():
        if "Pro level:" in line:
            match = re.search(r"Pro level:\s+(\d+)", line)
            if match:
                return int(match.group(1))
    return 0

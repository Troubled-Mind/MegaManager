import subprocess
import urllib.parse
from database import get_db
from models import MegaAccount
from utils.config import cmd
from utils.mega_session import hold_mega_session_lock

def run(command_args=None):
    """
    Finalizes MEGA account registration using a verification link.
    Usage: "account_id|verification_link"
    """
    try:
        if isinstance(command_args, list):
            command_args = command_args[0]

        if "|" not in command_args:
             return {"status": 400, "message": "Usage: account_id|verification_link"}

        acc_id_str, link = command_args.split("|", 1)
        acc_id = int(acc_id_str)
        # Note: link might be double-encoded depending on how it's sent,
        # but parse_qs usually handles it once.
        link = urllib.parse.unquote(link).strip()
    except Exception as e:
        return {"status": 400, "message": f"Error parsing arguments: {str(e)}"}

    with get_db() as db:
        account = db.query(MegaAccount).filter(MegaAccount.id == acc_id).first()
        if not account:
            return {"status": 404, "message": f"Account {acc_id} not found in database."}

        email = account.email
        password = account.password

        print(f"INFO Executing mega-confirm for {email}...")

        try:
            # Holds the process-wide MEGAcmd session lock across the logout +
            # confirm sequence, so a concurrent account_login/register/etc.
            # call can't log in mid-sequence and get logged straight back out.
            with hold_mega_session_lock():
                # Ensure no other session is active to prevent 'Access denied' during confirmation
                subprocess.run([cmd("mega-logout")], capture_output=True, text=True, timeout=10)

                # MEGA-CMD confirm usage: mega-confirm <link> <email> <password>
                process = subprocess.run(
                    [cmd("mega-confirm"), link, email, password],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

            if process.returncode == 0:
                print(f"DONE {email} is now Active.")
                account.status = "Active"
                db.commit()

                # Fetch quota immediately so it shows up (e.g. in Total Cloud
                # Pool) without requiring a separate manual refresh click.
                try:
                    from utils.commands.accounts.account_login import process_account
                    process_account(acc_id)
                    from utils.stats_cache import invalidate_and_refresh_async
                    invalidate_and_refresh_async()
                except Exception as quota_err:
                    print(f"WARNING Post-verification quota fetch failed for {email}: {quota_err}")

                return {"status": 200, "message": f"Account {email} successfully verified!"}
            else:
                raw_error = process.stderr.strip() or process.stdout.strip()
                print(f"ERROR Verification failed for {email}: {raw_error}")

                # Humanize known MEGA-CMD errors
                if "Failed to check email corresponds to link" in raw_error or "Not found" in raw_error:
                    error_msg = "The verification link does not match this account or has expired. Please verify using the latest link sent to this email."
                elif "Access denied" in raw_error:
                    error_msg = "Access denied by MEGA. Ensure the credentials are correct and you are not logged in elsewhere."
                elif "Already confirmed" in raw_error or "already registered" in raw_error.lower():
                    error_msg = "This account has already been confirmed."
                elif "Invalid link" in raw_error:
                    error_msg = "The verification link provided is invalid or malformed."
                else:
                    # Strip raw internal MEGA timestamp tags like [2026-08-10_... cmd ERR ...]
                    import re
                    cleaned = re.sub(r'\[\d{4}-\d{2}-\d{2}[^\]]*\]', '', raw_error).strip()
                    error_msg = cleaned if cleaned else raw_error

                return {"status": 500, "message": error_msg}

        except subprocess.TimeoutExpired:
            return {"status": 500, "message": "Verification timed out. Please check your internet connection and try again."}
        except Exception as e:
            return {"status": 500, "message": f"Internal error during confirmation: {str(e)}"}

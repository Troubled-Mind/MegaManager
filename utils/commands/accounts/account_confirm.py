import subprocess
import urllib.parse
from database import get_db
from models import MegaAccount
from utils.config import cmd

def run(command_args=None):
    """
    Finalizes MEGA account registration using a verification link.
    Usage: "account_id|verification_link"
    """
    if not command_args:
        return {"status": 400, "message": "Missing arguments"}

    raw_args = command_args[0] if isinstance(command_args, list) else command_args
    if "|" not in raw_args:
        return {"status": 400, "message": "Usage: account_id|verification_link"}

    try:
        acc_id_str, link = raw_args.split("|")
        acc_id = int(acc_id_str)
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
        # MEGA-CMD confirm usage: mega-confirm <link> <email> <password>
        try:
            # We use subprocess.run with a timeout because mega-confirm can occasionally hang if the link is invalid
            process = subprocess.run(
                [cmd("mega-confirm"), link, email, password],
                capture_output=True,
                text=True,
                timeout=30
            )

            if process.returncode == 0:
                print(f"DONE {email} is now Active.")
                account.status = "Active"
                db.commit()
                return {"status": 200, "message": f"Account {email} successfully verified!"}
            else:
                error_msg = process.stderr.strip() or process.stdout.strip()
                print(f"ERROR Verification failed for {email}: {error_msg}")
                return {"status": 500, "message": f"MEGA-CMD error: {error_msg}"}

        except subprocess.TimeoutExpired:
            return {"status": 500, "message": "Verification timed out. Please check if the link is valid."}
        except Exception as e:
            return {"status": 500, "message": f"Internal error during confirmation: {str(e)}"}

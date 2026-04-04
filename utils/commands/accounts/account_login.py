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
            print(f"📥 args = {args!r} (type = {type(args).__name__})")

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
            # User specifically requested full logout/login cycles for consistency
            print(f"INFO Resetting session for {email}...")
            subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Consistent Session Management
            from utils.mega_session import ensure_logged_in
            if not ensure_logged_in(email, password):
                return {"status": 500, "message": f"Authentication failed for {email}"}

            # Optional info retrieval
            is_pro = False
            used_quota = account.used_quota or "0"
            total_quota = account.total_quota or "0"

            try:
                # Get pro level
                whoami_output = subprocess.run([cmd("mega-whoami"), "-l"], capture_output=True, text=True)
                if pro_level_match := re.search(r"Pro level:\s+(\d+)", whoami_output.stdout):
                    pro_level = int(pro_level_match.group(1))
                    is_pro = pro_level > 0
                
                # Fetch quota
                df_cmd = [cmd("mega-df"), "-h"] if is_pro else [cmd("mega-df")]
                df_output = subprocess.run(df_cmd, capture_output=True, text=True)
                
                if df_output.returncode == 0:
                    u, t = parse_mega_df_h(df_output.stdout) if is_pro else parse_mega_df(df_output.stdout)
                    used_quota, total_quota = u, t
                else:
                    print(f"WARNING Could not fetch quota (Access Denied or similar): {df_output.stderr.strip()}")
            except Exception as e:
                print(f"WARNING Non-critical error fetching account info: {e}")

            # Update Account state
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



def parse_mega_df(output):
    for line in output.splitlines():
        if "USED STORAGE:" in line:
            match = re.search(r'USED STORAGE:\s+(\d+).*?of\s+(\d+)', line)
            if match:
                used = match.group(1)
                total = match.group(2)
                return used, total
    return "0", "0"


def parse_mega_df_h(output):
    for line in output.splitlines():
        if "USED STORAGE:" in line:
            match = re.search(r'USED STORAGE:\s+([0-9.]+\s*[KMGT]?B).*?of\s+([0-9.]+\s*[KMGT]?B)', line)
            if match:
                used = size_to_bytes(match.group(1))
                total = size_to_bytes(match.group(2))
                return used, total
    return "0", "0"


def parse_pro_level(output):
    for line in output.splitlines():
        if "Pro level:" in line:
            match = re.search(r"Pro level:\s+(\d+)", line)
            if match:
                return int(match.group(1))
    return 0

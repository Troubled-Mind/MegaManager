import os
import re
import sqlite3
import subprocess
from datetime import datetime
from utils.config import settings

DB_PATH = "database.db"

def run(args=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print(f"📥 args = {args!r} (type = {type(args).__name__})")

        if args == "all" or args is None:
            cursor.execute("SELECT id FROM mega_accounts")
            account_ids = [row[0] for row in cursor.fetchall()]
        elif isinstance(args, list):
            account_ids = [int(id) for id in args]
        else:
            account_ids = [int(args)]
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}
    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}
    finally:
        conn.close()

    overall_status = 200
    results = []

    for account_id in account_ids:
        print(f"\n🔁 Processing account ID {account_id}")
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT email, password FROM mega_accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"status": 404, "message": f"No account found with ID {account_id}"}

    email, password = row
    print(f"🔑 Email: {email} | Password: {password}")

    try:
        # Resolve executable paths
        base_cmd_path = settings.get("megacmd_path")
        def cmd(name):
            return os.path.join(base_cmd_path, name) if base_cmd_path else name

        # Logout to reset session
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Login command (safe list form)
        print(f"▶ Logging in: {email}")
        subprocess.run([cmd("mega-login"), email, password], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        print(f"✅ Logged in: {email}")

        # Fetch quota
        df_output = subprocess.run([cmd("mega-df")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        used_quota, total_quota = parse_mega_df(df_output.stdout.strip())
        print(f"💾 Used: {used_quota} / Total: {total_quota}")

        # Get pro level
        whoami_output = subprocess.run([cmd("mega-whoami"), "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        pro_level = parse_pro_level(whoami_output.stdout.strip())
        is_pro = pro_level > 0
        print(f"👤 Pro level: {pro_level} → {'✅ Pro' if is_pro else '❌ Free'}")

        # Update DB
        now = datetime.utcnow().isoformat()
        cursor.execute(
            "UPDATE mega_accounts SET is_pro_account = ?, used_quota = ?, total_quota = ?, storage_quota_updated = ?, last_login = ? WHERE id = ?",
            (1 if is_pro else 0, used_quota, total_quota, now, now, account_id)
        )
        conn.commit()

        # Logout
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        return {"status": 200, "message": f"Login successful for account {email}"}

    except subprocess.CalledProcessError as e:
        stdout = e.stdout.strip() if e.stdout else ""
        stderr = e.stderr.strip() if e.stderr else ""

        # Look for known error patterns
        if "unconfirmed account" in stdout.lower():
            error_msg = "Login failed: unconfirmed account. Please confirm your account"
        elif "already logged in" in stdout.lower():
            error_msg = "Already logged in"
        else:
            # Try to extract a cleaner message from stdout
            match = re.search(r'cmd ERR\s+(.*?)(]|\Z)', stdout)
            if match:
                error_msg = match.group(1).strip()
            else:
                error_msg = stderr or stdout or f"Unknown error (code {e.returncode})"

        print(f"❌ Error for {email}: {error_msg} | code: {e.returncode}")

        return {
            "status": 500,
            "message": error_msg,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": e.returncode
        }

    finally:
        conn.close()



def parse_mega_df(output):
    for line in output.splitlines():
        if "USED STORAGE:" in line:
            match = re.search(r'USED STORAGE:\s+(\d+).*?of\s+(\d+)', line)
            if match:
                used = match.group(1)
                total = match.group(2)
                return used, total
    return "0", "0"


def parse_pro_level(output):
    for line in output.splitlines():
        if "Pro level:" in line:
            match = re.search(r"Pro level:\s+(\d+)", line)
            if match:
                return int(match.group(1))
    return 0

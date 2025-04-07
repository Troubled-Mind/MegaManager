import re
import sqlite3
import subprocess
from datetime import datetime

DB_PATH = "database.db"

def run(args=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if args == "all" or args is None:
            cursor.execute("SELECT id FROM mega_accounts")
            account_ids = [row[0] for row in cursor.fetchall()]
        else:
            account_ids = [int(args)]
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}
    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}
    finally:
        conn.close()

    results = []

    for account_id in account_ids:
        print(f"\n🔁 Processing account ID {account_id}")
        result = process_account(account_id)
        results.append(f"Account {account_id}: {result['message']}")

    return {
        "status": 200,
        "account_ids": account_ids,
        "message": "\n\n".join(results)
    }

def process_account(account_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT email, password FROM mega_accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"status": 404, "message": f"No account found with ID {account_id}"}

    email, password = row

    try:
        # Ensure clean session
        subprocess.run(["mega-logout"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

        # Log in
        result = subprocess.run(["mega-login", email, password], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        login_output = result.stdout.strip()
        print(f"✅ Logged in: {email}")

        # Get quota info
        print("🔍 Getting storage quota info...")
        quota_result = subprocess.run(["mega-df"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        used_quota, total_quota = parse_mega_df(quota_result.stdout.strip())
        print(f"💾 Used: {used_quota} / Total: {total_quota}")

        now = datetime.utcnow().isoformat()
        cursor.execute(
            "UPDATE mega_accounts SET used_quota = ?, total_quota = ?, storage_quota_updated = ?, last_login = ? WHERE id = ?",
            (used_quota, total_quota, now, now, account_id)
        )
        conn.commit()

        # Log out
        logout_result = subprocess.run(["mega-logout"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        logout_output = logout_result.stdout.strip()
        print("👋 Logged out")

        return {
            "status": 200,
            "message": f"Login successful for account {email}"
        }

    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip()
        print(f"❌ Error for {email}: {error_output}")
        return {"status": 500, "message": f"{email} - Error: {error_output}"}

    finally:
        conn.close()

def parse_mega_df(output):
    """
    Parse the 'USED STORAGE' line from mega-cmd's df output:
    USED STORAGE:  16593337485          77.27% of 21474836480
    """
    for line in output.splitlines():
        if "USED STORAGE:" in line:
            match = re.search(r'USED STORAGE:\s+(\d+).*?of\s+(\d+)', line)
            if match:
                used = match.group(1)
                total = match.group(2)
                return used, total
    return "0", "0"

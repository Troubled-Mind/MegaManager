import re
import sqlite3
import subprocess
from datetime import datetime

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
        return {"status": 400, "message": "Invalid account ID"}, 400
    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}, 500
    finally:
        conn.close()

    overall_status = 200
    results = []

    for account_id in account_ids:
        print(f"\n🔁 Processing account ID {account_id}")
        result, status = process_account(account_id)
        results.append(f"Account {account_id}: {result['message']}")
        
        if status != 200:
            overall_status = 500

    return {
        "status": overall_status,
        "account_ids": account_ids,
        "message": "\n\n".join(results)
    }, overall_status

def process_account(account_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT email, password FROM mega_accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"status": 404, "message": f"No account found with ID {account_id}"}, 404

    email, password = row

    try:
        # Ensure clean session
        subprocess.run(["mega-logout"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True, check=False)

        # Log in
        result = subprocess.run(["mega-login", email, password], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True, check=True)
        login_output = result.stdout.strip()
        print(f"✅ Logged in: {email}")

        # Get quota info
        quota_result = subprocess.run(["mega-df"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True, check=True)
        used_quota, total_quota = parse_mega_df(quota_result.stdout.strip())
        print(f"💾 Used: {used_quota} / Total: {total_quota}")

        whoami_result = subprocess.run(
            ["mega-whoami", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
            check=True
        )
        pro_level = parse_pro_level(whoami_result.stdout.strip())
        is_pro = pro_level > 0
        print(f"👤 Pro level: {pro_level} → {'✅ Pro' if is_pro else '❌ Free'}")
        if is_pro:
            pro_account = 1
        else:
            pro_account = 0


        now = datetime.utcnow().isoformat()
        cursor.execute(
            "UPDATE mega_accounts SET is_pro_account = ?, used_quota = ?, total_quota = ?, storage_quota_updated = ?, last_login = ? WHERE id = ?",
            (pro_account, used_quota, total_quota, now, now, account_id)
        )
        conn.commit()

        # Log out
        logout_result = subprocess.run(["mega-logout"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True, check=True)
        logout_output = logout_result.stdout.strip()
        print("👋 Logged out")

        return {
            "status": 200,
            "message": f"Login successful for account {email}"
        }, 200

    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip()
        print(f"❌ Error for {email}: {error_output} | status: 500")
        return {"status": 500, "message": f"{email} - Error: {error_output}"}, 500

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

def parse_pro_level(output):
    """
    Extracts the Pro level from the output of `mega-whoami -l`
    Example line:
    Pro level: 1
    """
    for line in output.splitlines():
        if "Pro level:" in line:
            match = re.search(r"Pro level:\s+(\d+)", line)
            if match:
                return int(match.group(1))
    return 0
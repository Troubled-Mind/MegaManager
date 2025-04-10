import sqlite3
import subprocess
from utils.config import cmd
from utils.commands.shared import get_account_files

DB_PATH = "database.db"
OUTPUT_PATH = "files.txt"

def run(args=None):
    try:
        account_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email, password FROM mega_accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"status": 404, "message": f"No account found with ID {account_id}"}

    email, password = row
    print(f"🔑 Logging into MEGA as {email}")

    try:
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run([cmd("mega-login"), email, password], check=True, text=True)

        return get_account_files(account_id)

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to fetch folders: {e}")
        return {"status": 500, "message": "Failed to fetch folders from MEGA"}

import sqlite3
from datetime import datetime

DB_PATH = "database.db"

def run(args=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, email, password, is_pro_account, used_quota, total_quota, last_login FROM mega_accounts")
    rows = cursor.fetchall()
    conn.close()

    accounts = []
    for row in rows:
        id, email, password, is_pro, used, total, last_login = row
        accounts.append({
            "id": id,
            "email": email,
            "password": password,
            "is_pro": bool(is_pro),
            "used_quota": int(used) if used else 0,
            "total_quota": int(total) if total else 0,
            "last_login": last_login or ""
        })

    return {"status": 200, "accounts": accounts}

import sqlite3

DB_PATH = "database.db"

def run(args=None):
    try:
        account_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch account info
    cursor.execute("""
        SELECT id, email, password, is_pro_account, used_quota, total_quota, last_login
        FROM mega_accounts
        WHERE id = ?
    """, (account_id,))
    row = cursor.fetchone()

    # Count linked files in unified `files` table
    cursor.execute("SELECT COUNT(*) FROM files WHERE m_account_id = ?", (account_id,))
    file_count = cursor.fetchone()[0]
    conn.close()

    if not row:
        return {"status": 404, "message": f"No account found with ID {account_id}"}

    id, email, password, is_pro, used, total, last_login = row
    return {
        "status": 200,
        "account": {
            "id": id,
            "email": email,
            "password": password,
            "is_pro": bool(is_pro),
            "used_quota": int(used) if used else 0,
            "total_quota": int(total) if total else 0,
            "last_login": last_login or "",
            "linked_files": file_count
        }
    }

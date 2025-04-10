import sqlite3

DB_PATH = "database.db"

def run(args=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM mega_accounts")
        account_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        return {"status": 200, "account_ids": account_ids}
    except Exception as e:
        return {"status": 500, "message": str(e)}

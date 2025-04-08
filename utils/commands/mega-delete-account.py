import sqlite3

DB_PATH = "database.db"

def run(args=None):
    try:
        account_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if the account exists first
    cursor.execute("SELECT id FROM mega_accounts WHERE id = ?", (account_id,))
    if not cursor.fetchone():
        conn.close()
        return {"status": 404, "message": f"No account found with ID {account_id}"}

    # Delete the account
    cursor.execute("DELETE FROM mega_accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()

    return {"status": 200, "message": f"Account {account_id} deleted successfully"}

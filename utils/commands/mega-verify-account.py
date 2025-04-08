import sqlite3
import subprocess
from urllib.parse import unquote
from utils.config import settings

DB_PATH = "database.db"

def run(args=None):
    try:
        if not args or "|" not in args:
            return {"status": 400, "message": "Missing account ID or verification link"}, 400

        account_id_str, link_encoded = args.split("|", 1)
        account_id = int(account_id_str)
        verification_link = unquote(link_encoded).strip()

        if not verification_link.startswith("https://mega.nz/"):
            return {"status": 400, "message": "Invalid verification link format"}, 400

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT email, password FROM mega_accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"status": 404, "message": "Account not found"}, 404

        email, password = row
        if not email or not password:
            return {"status": 400, "message": "Missing email or password for account"}, 400

        # Get megacmd path from settings
        path = settings.get_megacmd_path()

        print(f"🔗 Verifying account {account_id} using link: {verification_link}")
        result = subprocess.run(
            [rf"{path}mega-confirm", verification_link, email, password],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        print(f"✅ Verification complete: {result.stdout.strip()}")
        return {
            "status": 200,
            "message": f"Verification successful for account ID {account_id}"
        }, 200

    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip()
        print(f"❌ Verification error: {error_output}")
        return {"status": 500, "message": f"Verification failed: {error_output}"}, 500
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {"status": 500, "message": f"Unexpected error: {e}"}, 500

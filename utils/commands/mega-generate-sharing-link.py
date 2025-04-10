import sqlite3
import subprocess
import re
from utils.config import cmd

def run(mega_file_id, expiry=None):

    # Ensure mega_file_id is an integer
    try:
        mega_file_id = int(mega_file_id)
    except ValueError:
        print("[ERROR] Invalid file ID format. Must be an integer.")
        return {"status": "error", "message": "Invalid file ID format. Must be an integer."}

    # Connect to the database
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
    except sqlite3.Error as e:
        print(f"[ERROR] Database connection failed: {e}")
        return {"status": "error", "message": f"Database connection failed: {e}"}

    # Retrieve file and account details
    try:
        cursor.execute("""
            SELECT mf.path, mf.folder_name, ma.email, ma.password
            FROM mega_files mf
            JOIN mega_accounts ma ON mf.mega_account_id = ma.id
            WHERE mf.id = ?
        """, (mega_file_id,))
        row = cursor.fetchone()
        conn.close()
    except sqlite3.Error as e:
        print(f"[ERROR] Database query failed: {e}")
        return {"status": "error", "message": f"Database query failed: {e}"}

    if not row:
        print("[WARNING] File or account not found.")
        return {"status": "error", "message": "File or account not found."}

    path, folder_name, email, password = row
    full_path = f"{path.rstrip('/')}/{folder_name}"

    # Login to MEGA account
    login_cmd = [cmd("mega-logout")]
    login_cmd = [cmd("mega-login"), email, password]
    login_result = subprocess.run(login_cmd, capture_output=True, text=True)
    if login_result.returncode != 0:
        return {"status": "error", "message": f"Login failed: {login_result.stderr.strip()}"}


    # Generate sharing link
    export_cmd = [cmd("mega-export"), "-a", full_path.strip()]
    if expiry:
        export_cmd += ["--expire", expiry]
    export_result = subprocess.run(export_cmd, capture_output=True, text=True)
    if export_result.returncode != 0:
        return {"status": "error", "message": f"Export failed: {export_result.stderr.strip()}"}

    # Extract the sharing link from the output
    match = re.search(r'https://mega\.nz/\S+', export_result.stdout)
    if not match:
        print("[ERROR] Export succeeded but no link was found.")
        return {"status": "error", "message": "Export succeeded but no link was found."}

    sharing_link = match.group(0)
    print(f"[INFO] Sharing link generated: {sharing_link}")
    login_cmd = [cmd("mega-logout")]
    return {"status": 200, "link": sharing_link}

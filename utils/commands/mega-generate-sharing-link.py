import sqlite3
import subprocess
import re
from utils.config import cmd

def run(file_id, expiry=None):
    # Ensure file_id is an integer
    try:
        file_id = int(file_id)
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
            SELECT f.m_path, f.m_folder_name, ma.email, ma.password
            FROM files f
            JOIN mega_accounts ma ON f.m_account_id = ma.id
            WHERE f.id = ?
        """, (file_id,))
        row = cursor.fetchone()
    except sqlite3.Error as e:
        conn.close()
        print(f"[ERROR] Database query failed: {e}")
        return {"status": "error", "message": f"Database query failed: {e}"}

    if not row:
        conn.close()
        print("[WARNING] File or account not found.")
        return {"status": "error", "message": "File or account not found."}

    path, folder_name, email, password = row
    full_path = f"{path.rstrip('/')}/{folder_name}"

    # Logout and login to MEGA
    subprocess.run([cmd("mega-logout")], capture_output=True, text=True)
    login_result = subprocess.run([cmd("mega-login"), email, password], capture_output=True, text=True)
    if login_result.returncode != 0:
        conn.close()
        return {"status": "error", "message": f"Login failed: {login_result.stderr.strip()}"}

    # Generate sharing link
    export_cmd = [cmd("mega-export"), "-a", full_path.strip()]
    if expiry:
        export_cmd += ["--expire", expiry]

    export_result = subprocess.run(export_cmd, capture_output=True, text=True)
    if export_result.returncode != 0:
        conn.close()
        return {"status": "error", "message": f"Export failed: {export_result.stderr.strip()}"}

    match = re.search(r'https://mega\.nz/\S+', export_result.stdout)
    if not match:
        conn.close()
        print("[ERROR] Export succeeded but no link was found.")
        return {"status": "error", "message": "Export succeeded but no link was found."}

    sharing_link = match.group(0)
    print(f"[INFO] Sharing link generated: {sharing_link}")

    # Save link to database
    try:
        cursor.execute("UPDATE files SET m_sharing_link = ? WHERE id = ?", (sharing_link, file_id))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[ERROR] Failed to update sharing link: {e}")
        return {"status": "error", "message": f"Failed to update sharing link: {e}"}
    finally:
        conn.close()

    subprocess.run([cmd("mega-logout")], capture_output=True, text=True)
    return {"status": 200, "link": sharing_link}

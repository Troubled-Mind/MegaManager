import re
import sqlite3
import subprocess
from collections import defaultdict
from utils.config import cmd

def run(args=None):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
    except sqlite3.Error as e:
        return {"status": 500, "message": f"Database connection failed: {e}"}

    # Get all files with no sharing link, but that have MEGA data
    cursor.execute("""
        SELECT f.id, f.m_path, f.m_folder_name, f.m_account_id, ma.email, ma.password
        FROM files f
        JOIN mega_accounts ma ON f.m_account_id = ma.id
        WHERE f.m_path IS NOT NULL
          AND (f.m_sharing_link IS NULL OR TRIM(f.m_sharing_link) = '')
    """)
    rows = cursor.fetchall()

    files_by_account = defaultdict(list)
    for row in rows:
        file_id, path, folder_name, acc_id, email, password = row
        files_by_account[acc_id].append({
            "id": file_id,
            "path": path,
            "folder_name": folder_name,
            "email": email,
            "password": password
        })

    results = []

    for acc_id, files in files_by_account.items():
        account = files[0]
        subprocess.run([cmd("mega-logout")], capture_output=True, text=True)
        login = subprocess.run([cmd("mega-login"), account["email"], account["password"]], capture_output=True, text=True)

        if login.returncode != 0:
            results.append({
                "account_id": acc_id,
                "email": account["email"],
                "status": "error",
                "message": f"Login failed: {login.stderr.strip()}"
            })
            continue

        account_results = []

        for file in files:
            full_path = f"{file['path'].rstrip('/')}/{file['folder_name']}"
            export_cmd = [cmd("mega-export"), "-a", full_path]
            export = subprocess.run(export_cmd, capture_output=True, text=True)

            if export.returncode == 0:
                match = re.search(r'https://mega\.nz/\S+', export.stdout)
                if match:
                    sharing_link = match.group(0)
                    cursor.execute("UPDATE files SET m_sharing_link = ? WHERE id = ?", (sharing_link, file["id"]))
                    account_results.append({"id": file["id"], "link": sharing_link})
                else:
                    account_results.append({"id": file["id"], "error": "No link found in output"})
            else:
                account_results.append({"id": file["id"], "error": export.stderr.strip()})

        conn.commit()
        results.append({
            "account_id": acc_id,
            "email": account["email"],
            "status": "success",
            "updated": account_results
        })

        subprocess.run([cmd("mega-logout")], capture_output=True, text=True)

    conn.close()
    return {"status": 200, "results": results}

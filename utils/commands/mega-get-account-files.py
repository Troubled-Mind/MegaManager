import os
import re
import sqlite3
import subprocess
from utils.config import settings, cmd
from database import get_db
from models import MegaFile

DB_PATH = "database.db"
OUTPUT_PATH = "files.txt"

def strftime_to_regex(fmt):
    """Convert a strftime-style format string into a regex pattern."""
    replacements = {
        "%Y": r"\d{4}",
        "%y": r"\d{2}",
        "%m": r"\d{2}",
        "%-m": r"\d{1,2}",
        "%B": r"[A-Za-z]+",
        "%b": r"[A-Za-z]{3}",
        "%d": r"\d{2}",
        "%-d": r"\d{1,2}",
        "%e": r"\d{1,2}",
        "%j": r"\d{3}",
        " ": r"\s",
        ",": r",",
        "\.": r"\.",
        "-": r"-",
        "/": r"[/-]",
    }
    pattern = re.escape(fmt)
    for k, v in replacements.items():
        pattern = pattern.replace(re.escape(k), v)
    return pattern

def extract_root_dated_folders(paths):
    """Extract highest-level folders that match any date pattern."""
    full_fmt = settings.get("date_format_full") or ""
    month_fmt = settings.get("date_format_month") or ""
    year_fmt = settings.get("date_format_year") or ""

    regex_patterns = []
    if full_fmt:
        regex_patterns.append(strftime_to_regex(full_fmt))
    if month_fmt:
        regex_patterns.append(strftime_to_regex(month_fmt))
    if year_fmt:
        regex_patterns.append(strftime_to_regex(year_fmt))

    if not regex_patterns:
        print("⚠️ No date formats configured in settings.")
        return []

    combined_pattern = re.compile(r"|".join(regex_patterns))
    root_folders = set()

    for path in paths:
        parts = path.strip("/").split("/")
        for i in range(len(parts)):
            if combined_pattern.search(parts[i]):
                root_folder = "/" + "/".join(parts[:i + 1])
                root_folders.add(root_folder)
                break

    return sorted(root_folders)

def get_account_files(account_id):
    """Call mega-find to get all paths, extract root dated folders and build mega_file objects."""
    result = subprocess.run(
        [cmd("mega-find"), "/"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
        encoding="utf-8"
    )

    raw_paths = result.stdout.strip().splitlines()
    root_dated_folders = extract_root_dated_folders(raw_paths)

    # Create mega_files objects
    mega_files = []
    for folder in root_dated_folders:
        path, folder_name = os.path.split(folder)
        mega_files.append(MegaFile(
            path=path,
            folder_name=folder_name,
            mega_account_id=account_id
        ))
    
    # Save to database
    session = next(get_db())
    try:
        session.add_all(mega_files)
        session.commit()
        return {"status": 200, "message": f"{len(mega_files)} folders saved to database"}
    except Exception as e:
        session.rollback()
        print(f"❌ Failed to save folders to database: {e}")
        return {"status": 500, "message": "Failed to save folders to database"}

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

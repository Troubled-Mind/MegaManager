import os
import re
import subprocess
from utils.config import settings, cmd
from database import get_db
from models import File

BYTE_MULTIPLIERS = {
    "B":1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4
}

def size_to_bytes(size_str):
    """Convert a human-readable size string (e.g. 6.34 TB) to bytes."""
    size_str = size_str.strip()
    number, unit = re.match(r"([0-9.]+)\s*([KMGT]?B)", size_str).groups()
    number = float(number)
    unit = unit.upper()

    if unit in BYTE_MULTIPLIERS:
        return int(number * BYTE_MULTIPLIERS[unit])
    raise ValueError(f"Unknown size unit: {unit}")

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
        r" ": r"\s",
        r",": r",",
        r"\.": r"\.",
        r"-": r"-",
        r"/": r"[/-]",
    }
    pattern = re.escape(fmt)
    for k, v in replacements.items():
        pattern = pattern.replace(k, v)
    return pattern

def extract_root_dated_folders(paths):
    """Extract highest-level folders that match any date pattern."""
    full_fmt = settings.get("date_format_full") or ""
    month_fmt = settings.get("date_format_month") or ""
    year_fmt = settings.get("date_format_year") or ""

    regex_patterns = []
    if full_fmt:
        regex_patterns.append(strftime_to_regex(full_fmt))
        print(f"📅 Using full date format: {full_fmt}")
    if month_fmt:
        regex_patterns.append(strftime_to_regex(month_fmt))
        print(f"🗓️ Using month format: {month_fmt}")
    if year_fmt:
        regex_patterns.append(strftime_to_regex(year_fmt))
        print(f"📆 Using year format: {year_fmt}")

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

    result = sorted(root_folders)
    print(f"📦 Extracted {len(result)} root folders.")
    return result

def get_account_files(account_id):
    """Call mega-find to get all paths, extract root dated folders and add to the files table."""
    print(f"🔍 Scanning MEGA account ID {account_id}...")
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

    session = next(get_db())
    added = 0
    updated = 0

    for folder in root_dated_folders:
        path, folder_name = os.path.split(folder.rstrip("/"))
        normalized_folder_name = folder_name.strip()

        # Check if MEGA record already exists
        existing = session.query(File).filter_by(m_path=path, m_folder_name=folder_name).first()
        if existing:
            print(f"🔁 Already exists: {folder}")
            continue

        # Try to match local-only file by folder name
        fallback = session.query(File).filter(
            File.m_path == None,
            File.l_folder_name == normalized_folder_name
        ).first()

        if fallback:
            print(f"🔁 Updating local-only entry to MEGA: {folder}")
            fallback.m_path = path
            fallback.m_folder_name = folder_name
            fallback.m_account_id = account_id
            updated += 1
            continue

        print(f"➕ Adding: {folder}")
        session.add(File(
            m_path=path,
            m_folder_name=folder_name,
            m_account_id=account_id
        ))
        added += 1

    try:
        session.commit()
        print(f"✅ {added} added, {updated} updated MEGA folders saved to database")
        return {"status": 200, "message": f"{added} added, {updated} updated"}
    except Exception as e:
        session.rollback()
        print(f"❌ Failed to save: {e}")
        return {"status": 500, "message": "Failed to save MEGA folders"}

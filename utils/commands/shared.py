import os
import re
import json
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
    if not size_str or size_str.strip() in ["0", "None", ""]:
        return 0

    size_str = size_str.strip()
    match = re.match(r"([0-9.]+)\s*([KMGT]?B)", size_str)
    if not match:
        # If it's just a number, assume bytes
        try:
            return int(float(size_str))
        except:
            return 0

    number, unit = match.groups()
    number = float(number)
    unit = unit.upper()

    if unit in BYTE_MULTIPLIERS:
        return int(number * BYTE_MULTIPLIERS[unit])
    return 0

def get_local_paths():
    """Parse the local_paths setting into a list of strings."""
    local_paths = settings.get("local_paths", [])
    if isinstance(local_paths, str):
        try:
            local_paths = json.loads(local_paths)
        except Exception:
            local_paths = []
    if not isinstance(local_paths, list):
        local_paths = []
    return local_paths

def strip_local_base(full_path, local_paths):
    """Strip a configured local root off full_path to get its MEGA-equivalent /Show/Venue/... scope.
    Returns None if full_path doesn't start with any configured local_paths entry.

    Requires a path-separator boundary at the match (not just a string prefix), so a
    root like "/mnt/media" doesn't falsely match a sibling directory "/mnt/media2/...".
    """
    for local_base in local_paths:
        base = local_base.rstrip(os.sep)
        if not base:
            continue
        if full_path == base:
            return "/"
        if full_path.startswith(base + os.sep):
            return "/" + full_path[len(base):].lstrip(os.sep)
    return None

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
        print(f"INFO Using full date format: {full_fmt}")
    if month_fmt:
        regex_patterns.append(strftime_to_regex(month_fmt))
        print(f"INFO Using month format: {month_fmt}")
    if year_fmt:
        regex_patterns.append(strftime_to_regex(year_fmt))
        print(f"INFO Using year format: {year_fmt}")

    if not regex_patterns:
        print("WARNING No date formats configured in settings.")
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
    print(f"INFO Extracted {len(result)} root folders.")
    return result

# Below this, a fuzzy (tolerance-based) size match is too unreliable to trust - the
# 1 MiB tolerance floor would dwarf a small file's own size and match almost anything
# nearby in scope. Small files still get matched via the exact-byte-equality path.
MIN_FUZZY_MATCH_BYTES = 5 * 1024 * 1024

def _size_within_tolerance(a, b, size_tolerance=0.005, min_tolerance_bytes=1024 * 1024):
    """True if two byte sizes are close enough to be considered the same file."""
    if a == b:
        return True
    if a < MIN_FUZZY_MATCH_BYTES or b < MIN_FUZZY_MATCH_BYTES:
        return False
    tolerance = max(max(a, b) * size_tolerance, min_tolerance_bytes)
    return abs(a - b) <= tolerance

def match_local_to_cloud(session, l_path, l_folder_name, l_max_file_size):
    """Find an existing MEGA-only File row corresponding to a local release folder.

    Tries an exact folder/file name match first (fast path for already-conforming
    content), then falls back to matching within the same Show/Venue scope by comparing
    the local folder's largest single file against each cloud candidate's size
    (exact byte match preferred, small tolerance as a fallback safety margin).
    """
    existing = session.query(File).filter(
        File.m_folder_name == l_folder_name,
        File.l_path == None
    ).first()
    if existing:
        return existing

    if not l_max_file_size:
        return None

    scope = strip_local_base(l_path, get_local_paths())
    if not scope:
        return None

    try:
        target = int(l_max_file_size)
    except (TypeError, ValueError):
        return None
    if not target:
        return None

    candidates = session.query(File).filter(
        File.l_path == None,
        File.m_path == scope,
        File.m_folder_size != None
    ).all()

    best = None
    for cand in candidates:
        cand_size = size_to_bytes(cand.m_folder_size)
        if cand_size == target:
            return cand
        if best is None and _size_within_tolerance(cand_size, target):
            best = cand
    return best

def match_cloud_to_local(session, m_path, m_folder_name, m_size_bytes=None):
    """Find an existing local-only File row corresponding to a cloud item.

    Mirror of match_local_to_cloud, used while indexing MEGA content. m_size_bytes is
    frequently unavailable at scan time (cloud sizes are only fetched on demand via
    "Update Details"), in which case only the exact-name fast path applies.
    """
    existing = session.query(File).filter(
        File.l_folder_name == m_folder_name,
        File.m_path == None
    ).first()
    if existing:
        return existing

    if not m_size_bytes:
        return None

    local_paths = get_local_paths()
    candidate_l_paths = [
        os.path.join(base.rstrip(os.sep), m_path.lstrip("/").replace("/", os.sep))
        for base in local_paths
    ]
    if not candidate_l_paths:
        return None

    candidates = session.query(File).filter(
        File.m_path == None,
        File.l_path.in_(candidate_l_paths),
        File.l_largest_file_size != None
    ).all()

    best = None
    for cand in candidates:
        cand_size = size_to_bytes(cand.l_largest_file_size)
        if cand_size == m_size_bytes:
            return cand
        if best is None and _size_within_tolerance(cand_size, m_size_bytes):
            best = cand
    return best

def get_account_files(account_id):
    """Call mega-find to get all paths, extract root dated folders and add to the files table."""
    print(f"INFO Scanning MEGA account ID {account_id}...")
    result = subprocess.run(
        [cmd("mega-find"), "/"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )

    if result.returncode != 0:
        # Exit 57 = MEGA_EEXPIRED: session expired or account not fully confirmed yet
        if result.returncode == 57:
            print(f"WARNING mega-find returned exit 57 (EEXPIRED) for account {account_id} - account may not be verified or session expired. Skipping file index.")
            return {"status": 202, "message": "Account session expired or not yet confirmed - file index skipped"}
        err_detail = result.stderr.strip() or f"exit code {result.returncode}"
        print(f"WARNING mega-find failed for account {account_id}: {err_detail}")
        return {"status": 500, "message": f"mega-find failed: {err_detail}"}

    raw_paths = result.stdout.strip().splitlines()
    root_dated_folders = extract_root_dated_folders(raw_paths)

    with get_db() as session:
        added = 0
        updated = 0

        for folder in root_dated_folders:
            path, folder_name = os.path.split(folder.rstrip("/"))
            normalized_folder_name = folder_name.strip()

            existing = session.query(File).filter_by(m_path=path, m_folder_name=folder_name).first()
            if existing:
                print(f"INFO Already exists: {folder}")
                continue

            # Try to match a local-only entry by name, or by same Show/Venue scope + size
            fallback = match_cloud_to_local(session, path, normalized_folder_name, None)

            if fallback:
                print(f"INFO Updating local-only entry to MEGA: {folder}")
                fallback.m_path = path
                fallback.m_folder_name = folder_name
                fallback.m_account_id = account_id
                updated += 1
                continue

            print(f"INFO Adding: {folder}")
            session.add(File(
                m_path=path,
                m_folder_name=folder_name,
                m_account_id=account_id
            ))
            added += 1

        try:
            session.commit()
            print(f"DONE {added} added, {updated} updated MEGA folders saved to database")
            return {"status": 200, "message": f"{added} added, {updated} updated"}
        except Exception as e:
            session.rollback()
            print(f"ERROR Failed to save: {e}")
            return {"status": 500, "message": "Failed to save MEGA folders"}

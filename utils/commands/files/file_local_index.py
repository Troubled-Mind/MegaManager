import unicodedata
import fnmatch
import os
import json
import threading
from utils.commands.shared import extract_root_dated_folders, match_local_to_cloud
from models import File  # unified `files` table
from database import get_db
from utils.config import settings

# Always-ignored system/metadata files (added on top of user-configured list).
_SYSTEM_IGNORED = {'.DS_Store', 'Thumbs.db', 'desktop.ini', '.localized'}

def _ignored_patterns():
    """Return the combined set of ignore patterns from settings + system defaults."""
    raw = settings.get("ignored_filenames", "[]")
    try:
        user = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        user = []
    return list(_SYSTEM_IGNORED) + [p for p in user if p]

def _is_ignored_file(name):
    """True when a filename matches any system default or user-configured pattern."""
    if name.startswith('._'):   # macOS resource forks
        return True
    for pat in _ignored_patterns():
        if fnmatch.fnmatch(name, pat) or name == pat:
            return True
    return False

def _is_ignored_dir(name):
    """Directories whose names match any ignore pattern are skipped entirely."""
    for pat in _ignored_patterns():
        if fnmatch.fnmatch(name, pat) or name == pat:
            return True
    return False

def _nfc(s):
    """NFC-normalise a string — covers all Unicode, not just umlauts."""
    return unicodedata.normalize('NFC', s) if s else s


def run(args=None):
    """Index folders from local paths into the files table in a background thread."""
    local_paths = settings.get("local_paths", [])
    if isinstance(local_paths, str):
        try:
            local_paths = json.loads(local_paths)
        except Exception as e:
            return {"status": 400, "message": "local_paths must be a list or a valid JSON list string"}

    if not local_paths:
        return {"status": 400, "message": "No local paths configured."}

    indexing_thread = threading.Thread(target=index_folders_in_background, args=(local_paths,))
    indexing_thread.start()

    return {
        "status": 200,
        "message": "Local folder indexing started in the background."
    }

def index_folders_in_background(local_paths):
    """Wait for threads and perform the indexing."""
    print("Starting background local folder indexing...")
    try:
        all_subfolders = collect_all_subfolders(local_paths)
        root_folders = extract_root_dated_folders(all_subfolders)

        if not root_folders:
            print("No folders matching date format found.")
            return

        with get_db() as session:
            new_count = 0
            updated_count = 0
            linked_count = 0

            for full_path in root_folders:
                base_path, folder_name = os.path.split(full_path.rstrip("/"))
                folder_name = _nfc(folder_name)
                folder_size = calculate_folder_size(full_path)
                max_file_size = calculate_folder_max_file_size(full_path)

                existing_local = session.query(File).filter_by(l_path=base_path, l_folder_name=folder_name).first()
                if existing_local:
                    if existing_local.l_folder_size != str(folder_size) or existing_local.l_largest_file_size != str(max_file_size):
                        existing_local.l_folder_size = str(folder_size)
                        existing_local.l_largest_file_size = str(max_file_size)
                        session.add(existing_local)
                        updated_count += 1
                    continue

                # Check for a matching MEGA-only entry (exact name match, or size+scope fallback)
                existing_mega = match_local_to_cloud(session, base_path, folder_name, max_file_size)
                if existing_mega:
                    existing_mega.l_path = base_path
                    existing_mega.l_folder_name = folder_name
                    existing_mega.l_folder_size = str(folder_size)
                    existing_mega.l_largest_file_size = str(max_file_size)
                    session.add(existing_mega)
                    linked_count += 1
                    continue

                session.add(File(
                    l_path=base_path,
                    l_folder_name=folder_name,
                    l_folder_size=str(folder_size),
                    l_largest_file_size=str(max_file_size),
                ))
                new_count += 1

            # Stale-entry sweep: clear local fields for entries whose disk path no
            # longer exists (e.g. after BootlegOrganiser renames a folder).
            # Scoped to configured local_paths so offline/unmounted drives are safe.
            local_prefixes = tuple(p.rstrip(os.sep) + os.sep for p in local_paths)
            stale_count = 0
            for entry in session.query(File).filter(File.l_path != None).all():
                if not any(entry.l_path.startswith(pfx.rstrip(os.sep)) for pfx in local_prefixes):
                    continue
                full = os.path.join(entry.l_path, entry.l_folder_name or "")
                if not os.path.exists(full):
                    entry.l_path = None
                    entry.l_folder_name = None
                    entry.l_folder_size = None
                    entry.l_largest_file_size = None
                    session.add(entry)
                    stale_count += 1

            session.commit()
            print(f"Background indexing done. {new_count} new, {linked_count} linked, {updated_count} updated, {stale_count} stale cleared.")

            from utils.stats_cache import invalidate_and_refresh_async
            invalidate_and_refresh_async()

    except Exception as e:
        print(f"Error during background indexing: {e}")


def calculate_folder_size(path):
    """Return folder size in bytes, excluding OS metadata and {ne}-tagged files."""
    total_size = 0
    for dirpath, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if not _is_ignored_dir(d)]
        for filename in filenames:
            if _is_ignored_file(filename):
                continue
            fp = os.path.join(dirpath, filename)
            try:
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
            except Exception as e:
                print(f"Skipped file {fp}: {e}")
    return total_size



def calculate_folder_max_file_size(path):
    """Return the size in bytes of the largest single file, excluding metadata/ignored files."""
    max_size = 0
    for dirpath, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if not _is_ignored_dir(d)]
        for filename in filenames:
            if _is_ignored_file(filename):
                continue
            fp = os.path.join(dirpath, filename)
            try:
                if os.path.exists(fp):
                    max_size = max(max_size, os.path.getsize(fp))
            except Exception as e:
                print(f"Skipped file {fp}: {e}")
    return max_size



def collect_all_subfolders(base_paths):
    """Recursively collect all subfolders under the given paths, skipping {ne} dirs."""
    print("Collecting all subfolders...")
    all_paths = []
    for base in base_paths:
        for root, dirs, _ in os.walk(base):
            dirs[:] = [d for d in dirs if not _is_ignored_dir(d)]
            for d in dirs:
                all_paths.append(os.path.join(root, d))
    return all_paths

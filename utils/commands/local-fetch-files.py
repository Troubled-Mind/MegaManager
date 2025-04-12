import os
import json
from utils.commands.shared import extract_root_dated_folders
from models import File  # unified `files` table
from database import get_db
from utils.config import settings

def run(args=None):
    """Index folders from local paths into the files table."""
    print("📁 Starting local folder indexing...")

    local_paths = settings.get("local_paths", [])
    if isinstance(local_paths, str):
        try:
            local_paths = json.loads(local_paths)
            print(f"🔧 Converted string to list: {local_paths}")
        except Exception as e:
            print(f"❌ Failed to parse local_paths: {e}")
            return {"status": 400, "message": "local_paths must be a list or a valid JSON list string"}

    if not local_paths:
        print("⚠️ No local paths configured in settings.")
        return {"status": 400, "message": "No local paths configured."}

    print(f"📂 Scanning paths recursively: {local_paths}")
    all_subfolders = collect_all_subfolders(local_paths)
    print(f"🔍 Found {len(all_subfolders)} total subfolders")

    root_folders = extract_root_dated_folders(all_subfolders)
    if not root_folders:
        print("⚠️ No folders matching date format found.")
        return {"status": 204, "message": "No dated folders found in local paths."}

    session = next(get_db())
    new_entries = 0
    updated_entries = 0
    linked_to_mega = 0

    for full_path in root_folders:
        base_path, folder_name = os.path.split(full_path.rstrip("/"))
        folder_size = calculate_folder_size(full_path)

        # Check for existing local entry
        existing_local = session.query(File).filter_by(l_path=base_path, l_folder_name=folder_name).first()
        if existing_local:
            if existing_local.l_folder_size != str(folder_size):
                print(f"🔧 Updating size: {existing_local.l_folder_size} → {folder_size}")
                existing_local.l_folder_size = str(folder_size)
                session.add(existing_local)
                updated_entries += 1
            continue

        # Check for MEGA entry with same folder name
        existing_mega = session.query(File).filter_by(m_folder_name=folder_name).first()
        if existing_mega:
            print(f"🔗 Linking local data to MEGA file: '{folder_name}'")
            existing_mega.l_path = base_path
            existing_mega.l_folder_name = folder_name
            existing_mega.l_folder_size = str(folder_size)
            session.add(existing_mega)
            linked_to_mega += 1
            continue

        # Otherwise, insert new local-only record
        print(f"➕ New local folder: '{folder_name}' | Path: '{base_path}' | Size: {folder_size / (1024**2):.2f} MB")
        session.add(File(
            l_path=base_path,
            l_folder_name=folder_name,
            l_folder_size=str(folder_size),
        ))
        new_entries += 1

    print("📝 Committing changes...")
    try:
        session.commit()
        print(f"✅ Done. {new_entries} new, {linked_to_mega} linked to MEGA, {updated_entries} updated.")
        return {
            "status": 200,
            "message": f"{new_entries} new, {linked_to_mega} linked to MEGA, {updated_entries} updated."
        }
    except Exception as e:
        session.rollback()
        print(f"❌ Database error: {e}")
        return {"status": 500, "message": f"Failed to save: {str(e)}"}


def calculate_folder_size(path):
    """Return folder size in bytes."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            fp = os.path.join(dirpath, filename)
            try:
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
            except Exception as e:
                print(f"⚠️ Skipped file {fp}: {e}")
    return total_size


def collect_all_subfolders(base_paths):
    """Recursively collect all subfolders under the given paths."""
    print("🔄 Collecting all subfolders...")
    all_paths = []
    for base in base_paths:
        for root, dirs, _ in os.walk(base):
            for d in dirs:
                folder_path = os.path.join(root, d)
                all_paths.append(folder_path)
    return all_paths

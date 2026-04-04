import os
import json
from utils.commands.shared import extract_root_dated_folders
from models import File  # unified `files` table
from database import get_db
from utils.config import settings

import threading

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

    # Start the indexing in a background thread
    indexing_thread = threading.Thread(target=index_folders_in_background, args=(local_paths,))
    indexing_thread.start()

    return {
        "status": 200,
        "message": "Local folder indexing started in the background."
    }

def index_folders_in_background(local_paths):
    """Wait for threads and perform the indexing."""
    print("📁 Starting background local folder indexing...")
    try:
        all_subfolders = collect_all_subfolders(local_paths)
        root_folders = extract_root_dated_folders(all_subfolders)
        
        if not root_folders:
            print("⚠️ No folders matching date format found.")
            return

        with get_db() as session:
            new_count = 0
            updated_count = 0
            linked_count = 0

            for full_path in root_folders:
                base_path, folder_name = os.path.split(full_path.rstrip("/"))
                folder_size = calculate_folder_size(full_path)

                # Check for existing local entry
                existing_local = session.query(File).filter_by(l_path=base_path, l_folder_name=folder_name).first()
                if existing_local:
                    if existing_local.l_folder_size != str(folder_size):
                        existing_local.l_folder_size = str(folder_size)
                        session.add(existing_local)
                        updated_count += 1
                    continue

                # Check for MEGA entry with same folder name
                existing_mega = session.query(File).filter_by(m_folder_name=folder_name).first()
                if existing_mega:
                    existing_mega.l_path = base_path
                    existing_mega.l_folder_name = folder_name
                    existing_mega.l_folder_size = str(folder_size)
                    session.add(existing_mega)
                    linked_count += 1
                    continue

                # Otherwise, insert new local-only record
                session.add(File(
                    l_path=base_path,
                    l_folder_name=folder_name,
                    l_folder_size=str(folder_size),
                ))
                new_count += 1

            session.commit()
            print(f"✅ Background indexing done. {new_count} new, {linked_count} linked, {updated_count} updated.")

    except Exception as e:
        print(f"❌ Error during background indexing: {e}")


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

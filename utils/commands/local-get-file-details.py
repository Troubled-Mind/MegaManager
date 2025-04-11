import os
from database import get_db
from models import File

def run(args=None):
    try:
        file_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid file ID"}

    session = next(get_db())
    local_file = session.query(File).filter(File.id == file_id).first()
    if not local_file:
        return {"status": 404, "message": f"No file found with ID {file_id}"}

    if not local_file.l_path or not local_file.l_folder_name:
        return {"status": 400, "message": "This file is not a local file or is missing path/folder_name"}

    full_path = os.path.join(local_file.l_path, local_file.l_folder_name)

    if not os.path.exists(full_path):
        return {"status": 404, "message": f"Local path does not exist: {full_path}"}

    folder_size = calculate_folder_size(full_path)
    local_file.l_folder_size = str(folder_size)

    try:
        session.commit()
        print(f"📦 Updated size for {local_file.l_folder_name}: {folder_size} bytes")

        return {
            "status": 200,
            "message": f"Local file details updated for {local_file.l_folder_name}",
            "file": {
                "id": local_file.id,
                "l_path": local_file.l_path,
                "l_folder_name": local_file.l_folder_name,
                "l_folder_size": str(folder_size),
                "is_local": True,
            },
        }

    except Exception as e:
        session.rollback()
        return {"status": 500, "message": f"Database error: {str(e)}"}


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

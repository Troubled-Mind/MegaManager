# utils/commands/get-ongoing-uploads.py
import json
from database import get_db
from models import File

def run(args=None):
    try:
        session = next(get_db())
        uploads = session.query(File).filter(File.upload_status == "In Progress").all()

        ongoing_uploads = []
        for upload in uploads:
            ongoing_uploads.append({
                "file_id": upload.id,
                "file_name": upload.l_folder_name,
                "progress": upload.upload_progress,
                "upload_status": upload.upload_status,
            })

        return {
            "status": 200,
            "uploads": ongoing_uploads
        }

    except Exception as e:
        return {"status": 500, "message": f"Error fetching ongoing uploads: {str(e)}"}

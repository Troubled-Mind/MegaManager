from database import get_db
from models import File

def run(args=None):
    """
    Clears the upload status and progress for a record, effectively 
    removing it from the 'Ongoing Uploads' view.
    """
    if not args:
        return {"status": 400, "message": "Usage: file_status_clear:<file_id>"}

    try:
        file_id = int(args[0]) if isinstance(args, list) else int(args)
    except (ValueError, TypeError, IndexError):
        return {"status": 400, "message": "Invalid file ID format."}

    with get_db() as db:
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            return {"status": 404, "message": f"No file found with ID {file_id}"}
        
        file.upload_status = None
        file.upload_progress = 0
        file.upload_speed = None
        file.upload_eta = None
        
        db.commit()
        return {"status": 200, "message": f"Status cleared for file #{file_id}"}

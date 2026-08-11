from database import get_db
from models import File

def run(args=None):
    try:
        with get_db() as session:
            # Find all files that are stopped or failed
            uploads = session.query(File).filter(
                (File.upload_status == "Stopped") |
                (File.upload_status.like("Failed%"))
            ).all()

            count = 0
            for upload in uploads:
                # Reset their status so they disappear from the active dashboard
                # and can be picked up by future batch syncs
                upload.upload_status = None
                upload.upload_progress = 0
                upload.upload_speed = None
                upload.upload_eta = None
                count += 1

            if count > 0:
                session.commit()

            return {"status": 200, "message": f"Cleared {count} stopped/failed transfers from the dashboard."}
    except Exception as e:
        return {"status": 500, "message": f"Error clearing stopped transfers: {str(e)}"}

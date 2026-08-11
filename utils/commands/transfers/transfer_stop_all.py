import subprocess
from database import get_db
from models import File
from utils.config import add_transfer_log


def run(args=None):
    """
    Kills all running rclone upload processes and marks any In-Progress or Queued
    uploads as 'Stopped' in the database.
    """
    try:
        # Uploads run via "rclone copy ..." (transfer_upload.py) - match specifically on
        # that rather than bare "rclone" so unrelated rclone calls (quota checks, verify,
        # etc.) aren't killed too.
        result = subprocess.run(
            ["pkill", "-f", "rclone copy"],
            capture_output=True,
            text=True
        )
        killed = result.returncode == 0  # 0 = processes were found and killed

        stopped_count = 0
        with get_db() as db:
            from sqlalchemy import or_
            active = db.query(File).filter(
                or_(
                    File.upload_status == "In Progress",
                    File.upload_status == "Queued"
                )
            ).all()

            for f in active:
                f.upload_status = "Stopped"
                f.upload_speed = None
                f.upload_eta = None
                stopped_count += 1

            db.commit()

        msg = f"Stopped {stopped_count} upload(s)."
        add_transfer_log(f"Stop All triggered - {msg}", "ERROR")
        return {"status": 200, "message": msg, "stopped": stopped_count}

    except Exception as e:
        return {"status": 500, "message": f"Failed to stop uploads: {e}"}

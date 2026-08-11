from database import get_db
from models import Setting
from utils.config import settings
from sqlalchemy.exc import SQLAlchemyError
import json

import os

def run(args=None):
    print(f"args = {args!r} (type = {type(args).__name__})")

    if not isinstance(args, dict):
        return {"status": 400, "message": "Invalid data format"}, 400

    valid_keys = {"app_password", "megacmd_path", "rclone_path", "mega_email", "mega_passwords", "local_paths", "date_format_full", "date_format_month", "date_format_year", "login_max_attempts"}
    updates = []

    with get_db() as session:
        try:
            for key in valid_keys:
                if key in args:
                    value = args[key]
                    if key == "local_paths":
                        value = json.dumps(value)  # convert list to JSON string
                    elif key == "megacmd_path" and value:
                        clean_val = os.path.expandvars(os.path.expanduser(str(value).strip()))
                        if os.path.isfile(clean_val) or os.path.basename(clean_val).startswith("mega-cmd"):
                            clean_val = os.path.dirname(clean_val)
                        value = clean_val

                    setting = session.query(Setting).filter_by(key=key).first()
                    if setting:
                        setting.value = value
                    else:
                        setting = Setting(key=key, value=value)
                        session.add(setting)

                    updates.append(key)

            session.commit()

        except SQLAlchemyError as e:
            session.rollback()
            return {"status": 500, "message": f"Database error: {str(e)}"}, 500

    settings.load()
    if "local_paths" in updates:
        try:
            from utils.commands.files.file_local_index import run as run_local_index
            run_local_index()
        except Exception as e:
            print(f"Auto-index trigger failed: {e}")

    return {
        "status": 200,
        "message": "Settings saved."
    }, 200

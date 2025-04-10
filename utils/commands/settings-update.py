from database import get_db
from models import Setting
from utils.config import settings
from sqlalchemy.exc import SQLAlchemyError
import json

def run(args=None):
    print(f"📥 args = {args!r} (type = {type(args).__name__})")

    if not isinstance(args, dict):
        return {"status": 400, "message": "Invalid data format"}, 400

    valid_keys = {"app_password", "megacmd_path", "mega_email", "mega_passwords", "local_paths", "date_format_full", "date_format_month", "date_format_year"}
    updates = []

    session = next(get_db())

    try:
        for key in valid_keys:
            if key in args:
                value = args[key]
                if key == "local_paths":
                    value = json.dumps(value)  # convert list to JSON string

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
    finally:
        settings.load()
        session.close()

    return {
        "status": 200,
        "message": f"Updated settings: {', '.join(updates)}"
    }, 200

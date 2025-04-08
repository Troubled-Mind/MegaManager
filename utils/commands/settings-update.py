from models import Setting
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

engine = create_engine("sqlite:///database.db")
Session = sessionmaker(bind=engine)

def run(args=None):
    print(f"📥 args = {args!r} (type = {type(args).__name__})")

    if not isinstance(args, dict):
        return {"status": 400, "message": "Invalid data format"}, 400

    valid_keys = {"app_password", "megacmd_path", "mega_email", "mega_passwords"}
    updates = []

    session = Session()

    try:
        for key in valid_keys:
            if key in args:
                setting = session.query(Setting).filter_by(key=key).first()
                if setting:
                    setting.value = args[key]
                else:
                    setting = Setting(key=key, value=args[key])
                    session.add(setting)
                updates.append(key)

        session.commit()

    except SQLAlchemyError as e:
        session.rollback()
        return {"status": 500, "message": f"Database error: {str(e)}"}, 500
    finally:
        session.close()

    return {
        "status": 200,
        "message": f"Updated settings: {', '.join(updates)}"
    }, 200

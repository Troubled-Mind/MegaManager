from database import get_db
from models import File, MegaAccount

def run(args=None):
    try:
        file_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid file ID"}

    session = next(get_db())

    file = session.query(File).filter(File.id == file_id).first()
    if not file or not file.l_folder_size:
        return {"status": 404, "message": "Local file not found or missing size"}

    try:
        file_size = int(file.l_folder_size)
    except ValueError:
        return {"status": 500, "message": "Invalid file size"}

    eligible_accounts = []

    accounts = session.query(MegaAccount).all()
    for account in accounts:
        if account.total_quota is None or account.used_quota is None:
            continue

        available = int(account.total_quota) - int(account.used_quota)
        if available > file_size:
            eligible_accounts.append({
                "id": account.id,
                "email": account.email,
                "available": available
            })

    return {
        "status": 200,
        "accounts": eligible_accounts
    }

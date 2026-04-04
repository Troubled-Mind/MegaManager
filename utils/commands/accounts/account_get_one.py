from database import get_db
from models import MegaAccount, File

def run(args=None):
    try:
        account_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}

    with get_db() as session:
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        
        if not account:
            return {"status": 404, "message": f"No account found with ID {account_id}"}
        
        # Count linked files
        file_count = session.query(File).filter(File.m_account_id == account_id).count()

        return {
            "status": 200,
            "account": {
                "id": account.id,
                "email": account.email,
                "password": account.password,
                "is_pro": bool(account.is_pro_account),
                "used_quota": int(account.used_quota) if account.used_quota else 0,
                "total_quota": int(account.total_quota) if account.total_quota else 0,
                "last_login": account.last_login.isoformat() if account.last_login else "",
                "linked_files": file_count,
                "status": account.status
            }
        }

from database import get_db
from models import MegaAccount

def run(args=None):
    with get_db() as session:
        accounts_data = session.query(MegaAccount).all()
        
        accounts = []
        for acc in accounts_data:
            accounts.append({
                "id": acc.id,
                "email": acc.email,
                "password": acc.password,
                "is_pro": bool(acc.is_pro_account),
                "used_quota": int(acc.used_quota) if acc.used_quota else 0,
                "total_quota": int(acc.total_quota) if acc.total_quota else 0,
                "last_login": acc.last_login.isoformat() if acc.last_login else "",
                "status": acc.status
            })

        return {"status": 200, "accounts": accounts}

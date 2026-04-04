from database import get_db
from models import MegaAccount

def run(args=None):
    """
    Returns a list of MEGA accounts with 'Pending Verification' status.
    """
    try:
        with get_db() as session:
            pending = session.query(MegaAccount).filter(MegaAccount.status == "Pending Verification").all()
            
            result_list = []
            for acc in pending:
                result_list.append({
                    "id": acc.id,
                    "email": acc.email,
                    "status": acc.status,
                    "created_at": acc.storage_quota_updated.isoformat() if acc.storage_quota_updated else None
                })
            
            return {
                "status": 200,
                "accounts": result_list
            }
    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}

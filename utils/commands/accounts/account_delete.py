from database import get_db
from models import MegaAccount

def run(args=None):
    try:
        account_id = int(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid account ID"}

    with get_db() as session:
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        
        if not account:
            return {"status": 404, "message": f"No account found with ID {account_id}"}
        
        session.delete(account)
        session.commit()

        return {"status": 200, "message": f"Account {account_id} deleted successfully"}

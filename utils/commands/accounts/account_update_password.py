import json
from database import get_db
from models import MegaAccount

def run(args=None):
    """Update the password for a MEGA account in the database.
    
    This is useful when the user manually changed their password on MEGA's website
    and needs to sync it with the local database.
    
    Args format: "account_id:new_password"
    """
    if not args or ":" not in args:
        return {
            "status": 400,
            "message": "Invalid args. Expected format: account_id:new_password"
        }
    
    try:
        account_id, new_password = args.split(":", 1)
        account_id = int(account_id)
    except ValueError:
        return {
            "status": 400,
            "message": "Invalid account_id. Must be an integer."
        }
    
    if not new_password or not new_password.strip():
        return {
            "status": 400,
            "message": "Password cannot be empty."
        }
    
    with get_db() as session:
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        
        if not account:
            return {
                "status": 404,
                "message": f"Account with ID {account_id} not found."
            }
        
        old_email = account.email
        account.password = new_password.strip()
        session.add(account)
        session.commit()
        
        print(f"Updated password for account {old_email} (ID: {account_id})")
        
        return {
            "status": 200,
            "message": f"Password updated successfully for {old_email}",
            "data": {
                "account_id": account_id,
                "email": old_email
            }
        }

import subprocess
from datetime import datetime
from database import get_db
from models import MegaAccount
from utils.config import cmd
from utils.rclone_config import get_account_quota, add_or_update_account

def run(args=None):
    """Empty trash folder and refresh quota for an account.
    
    Files in MEGA's trash/rubbish bin still count toward quota.
    This empties the trash and updates the quota values.
    
    Args: account_id
    """
    if not args:
        return {"status": 400, "message": "Missing account_id"}
    
    try:
        account_id = int(args)
    except ValueError:
        return {"status": 400, "message": "Invalid account_id"}
    
    with get_db() as session:
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        
        if not account:
            return {"status": 404, "message": f"Account {account_id} not found"}
        
        email = account.email
        password = account.password
        
        try:
            from utils.mega_session import mega_session
            with mega_session(email, password) as logged_in:
                if not logged_in:
                    return {"status": 500, "message": f"Login failed for {email}"}
                
                # Check trash size before emptying
                print(f"INFO Checking trash size for {email}...")
                trash_before = subprocess.run(
                    [cmd("mega-du"), "//bin"],
                    capture_output=True, text=True, timeout=10
                )
                
                # Empty the trash
                print(f"INFO Emptying trash for {email}...")
                empty_result = subprocess.run(
                    [cmd("mega-rm"), "-rf", "//bin/*"],
                    capture_output=True, text=True, timeout=60
                )
                
                if empty_result.returncode != 0:
                    return {
                        "status": 500,
                        "message": f"Failed to empty trash: {empty_result.stderr}"
                    }
                
                # Wait a moment for MEGA to update
                import time
                time.sleep(2)
                
                # Refresh quota via rclone
                print(f"INFO Refreshing quota for {email}...")
                add_or_update_account(account_id, email, password)
                r_used, r_total = get_account_quota(account_id)
                
                if r_used is not None and r_total is not None:
                    now = datetime.utcnow()
                    account.used_quota = str(r_used)
                    account.total_quota = str(r_total)
                    account.storage_quota_updated = now
                    session.commit()
                    
                    free_space = max(0, r_total - r_used)
                    
                    return {
                        "status": 200,
                        "message": f"Trash emptied and quota refreshed for {email}",
                        "data": {
                            "trash_before": trash_before.stdout.strip(),
                            "used_quota": r_used,
                            "total_quota": r_total,
                            "free_space": free_space,
                            "free_space_gb": round(free_space / (1024**3), 2)
                        }
                    }
                else:
                    return {
                        "status": 500,
                        "message": "Trash emptied but quota refresh failed"
                    }
                
        except Exception as e:
            return {"status": 500, "message": f"Error: {str(e)}"}

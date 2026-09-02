import json
import subprocess
from database import get_db
from models import MegaAccount
from utils.rclone_config import rclone_cmd, RCLONE_CONF_PATH, _section_name
from utils.config import cmd

def run(args=None):
    """Debug quota discrepancy - shows raw values from multiple sources.
    
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
        db_used = account.used_quota or "0"
        db_total = account.total_quota or "0"
        
        # Get quota from rclone
        section = _section_name(account_id)
        rclone_data = {}
        try:
            result = subprocess.run(
                [rclone_cmd(), "about", "--config", RCLONE_CONF_PATH,
                 f"{section}:", "--json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                rclone_data = json.loads(result.stdout)
        except Exception as e:
            rclone_data = {"error": str(e)}
        
        # Get quota from MEGAcmd
        mega_data = {}
        try:
            from utils.mega_session import mega_session
            with mega_session(email, password) as logged_in:
                if logged_in:
                    whoami_result = subprocess.run(
                        [cmd("mega-whoami"), "-l"],
                        capture_output=True, text=True, timeout=10
                    )
                    mega_data["whoami_output"] = whoami_result.stdout
                    
                    # Check trash
                    trash_result = subprocess.run(
                        [cmd("mega-du"), "//bin"],
                        capture_output=True, text=True, timeout=10
                    )
                    mega_data["trash_size"] = trash_result.stdout.strip()
                else:
                    mega_data["error"] = "Login failed"
        except Exception as e:
            mega_data["error"] = str(e)
        
        return {
            "status": 200,
            "message": "Quota debug info",
            "data": {
                "account_id": account_id,
                "email": email,
                "database": {
                    "used_quota": db_used,
                    "total_quota": db_total,
                    "free_space": str(max(0, int(db_total) - int(db_used))),
                    "updated_at": str(account.storage_quota_updated)
                },
                "rclone": {
                    "used": rclone_data.get("used", "N/A"),
                    "total": rclone_data.get("total", "N/A"),
                    "free": rclone_data.get("free", "N/A"),
                    "trashed": rclone_data.get("trashed", "N/A"),
                    "raw": rclone_data
                },
                "megacmd": mega_data,
                "diagnosis": generate_diagnosis(db_used, db_total, rclone_data, mega_data)
            }
        }

def generate_diagnosis(db_used, db_total, rclone_data, mega_data):
    """Generate diagnostic suggestions."""
    issues = []
    
    rclone_used = rclone_data.get("used", 0)
    rclone_total = rclone_data.get("total", 0)
    rclone_trashed = rclone_data.get("trashed", 0)
    
    if rclone_trashed and rclone_trashed > 0:
        issues.append(f"⚠️ Trash folder contains {format_bytes(rclone_trashed)} - this counts toward quota!")
    
    if int(db_used) != rclone_used or int(db_total) != rclone_total:
        issues.append("🔄 Database values don't match rclone - try refreshing the account")
    
    if rclone_data.get("error"):
        issues.append(f"❌ Rclone error: {rclone_data['error']}")
    
    if mega_data.get("error"):
        issues.append(f"❌ MEGAcmd error: {mega_data['error']}")
    
    if not issues:
        issues.append("✅ All sources agree - values are current")
    
    return issues

def format_bytes(bytes_val):
    """Format bytes to human readable."""
    try:
        bytes_val = int(bytes_val)
    except:
        return str(bytes_val)
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"

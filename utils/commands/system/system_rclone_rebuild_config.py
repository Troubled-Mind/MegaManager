"""
Rebuild the rclone.conf from all accounts in the database.
Called from the settings UI "Sync Config" button.
"""
from utils.rclone_config import rebuild_all_accounts, RCLONE_CONF_PATH

def run(args=None):
    try:
        rebuild_all_accounts()
        return {
            "status": 200,
            "message": f"rclone config rebuilt successfully {RCLONE_CONF_PATH}"
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"Failed to rebuild rclone config: {str(e)}"
        }

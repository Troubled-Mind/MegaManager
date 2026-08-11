"""
Verify rclone is installed and working.
"""
import subprocess
from utils.rclone_config import rclone_cmd, RCLONE_CONF_PATH
import os

def run(args=None):
    binary = rclone_cmd()
    try:
        result = subprocess.run(
            [binary, "version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unknown"
            return {
                "status": 200,
                "valid": True,
                "version": version_line,
                "binary": binary,
                "conf_path": RCLONE_CONF_PATH,
                "conf_exists": os.path.exists(RCLONE_CONF_PATH),
                "message": f"rclone is working: {version_line}"
            }
        else:
            return {
                "status": 200,
                "valid": False,
                "binary": binary,
                "message": result.stderr.strip() or "rclone returned a non-zero exit code."
            }
    except FileNotFoundError:
        return {
            "status": 200,
            "valid": False,
            "binary": binary,
            "message": f"rclone not found at '{binary}'. Please install it or set the path."
        }
    except Exception as e:
        return {
            "status": 200,
            "valid": False,
            "binary": binary,
            "message": str(e)
        }

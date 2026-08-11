"""
Auto-discover rclone binary path across common install locations.
"""
import subprocess
import shutil
import os

COMMON_PATHS = [
    "/usr/bin/rclone",
    "/usr/local/bin/rclone",
    "/snap/bin/rclone",
    "/opt/homebrew/bin/rclone",           # macOS ARM
    "/usr/local/Cellar/rclone/*/bin/rclone",  # macOS Intel (Homebrew)
    os.path.expanduser("~/.local/bin/rclone"),
    os.path.expanduser("~/bin/rclone"),
]

def run(args=None):
    # 1. Try shutil.which (searches system PATH)
    found = shutil.which("rclone")
    if found and _is_valid(found):
        return {"status": 200, "found": True, "path": found, "method": "PATH"}

    # 2. Try known locations
    import glob
    for pattern in COMMON_PATHS:
        for path in glob.glob(pattern):
            if _is_valid(path):
                return {"status": 200, "found": True, "path": path, "method": "known_location"}

    return {
        "status": 200,
        "found": False,
        "path": None,
        "message": "rclone not found. Visit https://rclone.org/downloads/ to install."
    }


def _is_valid(path):
    try:
        r = subprocess.run([path, "version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False

import os
import random
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

import collections
from datetime import datetime

from database import get_db
from models import Setting

USE_KAREN_LOGO = random.randint(1, 20) == 1

_transfer_logs = collections.deque(maxlen=250)

def add_transfer_log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {
        "time": timestamp,
        "level": str(level).upper(),
        "message": str(message).strip()
    }
    _transfer_logs.append(entry)

def get_transfer_logs(limit=80):
    return list(_transfer_logs)[-limit:]

def clear_transfer_logs():
    _transfer_logs.clear()

state = {
    "authenticated": False,
    "booting": True,
    "uploads_active": False,
    "batch_calculating": False,
    "batch_status": "",
    "login_attempts": 0,
    "login_locked": False,
    "update_applied": False,
    "update_version": None,
}

class Settings:
    def __init__(self):
        self._values = {}
        self.load()

    def load(self):
        try:
            with get_db() as session:
                self._values = {
                    setting.key: setting.value for setting in session.query(Setting).all()
                }
        except Exception:
            pass

    def get(self, key, default=None):
        return self._values.get(key, default)

    def __getitem__(self, key):
        return self._values.get(key)

    def __contains__(self, key):
        return key in self._values


settings = Settings()

# Resolve executable paths
def cmd(name):
    suffix = ".bat" if os.name == "nt" else ""
    target_binary = name + suffix
    base_path = settings.get("megacmd_path")
    if not base_path:
        return target_binary

    base_path = os.path.expandvars(os.path.expanduser(str(base_path).strip()))
    if os.path.isfile(base_path) or os.path.basename(base_path).startswith("mega-cmd"):
        dir_path = os.path.dirname(base_path)
    else:
        dir_path = base_path

    return os.path.join(dir_path, target_binary)

import re

def _parse_version(v_str):
    try:
        parts = [int(p) for p in re.findall(r'\d+', str(v_str))]
        return tuple(parts) if parts else (0,)
    except Exception:
        return (0,)

def check_for_update():
    local_version_path = "version"
    remote_version_url = "https://raw.githubusercontent.com/Troubled-Mind/MegaManager/refs/heads/main/version"

    try:
        if not os.path.exists(local_version_path):
            return
        with open(local_version_path, "r") as f:
            local_version = f.read().strip()

        req = urllib.request.Request(
            remote_version_url,
            headers={"User-Agent": f"MegaManager/{local_version}"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            remote_version = response.read().decode("utf-8").strip()

        if _parse_version(remote_version) > _parse_version(local_version):
            print(f"\nUPDATE A new version is available: {remote_version} (current: {local_version})")
            print("INFO Updating from GitHub...")

            repo_url = "https://github.com/Troubled-Mind/MegaManager"
            zip_url = f"{repo_url}/archive/refs/heads/main.zip"

            try:
                zip_req = urllib.request.Request(
                    zip_url,
                    headers={"User-Agent": f"MegaManager/{local_version}"}
                )
                with urllib.request.urlopen(zip_req, timeout=15) as response:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_zip:
                        tmp_zip.write(response.read())
                        zip_path = tmp_zip.name

                with tempfile.TemporaryDirectory() as tmp_dir:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(tmp_dir)

                    subdirs = [os.path.join(tmp_dir, d) for d in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, d))]
                    extracted_path = subdirs[0] if subdirs else tmp_dir

                    skip = {".git", "database.db", "rclone.conf"}
                    for item in os.listdir(extracted_path):
                        if item in skip:
                            continue
                        s = os.path.join(extracted_path, item)
                        d = os.path.join(os.getcwd(), item)

                        if os.path.isdir(s):
                            if os.path.exists(d):
                                shutil.rmtree(d)
                            shutil.copytree(s, d)
                        else:
                            shutil.copy2(s, d)

                if os.path.exists(zip_path):
                    os.remove(zip_path)

                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                        capture_output=True, text=True, timeout=120, check=True
                    )
                except Exception as pip_err:
                    print(f"WARNING Dependency install after update failed: {pip_err}")

                state["update_applied"] = True
                state["update_version"] = remote_version
                print("DONE Update complete! Please restart the application.\n")
            except Exception as e:
                print(f"ERROR Update failed: {e}")

    except Exception as e:
        local_version = "unknown"
        if os.path.exists(local_version_path):
            with open(local_version_path, "r") as f:
                local_version = f.read().strip()
        print(f"\nWARNING Unable to check for updates: {e}")
        print(f"INFO Local version: {local_version}\n")
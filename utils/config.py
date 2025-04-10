import os
import random

import urllib
from database import get_db
from models import Setting

USE_KAREN_LOGO = random.randint(1, 20) == 1

state = {
    "authenticated": False
}

class Settings:
    def __init__(self):
        self._values = {}

    def load(self):
        session = next(get_db())
        try:
            self._values = {
                setting.key: setting.value for setting in session.query(Setting).all()
            }
        finally:
            session.close()

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
    base_path = settings.get("megacmd_path")
    return os.path.join(base_path, name + suffix) if base_path else name
    
def check_for_update():
    local_version_path = "version"
    remote_version_url = "https://raw.githubusercontent.com/Troubled-Mind/MegaManager/refs/heads/main/version"

    try:
        if not os.path.exists(local_version_path):
            return
        with open(local_version_path, "r") as f:
            local_version = f.read().strip()

        with urllib.request.urlopen(remote_version_url, timeout=5) as response:
            remote_version = response.read().decode("utf-8").strip()

        if remote_version > local_version:
            print(f"\n🚨 A new version is available: {remote_version} (current: {local_version})")
            print("👉 Visit https://github.com/Troubled-Mind/MegaManager to update.\n")

    except Exception:
        local_version = "unknown"
        if os.path.exists(local_version_path):
            with open(local_version_path, "r") as f:
                local_version = f.read().strip()
        print(f"\n⚠️   Unable to check for updates. Please check your internet connection or try again later.")
        print(f"🔎  Local version: {local_version}\n")
        pass  # Silently fail if unreachable
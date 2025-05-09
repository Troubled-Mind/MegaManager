import os
import random
import shutil
import tempfile
import urllib.request
import zipfile

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
            print("👉 Updating from GitHub...")
            
            repo_url = "https://github.com/Troubled-Mind/MegaManager"
            zip_url = f"{repo_url}/archive/refs/heads/main.zip"

            try:
                with urllib.request.urlopen(zip_url) as response:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_zip:
                        tmp_zip.write(response.read())
                        zip_path = tmp_zip.name

                with tempfile.TemporaryDirectory() as tmp_dir:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(tmp_dir)

                    extracted_path = os.path.join(tmp_dir, "MegaManager-main")

                    for item in os.listdir(extracted_path):
                        s = os.path.join(extracted_path, item)
                        d = os.path.join(os.getcwd(), item)

                        if os.path.isdir(s):
                            if os.path.exists(d):
                                shutil.rmtree(d)
                            shutil.copytree(s, d)
                        else:
                            shutil.copy2(s, d)

                os.remove(zip_path)
                print("✅ Update complete! Please restart the application.\n")
            except Exception as e:
                print(f"❌ Update failed: {e}")

    except Exception as e:
        print(e)
        local_version = "unknown"
        if os.path.exists(local_version_path):
            with open(local_version_path, "r") as f:
                local_version = f.read().strip()
        print(f"\n⚠️   Unable to check for updates. Please check your internet connection or try again later.")
        print(f"🔎  Local version: {local_version}\n")
        pass  
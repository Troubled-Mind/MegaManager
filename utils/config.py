import random
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
    
    def get_megacmd_path(self):
        return self.get("megacmd_path") or ""

    def __getitem__(self, key):
        return self._values.get(key)

    def __contains__(self, key):
        return key in self._values

settings = Settings()

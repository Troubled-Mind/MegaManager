import random
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Setting

USE_KAREN_LOGO = random.randint(1, 20) == 1

engine = create_engine("sqlite:///database.db")
Session = sessionmaker(bind=engine)

state = {
    "authenticated": False
}

class Settings:
    def __init__(self):
        self._values = {}
        self.load()

    def load(self):
        session = Session()
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

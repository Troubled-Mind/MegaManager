from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from models import Base

DB_FILE = "database.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600
)

LocalSession = sessionmaker(bind=engine)

def create_database():
    Base.metadata.create_all(engine)

    from sqlalchemy import inspect, text
    inspector = inspect(engine)

    if inspector.has_table('files'):
        file_columns = [col['name'] for col in inspector.get_columns('files')]
        with engine.connect() as conn:
            if 'upload_speed' not in file_columns:
                print("INFO Migrating database: adding files.upload_speed")
                conn.execute(text("ALTER TABLE files ADD COLUMN upload_speed TEXT"))
                conn.commit()
            if 'upload_eta' not in file_columns:
                print("INFO Migrating database: adding files.upload_eta")
                conn.execute(text("ALTER TABLE files ADD COLUMN upload_eta TEXT"))
                conn.commit()
            if 'l_largest_file_size' not in file_columns:
                print("INFO Migrating database: adding files.l_largest_file_size")
                conn.execute(text("ALTER TABLE files ADD COLUMN l_largest_file_size TEXT"))
                conn.commit()

    if inspector.has_table('mega_accounts'):
        acc_columns = [col['name'] for col in inspector.get_columns('mega_accounts')]
        with engine.connect() as conn:
            if 'status' not in acc_columns:
                print("INFO Migrating database: adding mega_accounts.status")
                conn.execute(text("ALTER TABLE mega_accounts ADD COLUMN status TEXT DEFAULT 'Active'"))
                conn.commit()

create_database()

import contextlib

@contextlib.contextmanager
def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()

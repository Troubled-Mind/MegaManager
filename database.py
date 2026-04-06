from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from models import Base

DB_FILE = "database.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Create the SQLAlchemy engine with increased pool settings
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
    # Create the database file from the models if it doesn't exist
    if not os.path.exists(DB_FILE):
        Base.metadata.create_all(engine)
    else:
        # Check for missing columns and migrate if necessary
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        
        # Files table migrations
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
                
        # Mega accounts migrations
        acc_columns = [col['name'] for col in inspector.get_columns('mega_accounts')]
        with engine.connect() as conn:
            if 'status' not in acc_columns:
                print("INFO Migrating database: adding mega_accounts.status")
                conn.execute(text("ALTER TABLE mega_accounts ADD COLUMN status TEXT DEFAULT 'Active'"))
                conn.commit()

import contextlib

@contextlib.contextmanager
def get_db():
    # Get a new database session
    db = LocalSession()
    try:
        yield db
    finally:
        # Close the session when done
        db.close()

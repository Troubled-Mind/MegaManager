import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

DB_FILE = "database.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Create the SQLAlchemy engine + a session factory
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
LocalSession = sessionmaker(bind=engine)

def create_database():    
    # Create the database file from the models if it doesn't exist
    if not os.path.exists(DB_FILE):
        Base.metadata.create_all(engine)

def get_db():
    # Get a new database session
    db = LocalSession()
    try:
        yield db
    finally:
        # Close the session when done
        db.close()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

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

def get_db():
    # Get a new database session
    db = LocalSession()
    try:
        yield db
    finally:
        # Close the session when done
        db.close()

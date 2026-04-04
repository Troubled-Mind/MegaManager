import pytest
import sqlite3
import os
from database import get_db
from models import MegaAccount, File, Setting

def test_database_connection():
    """Verify that the database engine initialises and tables exist."""
    with get_db() as session:
        # Check if we can query the tables
        accounts = session.query(MegaAccount).all()
        assert isinstance(accounts, list)

def test_account_creation():
    """Test creating and deleting a MEGA account in the DB."""
    with get_db() as session:
        new_acc = MegaAccount(email="test@example.com", password="password123")
        session.add(new_acc)
        session.commit()
        
        saved_acc = session.query(MegaAccount).filter(MegaAccount.email == "test@example.com").first()
        assert saved_acc is not None
        assert saved_acc.password == "password123"
        
        session.delete(saved_acc)
        session.commit()
        
        deleted_acc = session.query(MegaAccount).filter(MegaAccount.email == "test@example.com").first()
        assert deleted_acc is None

def test_file_mapping():
    """Test the file-to-account relationship."""
    with get_db() as session:
        acc = MegaAccount(email="filetest@example.com", password="abc")
        session.add(acc)
        session.commit()
        
        file1 = File(l_folder_name="Folder1", m_path="/Cloud1", account=acc)
        session.add(file1)
        session.commit()
        
        assert len(acc.files) == 1
        assert acc.files[0].l_folder_name == "Folder1"
        
        session.delete(file1)
        session.delete(acc)
        session.commit()

def test_settings_storage():
    """Test application settings CRUD."""
    with get_db() as session:
        s = Setting(key="test_key", value="test_value")
        session.add(s)
        session.commit()
        
        saved_s = session.query(Setting).filter(Setting.key == "test_key").first()
        assert saved_s.value == "test_value"
        
        session.delete(saved_s)
        session.commit()

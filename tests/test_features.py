import pytest
from unittest.mock import patch, MagicMock
from utils.commands.accounts.account_get_all import run as get_all_accounts
from utils.commands.files.file_db_fetch import run as get_db_files
from utils.commands.transfers.transfer_status import run as get_transfer_status
from models import MegaAccount, File

@pytest.fixture
def mock_db():
    with patch('utils.commands.accounts.account_get_all.get_db') as mock_all:
        yield mock_all

def test_account_get_all_logic(mock_db):
    """Verify that account_get_all processes DB rows correctly."""
    session = MagicMock()
    mock_db.return_value.__enter__.return_value = session
    
    # Mock some accounts
    acc1 = MegaAccount(id=1, email="a@b.com", password="p", used_quota="100", total_quota="500")
    acc2 = MegaAccount(id=2, email="c@d.com", password="q", used_quota="0", total_quota="0")
    session.query.return_value.all.return_value = [acc1, acc2]
    
    result = get_all_accounts()
    assert result["status"] == 200
    assert len(result["accounts"]) == 2
    assert result["accounts"][0]["email"] == "a@b.com"

def test_file_db_fetch_logic():
    """Verify that file_db_fetch processes files correctly."""
    with patch('utils.commands.files.file_db_fetch.get_db') as mock_db:
        session = MagicMock()
        mock_db.return_value.__enter__.return_value = session
        
        f1 = File(id=10, l_folder_name="Local1", m_path="/Cloud1")
        session.query.return_value.all.return_value = [f1]
        
        result = get_db_files()
        assert result["status"] == 200
        assert len(result["files"]) == 1
        assert result["files"][0]["id"] == 10

def test_transfer_status_logic():
    """Verify that transfer_status filters by 'In Progress'."""
    with patch('utils.commands.transfers.transfer_status.get_db') as mock_db:
        session = MagicMock()
        mock_db.return_value.__enter__.return_value = session
        
        up1 = File(id=20, l_folder_name="UploadingNow", upload_status="In Progress", upload_progress=45)
        session.query.return_value.filter.return_value.all.return_value = [up1]
        
        result = get_transfer_status()
        assert result["status"] == 200
        assert len(result["uploads"]) == 1
        assert result["uploads"][0]["progress"] == 45

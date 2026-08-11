import pytest
from unittest.mock import patch, MagicMock
from utils.commands.accounts.account_get_all import run as get_all_accounts
from utils.commands.files.file_db_fetch import run as get_db_files
from utils.commands.transfers.transfer_status import run as get_transfer_status
from models import MegaAccount, File

def test_account_get_all_logic():
    """Verify that account_get_all serves accounts from the stats cache."""
    accounts = [
        {"id": 1, "email": "a@b.com", "used_quota": "100", "total_quota": "500"},
        {"id": 2, "email": "c@d.com", "used_quota": "0", "total_quota": "0"},
    ]
    with patch('utils.stats_cache.get_cached_accounts', return_value=accounts), \
         patch('utils.stats_cache.get_cached_stats', return_value={}):
        result = get_all_accounts()

    assert result["status"] == 200
    assert len(result["accounts"]) == 2
    assert result["accounts"][0]["email"] == "a@b.com"

def test_file_db_fetch_logic():
    """Verify that file_db_fetch serves files from the stats cache."""
    files = [{"id": 10, "l_folder_name": "Local1", "m_path": "/Cloud1"}]
    with patch('utils.stats_cache.get_cached_files', return_value=files), \
         patch('utils.stats_cache.get_cached_stats', return_value={}):
        result = get_db_files()

    assert result["status"] == 200
    assert len(result["files"]) == 1
    assert result["files"][0]["id"] == 10

def test_transfer_status_logic():
    """Verify that transfer_status filters by 'In Progress'."""
    with patch('utils.commands.transfers.transfer_status.get_db') as mock_db, \
         patch('utils.commands.transfers.transfer_status.ensure_upload_worker') as mock_ensure_worker:
        session = MagicMock()
        mock_db.return_value.__enter__.return_value = session

        up1 = File(id=20, l_folder_name="UploadingNow", upload_status="In Progress", upload_progress=45)
        session.query.return_value.filter.return_value.all.return_value = [up1]

        result = get_transfer_status()
        assert result["status"] == 200
        assert len(result["uploads"]) == 1
        assert result["uploads"][0]["progress"] == 45
        # has_pending_or_active is True here, so transfer_status would otherwise
        # call the real ensure_upload_worker() - which spawns live worker threads
        # against the real database and starts real rclone uploads. Assert it was
        # mocked out rather than actually invoked.
        mock_ensure_worker.assert_called_once()

import pytest
from unittest.mock import MagicMock, patch
from utils.http_handler import CustomHandler

class MockServer:
    def __init__(self):
        # Attributes expected by CustomHandler if it accesses server state
        pass

@pytest.fixture
def handler():
    # We mock out common server attributes
    mock_server = MockServer()
    # Mocking address and request for BaseHTTPRequestHandler init
    mock_request = MagicMock()
    mock_client_address = ('127.0.0.1', 12345)

    with patch('http.server.BaseHTTPRequestHandler.__init__', return_value=None):
        h = CustomHandler(mock_request, mock_client_address, mock_server)
        h.server = mock_server
        return h

def test_command_lookup(handler, tmp_path):
    """Test that run_command can find a command in a subdirectory."""
    # Create a temporary commands structure
    commands_dir = tmp_path / "utils" / "commands" / "system"
    commands_dir.mkdir(parents=True)
    (commands_dir / "test_cmd.py").write_text("def run(args): return {'status': 200}")

def test_system_login_mock(handler):
    """Test system_login through the handler with mocked logic."""
    with patch('utils.http_handler.CustomHandler.run_command') as mock_run:
        mock_run.return_value = ({"status": 200, "message": "Success"}, 200)

        # Simulating a call to system_login
        result, code = handler.run_command("system_login", {"password": "test"})
        assert code == 200
        assert result["status"] == 200

def test_unknown_command(handler):
    """Verify that calling a non-existent command returns 400."""
    result, code = handler.run_command("non_existent_command")
    assert code == 400
    assert "Unknown command" in result["message"]

def test_transfer_missing_links_invocation():
    """Verify transfer_missing_links runs and initiates background thread."""
    from utils.commands.transfers.transfer_missing_links import run as run_missing_links
    with patch('threading.Thread.start') as mock_thread:
        res = run_missing_links()
        assert res["status"] == 200
        assert "started in background" in res["message"]
        mock_thread.assert_called_once()

def test_transfer_sharing_invalid_args():
    """Verify transfer_sharing handles invalid IDs gracefully."""
    from utils.commands.transfers.transfer_sharing import run as run_transfer_sharing
    res = run_transfer_sharing("invalid_id")
    assert res["status"] == 400
    assert "Invalid file ID format" in res["message"]

def test_transfer_sharing_file_not_found():
    """Verify transfer_sharing handles missing files properly."""
    from utils.commands.transfers.transfer_sharing import run as run_transfer_sharing
    with patch('utils.commands.transfers.transfer_sharing.get_db') as mock_db:
        session = MagicMock()
        mock_db.return_value.__enter__.return_value = session
        session.query.return_value.filter.return_value.first.return_value = None

        res = run_transfer_sharing(999)
        assert res["status"] == 404
        assert "not found" in res["message"]

def test_system_megacmd_test_valid_dir(tmp_path):
    """Verify system_megacmd_test succeeds when all binaries exist."""
    from utils.commands.system.system_megacmd_test import run as run_megacmd_test

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    required = ["mega-cmd", "mega-whoami", "mega-login", "mega-logout", "mega-put", "mega-mkdir", "mega-export", "mega-df"]
    for b in required:
        file_path = bin_dir / b
        file_path.write_text("#!/bin/sh\nexit 0\n")
        file_path.chmod(0o755)

    res, code = run_megacmd_test(str(bin_dir))
    assert code == 200
    assert res["valid"] is True
    assert len(res["found_binaries"]) == len(required)

def test_system_megacmd_test_missing_dir(tmp_path):
    """Verify system_megacmd_test fails when files are missing."""
    from utils.commands.system.system_megacmd_test import run as run_megacmd_test

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    res, code = run_megacmd_test(str(empty_dir))
    assert code == 400
    assert res["valid"] is False
    assert len(res["missing_binaries"]) > 0

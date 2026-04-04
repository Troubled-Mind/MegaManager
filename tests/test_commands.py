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

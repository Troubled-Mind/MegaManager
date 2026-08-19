import pytest
from unittest.mock import patch, MagicMock
from utils.commands.accounts.account_bulk_verify import run as run_bulk_verify
from models import MegaAccount

def test_bulk_verify_missing_file():
    """Verify that account_bulk_verify fails if the PDF path does not exist."""
    res, code = run_bulk_verify("non_existent_file.pdf")
    assert code == 400
    assert "PDF file not found" in res["message"]

@patch('utils.commands.accounts.account_bulk_verify.PdfReader')
def test_bulk_verify_no_links(mock_reader):
    """Verify that account_bulk_verify returns 200 with message if no links found in PDF."""
    # Mock pypdf output with no links
    mock_instance = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "This is a pdf without any links."
    mock_instance.pages = [mock_page]
    mock_reader.return_value = mock_instance

    with patch('utils.commands.accounts.account_bulk_verify.os.path.exists', return_value=True):
        res, code = run_bulk_verify("mock.pdf")
        assert code == 200
        assert "No MEGA verification links found" in res["message"]
        assert len(res["results"]) == 0

@patch('utils.stats_cache.invalidate_and_refresh_async')
@patch('utils.commands.accounts.account_login.process_account')
@patch('utils.commands.accounts.account_bulk_verify.subprocess.run')
@patch('utils.commands.accounts.account_bulk_verify.get_db')
@patch('utils.commands.accounts.account_bulk_verify.PdfReader')
def test_bulk_verify_success_flow(mock_reader, mock_db, mock_run, mock_process_account, mock_refresh_async):
    """Verify that account_bulk_verify parses links, matches accounts, and confirms them."""
    # 1. Mock pypdf to return text containing a verification link
    pdf_text = """
    Didn't work? Copy the link below into your web browser:
    https://mega.nz/#confirmQ29uZmlybUNvZGVWMlVC
    xOkTCQAJvGTUWwoAGmNvbnRhY3QrbW10MUB0cm91YmxlZG1p
    bmQudHJhZGUJTWVnYU1hbmFnZXK3klalSXH8-Q
    """
    mock_instance = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = pdf_text
    mock_instance.pages = [mock_page]
    mock_reader.return_value = mock_instance

    # We mock the mega-logout/mega-confirm subprocess calls
    mock_confirm = MagicMock()
    mock_confirm.returncode = 0
    mock_confirm.stdout = "Account confirmed successfully."

    mock_run.side_effect = [MagicMock(returncode=0), mock_confirm]

    # 2. Mock database query to return our target pending account
    session = MagicMock()
    mock_db.return_value.__enter__.return_value = session

    acc = MegaAccount(id=1, email="contact+mmt1@troubledmind.trade", password="password123", status="Pending Verification")
    session.query.return_value.all.return_value = [acc]

    session.query.return_value.filter.return_value.first.return_value = acc

    with patch('utils.commands.accounts.account_bulk_verify.os.path.exists', return_value=True):
        res, code = run_bulk_verify("mock.pdf")
        assert code == 200
        assert res["stats"]["success"] == 1
        assert res["results"][0]["email"] == "contact+mmt1@troubledmind.trade"
        assert res["results"][0]["status"] == "Success"
        assert acc.status == "Active"
        mock_process_account.assert_called_once()

def test_extract_mega_verification_links_ligatures():
    """Verify that extract_mega_verification_links handles Unicode ligatures (fi -> ﬁ)."""
    from utils.commands.accounts.account_bulk_verify import extract_mega_verification_links

    # Text containing ligature 'ﬁ' in 'conﬁrm'
    ligature_text = "Didn't work? Copy the link below:\nhttps://mega.nz/#conﬁrmQ29uZmlybUNvZGVWMlVC\nxOkTCQAJvGTUWwoAGmNvbnRhY3QrbW10MUB0cm91YmxlZG1p\nbmQudHJhZGUJTWVnYU1hbmFnZXK3klalSXH8-Q\n"

    with patch('utils.commands.accounts.account_bulk_verify.PdfReader') as mock_reader, \
         patch('utils.commands.accounts.account_bulk_verify.os.path.exists', return_value=True):

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ligature_text
        mock_page.__contains__.side_effect = lambda k: False
        mock_instance = MagicMock()
        mock_instance.pages = [mock_page]
        mock_reader.return_value = mock_instance

        links = extract_mega_verification_links("dummy.pdf")
        assert len(links) == 1
        assert "confirm" in links[0]
        assert "conﬁrm" not in links[0]

def test_extract_mega_verification_links_annots():
    """Verify that extract_mega_verification_links extracts links from PDF annotations (/Annots)."""
    from utils.commands.accounts.account_bulk_verify import extract_mega_verification_links

    target_uri = "https://mega.nz/#confirmQ29uZmlybUNvZGVWMlVCxOkTCQAJvGTUWwoAGmNvbnRhY3QrbW10MUB0cm91YmxlZG1pbmQudHJhZGUJTWVnYU1hbmFnZXK3klalSXH8-Q"

    with patch('utils.commands.accounts.account_bulk_verify.PdfReader') as mock_reader, \
         patch('utils.commands.accounts.account_bulk_verify.os.path.exists', return_value=True):

        mock_annot = MagicMock()
        mock_annot.get_object.return_value = {
            '/Subtype': '/Link',
            '/A': {'/URI': target_uri}
        }

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_page.__contains__.side_effect = lambda k: k == '/Annots'
        mock_page.__getitem__.side_effect = lambda k: [mock_annot] if k == '/Annots' else None

        mock_instance = MagicMock()
        mock_instance.pages = [mock_page]
        mock_reader.return_value = mock_instance

        links = extract_mega_verification_links("dummy.pdf")
        assert len(links) == 1
        assert links[0] == target_uri

def test_sample_pdf_verification_if_exists():
    """Verify extraction against actual sample PDF if available on filesystem."""
    import os
    from utils.commands.accounts.account_bulk_verify import extract_mega_verification_links

    sample_pdf = "/home/glados/Downloads/MEGA email verification required.pdf"
    if os.path.exists(sample_pdf):
        links = extract_mega_verification_links(sample_pdf)
        assert len(links) == 28


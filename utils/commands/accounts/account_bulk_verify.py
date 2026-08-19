import subprocess
import os
import re
import base64
from database import get_db
from models import MegaAccount
from utils.config import cmd
from utils.mega_session import hold_mega_session_lock

import unicodedata

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

def extract_mega_verification_links(pdf_path):
    """
    Extracts all MEGA verification links from a PDF file.
    Robustly handles:
    - Interactive PDF Link Annotations (/Annots) embedded by browsers/email clients
    - Unicode ligatures (e.g. 'fi' ligature U+FB01 -> 'fi') via NFKC normalization
    - Control/zero-width characters and soft hyphens
    - Wrapped links split across multiple lines in extracted text
    - Various MEGA domain schemas (mega.nz, mega.io, mega.co.nz, etc.)
    - Deduplication while preserving order and filtering truncated link fragments
    """
    raw_candidates = []

    def clean_link(link_str):
        if not link_str:
            return ""
        s = link_str.strip()
        # Remove surrounding brackets, parentheses, angle brackets, quotes
        s = re.sub(r'^[<\(\[\'\"]+|[>\)\]\'\"]+$', '', s)
        # Strip trailing prose punctuation
        s = re.sub(r'[\.,;:!?]+$', '', s)
        if not s.startswith(('http://', 'https://')):
            if s.lower().startswith('mega.'):
                s = 'https://' + s
        return s

    # 1. Inspect PDF Annotations (/Annots) for embedded hyperlink URIs
    if PdfReader is not None:
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                if '/Annots' in page and page['/Annots']:
                    for annot in page['/Annots']:
                        try:
                            obj = annot.get_object() if hasattr(annot, 'get_object') else annot
                            if not isinstance(obj, dict):
                                continue
                            uri = None
                            if '/A' in obj:
                                action = obj['/A']
                                action_obj = action.get_object() if hasattr(action, 'get_object') else action
                                if isinstance(action_obj, dict) and '/URI' in action_obj:
                                    uri = str(action_obj['/URI'])
                            elif '/URI' in obj:
                                uri = str(obj['/URI'])

                            if uri and 'mega.' in uri.lower() and ('confirm' in uri.lower() or '#confirm' in uri.lower()):
                                c = clean_link(uri)
                                if c:
                                    raw_candidates.append(c)
                        except Exception:
                            pass
        except Exception:
            pass

    # 2. Extract page text using pypdf
    raw_texts = []
    if PdfReader is not None:
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                t = page.extract_text() or ''
                if t:
                    raw_texts.append(t)
        except Exception:
            pass

    # Fallback to system pdftotext binary if pypdf yielded no text
    if not any(raw_texts):
        try:
            res = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout:
                raw_texts.append(res.stdout)
        except Exception:
            pass

    full_text = '\n'.join(raw_texts)
    # Unicode NFKC normalization converts font ligatures (e.g. U+FB01 'fi' -> 'fi')
    norm_text = unicodedata.normalize('NFKC', full_text)
    # Remove control and zero-width characters (zero-width space, soft hyphen, etc.)
    norm_text = re.sub(r'[\u200b\u200c\u200d\ufeff\u00ad]', '', norm_text)

    # 3. Line-by-line scanning to handle wrapped links split across lines
    lines = [line.strip() for line in norm_text.splitlines() if line.strip()]
    STOP_WORDS = {'regards', 'thanks', 'sincerely', 'cheers', 'subject', 'from', 'date', 'to', 'team', 'privacy', 'mega', 'http', 'https', 'www'}

    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.search(r'(?:https?://)?(?:[a-zA-Z0-9-]+\.)*mega\.[a-z.]+[^\s]*confirm[A-Za-z0-9_=\-\/\+]*', line, re.IGNORECASE)
        if match:
            link = match.group(0)
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Check if next_line is a continuation of the base64 confirmation token
                if re.match(r'^[A-Za-z0-9_=\-\/\+]+$', next_line):
                    lowered = next_line.lower()
                    if any(sw in lowered for sw in STOP_WORDS):
                        break
                    link += next_line
                    j += 1
                else:
                    break
            c = clean_link(link)
            if c:
                raw_candidates.append(c)
            i = max(i + 1, j)
            continue
        i += 1

    # 4. Fallback global regex search in text for single-line or inline links
    matches = re.findall(r'(?:https?://)?(?:[a-zA-Z0-9-]+\.)*mega\.[a-z.]+(?:/[^\s"\':<>]*confirm[A-Za-z0-9_=\-\/\+]*|/#confirm[A-Za-z0-9_=\-\/\+]*)', norm_text, re.IGNORECASE)
    for m in matches:
        c = clean_link(m)
        if c:
            raw_candidates.append(c)

    # Filter and deduplicate candidates:
    # If candidate A is a prefix of candidate B (e.g. truncated link fragment vs full link), keep candidate B.
    valid_links = []
    seen = set()

    for cand in raw_candidates:
        if not cand or ('confirm' not in cand.lower() and '#confirm' not in cand.lower()):
            continue
        # Check if cand is a truncated prefix of another longer candidate
        is_truncated = False
        for other in raw_candidates:
            if other != cand and other.startswith(cand):
                is_truncated = True
                break
        if not is_truncated and cand not in seen:
            seen.add(cand)
            valid_links.append(cand)

    return valid_links

def run(command_args=None):
    """
    Parses a PDF containing MEGA verification links, extracts them, matches them
    with accounts in the database, and verifies them in bulk.
    Usage: "pdf_file_path"
    """
    if isinstance(command_args, list):
        command_args = command_args[0] if command_args else ""

    if not command_args:
        return {"status": 400, "message": "Usage: account_bulk_verify:pdf_file_path"}, 400

    pdf_path = command_args.strip()
    if not os.path.exists(pdf_path):
        return {"status": 400, "message": f"PDF file not found: {pdf_path}"}, 400

    if PdfReader is None:
        return {"status": 500, "message": "pypdf package is not installed. Please install it via pip."}, 500

    try:
        links = extract_mega_verification_links(pdf_path)
    except Exception as e:
        return {"status": 500, "message": f"Error extracting text from PDF: {str(e)}"}, 500

    if not links:
        return {"status": 200, "message": "No MEGA verification links found in the PDF.", "results": []}, 200

    # Retrieve all accounts from database to match emails
    with get_db() as db:
        all_accounts = db.query(MegaAccount).all()
        # Keep accounts list in memory for fast matching
        accounts_data = [{"id": acc.id, "email": acc.email, "password": acc.password, "status": acc.status} for acc in all_accounts]

    results = []

    # Process each link
    for idx, link in enumerate(links, 1):
        base64_part = link.split('#confirm')[-1]
        decoded_str = ""
        for p in range(4):
            try:
                decoded = base64.urlsafe_b64decode(base64_part + '=' * p)
                decoded_str = decoded.decode('utf-8', errors='ignore')
                break
            except Exception:
                pass

        if not decoded_str:
            results.append({
                "link": link,
                "email": "Unknown",
                "status": "Failed",
                "message": "Failed to decode link payload."
            })
            continue

        # Find matching account in database by checking if any account.email is a substring of decoded_str
        matched_acc = None
        for acc in accounts_data:
            if acc["email"] in decoded_str:
                matched_acc = acc
                break

        if not matched_acc:
            # Try a fuzzy lookup: extract email-like strings from decoded_str
            emails_found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', decoded_str)
            extracted_email = emails_found[0] if emails_found else "Unknown"

            if extracted_email != "Unknown":
                for acc in accounts_data:
                    if acc["email"] in extracted_email or extracted_email in acc["email"]:
                        matched_acc = acc
                        break

            if not matched_acc:
                results.append({
                    "link": link,
                    "email": extracted_email,
                    "status": "Ignored",
                    "message": "Account not found in the database."
                })
                continue

        # We found a matched account!
        email = matched_acc["email"]
        acc_id = matched_acc["id"]

        # Optimization: if already Active, skip verification
        if matched_acc["status"] == "Active":
            results.append({
                "link": link,
                "email": email,
                "status": "Success",
                "message": "Already Active."
            })
            continue

        # Perform confirmation using mega-confirm
        try:
            # Holds the process-wide MEGAcmd session lock across the logout +
            # confirm sequence, so a concurrent account_login/register/etc.
            # call can't log in mid-sequence and get logged straight back out.
            with hold_mega_session_lock():
                # Logout to prevent conflicts
                subprocess.run([cmd("mega-logout")], capture_output=True, text=True, timeout=10)

                # Execute mega-confirm
                confirm_proc = subprocess.run(
                    [cmd("mega-confirm"), link, email, matched_acc["password"]],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

            if confirm_proc.returncode == 0:
                # Update status in db
                with get_db() as db:
                    db_acc = db.query(MegaAccount).filter(MegaAccount.id == acc_id).first()
                    if db_acc:
                        db_acc.status = "Active"
                        db.commit()

                # Fetch quota immediately so it shows up (e.g. in Total Cloud
                # Pool) without requiring a separate manual refresh click.
                try:
                    from utils.commands.accounts.account_login import process_account
                    process_account(acc_id)
                except Exception as quota_err:
                    print(f"WARNING Post-verification quota fetch failed for {email}: {quota_err}")

                results.append({
                    "link": link,
                    "email": email,
                    "status": "Success",
                    "message": "Verified successfully."
                })
            else:
                raw_err = confirm_proc.stderr.strip() or confirm_proc.stdout.strip()
                # Clean up error
                if "Failed to check email corresponds to link" in raw_err or "Not found" in raw_err:
                    err_msg = "Link mismatch or expired."
                elif "Already confirmed" in raw_err or "already registered" in raw_err.lower():
                    err_msg = "Already confirmed."
                    # Update status to Active since it's already confirmed
                    with get_db() as db:
                        db_acc = db.query(MegaAccount).filter(MegaAccount.id == acc_id).first()
                        if db_acc:
                            db_acc.status = "Active"
                            db.commit()
                else:
                    err_msg = re.sub(r'\[\d{4}-\d{2}-\d{2}[^\]]*\]', '', raw_err).strip()
                    if not err_msg:
                        err_msg = "Verification process failed."

                results.append({
                    "link": link,
                    "email": email,
                    "status": "Failed",
                    "message": err_msg
                })
        except subprocess.TimeoutExpired:
            results.append({
                "link": link,
                "email": email,
                "status": "Failed",
                "message": "Verification timed out."
            })
        except Exception as e:
            results.append({
                "link": link,
                "email": email,
                "status": "Failed",
                "message": f"Error: {str(e)}"
            })

    # Count stats
    total = len(results)
    success = sum(1 for r in results if r["status"] == "Success")
    failed = sum(1 for r in results if r["status"] == "Failed")
    ignored = sum(1 for r in results if r["status"] == "Ignored")

    # Invalidate stats cache since accounts might have updated their status
    from utils.stats_cache import invalidate_and_refresh_async
    invalidate_and_refresh_async()

    return {
        "status": 200,
        "message": f"Bulk verification completed: {success} Succeeded, {failed} Failed, {ignored} Ignored.",
        "stats": {
            "total": total,
            "success": success,
            "failed": failed,
            "ignored": ignored
        },
        "results": results
    }, 200

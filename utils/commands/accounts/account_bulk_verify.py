import subprocess
import os
import re
import base64
from database import get_db
from models import MegaAccount
from utils.config import cmd
from utils.mega_session import hold_mega_session_lock

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

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
        # Extract text using pypdf instead of system pdftotext
        reader = PdfReader(pdf_path)
        text_pages = []
        for page in reader.pages:
            text_pages.append(page.extract_text() or "")
        text = "\n".join(text_pages)
    except Exception as e:
        return {"status": 500, "message": f"Error extracting text from PDF: {str(e)}"}, 500

    # Extract verification links from the text
    lines = [line.strip() for line in text.split('\n')]
    links = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'https://mega.nz/#confirm' in line:
            match = re.search(r'https://mega.nz/#confirm[A-Za-z0-9_=\-\/\+]*', line)
            if match:
                link = match.group(0)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if not next_line:
                        j += 1
                        continue
                    if re.match(r'^[A-Za-z0-9_=\-\/\+]+$', next_line):
                        link += next_line
                        j += 1
                    else:
                        break
                links.append(link)
                i = j
                continue
        i += 1

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

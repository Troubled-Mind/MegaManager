import csv
import io
from database import get_db
from models import File, MegaAccount
from utils.config import cmd

FILENAME = "mega_accounts.csv"

def run(args=None):
    """Export data to a CSV file."""
    if not args:
        return {"status": 400, "message": "No arguments provided."}
    if args == "accounts":
        return export_mega_accounts()

def export_mega_accounts():
    """Export all MEGA accounts to a CSV file."""
    session = next(get_db())
    accounts = session.query(MegaAccount).all()

    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["email", "password"]
    writer.writerow(headers)

    for account in accounts:
        writer.writerow([getattr(account, header) for header in headers])

    # Return file as a download
    output.seek(0)
    return {
        "status": 200,
        "body": output.read()
    }

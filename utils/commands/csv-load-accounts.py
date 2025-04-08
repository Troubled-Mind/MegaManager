import csv
from database import get_db
from models import MegaAccount

def run(args=None):
    try:
        file_path = str(args)
    except (TypeError, ValueError):
        return {"status": 400, "message": "Invalid file path"}

    # Get database session
    db = next(get_db())

    with open(file_path, mode="r") as f:
        reader = csv.DictReader(f)
        account_ids = []

        for row in reader:
            email = row["email"] or row["Email"]
            password = row["password"] or row["Password"]

            # Check if the account already exists in the database
            account = db.query(MegaAccount).filter(MegaAccount.email == email).first()
            if account:
                # Skip if account already exists
                print(f"Account already exists: {email}")
                continue
            else:
                # Add new account to the database
                new_account = MegaAccount(email=email, password=password)
                db.add(new_account)

                # Get ID of the new account
                db.flush()
                account_ids.append(new_account.id)

                db.commit()
                print(f"Added account: {email}")
    
    return {
        "status": 200,
        "account_ids": account_ids
    }

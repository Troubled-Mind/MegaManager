import csv
from database import get_db
from models import MegaAccount

def load_accounts_from_csv(file_path):
    # Get database session
    db = next(get_db())

    with open(file_path, mode="r") as f:
        reader = csv.DictReader(f)

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
                db.commit()

                print(f"Added account: {email}")

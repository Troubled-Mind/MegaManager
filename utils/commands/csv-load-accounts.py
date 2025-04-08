import csv
from database import get_db
from models import MegaAccount

def run(args=None):
    try:
        # Ensure args is passed and has valid data
        if not args or len(args) < 1:
            return {"status": 400, "message": "Invalid CSV data"}, 400

        # Get database session
        db = next(get_db())
        
        account_ids = []

        # Loop through the incoming CSV data rows (args)
        for row in args:
            # Split each row by comma to get email and password
            email, password = row.split(',')

            # Trim extra spaces from email and password
            email = email.strip()
            password = password.strip()

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
                db.flush()  # Ensure the account is flushed to get the ID
                account_ids.append(new_account.id)

                db.commit()
                print(f"Added account: {email}")

        return {
            "status": 200,
            "account_ids": account_ids
        }, 200

    except Exception as e:
        print(f"Error while processing CSV data: {e}")
        return {"status": 500, "message": "Internal server error"}, 500

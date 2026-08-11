import random
import os
import string
import urllib.parse
import subprocess
from utils.config import settings, cmd
from utils.mega_session import hold_mega_session_lock
from database import get_db
from models import MegaAccount

def run(command_args=None):
    if not command_args:
        return {"status": 400, "message": "No email provided"}, 400

    encoded_email = command_args[0]
    email = urllib.parse.unquote(encoded_email)

    # Check for a pre-configured password in settings (handle both singular and plural keys)
    password = settings.get("mega_password") or settings.get("mega_passwords")

    if not password:
        print("INFO No pre-set password found. Generating a secure random one.")
        unsafe = r"|&;<>()$`\"\'!*?~#=%@^,:{}[]+"
        safe_punctuation = string.punctuation.translate(str.maketrans('', '', unsafe))
        chars = string.ascii_letters + string.digits + safe_punctuation
        password = ''.join(random.SystemRandom().choice(chars) for _ in range(22))
    else:
        print(f"INFO Using pre-set password from settings for registration of {email}")

    try:
        # Holds the process-wide MEGAcmd session lock across the logout +
        # signup sequence, so a concurrent account_login/confirm/etc. call
        # can't log in mid-sequence and get logged straight back out again.
        with hold_mega_session_lock():
            # User requested a logout before registering to avoid session conflicts
            try:
                subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            except Exception as logout_err:
                print(f"Logout notice before registration: {logout_err}")

            args = [cmd("mega-signup"), email, password, "--name=Mega Manager"]
            print(f"Running: {cmd('mega-signup')} {email} [PROTECTED] --name=\"Mega Manager\"")

            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

        if result.returncode != 0:
            err_msg = result.stderr.strip() or result.stdout.strip() or f"Registration failed with code {result.returncode}"
            print(f"mega-signup error: {err_msg}")
            return {
                "status": 500,
                "message": err_msg
            }, 500

        with get_db() as db:
            existing = db.query(MegaAccount).filter(MegaAccount.email == email).first()
            if existing:
                print(f"DONE {email} is now Active.")
                return {
                    "status": 409,
                    "message": f"Account already exists in the database: {email}"
                }, 409

            new_account = MegaAccount(email=email, password=password, status="Pending Verification")
            db.add(new_account)
            db.commit()
            db.refresh(new_account)

            return {
                "status": 200,
                "message": f"Account registered: {email}",
                "password": password,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "id": new_account.id,
            }, 200

    except Exception as e:
        return {
            "status": 500,
            "message": str(e)
        }, 500

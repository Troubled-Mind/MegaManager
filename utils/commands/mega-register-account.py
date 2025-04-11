import random
import os
import string
import urllib.parse
import subprocess
from utils.config import settings, cmd
from database import get_db
from models import MegaAccount

def run(command_args=None):
    if not command_args:
        return {"status": 400, "message": "No email provided"}, 400

    encoded_email = command_args[0]
    email = urllib.parse.unquote(encoded_email)

    password = settings.get("mega_password")
    if not password:
        unsafe = r"|&;<>()$`\"\' !*?~#=%@^,:{}[]+"
        safe_punctuation = string.punctuation.translate(str.maketrans('', '', unsafe))
        chars = string.ascii_letters + string.digits + safe_punctuation
        password = ''.join(random.SystemRandom().choice(chars) for _ in range(22))

    try:
        command = f'"{cmd("mega-signup")}" "{email}" "{password}" --name="Mega Manager"'
        print("▶ Running:", command)  # optional: debug log

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
            check=True
        )
        # Save to database
        db = next(get_db())

        existing = db.query(MegaAccount).filter(MegaAccount.email == email).first()
        if existing:
            return {
                "status": 409,
                "message": f"Account already exists in the database: {email}"
            }, 409

        new_account = MegaAccount(email=email, password=password)
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

    except subprocess.CalledProcessError as e:
        return {
            "status": 500,
            "message": e.stderr.strip()
        }, 500

import subprocess
import re
from utils.config import cmd

def ensure_logged_in(email, password):
    """
    Ensures that the specified MEGA account is currently active.
    Returns True if logged in successfully, False otherwise.
    """
    try:
        # Check current login status
        whoami = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True)
        current_logout_required = False
        
        if whoami.returncode == 0:
            current_user = whoami.stdout.strip()
            if email.lower() in current_user.lower():
                print(f"INFO Session already active for {email}")
                return True
            elif current_user and "not logged in" not in current_user.lower():
                # A different user is logged in
                current_logout_required = True

        if current_logout_required:
            print(f"INFO Switching from current account to {email}...")
            subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Proceed with login.
        print(f"INFO Initiating persistent session for {email}...")
        login_res = subprocess.run([cmd("mega-login"), email, password], capture_output=True, text=True)
        
        if login_res.returncode == 0:
            # Verify again
            whoami = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True)
            if email.lower() in whoami.stdout.lower():
                print(f"INFO Persistent session established for {email}")
                return True
        
        print(f"ERROR Login failed for {email}: {login_res.stderr.strip() or login_res.stdout.strip()}")
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return False
        
    except Exception as e:
        print(f"WARNING mega_session error: {e}")
        return False

def logout_if_active(email):
    """Safely logs out if the specified email is active."""
    whoami = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True)
    if email.lower() in whoami.stdout.lower():
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    return False

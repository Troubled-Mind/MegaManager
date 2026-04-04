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
        if whoami.returncode == 0 and email.lower() in whoami.stdout.lower():
            print(f"INFO Session already active for {email}")
            return True

        # If not logged in as the target account, perform login.
        # Note: We don't logout first to avoid killing transfers of other accounts,
        # but mega-cmd-server only supports one active login at a time for most commands.
        # However, multiple logins can coexist in the session cache.
        print(f"INFO Initiating persistent session for {email}...")
        login_res = subprocess.run([cmd("mega-login"), email, password], capture_output=True, text=True)
        
        if login_res.returncode == 0:
            # Verify again
            whoami = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True)
            if email.lower() in whoami.stdout.lower():
                print(f"INFO Persistent session established for {email}")
                return True
        
        print(f"ERROR Login failed for {email}: {login_res.stderr.strip() or login_res.stdout.strip()}")
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

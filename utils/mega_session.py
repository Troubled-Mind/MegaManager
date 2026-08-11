import subprocess
import re
import time
import threading
from contextlib import contextmanager
from utils.config import cmd

# MEGAcmd's background daemon holds exactly one authenticated session for the
# whole machine. The server is multi-threaded (ThreadingHTTPServer, plus
# background workers), so anything that logs in, does a batch of MEGA CLI
# calls, and logs out needs to hold this for that *entire* window - not just
# the login handshake - otherwise a concurrent caller can log in as a
# different account partway through and silently redirect commands like
# mega-du/mega-export to the wrong account (or just fail outright).
_SESSION_LOCK = threading.Lock()

def _do_login(email, password):
    """The actual login handshake. Caller must already hold _SESSION_LOCK."""
    # Fast path: already logged in as this account
    try:
        whoami = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True, timeout=10)
        if whoami.returncode == 0 and email.lower() in whoami.stdout.lower():
            print(f"INFO Session already active for {email}")
            return True
    except Exception:
        pass

    # Always logout unconditionally - MegaCMD daemon must clear the session
    # before a new mega-login can succeed without conflict
    print(f"INFO Clearing MegaCMD session before logging in as {email}...")
    try:
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"WARNING mega-logout failed before login for {email}: {e}")

    # Poll for the daemon to fully release the session (up to 5s)
    for _ in range(10):
        time.sleep(0.5)
        try:
            check = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True, timeout=5)
            out = check.stdout.lower()
            if "not logged in" in out or check.returncode != 0:
                break
        except Exception:
            break

    for attempt in range(1, 4):
        try:
            print(f"INFO Logging in as {email} (attempt {attempt}/3)...")
            login_res = subprocess.run(
                [cmd("mega-login"), email, password],
                capture_output=True, text=True, timeout=30
            )

            if login_res.returncode == 0:
                whoami2 = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True, timeout=10)
                if email.lower() in whoami2.stdout.lower():
                    print(f"INFO Session established for {email}")
                    return True

            raw_err = login_res.stderr.strip() or login_res.stdout.strip() or "No output from mega-login"
            print(f"ERROR Login attempt {attempt}/3 failed for {email}: {raw_err}")

            if attempt < 3:
                # Force another logout in case the daemon got into a bad state
                subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                time.sleep(3)

        except Exception as e:
            print(f"WARNING mega_session error on attempt {attempt}/3 for {email}: {e}")
            if attempt < 3:
                time.sleep(3)

    try:
        subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"WARNING mega-logout failed after exhausting login attempts for {email}: {e}")
    return False


def ensure_logged_in(email, password):
    """
    Ensures that the specified MEGA account is currently active, for a single
    quick operation immediately following this call.

    NOTE: this only holds the session lock for the login handshake itself.
    If you're about to make *several* MEGA CLI calls in a row (looping over
    files for one account, etc.), use the `mega_session()` context manager
    below instead so a concurrent thread can't log in as a different account
    partway through your loop.

    Returns True if logged in successfully, False otherwise - never raises,
    since every caller relies on this being a safe boolean check.
    """
    with _SESSION_LOCK:
        try:
            return _do_login(email, password)
        except Exception as e:
            print(f"ERROR Unexpected error in ensure_logged_in for {email}: {e}")
            return False


@contextmanager
def mega_session(email, password):
    """
    Context manager that holds the process-wide MEGAcmd session lock for the
    full duration of the `with` block, so a concurrent thread can't hijack
    the active session between your MEGA CLI calls. Use this for any batch
    of operations against one account (e.g. looping over that account's
    files) instead of ensure_logged_in().

        with mega_session(account.email, account.password) as ok:
            if not ok:
                return
            subprocess.run([cmd("mega-du"), path])
            subprocess.run([cmd("mega-export"), path])
    """
    _SESSION_LOCK.acquire()
    try:
        ok = False
        try:
            ok = _do_login(email, password)
        except Exception as e:
            print(f"ERROR Unexpected error in mega_session for {email}: {e}")
        yield ok
    finally:
        _SESSION_LOCK.release()


@contextmanager
def hold_mega_session_lock():
    """
    Holds the process-wide MEGAcmd session lock for the duration of the `with`
    block without performing a login - for operations that need exclusive
    access to run their own logout/custom command sequence (account
    registration, confirmation) without a concurrent thread's login/logout
    interleaving mid-sequence. Use `mega_session()` instead when you're
    logging in as a specific account to run a batch of calls against it.

        with hold_mega_session_lock():
            subprocess.run([cmd("mega-logout")], ...)
            subprocess.run([cmd("mega-signup"), email, password], ...)
    """
    _SESSION_LOCK.acquire()
    try:
        yield
    finally:
        _SESSION_LOCK.release()


def logout_if_active(email):
    """Safely logs out if the specified email is active."""
    with _SESSION_LOCK:
        whoami = subprocess.run([cmd("mega-whoami")], capture_output=True, text=True)
        if email.lower() in whoami.stdout.lower():
            subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        return False

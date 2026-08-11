"""
rclone Config Manager for MegaManager
Manages a project-local rclone.conf with one entry per MEGA account.
"""

import os
import re
import subprocess
import configparser
import threading
from io import StringIO

# Path to the project-local rclone config file
RCLONE_CONF_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rclone.conf")

# Guards the read-modify-write functions below. Without this, two concurrent
# writers (e.g. a bulk CSV import looping over add_or_update_account while a
# user deletes an unrelated account) can both read the file, each apply only
# their own change, and whichever writes last silently clobbers the other's.
_CONFIG_FILE_LOCK = threading.Lock()


def rclone_cmd():
    """Return the path to the rclone binary from settings, falling back to 'rclone'."""
    try:
        from database import get_db
        from models import Setting
        with get_db() as session:
            setting = session.query(Setting).filter_by(key="rclone_path").first()
            if setting and setting.value and setting.value.strip():
                return setting.value.strip()
    except Exception:
        pass
    return "rclone"


def _section_name(account_id):
    """Return the rclone config section name for a given account ID."""
    return f"mega-acct-{account_id}"


def obscure_password(password):
    """
    Use rclone obscure to encrypt a password for the config file.
    Falls back to plain text if rclone isn't available yet.
    """
    try:
        result = subprocess.run(
            [rclone_cmd(), "obscure", password],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback: store plain text (rclone can handle both in some contexts,
    # but this is just a safety net for initial setup before rclone is verified)
    return password


def _read_config():
    """Read the current rclone.conf into a ConfigParser."""
    config = configparser.RawConfigParser()
    config.optionxform = str  # preserve case
    if os.path.exists(RCLONE_CONF_PATH):
        with open(RCLONE_CONF_PATH, "r") as f:
            config.read_file(f)
    return config


def _write_config(config):
    """Write the ConfigParser back to rclone.conf."""
    with open(RCLONE_CONF_PATH, "w") as f:
        config.write(f)


def add_or_update_account(account_id, email, password):
    """Add or update a single account entry in rclone.conf."""
    obscured = obscure_password(password)
    section = _section_name(account_id)

    with _CONFIG_FILE_LOCK:
        config = _read_config()

        if not config.has_section(section):
            config.add_section(section)

        config.set(section, "type", "mega")
        config.set(section, "user", email)
        config.set(section, "pass", obscured)

        _write_config(config)
    print(f"INFO rclone config: updated entry [{section}] for {email}")


def remove_account(account_id):
    """Remove an account entry from rclone.conf."""
    section = _section_name(account_id)
    with _CONFIG_FILE_LOCK:
        config = _read_config()
        if config.has_section(section):
            config.remove_section(section)
            _write_config(config)
        else:
            return
    print(f"INFO rclone config: removed entry [{section}]")


def rebuild_all_accounts():
    """
    Rebuild the entire rclone.conf from all accounts in the database.
    Safe to call at startup or after bulk import.
    """
    try:
        from database import get_db
        from models import MegaAccount
        with get_db() as session:
            accounts = session.query(MegaAccount).all()
            # Start with a fresh config
            config = configparser.RawConfigParser()
            config.optionxform = str
            for acc in accounts:
                if acc.email and acc.password:
                    section = _section_name(acc.id)
                    config.add_section(section)
                    config.set(section, "type", "mega")
                    config.set(section, "user", acc.email)
                    config.set(section, "pass", obscure_password(acc.password))

            with _CONFIG_FILE_LOCK:
                _write_config(config)
            print(f"INFO rclone config: rebuilt with {len(accounts)} account(s) -> {RCLONE_CONF_PATH}")
    except Exception as e:
        print(f"ERROR rclone config rebuild failed: {e}")


def get_account_quota(account_id):
    """
    Run 'rclone about' for a specific account and return (used_bytes, total_bytes).
    Returns (None, None) on failure.
    """
    section = _section_name(account_id)
    try:
        result = subprocess.run(
            [rclone_cmd(), "about", "--config", RCLONE_CONF_PATH,
             f"{section}:", "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            used = data.get("used", 0)
            total = data.get("total", 0)
            return int(used or 0), int(total or 0)
    except Exception as e:
        print(f"WARNING rclone about failed for {section}: {e}")
    return None, None


def rclone_copy(account_id, local_path, remote_path, on_log=None):
    """
    Run an rclone copy for a given account. Returns (returncode, stderr_text).
    on_log: optional callable(line) for streaming log output.
    """
    section = _section_name(account_id)
    remote_target = f"{section}:{remote_path}"

    cmd = [
        rclone_cmd(),
        "copy",
        "--config", RCLONE_CONF_PATH,
        local_path,
        remote_target,
        "--transfers", "4",
        "--checkers", "8",
        "--retries", "3",
        "--log-level", "INFO",
        "--stats", "5s",
        "--stats-log-level", "INFO",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    output_lines = []
    for line in process.stdout:
        line = line.rstrip()
        output_lines.append(line)
        if on_log:
            on_log(line)

    process.wait()
    return process.returncode, "\n".join(output_lines)

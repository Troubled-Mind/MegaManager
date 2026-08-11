import os
import subprocess
import shutil
from utils.config import settings

# Platform-specific MEGAcmd binary suffixes
# Windows: scripts ship as .bat wrappers; raw .exe also exists
# macOS/Linux: no suffix
def _get_suffixes():
    if os.name == "nt":
        return [".bat", ".exe", ""]
    return [""]

# Known default paths per platform
def _default_search_dirs():
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        return [
            os.path.join(local_app, "MEGAcmd") if local_app else "",
            os.path.join(program_files, "MEGAcmd"),
        ]
    if os.uname().sysname == "Darwin":
        return [
            "/Applications/MegaCMD.app/Contents/MacOS",
            "/usr/local/bin",
        ]
    # Linux
    return ["/usr/bin", "/usr/local/bin"]

def _find_binary(name, directory, suffixes):
    for sfx in suffixes:
        candidate = os.path.join(directory, name + sfx)
        if os.path.isfile(candidate):
            return candidate
    return None

def run(args=None):
    target_path = None
    if isinstance(args, dict):
        target_path = args.get("megacmd_path") or args.get("path")
    elif isinstance(args, str) and args.strip():
        target_path = args.strip()

    if not target_path:
        target_path = settings.get("megacmd_path") or ""

    target_path = os.path.expandvars(os.path.expanduser(target_path.strip())) if target_path else ""

    # Track whether we are using a user-explicit path or auto-detected one.
    # Only use PATH-level fallbacks when no explicit directory was specified.
    user_specified = bool(target_path)

    # Auto-detect if no path is provided
    if not target_path:
        found_in_path = shutil.which("mega-cmd") or shutil.which("mega-whoami")
        if found_in_path:
            target_path = os.path.dirname(found_in_path)
        else:
            for default_dir in _default_search_dirs():
                if not default_dir:
                    continue
                probe = os.path.join(default_dir, "mega-cmd" + (".bat" if os.name == "nt" else ""))
                probe_exe = os.path.join(default_dir, "mega-cmd.exe")
                if os.path.exists(probe) or os.path.exists(probe_exe):
                    target_path = default_dir
                    break

    if not target_path:
        return {
            "status": 400,
            "valid": False,
            "message": "No MEGAcmd path provided and could not be detected in system PATH."
        }, 400

    # Determine base directory from provided path
    if os.path.isfile(target_path):
        target_dir = os.path.dirname(target_path)
    elif os.path.isdir(target_path):
        target_dir = target_path
    else:
        return {
            "status": 400,
            "valid": False,
            "message": f"Directory or file does not exist: {target_path}",
            "directory": target_path
        }, 400

    suffixes = _get_suffixes()

    required_binaries = [
        "mega-cmd",
        "mega-whoami",
        "mega-login",
        "mega-logout",
        "mega-put",
        "mega-mkdir",
        "mega-export",
        "mega-df"
    ]

    missing = []
    found = []

    for name in required_binaries:
        if _find_binary(name, target_dir, suffixes):
            found.append(name)
        elif not user_specified and shutil.which(name):
            # Only fall back to PATH resolution when no explicit directory was given
            found.append(name)
        else:
            missing.append(name)

    if missing:
        issue_msg = f"Missing {len(missing)} required MEGAcmd binary(s): {', '.join(missing)}"
        return {
            "status": 400,
            "valid": False,
            "message": issue_msg,
            "directory": target_dir,
            "missing_binaries": missing,
            "found_binaries": found
        }, 400

    # Attempt to run mega-whoami --version to confirm executable
    exec_path = (_find_binary("mega-whoami", target_dir, suffixes)
                 or shutil.which("mega-whoami")
                 or _find_binary("mega-cmd", target_dir, suffixes)
                 or shutil.which("mega-cmd"))

    version_str = "Verified"
    if exec_path:
        try:
            res = subprocess.run([exec_path, "--version"], capture_output=True, text=True, timeout=5)
            if res.stdout and res.stdout.strip():
                version_str = res.stdout.strip().splitlines()[0]
        except PermissionError:
            return {
                "status": 400,
                "valid": False,
                "message": f"Permission denied executing MEGAcmd binaries in {target_dir}.",
                "directory": target_dir,
                "missing_binaries": [],
                "found_binaries": found
            }, 400
        except Exception:
            pass  # Non-fatal - binaries exist, execution may require server to be running

    return {
        "status": 200,
        "valid": True,
        "message": f"All {len(found)} MEGAcmd binaries verified in {target_dir}.",
        "directory": target_dir,
        "version": version_str,
        "found_binaries": found
    }, 200

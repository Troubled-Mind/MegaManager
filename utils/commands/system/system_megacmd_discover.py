import os
import shutil

# Common install paths per platform
_SEARCH_PATHS = {
    "nt": [  # Windows
        lambda: os.path.join(os.environ.get("LOCALAPPDATA", ""), "MEGAcmd"),
        lambda: os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "MEGAcmd"),
        lambda: os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "MEGAcmd"),
    ],
    "darwin": [  # macOS
        lambda: "/Applications/MegaCMD.app/Contents/MacOS",
        lambda: "/usr/local/bin",
        lambda: "/opt/homebrew/bin",
    ],
    "posix": [  # Linux
        lambda: "/usr/bin",
        lambda: "/usr/local/bin",
        lambda: "/snap/bin",
        lambda: os.path.expanduser("~/.local/bin"),
    ],
}

_PROBE_BINARIES = ["mega-cmd", "mega-whoami"]

def _binary_exists(directory, name):
    for sfx in ([".bat", ".exe", ""] if os.name == "nt" else [""]):
        if os.path.isfile(os.path.join(directory, name + sfx)):
            return True
    return False

def run(args=None):
    # 1. Check if megacmd is already discoverable on PATH
    for binary in _PROBE_BINARIES:
        found = shutil.which(binary)
        if found:
            directory = os.path.dirname(os.path.abspath(found))
            return {
                "status": 200,
                "found": True,
                "path": directory,
                "method": "PATH",
                "message": f"Found via system PATH: {directory}"
            }, 200

    # 2. Check known install locations for this platform
    platform_key = os.name  # "nt" on Windows, "posix" on Linux/macOS
    if platform_key == "posix":
        try:
            import platform
            if platform.system() == "Darwin":
                platform_key = "darwin"
        except Exception:
            pass

    search_dirs = _SEARCH_PATHS.get(platform_key, _SEARCH_PATHS["posix"])

    for dir_fn in search_dirs:
        try:
            directory = dir_fn()
        except Exception:
            continue

        if not directory or not os.path.isdir(directory):
            continue

        for binary in _PROBE_BINARIES:
            if _binary_exists(directory, binary):
                return {
                    "status": 200,
                    "found": True,
                    "path": directory,
                    "method": "default_path",
                    "message": f"Found at default install location: {directory}"
                }, 200

    return {
        "status": 404,
        "found": False,
        "path": "",
        "message": "MEGAcmd could not be found automatically. Please install it and enter the path manually."
    }, 404

#!/usr/bin/env bash
# MegaManager setup - installs everything needed to run the app: Python (via a
# local virtualenv), MegaCMD, and rclone. Safe to re-run any time; every step
# checks what's already present and skips it.
#
# Usage: ./setup.sh
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}==>${NC} $1"; }
warn()  { echo -e "${YELLOW}WARNING${NC} $1"; }
error() { echo -e "${RED}ERROR${NC} $1"; }

OS="$(uname -s)"
FAILED_STEPS=()

# ---------------------------------------------------------------------------
# 1. Python 3
# ---------------------------------------------------------------------------
find_python() {
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_BIN="$(find_python || true)"

if [ -z "$PYTHON_BIN" ]; then
    info "Python 3.9+ not found, installing..."
    if [ "$OS" = "Darwin" ]; then
        if ! command -v brew >/dev/null 2>&1; then
            info "Homebrew not found, installing it first (this may ask for your password)..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || warn "Homebrew install failed."
            if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
            if [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi
        fi
        if command -v brew >/dev/null 2>&1; then
            brew install python3 || warn "brew install python3 failed."
        fi
    else
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv || warn "apt-get python3 install failed."
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y python3 python3-pip || warn "dnf python3 install failed."
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -Sy --noconfirm python python-pip || warn "pacman python install failed."
        elif command -v zypper >/dev/null 2>&1; then
            sudo zypper install -y python3 python3-pip || warn "zypper python3 install failed."
        else
            error "No supported package manager found (apt/dnf/pacman/zypper). Install Python 3.9+ manually from https://www.python.org/downloads/ and re-run this script."
            FAILED_STEPS+=("python")
        fi
    fi
    PYTHON_BIN="$(find_python || true)"
fi

if [ -z "$PYTHON_BIN" ]; then
    error "Python 3.9+ still not available after install attempt."
    FAILED_STEPS+=("python")
else
    info "Python OK: $($PYTHON_BIN --version)"
fi

# ---------------------------------------------------------------------------
# 2. Virtualenv + pip requirements
# ---------------------------------------------------------------------------
if [ -n "$PYTHON_BIN" ]; then
    if [ ! -x ".venv/bin/python3" ] && [ ! -x ".venv/bin/python" ]; then
        info "Creating virtual environment in .venv..."
        "$PYTHON_BIN" -m venv .venv || { error "Failed to create .venv"; FAILED_STEPS+=("venv"); }
    fi

    if [ -x ".venv/bin/python3" ] || [ -x ".venv/bin/python" ]; then
        VENV_PY=".venv/bin/python3"
        [ -x "$VENV_PY" ] || VENV_PY=".venv/bin/python"

        info "Installing/updating Python dependencies..."
        "$VENV_PY" -m pip install --upgrade pip --quiet || warn "pip self-upgrade failed, continuing anyway."
        "$VENV_PY" -m pip install -r requirements.txt || { error "Failed to install requirements.txt"; FAILED_STEPS+=("requirements"); }
    fi
fi

# ---------------------------------------------------------------------------
# 3. MegaCMD
# ---------------------------------------------------------------------------
if command -v mega-cmd >/dev/null 2>&1 || command -v mega-login >/dev/null 2>&1; then
    info "MegaCMD already installed."
else
    info "MegaCMD not found, installing..."
    if [ "$OS" = "Darwin" ]; then
        if command -v brew >/dev/null 2>&1; then
            brew install --cask megacmd-app || warn "brew cask megacmd-app failed."
            # MegaCMD's helper scripts call mega-exec by bare name and need it on
            # PATH - see README's "mega-exec: command not found" section.
            MEGA_EXEC="/Applications/MEGAcmd.app/Contents/MacOS/mega-exec"
            if [ -f "$MEGA_EXEC" ]; then
                BREW_PREFIX="$(brew --prefix 2>/dev/null || echo /usr/local)"
                sudo mkdir -p "$BREW_PREFIX/bin"
                sudo ln -sf "$MEGA_EXEC" "$BREW_PREFIX/bin/mega-exec"
                sudo ln -sf "/Applications/MEGAcmd.app/Contents/MacOS" "$BREW_PREFIX/opt/megacmd-bin" 2>/dev/null
                # Symlink every mega-* helper script onto PATH too.
                for f in /Applications/MEGAcmd.app/Contents/MacOS/mega-*; do
                    sudo ln -sf "$f" "$BREW_PREFIX/bin/$(basename "$f")"
                done
            fi
        else
            error "Homebrew is required to auto-install MegaCMD on macOS. Install it from https://mega.io/cmd manually and re-run."
            FAILED_STEPS+=("megacmd")
        fi
    else
        INSTALLED=false
        if command -v apt-get >/dev/null 2>&1 && [ -f /etc/os-release ]; then
            . /etc/os-release
            DISTRO_LABEL=""
            case "$ID" in
                ubuntu) DISTRO_LABEL="xUbuntu_${VERSION_ID}" ;;
                debian) DISTRO_LABEL="Debian_${VERSION_ID%%.*}" ;;
                linuxmint) DISTRO_LABEL="xUbuntu_${UBUNTU_CODENAME:+22.04}" ;;
                *) DISTRO_LABEL="xUbuntu_$(lsb_release -rs 2>/dev/null || echo 22.04)" ;;
            esac
            REPO_URL="https://mega.nz/linux/repo/${DISTRO_LABEL}/amd64/"
            info "Looking up latest MegaCMD package for ${DISTRO_LABEL}..."
            DEB_NAME="$(curl -fsSL "$REPO_URL" 2>/dev/null | grep -oE 'megacmd_[^"'\'']+_amd64\.deb' | head -n1)"
            if [ -n "$DEB_NAME" ]; then
                TMP_DEB="/tmp/${DEB_NAME}"
                if curl -fsSL "${REPO_URL}${DEB_NAME}" -o "$TMP_DEB"; then
                    sudo apt-get update
                    if sudo apt-get install -y "$TMP_DEB"; then
                        INSTALLED=true
                    fi
                    rm -f "$TMP_DEB"
                fi
            fi
        elif command -v dnf >/dev/null 2>&1 && [ -f /etc/os-release ]; then
            . /etc/os-release
            REPO_URL="https://mega.nz/linux/repo/Fedora_${VERSION_ID}/x86_64/"
            info "Looking up latest MegaCMD package for Fedora ${VERSION_ID}..."
            RPM_NAME="$(curl -fsSL "$REPO_URL" 2>/dev/null | grep -oE 'megacmd-[^"'\'']+\.x86_64\.rpm' | head -n1)"
            if [ -n "$RPM_NAME" ]; then
                TMP_RPM="/tmp/${RPM_NAME}"
                if curl -fsSL "${REPO_URL}${RPM_NAME}" -o "$TMP_RPM"; then
                    if sudo dnf install -y "$TMP_RPM"; then
                        INSTALLED=true
                    fi
                    rm -f "$TMP_RPM"
                fi
            fi
        fi

        if [ "$INSTALLED" = true ]; then
            info "MegaCMD installed."
        else
            error "Could not auto-install MegaCMD for this distro. Download it manually from https://mega.io/cmd (Arch users: available in the AUR as 'megacmd'), then re-run this script or set the path in Settings -> Core Config."
            FAILED_STEPS+=("megacmd")
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 4. rclone
# ---------------------------------------------------------------------------
if command -v rclone >/dev/null 2>&1; then
    info "rclone already installed."
else
    info "rclone not found, installing..."
    if [ "$OS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
        brew install rclone || warn "brew install rclone failed, falling back to official installer."
    fi
    if ! command -v rclone >/dev/null 2>&1; then
        curl -fsSL https://rclone.org/install.sh | sudo bash || {
            error "rclone install failed. Install it manually from https://rclone.org/downloads/ and re-run."
            FAILED_STEPS+=("rclone")
        }
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
    info "Setup complete. Run ./run.sh to start MegaManager."
    exit 0
else
    error "Setup finished with problems in: ${FAILED_STEPS[*]}"
    error "Fix the steps above and re-run ./setup.sh, or run ./run.sh anyway if the app can work without them for now."
    exit 1
fi

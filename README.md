# MegaManager

MegaManager was created to make managing files across multiple MEGA accounts simpler. It handles account logins, monitors quotas, queues and runs uploads automatically, and gives you a live view of what is happening.

Everything runs locally on your machine. A local SQLite database stores your account credentials, file records, and settings. None of this data is sent anywhere.

> [!CAUTION]
> Never share your database.db file with anyone. It contains account passwords, sharing links, and other sensitive information. You are responsible for keeping it safe and backed up.

> [!CAUTION]
> Never share your rclone.conf file. It contains obscured MEGA account credentials for every account managed by MegaManager. Treat it like your database.db.


# Requirements and Setup

## MegaCMD

Download and install [MegaCMD](https://mega.io/cmd) for your operating system. MegaManager uses MegaCMD for account management, quota checking, and file indexing.

MegaManager will attempt to detect MegaCMD automatically on startup and via the "Auto-discover" button in settings. If it is installed in a standard location or is available on your system PATH, no manual configuration is needed. If auto-detection fails, you can enter the path to the MegaCMD binary directory manually in the Core Config settings tab.

Common install locations:
- Windows: `%LOCALAPPDATA%\MEGAcmd`
- macOS: `/Applications/MegaCMD.app/Contents/MacOS`
- Linux: `/usr/bin`

## rclone

Download and install [rclone](https://rclone.org/downloads/) for your operating system. MegaManager uses rclone for all file uploads. Unlike MegaCMD, rclone maintains an independent session per account, which means multiple accounts can upload simultaneously with no session conflicts.

MegaManager will attempt to detect rclone automatically and via the "Auto-discover" button in Core Config settings. rclone does not require any manual configuration - MegaManager generates and manages an `rclone.conf` file automatically in the project folder.

Common install locations:
- Windows: add `rclone.exe` to your PATH or place it anywhere and set the path manually
- macOS: `/opt/homebrew/bin/rclone` (Homebrew) or `/usr/local/bin/rclone`
- Linux: `/usr/bin/rclone` or `/usr/local/bin/rclone`

To install on Linux/macOS in one command:
```
sudo -v ; curl https://rclone.org/install.sh | sudo bash
```

## Python

Download and install [Python](https://www.python.org/downloads/) if you do not already have it.

When installing on Windows, make sure to tick the box labelled "Add Python to PATH". Without this, the commands below will not work.

## MegaManager

Click `Code -> Download ZIP` at the top of this page to get the latest version, then extract it somewhere on your computer.

The application checks for updates on startup and will apply them automatically if a newer version is available. You will be prompted to restart after an update.

## First-time setup

Open a terminal, navigate to the folder you extracted MegaManager into, and run:

```
pip install -r requirements.txt
python server.py
```

Once running, open a browser and go to `http://localhost:6342`.

Why port 6342? It spells MEGA on a T9 keypad.


# Configuration

Go to `/settings` after starting the server. The settings page is split into four sections:

**Core Config** - Set the path to your MegaCMD installation and your rclone binary. Both can be auto-discovered using the respective buttons. Also set the template email and password used when registering new accounts in bulk. The rclone config file path is shown here for reference - it is managed automatically and does not need to be edited manually.

**Monitored Folders** - Add the local directory paths that MegaManager should scan for files. Below that, configure the date formats used to detect recording dates from folder names. These use standard strftime format codes.

**Security** - Optionally set a password that must be entered before anyone can access the dashboard. You can also configure how many incorrect login attempts are allowed before the dashboard locks permanently. Unlocking requires a server restart. The default is 5 attempts.

**Data** - Export your accounts, local files, or cloud file records as CSV files for backup or review.

After changing anything, click "Save All" in the top right.


# Core Features

### Multi-Account Management

View all of your MEGA accounts in one place, with filters for status, account type, activity, and used capacity. MegaManager tracks available storage, used space, and account status for each one. Quotas refresh automatically in the background. You can also trigger a manual refresh at any time.

### Account Registration

Register large numbers of MEGA accounts using a single base email with plus-addressing. MegaManager generates the accounts, handles the signup process, and flags any that need email confirmation. A dedicated verification page lets you paste confirmation links from your inbox to complete the process one at a time, or bulk-verify by uploading a single PDF containing all of your confirmation emails - MegaManager extracts every verification link and confirms them in one pass.

You can also import existing MEGA accounts by CSV instead of registering new ones, as plain `email,password` per line. A header row is optional - MegaManager detects and skips one automatically if the first line isn't itself a valid email:

```
someone@example.com,SuperSecretPassword1
someone.else@example.com,AnotherPassword2
```

Accounts already in the database (matched by email) are skipped rather than duplicated.

### Automated Uploads

When you start a batch upload, MegaManager scans your monitored folders, checks available space across all accounts using rclone, distributes files to the accounts with room for them, and starts uploading immediately as each account is confirmed - without waiting for all accounts to be checked first. Files are assigned from largest to smallest to pack accounts as efficiently as possible. Multiple accounts upload in parallel. The queue persists in the background even if you close the browser.

### Smart Re-upload

For files that only partially made it to the cloud (a size mismatch between the local and cloud copy), MegaManager can resume the upload on the same account if there's now room, or automatically relocate it to a different account with enough free space if not - clearing out the incomplete remote copy first so nothing is left half-uploaded.

### Cloud Verification and Reorganization

MegaManager can sweep an account's cloud storage to find files that ended up outside their expected folder structure and move them into place, matching releases by their unique ID rather than just a shared date so that two different uploads never get merged together. A separate size discrepancy filter on the files page flags any file where the local and cloud copies don't match, so it's easy to spot problems and fix them.

### Upload Monitoring

The uploads page shows active and pending transfers in real time. You can see current upload speed, the total size of the pending queue, and live log output from running transfers, ordered consistently so rows don't jump around as multiple files upload at once. Stopped or failed uploads can be cleared from the dashboard without affecting the queue for other files.

### Mega Link Import

Import files or folders directly into your MEGA accounts using public sharing links, or bulk-import a whole list of links at once. Useful for copying content from one MEGA account to another without downloading it locally first.

### File Dashboard

The files page lists all locally indexed files and their cloud upload status, with filters for location, account, show, and size discrepancies. You can see the total size of all local files and, on the accounts page, the total cloud space used and available across all accounts. Both pages cache their data and refresh it in the background, so the dashboard stays fast even with a large library.

### Security

If a dashboard password is set, all pages require authentication before they can be accessed. The login system includes a configurable lockout that permanently blocks access after a set number of wrong attempts. The lockout limit is not shown to the user. Restarting the server resets the counter.

### Auto-Update

On startup, MegaManager checks the GitHub repository for a newer version. If one exists, it downloads and applies the update automatically, preserving your database and git history, and reinstalls any new Python dependencies. A banner prompts you to restart the server once the update is applied.

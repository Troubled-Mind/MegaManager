import subprocess
import re
from utils.commands.accounts.account_get_all import run as get_all_accounts
from utils.config import cmd
from utils.mega_session import mega_session

# TODO: see if we can prevent importing to accounts with an active upload

def run(args=None):
    """
    Import a list of mega links into available accounts.
    This is janky, but until mega lets you check the size of a public link, idk how else to do it.

    Args should be a dict: {"links": [list of links]}
    Returns: {"imported": [{folder, new_link}], "failed": [links]}
    """
    links = args.get("links", []) if isinstance(args, dict) else []
    accounts = get_all_accounts()["accounts"]
    account_bins = []
    for acc in accounts:
        try:
            total = int(acc["total_quota"])
            used = int(acc["used_quota"])
            free = total - used
        except:
            free = 0
        account_bins.append({"id": acc["id"], "email": acc["email"], "password": acc["password"], "free": free})

    imported = []
    failed = []

    for link in links:
        try:
            assigned = False
            link_size = None

            # Check accounts with the smallest free space first to see if it fits
            # Could probably improve with an actual bin packing algo, but this works for now
            for acc in sorted(account_bins, key=lambda x: -x["free"]):
                if link_size != None and acc["free"] < link_size:
                    continue

                # Holds the process-wide MEGAcmd session lock for this
                # account's whole import/du/export sequence, so a concurrent
                # upload/sync job can't log in as a different account
                # mid-way and redirect these commands to the wrong place.
                with mega_session(acc["email"], acc["password"]) as logged_in:
                    if not logged_in:
                        continue

                    # Mega won't let you get the size of a public link, so
                    # import first and check its size afterward.
                    import_proc = subprocess.run([cmd("mega-import"), link], capture_output=True, text=True)
                    if import_proc.returncode != 0:
                        failed.append({
                            "link": link,
                            "size": link_size
                        })
                        assigned = True
                        break

                    match = re.search(r'(?:Imported|Import) (?:folder|file) complete:\s+([^\r\n]+)', import_proc.stdout)
                    if match:
                        imported_path = match.group(1).strip().rstrip(",")
                    else:
                        failed.append({
                            "link": link,
                            "size": link_size
                        })
                        assigned = True
                        break

                    du_proc = subprocess.run([cmd("mega-du"), imported_path], capture_output=True, text=True)
                    size_match = re.search(r"Total storage used:\s*([0-9]+)", du_proc.stdout)
                    link_size = int(size_match.group(1)) if size_match else 0

                    from utils.rclone_config import get_account_quota
                    used_b, total_b = get_account_quota(acc["id"])
                    if used_b is not None and total_b is not None:
                        free = total_b - used_b
                    elif link_size != None:
                        free = acc["free"] - link_size

                    if free < 0:
                        subprocess.run([cmd("mega-rm"), "-r", "-f", imported_path], capture_output=True, text=True)
                        continue

                    export_proc = subprocess.run([cmd("mega-export"), "-a", imported_path], capture_output=True, text=True)
                    new_link_match = re.search(r"https://mega.nz/[^\s\)]+", export_proc.stdout)
                    new_link = new_link_match.group(0) if new_link_match else None

                    imported.append({
                        "account": acc["email"],
                        "path": imported_path,
                        "size": link_size,
                        "link": new_link
                    })
                    acc["free"] -= link_size
                    assigned = True
                    print("INFO Successfully imported link to account", acc["email"])
                    break

            if not assigned:
                failed.append({
                    "link": link,
                    "size": link_size
                })
        except Exception as e:
            print(f"ERROR Unexpected error importing link {link}: {e}")
            failed.append({"link": link, "size": None})

    return {"status": 200, "imported": imported, "failed": failed}

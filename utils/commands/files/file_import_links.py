import subprocess
import re
from utils.commands.accounts.account_get_all import run as get_all_accounts
from utils.commands.accounts.account_login import parse_mega_df, parse_mega_df_h
from utils.config import cmd
from utils.mega_session import ensure_logged_in

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
    
    # Try to import each
    for link in links:
        assigned = False
        link_size = None

        # Check accounts with the smallest free space first to see if it fits
        # Could probably improve with an actual bin packing algo, but this works for now
        for acc in sorted(account_bins, key=lambda x: -x["free"]):
            # Skip accounts with not enough space
            if link_size != None and acc["free"] < link_size:
                continue

            if ensure_logged_in(acc["email"], acc["password"]):
                # Mega won't let you get the size of a public link
                # So try importing to the first available account so we can check its size
                import_proc = subprocess.run([cmd("mega-import"), link], capture_output=True, text=True)
                if import_proc.returncode != 0:
                    # Import only fails if, e.g some issue with the link
                    failed.append({
                        "link": link,
                        "size": link_size
                    })
                    assigned = True
                    break
                    
                # Get imported file/folder path
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

                # Get actual size
                du_proc = subprocess.run([cmd("mega-du"), imported_path], capture_output=True, text=True)                
                size_match = re.search(r"Total storage used:\s*([0-9]+)", du_proc.stdout)
                link_size = int(size_match.group(1)) if size_match else 0

                # Re-check account quota
                df_cmd = [cmd("mega-df"), "-h"] if acc.get("is_pro") else [cmd("mega-df")]
                df_proc = subprocess.run(df_cmd, capture_output=True, text=True)
                if df_proc.returncode == 0:
                    used, total = parse_mega_df_h(df_proc.stdout) if acc.get("is_pro") else parse_mega_df(df_proc.stdout)
                    free = int(total) - int(used)
                elif link_size != None:
                    free = acc["free"] - link_size

                if free < 0:
                    # Over quota, delete the imported folder and try next account
                    subprocess.run([cmd("mega-rm"), "-r", "-f", imported_path], capture_output=True, text=True)
                    continue

                # Export new link
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

    return {"status": 200, "imported": imported, "failed": failed}

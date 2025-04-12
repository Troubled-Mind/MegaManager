import re
import subprocess
from collections import defaultdict
from database import get_db
from models import File, MegaAccount
from utils.config import cmd

def run(args=None):
    """Batch update MEGA file sizes and links grouped by account."""
    session = next(get_db())

    results = []
    files_by_account = defaultdict(list)

    # Group files by account
    all_files = session.query(File).filter(File.m_path != None).all()
    for f in all_files:
        files_by_account[f.m_account_id].append(f)

    for account_id, files in files_by_account.items():
        account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
        if not account:
            results.append({"account_id": account_id, "status": 404, "message": "Account not found"})
            continue

        try:
            subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run([cmd("mega-login"), account.email, account.password], check=True, text=True)
            print(f"✅ Logged in: {account.email}")

            account_results = []

            for file in files:
                full_path = f"{file.m_path}/{file.m_folder_name}"
                try:
                    du_result = subprocess.run([cmd("mega-du"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                    storage = parse_mega_du(du_result.stdout.strip())
                    file.m_folder_size = storage

                    export_result = subprocess.run([cmd("mega-export"), full_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                    link = parse_mega_export(export_result.stdout.strip())
                    file.m_sharing_link = link

                    account_results.append({
                        "id": file.id,
                        "cloud_path": file.m_path,
                        "folder_name": file.m_folder_name,
                        "m_folder_size": storage,
                        "is_cloud": True,
                        "cloud_email": account.email,
                        "m_sharing_link": link,
                    })

                except subprocess.CalledProcessError as e:
                    stdout = e.stdout.strip() if e.stdout else ""
                    stderr = e.stderr.strip() if e.stderr else ""

                    if "not exported" in stdout.lower():
                        file.m_folder_size = storage
                        file.m_sharing_link = None

                        account_results.append({
                            "id": file.id,
                            "cloud_path": file.m_path,
                            "folder_name": file.m_folder_name,
                            "m_folder_size": storage,
                            "is_cloud": True,
                            "cloud_email": account.email,
                            "m_sharing_link": None,
                        })
                    else:
                        account_results.append({
                            "id": file.id,
                            "error": stderr or stdout or f"Unknown error (code {e.returncode})"
                        })

            session.commit()
            results.append({
                "account_id": account.id,
                "email": account.email,
                "status": 200,
                "files": account_results
            })

        except subprocess.CalledProcessError as e:
            results.append({
                "account_id": account.id,
                "email": account.email,
                "status": 500,
                "message": f"Login or command error: {e.stderr or e.stdout}"
            })

        except Exception as e:
            session.rollback()
            results.append({
                "account_id": account.id,
                "email": account.email,
                "status": 500,
                "message": str(e)
            })

        finally:
            subprocess.run([cmd("mega-logout")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    return {
        "status": 200,
        "results": results
    }

def parse_mega_du(output):
    for line in output.splitlines():
        if "Total storage used:" in line:
            return int(line.strip().split()[-1])
    return 0

def parse_mega_export(output):
    match = re.search(r'https://mega\.nz/folder/[^\s)]+', output)
    return match.group(0) if match else None
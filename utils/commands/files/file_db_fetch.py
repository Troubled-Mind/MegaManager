from database import get_db
from models import File, MegaAccount

def run(args=None):
    try:
        with get_db() as session:
            # Using join for performance and to get cloud_email
            rows = session.query(File, MegaAccount).outerjoin(MegaAccount, File.m_account_id == MegaAccount.id).all()

            files = []
            for file, account in rows:
                files.append({
                    "id": file.id,
                    "l_path": file.l_path,
                    "l_folder_name": file.l_folder_name,
                    "l_folder_size": file.l_folder_size,
                    "m_path": file.m_path,
                    "m_folder_name": file.m_folder_name,
                    "m_folder_size": file.m_folder_size,
                    "m_sharing_link": file.m_sharing_link,
                    "m_sharing_link_expiry": file.m_sharing_link_expiry,
                    "m_account_id": file.m_account_id,
                    "cloud_email": account.email if account else None,
                    "pro_account": bool(account.is_pro_account) if account else False,
                    "is_local": bool(file.l_path),
                    "is_cloud": bool(file.m_path),
                })

            return {
                "status": 200,
                "files": files
            }

    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}

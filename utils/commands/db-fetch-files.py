import sqlite3

def run(args=None):
    try:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT
                f.id,
                f.l_path,
                f.l_folder_name,
                f.l_folder_size,
                f.m_path,
                f.m_folder_name,
                f.m_folder_size,
                f.m_sharing_link,
                f.m_sharing_link_expiry,
                f.m_account_id,
                ma.email AS cloud_email,
                ma.is_pro_account AS pro_account,
                CASE WHEN f.l_path IS NOT NULL THEN 1 ELSE 0 END AS is_local,
                CASE WHEN f.m_path IS NOT NULL THEN 1 ELSE 0 END AS is_cloud
            FROM files f
            LEFT JOIN mega_accounts ma ON f.m_account_id = ma.id
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        files = []
        for row in rows:
            files.append({
                "id": row["id"],
                "l_path": row["l_path"],
                "l_folder_name": row["l_folder_name"],
                "l_folder_size": row["l_folder_size"],
                "m_path": row["m_path"],
                "m_folder_name": row["m_folder_name"],
                "m_folder_size": row["m_folder_size"],
                "m_sharing_link": row["m_sharing_link"],
                "m_sharing_link_expiry": row["m_sharing_link_expiry"],
                "m_account_id": row["m_account_id"],
                "cloud_email": row["cloud_email"],
                "pro_account": bool(row["pro_account"]),
                "is_local": bool(row["is_local"]),
                "is_cloud": bool(row["is_cloud"]),
            })

        return {
            "status": 200,
            "files": files
        }

    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}

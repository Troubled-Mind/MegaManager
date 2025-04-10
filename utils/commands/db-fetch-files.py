import sqlite3

def run(args=None):
    try:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
        SELECT
            mf.id,
            f.path AS local_path,
            mf.path AS cloud_path,
            mf.folder_name,
            CASE WHEN f.id IS NOT NULL THEN 1 ELSE 0 END AS is_local,
            CASE WHEN mf.mega_account_id IS NOT NULL THEN 1 ELSE 0 END AS is_cloud
        FROM mega_files mf
        LEFT JOIN files f ON mf.local_id = f.id
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        files = []
        for row in rows:
            files.append({
                "id": row["id"],
                "local_path": row["local_path"],
                "cloud_path": row["cloud_path"],
                "folder_name": row["folder_name"],
                "is_local": bool(row["is_local"]),
                "is_cloud": bool(row["is_cloud"]),
            })

        return {
            "status": 200,
            "files": files
        }

    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}

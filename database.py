import sqlite3
import os

def create_database():
    db_file = "database.db"
    
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct the absolute path to the schema.sql file
    schema_path = os.path.join(script_dir, "web", "resources", "dbschema.sql")

    if not os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Read schema from SQL file and execute it
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                schema = f.read()
                cursor.executescript(schema)

            conn.commit()
            conn.close()
        else:
            print(f"Schema file not found at {schema_path}")
            os.remove(db_file)  # Clean up the database file if schema is not found

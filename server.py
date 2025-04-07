import os
from http.server import HTTPServer
from database import create_database
from utils.__http_handler import CustomHandler  # ← import from the new file

def run_server():
    os.chdir(os.getcwd())  # Optional: ensure project root
    create_database()  # Ensure the database and schema are created
    server_address = ("localhost", 6342)
    httpd = HTTPServer(server_address, CustomHandler)
    print("Server running at http://localhost:6342/")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()

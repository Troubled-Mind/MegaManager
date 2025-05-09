import os
from http.server import HTTPServer
from database import create_database
from utils.config import settings, check_for_update
from utils.http_handler import CustomHandler 

def run_server():
    os.chdir(os.getcwd())  
    create_database()  # Ensure the database and schema are created
    check_for_update()  
    server_address = ("0.0.0.0", 6342)
    httpd = HTTPServer(server_address, CustomHandler)
    settings.load()  # Load settings from the database
    print("Server running at http://localhost:6342/")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()

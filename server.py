import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from database import create_database

# Custom HTTP request handler
class CustomHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Force all paths to serve from ./web directory
        path = super().translate_path(path)
        relpath = os.path.relpath(path, os.getcwd())
        return os.path.join(os.getcwd(), 'web', relpath)

# Start the HTTP server
def run_server():
    os.chdir(os.getcwd())  # Optional: make sure cwd is project root
    create_database()  # Ensure the database and schema are created
    server_address = ("localhost", 6342)
    httpd = HTTPServer(server_address, CustomHandler)
    print("Server running at http://localhost:6342/")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()

import os
import json
import importlib.util
from http.server import SimpleHTTPRequestHandler
from urllib.parse import parse_qs
from utils.config import settings, state

class CustomHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = super().translate_path(path)
        relpath = os.path.relpath(path, os.getcwd())
        return os.path.join(os.getcwd(), 'web', relpath)

    def do_GET(self):
        restricted_paths = [
            "/",  
            "/index.html",
            "/files.html",
            "/accounts.html",
            "/settings.html",
            "/testing.html",
            '/uploads.html'
        ]

        public_paths = ["/login.html"]
        is_static = self.path.startswith("/resources/") or self.path.startswith("/scripts/")

        # Normalize path by removing query strings and trailing slashes
        clean_path = self.path.split('?')[0].rstrip('/')
        if not clean_path: clean_path = "/"

        if clean_path == "/api/settings":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(settings._values).encode())
            return

        if clean_path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state).encode("utf-8"))
            return

        if clean_path == "/api/version":
            try:
                with open("version", "r") as f:
                    version = f.read().strip()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"version": version}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        if is_static or clean_path in public_paths:
            return super().do_GET()

        if clean_path in restricted_paths:
            if settings.get("app_password") and not state["authenticated"]:
                print(f"🔒 Access blocked to {self.path} → not authenticated")
                self.send_response(302)
                self.send_header("Location", "/login.html")
                self.end_headers()
                return

        return super().do_GET()



    def do_POST(self):
        if self.path == "/run-command":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode()
            content_type = self.headers.get("Content-Type", "")

            try:
                if "application/json" in content_type:
                    data = json.loads(post_data)
                    command = data.get("command", "")
                    args = data.get("args", [])
                else:
                    data = parse_qs(post_data)
                    command = data.get("command", [""])[0]
                    args = data.get("args", [])  

                # Extract argument from command (e.g. mega-login:1)
                if ":" in command and (not args or args == [""]):
                    _, _, arg_str = command.partition(":")
                    args = arg_str if arg_str else None

                result = self.run_command(command, args)

                if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict):
                    payload, status = result
                else:
                    payload = result
                    status = result.get("status", 200) if isinstance(result, dict) else 200

                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

                if isinstance(payload, dict):
                    self.wfile.write(json.dumps(payload).encode())
                else:
                    self.wfile.write(json.dumps({"status": 500, "message": str(payload)}).encode())

            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON payload")
            except Exception as e:
                self.send_error_response(500, f"Unexpected error: {str(e)}")

    def run_command(self, command, args=None):
        if ":" in command:
            command_name, _, _ = command.partition(":")
        else:
            command_name = command

        # Prevent account operations while uploads are active to avoid session corruption
        RESTRICTED_DURING_UPLOAD = [
            "account_login", 
            "account_register", 
            "account_bulk_register", 
            "account_confirm", 
            "account_delete"
        ]

        if state["uploads_active"] and command_name in RESTRICTED_DURING_UPLOAD:
            return {"status": 403, "message": "Account operations are locked during active uploads to prevent session corruption."}, 403

        # Find the command file recursively in subdirectories
        command_path = None
        commands_root = os.path.join(os.getcwd(), "utils", "commands")
        
        for root, dirs, files in os.walk(commands_root):
            if f"{command_name}.py" in files:
                command_path = os.path.join(root, f"{command_name}.py")
                break

        if not command_path or not os.path.exists(command_path):
            return {"status": 400, "message": f"Unknown command: {command_name}"}, 400

        try:
            # We use the full path for the spec to avoid any ambiguity
            spec = importlib.util.spec_from_file_location(command_name, command_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "run"):
                return module.run(args)
            else:
                return {"status": 500, "message": f"{command_name} does not define a run() function."}
        except Exception as e:
            return {"status": 500, "message": f"Command execution error: {str(e)}"}


    def send_error_response(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": status, "message": message}).encode())

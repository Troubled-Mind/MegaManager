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
        public_paths = ["/login.html"]
        is_static = self.path.startswith("/resources/") or self.path.startswith("/scripts/")

        # Handle /api/settings by returning current settings from the global Settings instance
        if self.path == "/api/settings":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            print("settings._values:", settings._values)
            self.wfile.write(json.dumps(settings._values).encode())
            return
        
        if self.path == "/api/version":
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

        if self.path in public_paths:
            return super().do_GET()

        # 🔐 Protect everything else if password is set and not authenticated
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
                # Parse body based on content type
                if "application/json" in content_type:
                    data = json.loads(post_data)
                    command = data.get("command", "")
                    args = data.get("args", [])
                else:
                    data = parse_qs(post_data)
                    command = data.get("command", [""])[0]
                    args = data.get("args", [])  # this will be a list if provided, else empty

                print(f"📥 Command Received = {command!r}")
                print(f"📥 Arguments = {args!r} (type = {type(args).__name__})")

                # Extract argument from command (e.g. mega-login:1)
                if ":" in command and (not args or args == [""]):
                    _, _, arg_str = command.partition(":")
                    args = arg_str if arg_str else None

                result = self.run_command(command, args)

                # Unpack result
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

        command_path = f"utils/commands/{command_name}.py"
        if not os.path.exists(command_path):
            return {"status": 400, "message": f"Unknown command: {command_name}"}, 400

        try:
            spec = importlib.util.spec_from_file_location(command_name, command_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "run"):
                return module.run(args)
            else:
                return {"status": 500, "message": f"{command_name} does not define a run() function."}
        except Exception as e:
            return {"status": 500, "message": str(e)}

    def send_error_response(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": status, "message": message}).encode())

import os
import sys
import json
import threading
import importlib
from http.server import SimpleHTTPRequestHandler
from urllib.parse import parse_qs
from utils.config import settings, state

# Command dispatch caches, shared across requests/threads. A new CustomHandler
# instance is created per request, so these live at module scope instead.
_COMMAND_PATH_CACHE = {}          # command_name -> resolved file path
_COMMAND_MODULE_MTIME = {}        # dotted module name -> mtime last (re)loaded at
_COMMAND_CACHE_LOCK = threading.Lock()

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
            "/uploads.html",
            "/import.html"
        ]

        public_paths = ["/login.html"]
        is_static = self.path.startswith("/resources/") or self.path.startswith("/scripts/")

        clean_path = self.path.split('?')[0].rstrip('/')
        if not clean_path: clean_path = "/"

        if clean_path == "/api/settings":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(settings._values).encode())
            return

        if clean_path == "/api/status":
            try:
                from database import get_db
                from models import File
                with get_db() as db_session:
                    active_count = db_session.query(File).filter(File.upload_status == "In Progress").count()
                    queued_count = db_session.query(File).filter(File.upload_status == "Queued").count()
                    uploads_active = (active_count + queued_count) > 0
                    state["uploads_active"] = uploads_active
            except Exception:
                active_count = 0
                queued_count = 0
                uploads_active = state.get("uploads_active", False)

            status_payload = {
                **state,
                "uploads_active": uploads_active,
                "active_count": active_count,
                "queued_count": queued_count
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status_payload).encode("utf-8"))
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

        if clean_path == "/api/upload-summary":
            # Public, anonymised aggregate stats - no filenames or account info
            try:
                from database import get_db
                from models import File
                with get_db() as db_session:
                    active = db_session.query(File).filter(File.upload_status == "In Progress").all()
                    queued = db_session.query(File).filter(File.upload_status == "Queued").all()
                    all_active = active + queued

                    active_count = len(active)
                    queued_count = len(queued)
                    total_bytes = sum(int(f.l_folder_size or 0) for f in all_active)

                    # Best-effort ETA from active uploads
                    total_eta_s = None
                    eta_samples = []
                    for f in active:
                        eta_raw = getattr(f, "upload_eta", None)
                        if eta_raw and str(eta_raw).strip() not in ("", "0", "None", "N/A"):
                            try:
                                eta_samples.append(float(eta_raw))
                            except (ValueError, TypeError):
                                pass
                    if eta_samples:
                        total_eta_s = max(eta_samples)

                    def _fmt(b):
                        s = float(b or 0)
                        for u in ['B','KB','MB','GB','TB']:
                            if s < 1024.0 or u == 'TB': return f"{s:.1f} {u}"
                            s /= 1024.0

                    def _fmt_eta(secs):
                        if secs is None: return None
                        secs = int(secs)
                        h, rem = divmod(secs, 3600)
                        m, s2 = divmod(rem, 60)
                        if h: return f"{h}h {m}m"
                        if m: return f"{m}m {s2}s"
                        return f"{s2}s"

                    payload = {
                        "active_count": active_count,
                        "queued_count": queued_count,
                        "total_count": active_count + queued_count,
                        "total_bytes": total_bytes,
                        "total_size": _fmt(total_bytes),
                        "eta_seconds": total_eta_s,
                        "eta_display": _fmt_eta(total_eta_s),
                        "uploads_active": (active_count + queued_count) > 0,
                    }
            except Exception as e:
                payload = {"error": str(e), "uploads_active": False, "total_count": 0}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return


        if is_static or clean_path in public_paths:
            return super().do_GET()

        if clean_path in restricted_paths:
            if settings.get("app_password") and not state["authenticated"]:
                print(f"Access blocked to {self.path}, not authenticated")
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

                if not isinstance(status, int):
                    try:
                        status = int(status)
                    except (ValueError, TypeError):
                        if isinstance(payload, dict) and payload.get("status") in ("error", "failed"):
                            status = 400
                        else:
                            status = 200

                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

                if isinstance(payload, dict):
                    self.wfile.write(json.dumps(payload).encode())
                else:
                    self.wfile.write(json.dumps({"status": 500, "message": str(payload)}).encode())

            except (BrokenPipeError, ConnectionResetError):
                # Client closed socket connection early (e.g. refreshed or navigated away)
                pass
            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON payload")
            except Exception as e:
                self.send_error_response(500, f"Unexpected error: {str(e)}")

        elif self.path == "/api/upload-pdf":
            if settings.get("app_password") and not state["authenticated"]:
                self.send_error_response(401, "Not authenticated")
                return

            content_length = int(self.headers.get('Content-Length', 0))
            content_type = self.headers.get("Content-Type", "")

            if "multipart/form-data" in content_type:
                import re
                import tempfile
                boundary_match = re.search(r'boundary=([^;\s]+)', content_type)
                if boundary_match:
                    boundary = boundary_match.group(1).encode('utf-8')
                    body = self.rfile.read(content_length)

                    parts = body.split(b'--' + boundary)
                    file_content = None

                    for part in parts:
                        if b'filename="' in part:
                            header_end = part.find(b'\r\n\r\n')
                            if header_end != -1:
                                file_content = part[header_end+4:-2]
                                break

                    if file_content:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(file_content)
                            tmp_path = tmp.name

                        try:
                            result = self.run_command("account_bulk_verify", tmp_path)

                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)

                            if isinstance(result, tuple) and len(result) == 2:
                                payload, status = result
                            else:
                                payload = result
                                status = 200

                            self.send_response(status)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps(payload).encode())
                        except Exception as e:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                            self.send_error_response(500, f"Error processing uploaded PDF: {str(e)}")
                    else:
                        self.send_error_response(400, "No file found in upload.")
                else:
                    self.send_error_response(400, "No multipart boundary found.")
            else:
                self.send_error_response(400, "Content-Type must be multipart/form-data")

    def run_command(self, command, args=None):
        if ":" in command:
            command_name, _, _ = command.partition(":")
        else:
            command_name = command

        command_path = self._resolve_command_path(command_name)
        if not command_path or not os.path.exists(command_path):
            return {"status": 400, "message": f"Unknown command: {command_name}"}, 400

        try:
            module = self._load_command_module(command_name, command_path)

            if hasattr(module, "run"):
                return module.run(args)
            else:
                return {"status": 500, "message": f"{command_name} does not define a run() function."}
        except Exception as e:
            return {"status": 500, "message": f"Command execution error: {str(e)}"}

    def _resolve_command_path(self, command_name):
        """Resolve a command name to its file path, caching the result so we
        don't have to walk utils/commands on every single request."""
        cached = _COMMAND_PATH_CACHE.get(command_name)
        if cached and os.path.exists(cached):
            return cached

        commands_root = os.path.join(os.getcwd(), "utils", "commands")
        for root, dirs, files in os.walk(commands_root):
            if f"{command_name}.py" in files:
                command_path = os.path.join(root, f"{command_name}.py")
                with _COMMAND_CACHE_LOCK:
                    _COMMAND_PATH_CACHE[command_name] = command_path
                return command_path

        return None

    def _load_command_module(self, command_name, command_path):
        """Load (and cache) a command module through Python's normal import
        system rather than exec'ing the file fresh on every request.

        This matters for more than speed: command modules like
        transfer_upload.py keep module-level state (e.g. the active-worker
        count and in-flight file/account sets) that other modules reference
        via a regular `import`. Loading a *separate* module object per
        request - as a raw file-exec does - silently disconnects that
        dispatched-via-HTTP instance from the one everything else shares,
        so bookkeeping like the concurrent-upload cap can't actually see
        what's in flight. Routing through importlib.import_module() keeps
        one canonical module object in sys.modules, same as any other
        import in the codebase. We still pick up on-disk edits (no restart
        needed) by reloading in place when the file's mtime changes.
        """
        rel_path = os.path.relpath(command_path, os.getcwd())
        dotted_name = os.path.splitext(rel_path)[0].replace(os.sep, ".")
        mtime = os.path.getmtime(command_path)

        with _COMMAND_CACHE_LOCK:
            existing = sys.modules.get(dotted_name)
            if existing is not None and _COMMAND_MODULE_MTIME.get(dotted_name) == mtime:
                return existing

            module = importlib.reload(existing) if existing is not None else importlib.import_module(dotted_name)
            _COMMAND_MODULE_MTIME[dotted_name] = mtime

        return module

    def send_error_response(self, status, message):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": status, "message": message}).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"Error sending HTTP error response: {e}")

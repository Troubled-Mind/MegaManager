from utils.config import settings, state

_FALLBACK_MAX = 5
_HARD_MAX = 10
_HARD_MIN = 1

def _get_max_attempts():
    try:
        val = int(settings.get("login_max_attempts", _FALLBACK_MAX))
        return max(_HARD_MIN, min(_HARD_MAX, val))
    except (TypeError, ValueError):
        return _FALLBACK_MAX

def run(args=None):
    # Hard lockout - only cleared by restarting the server
    if state.get("login_locked"):
        return {
            "status": 403,
            "message": "Dashboard is locked. Please restart the server to regain access."
        }, 403

    if not isinstance(args, dict):
        return {"status": 400, "message": "Invalid login data"}, 400

    expected = settings.get("app_password", "")
    provided = args.get("password", "")

    if not expected:
        return {"status": 403, "message": "Password protection not enabled"}, 403

    if provided == expected:
        state["login_attempts"] = 0
        state["authenticated"] = True
        return {"status": 200, "message": "Login successful"}, 200

    state["login_attempts"] = state.get("login_attempts", 0) + 1
    max_attempts = _get_max_attempts()

    if state["login_attempts"] >= max_attempts:
        state["login_locked"] = True
        print("SECURITY Dashboard locked after too many failed login attempts. Restart the server to unlock.")
        return {
            "status": 403,
            "message": "Dashboard is locked. Please restart the server to regain access."
        }, 403

    return {"status": 401, "message": "Incorrect password"}, 401

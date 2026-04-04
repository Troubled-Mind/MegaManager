from utils.config import settings, state

def run(args=None):
    global authenticated

    if not isinstance(args, dict):
        return {"status": 400, "message": "Invalid login data"}, 400

    expected = settings.get("app_password", "")
    provided = args.get("password", "")

    if not expected:
        return {"status": 403, "message": "Password protection not enabled"}, 403

    if provided == expected:
        state["authenticated"] = True
        return {"status": 200, "message": "Login successful"}, 200
    else:
        return {"status": 401, "message": "Incorrect password"}, 401

from utils.config import state

def run(args=None):
    progress = state.get("verify_progress", {"current": 0, "total": 0, "message": "Not running", "done": True})
    return {
        "status": 200,
        "is_running": state.get("verify_running", False),
        "current": progress.get("current", 0),
        "total": progress.get("total", 0),
        "message": progress.get("message", ""),
        "done": progress.get("done", True)
    }

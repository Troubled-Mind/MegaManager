import json
from utils.config import settings

def run(args=None):
    try:
        local_paths_raw = settings.get("local_paths", [])
        if isinstance(local_paths_raw, str):
            try:
                local_paths = json.loads(local_paths_raw)
            except Exception:
                local_paths = [local_paths_raw] if local_paths_raw else []
        elif isinstance(local_paths_raw, list):
            local_paths = local_paths_raw
        else:
            local_paths = []

        from utils.stats_cache import get_cached_files, get_cached_stats
        return {
            "status": 200,
            "files": get_cached_files(),
            "local_paths": local_paths,
            "stats": get_cached_stats()
        }

    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}

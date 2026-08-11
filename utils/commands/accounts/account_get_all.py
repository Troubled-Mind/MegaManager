def run(args=None):
    try:
        from utils.stats_cache import get_cached_accounts, get_cached_stats
        return {
            "status": 200,
            "accounts": get_cached_accounts(),
            "stats": get_cached_stats()
        }
    except Exception as e:
        return {"status": 500, "message": f"Database error: {str(e)}"}

import json
import threading
from datetime import datetime, timezone
from database import get_db
from models import File, MegaAccount, Setting

_STATS_LOCK = threading.Lock()
_STATS_CACHE = None

_FILES_LOCK = threading.Lock()
_FILES_CACHE = None

_ACCOUNTS_LOCK = threading.Lock()
_ACCOUNTS_CACHE = None

def _safe_to_int(val):
    if not val:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

def compute_and_cache_stats():
    """Recalculate storage stats across files and accounts and update the cache."""
    global _STATS_CACHE

    try:
        with get_db() as session:
            # Query files
            files = session.query(File.l_folder_size, File.m_folder_size, File.l_path, File.m_path).all()
            total_local = 0
            total_cloud = 0
            synced_count = 0
            total_files = len(files)

            for l_size, m_size, l_path, m_path in files:
                total_local += _safe_to_int(l_size)
                total_cloud += _safe_to_int(m_size)
                if l_path and m_path:
                    synced_count += 1

            # Query accounts
            accounts = session.query(MegaAccount.used_quota, MegaAccount.total_quota).all()
            total_used = 0
            total_capacity = 0
            total_accounts = len(accounts)

            for used_q, total_q in accounts:
                total_used += _safe_to_int(used_q)
                total_capacity += _safe_to_int(total_q)

            total_available = max(0, total_capacity - total_used)

            stats = {
                "total_local_size": total_local,
                "total_cloud_size": total_cloud,
                "total_files": total_files,
                "synced_files": synced_count,
                "cloud_capacity": total_capacity,
                "cloud_used": total_used,
                "cloud_available": total_available,
                "total_accounts": total_accounts,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            with _STATS_LOCK:
                _STATS_CACHE = stats

            # Persist to database settings
            try:
                setting = session.query(Setting).filter_by(key="cached_storage_stats").first()
                if setting:
                    setting.value = json.dumps(stats)
                else:
                    session.add(Setting(key="cached_storage_stats", value=json.dumps(stats)))
                session.commit()
            except Exception as e:
                print(f"WARNING Could not persist cached stats to Setting: {e}")

            print(f"INFO Storage stats refreshed: {total_local} bytes local, {total_cloud} bytes cloud across {total_files} files.")
            return stats

    except Exception as e:
        print(f"ERROR Failed to compute storage stats: {e}")
        with _STATS_LOCK:
            if _STATS_CACHE is not None:
                return _STATS_CACHE
            return {
                "total_local_size": 0,
                "total_cloud_size": 0,
                "total_files": 0,
                "synced_files": 0,
                "cloud_capacity": 0,
                "cloud_used": 0,
                "cloud_available": 0,
                "total_accounts": 0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

def get_cached_stats(auto_compute_if_missing=True):
    """Retrieve the cached stats in O(1) time."""
    global _STATS_CACHE

    with _STATS_LOCK:
        if _STATS_CACHE is not None:
            return dict(_STATS_CACHE)

    # Try loading from DB Setting
    try:
        with get_db() as session:
            setting = session.query(Setting).filter_by(key="cached_storage_stats").first()
            if setting and setting.value:
                stats = json.loads(setting.value)
                with _STATS_LOCK:
                    _STATS_CACHE = stats
                return dict(stats)
    except Exception as e:
        print(f"WARNING Could not load cached stats from DB Setting: {e}")

    if auto_compute_if_missing:
        return compute_and_cache_stats()

    return {
        "total_local_size": 0,
        "total_cloud_size": 0,
        "total_files": 0,
        "synced_files": 0,
        "cloud_capacity": 0,
        "cloud_used": 0,
        "cloud_available": 0,
        "total_accounts": 0,
        "updated_at": None,
    }

def compute_and_cache_files():
    """Recalculate the full files list (joined with account info) and update the cache."""
    global _FILES_CACHE

    try:
        with get_db() as session:
            rows = session.query(File, MegaAccount).outerjoin(MegaAccount, File.m_account_id == MegaAccount.id).all()

            files = []
            for file, account in rows:
                files.append({
                    "id": file.id,
                    "l_path": file.l_path,
                    "l_folder_name": file.l_folder_name,
                    "l_folder_size": file.l_folder_size,
                    "m_path": file.m_path,
                    "m_folder_name": file.m_folder_name,
                    "m_folder_size": file.m_folder_size,
                    "m_sharing_link": file.m_sharing_link,
                    "m_sharing_link_expiry": file.m_sharing_link_expiry,
                    "m_account_id": file.m_account_id,
                    "cloud_email": account.email if account else None,
                    "pro_account": bool(account.is_pro_account) if account else False,
                    "is_local": bool(file.l_path),
                    "is_cloud": bool(file.m_path),
                    "upload_status": file.upload_status,
                    "upload_progress": file.upload_progress,
                })

            with _FILES_LOCK:
                _FILES_CACHE = files
            return files

    except Exception as e:
        print(f"ERROR Failed to compute files cache: {e}")
        with _FILES_LOCK:
            if _FILES_CACHE is not None:
                return _FILES_CACHE
        return []

def get_cached_files(auto_compute_if_missing=True):
    """Retrieve the cached files list in O(1) time."""
    with _FILES_LOCK:
        if _FILES_CACHE is not None:
            return list(_FILES_CACHE)

    if auto_compute_if_missing:
        return compute_and_cache_files()

    return []

def compute_and_cache_accounts():
    """Recalculate the full accounts list and update the cache."""
    global _ACCOUNTS_CACHE

    try:
        with get_db() as session:
            accounts_data = session.query(MegaAccount).all()

            accounts = []
            for acc in accounts_data:
                accounts.append({
                    "id": acc.id,
                    "email": acc.email,
                    "password": acc.password,
                    "is_pro": bool(acc.is_pro_account),
                    "used_quota": int(acc.used_quota) if acc.used_quota else 0,
                    "total_quota": int(acc.total_quota) if acc.total_quota else 0,
                    "last_login": acc.last_login.isoformat() if acc.last_login else "",
                    "status": acc.status
                })

            with _ACCOUNTS_LOCK:
                _ACCOUNTS_CACHE = accounts
            return accounts

    except Exception as e:
        print(f"ERROR Failed to compute accounts cache: {e}")
        with _ACCOUNTS_LOCK:
            if _ACCOUNTS_CACHE is not None:
                return _ACCOUNTS_CACHE
        return []

def get_cached_accounts(auto_compute_if_missing=True):
    """Retrieve the cached accounts list in O(1) time."""
    with _ACCOUNTS_LOCK:
        if _ACCOUNTS_CACHE is not None:
            return list(_ACCOUNTS_CACHE)

    if auto_compute_if_missing:
        return compute_and_cache_accounts()

    return []

def refresh_all_caches():
    """Recompute stats, files, and accounts caches together."""
    compute_and_cache_stats()
    compute_and_cache_files()
    compute_and_cache_accounts()

def invalidate_and_refresh_async():
    """Trigger an async recalculation of all caches (stats, files, accounts) in a background thread."""
    t = threading.Thread(target=refresh_all_caches, daemon=True)
    t.start()
    return t

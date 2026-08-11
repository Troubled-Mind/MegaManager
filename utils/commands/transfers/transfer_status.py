import json
import time
import re
from database import get_db
from models import File
from utils.config import state, get_transfer_logs, clear_transfer_logs
from utils.commands.transfers.transfer_upload import ensure_upload_worker

def _parse_size_bytes(val_str, unit_str):
    try:
        val = float(val_str)
        unit = unit_str.strip().upper()
        multiplier = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4
        }.get(unit, 1)
        return val * multiplier
    except (ValueError, TypeError):
        return 0

def _parse_speed_string(speed_str):
    """Parse a per-file speed string like '12.3 MB/s' (as reported by rclone
    and stored on File.upload_speed) into bytes/sec."""
    if not speed_str:
        return 0.0
    m = re.match(r'([\d.]+)\s*([KMGT]?B)/s', str(speed_str).strip(), re.IGNORECASE)
    if not m:
        return 0.0
    return _parse_size_bytes(m.group(1), m.group(2))

def run(args=None):
    if args == "clear_logs":
        clear_transfer_logs()
        return {"status": 200, "message": "Transfer logs cleared."}

    try:
        with get_db() as session:
            from sqlalchemy import or_
            uploads = session.query(File).filter(
                or_(
                    File.upload_status.in_(["In Progress", "Queued", "Stopped"]),
                    File.upload_status.like("Failed%")
                )
            ).all()

            ongoing_uploads = []
            has_pending_or_active = False
            has_in_progress = False
            queued_total_bytes = 0
            total_speed_bps = 0.0

            # Sort by ID to process queue in order
            uploads = sorted(uploads, key=lambda x: x.id)
            account_future_usage = {}

            for upload in uploads:
                if upload.upload_status in ("In Progress", "Queued"):
                    has_pending_or_active = True
                if upload.upload_status == "In Progress":
                    has_in_progress = True
                    total_speed_bps += _parse_speed_string(upload.upload_speed)
                if upload.upload_status in ("Queued", "Pending"):
                    try:
                        queued_total_bytes += int(upload.l_folder_size or 0)
                    except (ValueError, TypeError):
                        pass

                acc_email = "Unknown"
                post_upload_pct = 0.0
                if upload.account:
                    acc = upload.account
                    acc_email = acc.email
                    if acc.id not in account_future_usage:
                        try:
                            account_future_usage[acc.id] = {
                                "used": float(acc.used_quota or 0),
                                "total": float(acc.total_quota or 0)
                            }
                        except (ValueError, TypeError):
                            account_future_usage[acc.id] = {"used": 0.0, "total": 0.0}

                    file_size = 0
                    try:
                        file_size = float(upload.l_folder_size or 0)
                    except (ValueError, TypeError):
                        pass

                    account_future_usage[acc.id]["used"] += file_size
                    tot = account_future_usage[acc.id]["total"]
                    us = account_future_usage[acc.id]["used"]
                    if tot > 0:
                        post_upload_pct = min(100.0, (us / tot) * 100.0)

                ongoing_uploads.append({
                    "file_id": upload.id,
                    "file_name": upload.l_folder_name,
                    "folder_size": upload.l_folder_size,
                    "progress": upload.upload_progress,
                    "upload_status": upload.upload_status,
                    "speed": upload.upload_speed,
                    "eta": upload.upload_eta,
                    "account_email": acc_email,
                    "post_upload_pct": round(post_upload_pct, 1)
                })

            if has_pending_or_active:
                ensure_upload_worker()

            speed_bps = total_speed_bps
            speed_mb_s = speed_bps / (1024 * 1024)
            speed_mbps = (speed_bps * 8) / 1_000_000

            def _fmt_bytes(size):
                try:
                    s = float(size or 0)
                    for u in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
                        if s < 1024.0 or u == 'PB':
                            return f"{s:.2f} {u}" if u not in ('B', 'KB') else f"{int(s)} {u}"
                        s /= 1024.0
                except Exception:
                    return "0 B"

            return {
                "status": 200,
                "uploads": ongoing_uploads,
                "is_calculating": bool(state.get("batch_calculating", False)),
                "calculating_message": state.get("batch_status", "Calculating file distribution and free quota..."),
                "logs": get_transfer_logs(80),
                "speed_bps": speed_bps,
                "speed_mb_s": round(speed_mb_s, 2),
                "speed_mbps": round(speed_mbps, 1),
                "formatted_speed": f"{speed_mb_s:.2f} MB/s",
                "formatted_mbps": f"({speed_mbps:.1f} Mbps)",
                "speed_display": f"{speed_mb_s:.2f} MB/s ({speed_mbps:.1f} Mbps)" if speed_bps > 1000 else "0.00 MB/s (0.0 Mbps)",
                "queued_total_bytes": queued_total_bytes,
                "queued_total_size": _fmt_bytes(queued_total_bytes)
            }

    except Exception as e:
        return {"status": 500, "message": f"Error fetching ongoing uploads: {str(e)}"}

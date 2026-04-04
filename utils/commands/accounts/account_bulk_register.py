import time
import urllib.parse
from utils.commands.accounts.account_register import run as register_single

def run(command_args=None):
    """
    Bulk registers a range of MEGA accounts.
    Expected args: "prefix|start_idx|end_idx|domain"
    Example: "contact|1|20|troubledmind.trade" 
    -> contact+1@troubledmind.trade ... contact+20@troubledmind.trade
    """
    if not command_args:
        return {"status": 400, "message": "Usage: prefix|start|end|domain"}, 400
        
    raw_args = command_args[0] if isinstance(command_args, list) else str(command_args)
    if "|" not in raw_args:
        return {"status": 400, "message": "Usage: prefix|start|end|domain (missing separator)"}, 400

    try:
        prefix, start_str, end_str, domain = raw_args.split("|")
        start = int(start_str)
        end = int(end_str)
    except (ValueError, TypeError, IndexError):
        return {"status": 400, "message": "Start and End must be integers and format must be correct."}, 400

    if start > end:
        return {"status": 400, "message": "Start index cannot be greater than End index."}, 400

    count = end - start + 1
    if count > 50:
         return {"status": 400, "message": "Bulk registration limited to 50 accounts per request."}, 400

    results = []
    success_count = 0
    fail_count = 0

    print(f"🚀 Starting bulk registration for {count} accounts...")

    for i in range(start, end + 1):
        separator = "+" if "+" not in prefix else ""
        email = f"{prefix}{separator}{i}@{domain}"
        print(f"▶ [{i - start + 1}/{count}] Registering {email}...")
        
        # We call the existing register_single logic
        # Note: account_register.run(args) expects [encoded_email]
        res, status = register_single([urllib.parse.quote(email)])
        
        if status == 200:
            success_count += 1
            results.append({"email": email, "status": "Success"})
        else:
            fail_count += 1
            results.append({"email": email, "status": "Failed", "message": res.get("message")})
        
        # Small sleep to be somewhat polite to the system (and avoid potential race conditions on local files)
        time.sleep(1)

    return {
        "status": 200 if success_count > 0 else 500,
        "message": f"Bulk registration finished. Success: {success_count}, Failed: {fail_count}",
        "results": results
    }, 200

import re
import subprocess
import threading
from collections import defaultdict

from database import get_db
from models import File, MegaAccount
from utils.config import cmd, settings, add_transfer_log
from utils.mega_session import mega_session
from utils.commands.shared import strftime_to_regex


def run(args=None):
    """Move non-conforming cloud files into a wrapper folder matching their local
    release folder name, in a background thread."""
    thread = threading.Thread(target=reorg_cloud_files_in_background)
    thread.start()

    return {
        "status": 200,
        "message": "Cloud reorganization started in the background."
    }


def _date_token(name):
    """Extract the date-token substring from a name using the configured date formats."""
    full_fmt = settings.get("date_format_full") or ""
    month_fmt = settings.get("date_format_month") or ""
    year_fmt = settings.get("date_format_year") or ""

    patterns = [strftime_to_regex(f) for f in (full_fmt, month_fmt, year_fmt) if f]
    if not patterns:
        return None

    combined = re.compile(r"|".join(patterns))
    match = combined.search(name)
    if not match:
        return None

    token = match.group(0)
    # Extend to include a trailing "(N)" disambiguator if present. A bare date/month
    # token collides across genuinely different releases that share an approximate or
    # unknown exact date (e.g. "[2022-05-xx (1)]".."(4)" are four distinct dates in the
    # same library) - pulling in the disambiguator keeps the sweep scoped to one release.
    rest = name[match.end():]
    disambiguator = re.match(r"\s*\(\d+\)", rest)
    if disambiguator:
        token += disambiguator.group(0)
    return token


_ENCORA_ID_RE = re.compile(r"\{e-\d+\}")


def _release_identity(name):
    """Extract the encora ID and uploader ("master") name from a release name
    like '[2025-02-10] If_Then ~ TroubledMind {e-2010240}' - both are unique
    per release and used to tell apart two different releases that happen to
    share the same date (e.g. two recordings of the same show uploaded the
    same night by different people)."""
    id_match = _ENCORA_ID_RE.search(name)
    encora_id = id_match.group(0) if id_match else None

    if encora_id:
        up_match = re.search(r"~\s*(.+?)\s*" + re.escape(encora_id), name)
    else:
        up_match = re.search(r"~\s*(.+?)\s*$", name)

    uploader = None
    if up_match:
        uploader = re.sub(r"\s*[\[\{].*$", "", up_match.group(1)).strip() or None

    return encora_id, uploader


def _is_same_release(target_name, candidate_name):
    """True only if candidate_name carries the target's own encora ID or
    uploader name - not just a matching date, which two unrelated releases
    can share. Without this, the sibling sweep below could merge two
    different people's recordings of the same show into one folder (as
    happened before this check existed: two If_Then recordings uploaded the
    same date got tangled together into a single corrupted folder).
    """
    encora_id, uploader = _release_identity(target_name)
    if encora_id and encora_id in candidate_name:
        return True
    if uploader and uploader in candidate_name:
        return True
    return False


def reorg_cloud_files_in_background():
    """Find linked File rows whose cloud item isn't nested inside a folder named after
    the matched local release folder, and move it (plus same-release siblings) there."""
    print("Starting background cloud reorganization...")
    moved = 0
    failed = 0

    with get_db() as session:
        candidates = session.query(File).filter(
            File.l_folder_name != None,
            File.m_folder_name != None,
            File.m_path != None
        ).all()

        # No "already done" pre-filter here: m_folder_name already matching l_folder_name
        # doesn't necessarily mean the wrapper folder exists yet with real content in it -
        # it can also be a stale/phantom link (no real object at that exact path) that
        # still needs the sibling sweep below to pull in the real flat legacy files. Every
        # step in the loop is idempotent (mkdir -p, the self-move guard, and the sweep all
        # no-op safely if there's nothing left to do), so it's safe to always reprocess.
        by_account = defaultdict(list)
        for f in candidates:
            by_account[f.m_account_id].append(f)

        for account_id, files in by_account.items():
            account = session.query(MegaAccount).filter(MegaAccount.id == account_id).first()
            if not account:
                failed += len(files)
                continue

            # Holds the process-wide MEGAcmd session lock for this account's
            # whole batch of mkdir/mv/ls calls, so a concurrent upload/sync
            # job can't log in as a different account mid-loop and redirect
            # these filesystem operations to the wrong account.
            with mega_session(account.email, account.password) as logged_in:
                if not logged_in:
                    add_transfer_log(f"Reorg: failed to log into {account.email}, skipping {len(files)} file(s)", "ERROR")
                    failed += len(files)
                    continue  # move on to the next account instead of aborting the whole batch

                for f in files:
                    try:
                        old_full_path = f"{f.m_path}/{f.m_folder_name}"
                        new_folder = f"{f.m_path}/{f.l_folder_name}"

                        mkdir_res = subprocess.run(
                            [cmd("mega-mkdir"), "-p", new_folder],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                        )
                        if mkdir_res.returncode != 0 and "already exists" not in (mkdir_res.stderr or "").lower():
                            raise Exception(f"mega-mkdir failed: {mkdir_res.stderr.strip() or mkdir_res.stdout.strip()}")

                        if old_full_path == new_folder:
                            # The cloud item's current name already equals the local folder
                            # name (a stale/phantom link with no matching real object at that
                            # exact path, or an already-correct item). Moving it would be a
                            # self-move (mega-mv X into X/), which corrupts MEGA by nesting the
                            # folder inside itself. Nothing to move - mkdir above already
                            # ensured the wrapper folder exists; the sibling sweep below pulls
                            # in the real content.
                            add_transfer_log(f"Reorg: #{f.id} already named correctly ({f.m_folder_name}) - skipping self-move, sweeping siblings only", "INFO")
                        else:
                            mv_res = subprocess.run(
                                [cmd("mega-mv"), old_full_path, new_folder + "/"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                            )
                            if mv_res.returncode != 0:
                                raise Exception(f"mega-mv failed: {mv_res.stderr.strip() or mv_res.stdout.strip()}")

                        # Sweep sibling files left in the same source directory that share the
                        # same date-token (e.g. a legacy sidecar .txt uploaded alongside the video)
                        # AND carry this release's own encora ID or uploader name - the date alone
                        # isn't unique (two different people's recordings of the same show can
                        # share a date), so date-only matching can merge unrelated releases
                        # together into one corrupted folder.
                        token = _date_token(f.m_folder_name)
                        if token:
                            ls_res = subprocess.run(
                                [cmd("mega-ls"), f.m_path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                            )
                            if ls_res.returncode == 0:
                                for line in ls_res.stdout.splitlines():
                                    sibling_name = line.strip()
                                    if not sibling_name or sibling_name == f.m_folder_name:
                                        continue
                                    if token in sibling_name and _is_same_release(f.m_folder_name, sibling_name):
                                        sib_res = subprocess.run(
                                            [cmd("mega-mv"), f"{f.m_path}/{sibling_name}", new_folder + "/"],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                                        )
                                        if sib_res.returncode == 0:
                                            add_transfer_log(f"Reorg: swept sibling '{sibling_name}' into {new_folder}", "INFO")

                        # m_path stays the same (it's already the parent directory the wrapper
                        # folder now lives directly under) - only the item's own name changes.
                        # Setting m_path to new_folder here was the bug: full_path is built
                        # everywhere else in this codebase as m_path + "/" + m_folder_name, so
                        # that would have addressed a nonexistent doubly-nested path.
                        f.m_folder_name = f.l_folder_name
                        session.add(f)
                        session.commit()
                        moved += 1
                        add_transfer_log(f"Reorg: moved #{f.id} into {new_folder}", "SUCCESS")

                    except Exception as e:
                        session.rollback()
                        failed += 1
                        add_transfer_log(f"Reorg: failed for #{f.id} ({f.m_folder_name}): {e}", "ERROR")

    print(f"Cloud reorganization done. {moved} moved, {failed} failed.")
    add_transfer_log(f"Cloud reorganization done: {moved} moved, {failed} failed.", "INFO")

    from utils.stats_cache import invalidate_and_refresh_async
    invalidate_and_refresh_async()

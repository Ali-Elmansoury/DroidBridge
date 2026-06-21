"""Plain-Python Backup Manager GUI operations (sub-phase 6.4) — no Qt imports."""

import time
from datetime import datetime, timezone

from droidbridge.modules import backup_manager as backup_module
from droidbridge.modules import transfer as transfer_module


def list_profiles():
    profiles = backup_module.load_profiles(backup_module.DEFAULT_PROFILES_PATH)
    return list(profiles.values())


def save_profile(name, sources, dest, conflict, excludes):
    profile = backup_module.BackupProfile(
        name=name, sources=list(sources), dest=dest, conflict=conflict, excludes=list(excludes),
    )
    backup_module.save_profile(backup_module.DEFAULT_PROFILES_PATH, profile)


def remove_profile(name):
    return backup_module.delete_profile(backup_module.DEFAULT_PROFILES_PATH, name)


def get_profile(name):
    return backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, name)


def run_backup(client, serial, profile_name, no_verify, progress_callback=None):
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, profile_name)
    if profile is None:
        raise ValueError(f"Profile {profile_name!r} not found.")

    plan = backup_module.plan_backup(client, serial, profile)
    relevant = [i for i in plan.items if i.action != transfer_module.ACTION_SKIP_CONFLICT]
    file_count = len(relevant)
    total_bytes = sum(i.size for i in relevant)

    done_files = 0
    failed = 0
    duration = 0.0
    if plan.to_transfer:
        start = time.monotonic()
        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=progress_callback)
        duration = time.monotonic() - start
        done_files = progress.done_files
        failed = len(progress.failed)

    verified = None
    if not no_verify:
        verified = transfer_module.verify_pull(plan).ok

    backup_module.append_history(
        backup_module.DEFAULT_HISTORY_PATH,
        backup_module.BackupRecord(
            profile=profile.name,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            file_count=file_count,
            total_bytes=total_bytes,
            duration_seconds=duration,
            destination=profile.dest,
            verified=bool(verified),
        ),
    )
    return {"done": done_files, "total": plan.total_files, "failed": failed, "verified": verified}


def run_verify(profile_name):
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, profile_name)
    if profile is None:
        raise ValueError(f"Profile {profile_name!r} not found.")

    history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
    record = backup_module.last_backup(history, profile_name)
    if record is None:
        raise ValueError(f"No backups recorded for profile {profile_name!r}. Run a backup first.")

    actual_files, actual_bytes = backup_module.measure_destination(record.destination)
    result = transfer_module.VerificationResult(
        expected_files=record.file_count,
        expected_bytes=record.total_bytes,
        actual_files=actual_files,
        actual_bytes=actual_bytes,
    )
    return {
        "ok": result.ok,
        "expected_files": result.expected_files,
        "expected_bytes": result.expected_bytes,
        "actual_files": result.actual_files,
        "actual_bytes": result.actual_bytes,
    }


def get_history(profile_name=None, max_age_days=7):
    history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
    if profile_name is None:
        return {"records": history, "outdated": None, "comparison": None}

    matches = [r for r in history if r.profile == profile_name]
    outdated = backup_module.is_outdated(history, profile_name, max_age_days)
    comparison = backup_module.compare_backups(history, profile_name)
    return {"records": matches, "outdated": outdated, "comparison": comparison}


def run_restore(client, serial, profile_name, sources, after, before, conflict, no_verify, progress_callback=None):
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, profile_name)
    if profile is None:
        raise ValueError(f"Profile {profile_name!r} not found.")

    targets = backup_module.plan_restore(client, serial, profile, sources=sources or None, conflict=conflict)

    results = []
    for target in targets:
        plan = target.plan
        if after or before:
            plan = backup_module.filter_plan_by_date(plan, after=after, before=before)

        if not plan.to_transfer:
            results.append({"source": target.source, "done": 0, "total": 0, "failed": 0, "verified": None})
            continue

        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=progress_callback)
        verified = None
        if not no_verify:
            verified = transfer_module.verify_push(client, serial, plan, target.remote_dir).ok

        results.append({
            "source": target.source,
            "done": progress.done_files,
            "total": plan.total_files,
            "failed": len(progress.failed),
            "verified": verified,
        })
    return results

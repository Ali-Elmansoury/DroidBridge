"""Module 6 - Backup Manager: profiles, incremental backup, history, and restore."""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from droidbridge.modules import transfer as transfer_module

DEFAULT_DATA_DIR = Path.home() / ".droidbridge"
DEFAULT_PROFILES_PATH = DEFAULT_DATA_DIR / "backup_profiles.json"
DEFAULT_HISTORY_PATH = DEFAULT_DATA_DIR / "backup_history.json"


@dataclass
class BackupProfile:
    """A named backup profile: source folders on the device + a local destination (spec §6.1)."""

    name: str
    sources: list
    dest: str
    conflict: str = transfer_module.CONFLICT_SKIP


def load_profiles(path=DEFAULT_PROFILES_PATH):
    """Load all saved BackupProfiles from `path`, keyed by name. Returns {} if the file doesn't exist."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {name: BackupProfile(**fields) for name, fields in data.items()}


def _write_profiles(path, profiles):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({name: asdict(p) for name, p in profiles.items()}, f, indent=2)


def save_profile(path, profile):
    """Save (or overwrite) `profile` under `path`'s profile store."""
    profiles = load_profiles(path)
    profiles[profile.name] = profile
    _write_profiles(path, profiles)


def get_profile(path, name):
    """Return the BackupProfile named `name`, or None if it doesn't exist."""
    return load_profiles(path).get(name)


def delete_profile(path, name):
    """Delete the profile named `name`. Returns True if it existed, False otherwise."""
    profiles = load_profiles(path)
    if name not in profiles:
        return False
    del profiles[name]
    _write_profiles(path, profiles)
    return True


# Backup execution (spec §6.2)


def plan_backup(client, serial, profile):
    """Build a combined pull plan for all of `profile`'s source folders into `profile.dest`.

    Reuses `transfer_module.plan_pull`'s same-size skip-existing classification
    for incremental backups (only new/changed files are transferred).
    """
    items = []
    for source in profile.sources:
        plan = transfer_module.plan_pull(client, serial, source, profile.dest, conflict=profile.conflict)
        items.extend(plan.items)
    return transfer_module.TransferPlan(direction="pull", items=items)


# Backup verification (spec §6.3)


def find_failed_pull_items(plan):
    """Return items from a pull `plan` whose local copy is missing or the wrong size."""
    relevant = [i for i in plan.items if i.action != transfer_module.ACTION_SKIP_CONFLICT]
    return [i for i in relevant if not (os.path.exists(i.dest) and os.path.getsize(i.dest) == i.size)]


def measure_destination(dest):
    """Walk `dest` and return (file_count, total_bytes) for all files under it (spec §6.3)."""
    file_count = 0
    total_bytes = 0
    for root, _, files in os.walk(dest):
        for fname in files:
            total_bytes += os.path.getsize(os.path.join(root, fname))
            file_count += 1
    return file_count, total_bytes


# Backup history (spec §6.4)


@dataclass
class BackupRecord:
    """One logged backup run: when, which profile, how much, how long, and whether it verified."""

    profile: str
    timestamp: str
    file_count: int
    total_bytes: int
    duration_seconds: float
    destination: str
    verified: bool


def load_history(path=DEFAULT_HISTORY_PATH):
    """Load the backup history log from `path`. Returns [] if the file doesn't exist."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [BackupRecord(**fields) for fields in data]


def append_history(path, record):
    """Append `record` to the backup history log at `path`."""
    path = Path(path)
    history = load_history(path)
    history.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in history], f, indent=2)


def last_backup(history, profile_name):
    """Return the most recent BackupRecord for `profile_name`, or None if there isn't one."""
    matches = [r for r in history if r.profile == profile_name]
    if not matches:
        return None
    return max(matches, key=lambda r: r.timestamp)


def is_outdated(history, profile_name, max_age_days, now=None):
    """Return True if `profile_name` has never been backed up, or its last backup is older than `max_age_days`."""
    record = last_backup(history, profile_name)
    if record is None:
        return True
    now = now or datetime.now(timezone.utc)
    return now - datetime.fromisoformat(record.timestamp) > timedelta(days=max_age_days)


def compare_backups(history, profile_name):
    """Compare the two most recent backups for `profile_name`.

    Returns a dict with `file_count_delta`/`total_bytes_delta`/`previous`/`latest`,
    or None if fewer than two backups are logged for this profile.
    """
    matches = sorted((r for r in history if r.profile == profile_name), key=lambda r: r.timestamp)
    if len(matches) < 2:
        return None

    previous, latest = matches[-2], matches[-1]
    return {
        "file_count_delta": latest.file_count - previous.file_count,
        "total_bytes_delta": latest.total_bytes - previous.total_bytes,
        "previous": previous,
        "latest": latest,
    }


# Restore (spec §6.5)


@dataclass
class RestoreTarget:
    """A push plan restoring one of a profile's sources from its local backup copy."""

    source: str
    local_path: str
    remote_dir: str
    plan: object


def plan_restore(client, serial, profile, sources=None, conflict=None):
    """Build a per-source push plan restoring `profile.dest` back onto the device.

    Only sources listed in `sources` are restored (default: all of `profile.sources`).
    Each source gets its own `RestoreTarget`, mirroring `plan_backup`'s pull pathing
    in reverse: the local copy at `profile.dest/<basename>` is pushed back to the
    source's parent directory on the device.
    """
    conflict = conflict or profile.conflict
    wanted = set(sources) if sources is not None else set(profile.sources)

    targets = []
    for source in profile.sources:
        if source not in wanted:
            continue
        source_path = PurePosixPath(source.rstrip("/"))
        local_path = os.path.join(profile.dest, source_path.name)
        remote_dir = str(source_path.parent)
        plan = transfer_module.plan_push(client, serial, local_path, remote_dir, conflict=conflict)
        targets.append(RestoreTarget(source=source, local_path=local_path, remote_dir=remote_dir, plan=plan))
    return targets


def filter_plan_by_date(plan, after=None, before=None):
    """Return a copy of a push `plan` containing only items last modified within [`after`, `before`].

    `after`/`before` are `datetime.date` objects (inclusive); `item.source` is the
    local file path for a push plan.
    """
    items = []
    for item in plan.items:
        file_date = datetime.fromtimestamp(os.path.getmtime(item.source)).date()
        if after and file_date < after:
            continue
        if before and file_date > before:
            continue
        items.append(item)
    return transfer_module.TransferPlan(direction=plan.direction, items=items)

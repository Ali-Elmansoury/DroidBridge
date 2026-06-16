"""Module 3 - Smart Transfer Engine: pull/push with progress, conflict
resolution, resume support, and post-transfer verification.
"""

import os
import shlex
import time
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from droidbridge.core.adb import AdbError
from droidbridge.modules import search as search_module

CONFLICT_SKIP = "skip"
CONFLICT_OVERWRITE = "overwrite"
CONFLICT_RENAME = "rename"
CONFLICT_MODES = (CONFLICT_SKIP, CONFLICT_OVERWRITE, CONFLICT_RENAME)

ACTION_COPY = "copy"
ACTION_OVERWRITE = "overwrite"
ACTION_RENAME = "rename"
ACTION_SKIP_EXISTING = "skip_existing"
ACTION_SKIP_CONFLICT = "skip_conflict"

_TRANSFER_ACTIONS = (ACTION_COPY, ACTION_OVERWRITE, ACTION_RENAME)


@dataclass
class TransferItem:
    """A single file to (maybe) transfer, and the action to take for it."""

    source: str
    dest: str
    size: int
    action: str


@dataclass
class FailedTransferItem:
    """A transfer item that failed even after all retries."""

    item: TransferItem
    error: str


@dataclass
class ExtraItem:
    """A file on the destination but not on the source — mirror-mode deletion candidate."""

    path: str
    size: int


@dataclass
class FailedExtraItem:
    """An ExtraItem that could not be deleted."""

    item: ExtraItem
    error: str


@dataclass
class TransferPlan:
    """The full set of items considered for a pull or push, with their actions."""

    direction: str
    items: list
    extra_items: list["ExtraItem"] = field(default_factory=list)

    @property
    def to_transfer(self):
        return [i for i in self.items if i.action in _TRANSFER_ACTIONS]

    @property
    def total_files(self):
        return len(self.to_transfer)

    @property
    def total_bytes(self):
        return sum(i.size for i in self.to_transfer)

    @property
    def already_present(self):
        return [i for i in self.items if i.action == ACTION_SKIP_EXISTING]

    @property
    def conflicts_skipped(self):
        return [i for i in self.items if i.action == ACTION_SKIP_CONFLICT]

    @property
    def extra_files(self):
        return len(self.extra_items)

    @property
    def extra_bytes(self):
        return sum(i.size for i in self.extra_items)


@dataclass
class TransferProgress:
    """Tracks progress of an in-flight transfer (count, bytes, speed, ETA)."""

    total_files: int
    total_bytes: int
    done_files: int = 0
    done_bytes: int = 0
    start_time: float = field(default_factory=time.monotonic)
    failed: list["FailedTransferItem"] = field(default_factory=list)

    @property
    def percent(self):
        if self.total_bytes == 0:
            return 100.0
        return (self.done_bytes / self.total_bytes) * 100.0

    @property
    def elapsed(self):
        return time.monotonic() - self.start_time

    @property
    def speed_bps(self):
        elapsed = self.elapsed
        if elapsed <= 0:
            return 0.0
        return self.done_bytes / elapsed

    @property
    def eta_seconds(self):
        speed = self.speed_bps
        if speed <= 0:
            return None
        return (self.total_bytes - self.done_bytes) / speed


@dataclass
class MirrorResult:
    """Result of execute_mirror: the underlying transfer progress plus extras handling."""

    progress: TransferProgress
    deleted_files: int = 0
    deleted_bytes: int = 0
    failed_deletions: list["FailedExtraItem"] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of comparing the transfer plan against what's actually present."""

    expected_files: int
    expected_bytes: int
    actual_files: int
    actual_bytes: int

    @property
    def ok(self):
        return self.expected_files == self.actual_files and self.expected_bytes == self.actual_bytes


def resolve_conflict_path(dest_path, exists_fn):
    """Return `dest_path`, or if it conflicts, the first `_1`, `_2`, ... variant that doesn't."""
    if not exists_fn(dest_path):
        return dest_path

    base, ext = os.path.splitext(dest_path)
    counter = 1
    while True:
        candidate = f"{base}_{counter}{ext}"
        if not exists_fn(candidate):
            return candidate
        counter += 1


def _stat_remote_path(client, serial, path):
    """Return ('dir', None) or ('file', size) for `path` on the device.

    Raises AdbError if `path` does not exist.
    """
    cmd = (
        f"if [ -d {shlex.quote(path)} ]; then echo DIR; "
        f"else find -L {shlex.quote(path)} -maxdepth 0 -printf '%s'; fi"
    )
    output = client.shell(serial, cmd).strip()
    if output == "DIR":
        return "dir", None
    return "file", int(output)


def _remote_dir_exists(client, serial, path):
    output = client.shell(serial, f"[ -d {shlex.quote(path)} ] && echo DIR || echo NO").strip()
    return output == "DIR"


def _remote_manifest(client, serial, remote_dir):
    """Return {absolute_path: size} for files under `remote_dir`, or {} if it doesn't exist."""
    if not _remote_dir_exists(client, serial, remote_dir):
        return {}
    results = search_module.search_files(client, serial, remote_dir)
    return {r.path: r.size for r in results}


def _local_manifest(local_root):
    """Return {relative_posix_path: size} for files under `local_root`, or {} if it doesn't exist."""
    if not os.path.isdir(local_root):
        return {}
    manifest = {}
    for root, _, files in os.walk(local_root):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, local_root)
            manifest[PurePosixPath(rel.replace(os.sep, "/")).as_posix()] = os.path.getsize(full)
    return manifest


def _classify(source, dest, size, conflict, exists_fn, size_fn):
    if exists_fn(dest):
        if size_fn(dest) == size:
            return TransferItem(source=source, dest=dest, size=size, action=ACTION_SKIP_EXISTING)
        if conflict == CONFLICT_SKIP:
            return TransferItem(source=source, dest=dest, size=size, action=ACTION_SKIP_CONFLICT)
        if conflict == CONFLICT_OVERWRITE:
            return TransferItem(source=source, dest=dest, size=size, action=ACTION_OVERWRITE)
        new_dest = resolve_conflict_path(dest, exists_fn)
        return TransferItem(source=source, dest=new_dest, size=size, action=ACTION_RENAME)

    return TransferItem(source=source, dest=dest, size=size, action=ACTION_COPY)


def plan_pull(client, serial, remote_path, local_dir, conflict=CONFLICT_SKIP):
    """Build a transfer plan for pulling `remote_path` (file or directory) into `local_dir`."""
    if conflict not in CONFLICT_MODES:
        raise ValueError(f"Unknown conflict mode: {conflict!r}; expected one of {CONFLICT_MODES}")

    remote_path = remote_path.rstrip("/") or "/"
    kind, size = _stat_remote_path(client, serial, remote_path)

    items = []
    if kind == "file":
        name = PurePosixPath(remote_path).name
        dest = os.path.join(local_dir, name)
        items.append(_classify(remote_path, dest, size, conflict, os.path.exists, os.path.getsize))
    else:
        results = search_module.search_files(client, serial, remote_path)
        base_name = PurePosixPath(remote_path).name
        for r in results:
            rel = PurePosixPath(r.path).relative_to(remote_path)
            dest = os.path.join(local_dir, base_name, *rel.parts)
            items.append(_classify(r.path, dest, r.size, conflict, os.path.exists, os.path.getsize))

    return TransferPlan(direction="pull", items=items)


def plan_push(client, serial, local_path, remote_dir, conflict=CONFLICT_SKIP):
    """Build a transfer plan for pushing `local_path` (file or directory) to `remote_dir`."""
    if conflict not in CONFLICT_MODES:
        raise ValueError(f"Unknown conflict mode: {conflict!r}; expected one of {CONFLICT_MODES}")

    existing = _remote_manifest(client, serial, remote_dir)
    remote_dir = remote_dir.rstrip("/") or "/"

    items = []
    if os.path.isdir(local_path):
        local_root = local_path.rstrip("/")
        base_name = os.path.basename(local_root)
        for root, _, files in os.walk(local_root):
            for fname in sorted(files):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, local_root)
                rel_parts = PurePosixPath(rel.replace(os.sep, "/")).parts
                dest = "/".join([remote_dir, base_name, *rel_parts])
                size = os.path.getsize(full)
                items.append(_classify_remote(full, dest, size, conflict, existing))
    else:
        name = os.path.basename(local_path)
        dest = "/".join([remote_dir, name])
        size = os.path.getsize(local_path)
        items.append(_classify_remote(local_path, dest, size, conflict, existing))

    return TransferPlan(direction="push", items=items)


def _classify_remote(source, dest, size, conflict, existing):
    if dest in existing:
        if existing[dest] == size:
            return TransferItem(source=source, dest=dest, size=size, action=ACTION_SKIP_EXISTING)
        if conflict == CONFLICT_SKIP:
            return TransferItem(source=source, dest=dest, size=size, action=ACTION_SKIP_CONFLICT)
        if conflict == CONFLICT_OVERWRITE:
            return TransferItem(source=source, dest=dest, size=size, action=ACTION_OVERWRITE)
        new_dest = resolve_conflict_path(dest, lambda p: p in existing)
        return TransferItem(source=source, dest=new_dest, size=size, action=ACTION_RENAME)

    return TransferItem(source=source, dest=dest, size=size, action=ACTION_COPY)


def plan_mirror_pull(client, serial, remote_path, local_dir):
    """Mirror-pull: pull new/changed files from `remote_path` with conflict=overwrite,
    then identify local files under the mirror root not present on the device as extra_items."""
    remote_path = remote_path.rstrip("/") or "/"
    plan = plan_pull(client, serial, remote_path, local_dir, conflict=CONFLICT_OVERWRITE)

    # Only process extra items if this was a directory pull.
    # For directory pulls, the dest includes local_dir/base_name/ as a prefix.
    base_name = PurePosixPath(remote_path).name
    local_root = os.path.join(local_dir, base_name)
    if plan.items and plan.items[0].dest.startswith(local_root + os.sep):
        remote_files = _remote_manifest(client, serial, remote_path)
        remote_rels = {PurePosixPath(p).relative_to(remote_path).as_posix() for p in remote_files}
        for rel, size in _local_manifest(local_root).items():
            if rel not in remote_rels:
                plan.extra_items.append(ExtraItem(path=os.path.join(local_root, rel), size=size))

    return plan


def plan_mirror_push(client, serial, local_path, remote_dir):
    """Mirror-push: push new/changed files from `local_path` with conflict=overwrite,
    then identify remote files under the mirror root not present locally as extra_items."""
    remote_dir_clean = remote_dir.rstrip("/") or "/"
    plan = plan_push(client, serial, local_path, remote_dir, conflict=CONFLICT_OVERWRITE)

    if os.path.isdir(local_path):
        local_root = local_path.rstrip("/")
        base_name = os.path.basename(local_root)
        remote_root = "/".join([remote_dir_clean, base_name])

        local_rels = set()
        for root, _, files in os.walk(local_root):
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, local_root)
                local_rels.add(PurePosixPath(rel.replace(os.sep, "/")).as_posix())

        for path, size in _remote_manifest(client, serial, remote_root).items():
            rel = PurePosixPath(path).relative_to(remote_root).as_posix()
            if rel not in local_rels:
                plan.extra_items.append(ExtraItem(path=path, size=size))

    return plan


def execute_plan(
    client, serial, plan, progress_callback=None, should_cancel=None,
    retry_count=3, retry_delay=1.0, sleep_fn=time.sleep,
):
    """Execute `plan`, pulling/pushing each transferable item.

    Each item is attempted up to retry_count+1 times. Between attempts,
    sleep_fn(retry_delay) is called (tests pass a no-op). If every attempt
    raises AdbError, a FailedTransferItem is appended to progress.failed,
    progress_callback is still called, and the loop continues to the next
    item. retry_count=0 disables retries.

    Calls `progress_callback(progress)` after each file (if given). If
    `should_cancel` is given, it's called with no arguments before each item;
    if it returns a truthy value, the loop stops without transferring that
    item (items already transferred remain on disk/device, and `progress`
    reflects what completed). `should_cancel=None` (the default) preserves
    the previous behavior exactly. Returns the final TransferProgress.
    """
    to_transfer = plan.to_transfer
    progress = TransferProgress(
        total_files=len(to_transfer),
        total_bytes=sum(i.size for i in to_transfer),
    )

    for item in to_transfer:
        if should_cancel is not None and should_cancel():
            break

        attempt = 0
        while True:
            try:
                if plan.direction == "pull":
                    local_dir = os.path.dirname(item.dest)
                    if local_dir:
                        os.makedirs(local_dir, exist_ok=True)
                    client.pull(serial, item.source, item.dest)
                else:
                    remote_dir = item.dest.rsplit("/", 1)[0] or "/"
                    client.shell(serial, f"mkdir -p {shlex.quote(remote_dir)}")
                    client.push(serial, item.source, item.dest)
            except AdbError as exc:
                if attempt >= retry_count:
                    progress.failed.append(FailedTransferItem(item=item, error=str(exc)))
                    if progress_callback:
                        progress_callback(progress)
                    break
                attempt += 1
                sleep_fn(retry_delay)
            else:
                progress.done_files += 1
                progress.done_bytes += item.size
                if progress_callback:
                    progress_callback(progress)
                break

    return progress


def verify_pull(plan):
    """Compare a pull plan's transferred + already-present files against local disk."""
    relevant = [i for i in plan.items if i.action != ACTION_SKIP_CONFLICT]
    expected_files = len(relevant)
    expected_bytes = sum(i.size for i in relevant)

    actual_files = 0
    actual_bytes = 0
    for item in relevant:
        if os.path.exists(item.dest) and os.path.getsize(item.dest) == item.size:
            actual_files += 1
            actual_bytes += item.size

    return VerificationResult(expected_files, expected_bytes, actual_files, actual_bytes)


def verify_push(client, serial, plan, remote_dir):
    """Compare a push plan's transferred + already-present files against the device."""
    relevant = [i for i in plan.items if i.action != ACTION_SKIP_CONFLICT]
    expected_files = len(relevant)
    expected_bytes = sum(i.size for i in relevant)

    existing = _remote_manifest(client, serial, remote_dir)
    actual_files = 0
    actual_bytes = 0
    for item in relevant:
        if existing.get(item.dest) == item.size:
            actual_files += 1
            actual_bytes += item.size

    return VerificationResult(expected_files, expected_bytes, actual_files, actual_bytes)

# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Module 4 - WhatsApp Toolkit: analysis, backup, organization, cleanup, database."""

import calendar
import os
import re
import shlex
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePosixPath

from droidbridge.modules import search as search_module
from droidbridge.modules import transfer as transfer_module

SECTION_RECEIVED = "Received"
SECTION_SENT = "Sent"
SECTION_PRIVATE = "Private"
_SECTION_ORDER = (SECTION_RECEIVED, SECTION_SENT, SECTION_PRIVATE)

# (package, label) - label is also the on-device folder name under both the
# Android 10+ scoped-storage path and the legacy pre-10 path.
WHATSAPP_APPS = (
    ("com.whatsapp", "WhatsApp"),
    ("com.whatsapp.w4b", "WhatsApp Business"),
)


@dataclass
class WhatsAppInstall:
    """A detected WhatsApp or WhatsApp Business install and its media base path."""

    package: str
    label: str
    base_path: str

    @property
    def media_path(self):
        return f"{self.base_path}/Media"


def _candidate_paths():
    candidates = []
    for package, label in WHATSAPP_APPS:
        candidates.append((package, label, f"/sdcard/Android/media/{package}/{label}"))
        candidates.append((package, label, f"/sdcard/{label}"))
    return candidates


def detect_installs(client, serial):
    """Detect installed WhatsApp / WhatsApp Business and their media base paths.

    Checks both the Android 10+ scoped-storage path
    (/sdcard/Android/media/<package>/<label>) and the legacy path
    (/sdcard/<label>) for each app in a single shell call, preferring the
    modern path. Returns a list ordered WhatsApp, then WhatsApp Business.
    """
    candidates = _candidate_paths()
    command = " ; ".join(
        f"[ -d {shlex.quote(path)} ] && echo 1 || echo 0" for _, _, path in candidates
    )
    output = client.shell(serial, command)
    flags = output.split()

    found = {}
    for (package, label, path), flag in zip(candidates, flags):
        if flag == "1" and package not in found:
            found[package] = WhatsAppInstall(package=package, label=label, base_path=path)

    return [found[package] for package, _ in WHATSAPP_APPS if package in found]


# WhatsApp media filenames follow `<TYPE>-YYYYMMDD-WA####.ext` (e.g.
# IMG-20230115-WA0001.jpg, PTT-20210615-WA0002.opus).
_WA_FILENAME_DATE_RE = re.compile(r"-(\d{4})(\d{2})(\d{2})-WA")

# Valid year range for WhatsApp media (spec §4.5) - rejects malformed dates
# such as student IDs/serial numbers mistaken for dates.
_MIN_YEAR = 2009
_MAX_YEAR = 2030


def _parse_date(filename):
    """Parse a `datetime.date` from a WhatsApp-style filename, or None."""
    match = _WA_FILENAME_DATE_RE.search(filename)
    if not match:
        return None

    year, month, day = (int(part) for part in match.groups())
    if not (_MIN_YEAR <= year <= _MAX_YEAR) or not (1 <= month <= 12):
        return None

    try:
        return date(year, month, day)
    except ValueError:
        return None


@dataclass
class MediaFile:
    """A single file found under a WhatsApp install's Media/ folder."""

    path: str
    size: int
    mtime: object
    folder_type: str
    section: str

    @property
    def extension(self):
        return PurePosixPath(self.path).suffix.lstrip(".").lower()

    @property
    def date(self):
        """`datetime.date` parsed from the WhatsApp filename date convention, or None."""
        return _parse_date(PurePosixPath(self.path).name)

    @property
    def year_month(self):
        """"YYYY-MM" string derived from `.date`, or "Unknown" if unparseable."""
        parsed = self.date
        if parsed is None:
            return "Unknown"
        return f"{parsed.year:04d}-{parsed.month:02d}"


def _classify(path, install):
    rel_parts = PurePosixPath(path).relative_to(install.media_path).parts
    if len(rel_parts) == 1:
        # Loose file directly in Media/, not inside any of the type folders.
        return "Other", SECTION_RECEIVED

    folder_type = rel_parts[0]
    prefix = f"{install.label} "
    if folder_type.startswith(prefix):
        folder_type = folder_type[len(prefix) :]

    middle_parts = rel_parts[1:-1]
    if SECTION_SENT in middle_parts:
        section = SECTION_SENT
    elif SECTION_PRIVATE in middle_parts:
        section = SECTION_PRIVATE
    else:
        section = SECTION_RECEIVED

    return folder_type, section


def _is_hidden(rel_parts):
    """True if any path component is dot-prefixed (WhatsApp internal cache/metadata)."""
    return any(part.startswith(".") for part in rel_parts)


def scan_media(client, serial, install):
    """Recursively scan an install's Media/ folder, returning one MediaFile per file.

    Skips dot-prefixed folders/files (e.g. .Statuses, .Shared, .wamocache) -
    these are WhatsApp's internal caches, not the user media covered by
    spec §4.2's folder table.
    """
    results = search_module.search_files(client, serial, install.media_path)

    media_files = []
    for result in results:
        rel_parts = PurePosixPath(result.path).relative_to(install.media_path).parts
        if _is_hidden(rel_parts):
            continue

        folder_type, section = _classify(result.path, install)
        media_files.append(
            MediaFile(
                path=result.path,
                size=result.size,
                mtime=result.mtime,
                folder_type=folder_type,
                section=section,
            )
        )
    return media_files


@dataclass
class FolderSummary:
    """File count and total size for one (folder_type, section) group."""

    folder_type: str
    section: str
    file_count: int
    total_size: int


def summarize_by_folder(media_files):
    """Group media files by (folder_type, section) with file count and total size.

    Results are ordered by folder type (alphabetically), then by section in
    Received/Sent/Private order (matching spec §4.1).
    """
    groups = {}
    for media_file in media_files:
        key = (media_file.folder_type, media_file.section)
        if key not in groups:
            groups[key] = FolderSummary(
                folder_type=media_file.folder_type,
                section=media_file.section,
                file_count=0,
                total_size=0,
            )
        groups[key].file_count += 1
        groups[key].total_size += media_file.size

    return sorted(groups.values(), key=lambda s: (s.folder_type, _SECTION_ORDER.index(s.section)))


@dataclass
class YearMonthSummary:
    """File count and total size for one year-month group (or "Unknown")."""

    year_month: str
    file_count: int
    total_size: int


def summarize_by_year_month(media_files):
    """Group media files by year-month (parsed from filename) with file count and total size.

    Results are ordered chronologically, with "Unknown" (no parseable date) last.
    """
    groups = {}
    for media_file in media_files:
        key = media_file.year_month
        if key not in groups:
            groups[key] = YearMonthSummary(year_month=key, file_count=0, total_size=0)
        groups[key].file_count += 1
        groups[key].total_size += media_file.size

    return sorted(groups.values(), key=lambda s: (s.year_month == "Unknown", s.year_month))


@dataclass
class ExtensionSummary:
    """File count and total size for one file extension."""

    extension: str
    file_count: int
    total_size: int


def summarize_by_extension(media_files):
    """Group media files by file extension with file count and total size.

    Results are ordered alphabetically by extension.
    """
    groups = {}
    for media_file in media_files:
        key = media_file.extension
        if key not in groups:
            groups[key] = ExtensionSummary(extension=key, file_count=0, total_size=0)
        groups[key].file_count += 1
        groups[key].total_size += media_file.size

    return sorted(groups.values(), key=lambda s: s.extension)


@dataclass
class CutoffSummary:
    """Pre/post-cutoff and unknown-date file counts and sizes for one folder type."""

    folder_type: str
    pre_count: int
    pre_size: int
    post_count: int
    post_size: int
    unknown_count: int
    unknown_size: int


def summarize_by_cutoff(media_files, cutoff):
    """Group media files by folder type, splitting each into pre-cutoff,
    post-cutoff, and unknown-date counts/sizes (spec §4.7).

    `cutoff` is a `datetime.date`. Files dated before it are "pre-cutoff",
    on or after it are "post-cutoff", and files with no parseable date are
    "unknown". Results are ordered by folder type, alphabetically.
    """
    groups = {}
    for media_file in media_files:
        key = media_file.folder_type
        if key not in groups:
            groups[key] = CutoffSummary(
                folder_type=key,
                pre_count=0, pre_size=0,
                post_count=0, post_size=0,
                unknown_count=0, unknown_size=0,
            )

        summary = groups[key]
        file_date = media_file.date
        if file_date is None:
            summary.unknown_count += 1
            summary.unknown_size += media_file.size
        elif file_date < cutoff:
            summary.pre_count += 1
            summary.pre_size += media_file.size
        else:
            summary.post_count += 1
            summary.post_size += media_file.size

    return sorted(groups.values(), key=lambda s: s.folder_type)


STATUS_FOLDER = ".Statuses"

IMAGE_STATUS_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VIDEO_STATUS_EXTENSIONS = {"mp4", "3gp", "mkv"}
STATUS_EXTENSIONS = IMAGE_STATUS_EXTENSIONS | VIDEO_STATUS_EXTENSIONS


def list_statuses(client, serial, install):
    """List current WhatsApp Status images/videos for `install`.

    Scans <media_path>/.Statuses/ - the folder scan_media() excludes as
    internal cache - and returns only image/video files (skips .nomedia and
    other marker files). Returns [] if the install has no .Statuses folder
    (e.g. no status has been viewed yet).
    """
    statuses_path = f"{install.media_path}/{STATUS_FOLDER}"
    exists = client.shell(serial, f"[ -d {shlex.quote(statuses_path)} ] && echo 1 || echo 0").strip()
    if exists != "1":
        return []

    results = search_module.search_files(client, serial, statuses_path)
    return [r for r in results if r.extension in STATUS_EXTENSIONS]


def plan_save_statuses(client, serial, installs, dest_dir, conflict=transfer_module.CONFLICT_SKIP):
    """Build a transfer plan to pull current status media for `installs`.

    Each install's statuses are pulled into `<dest_dir>/<label>/Statuses/`,
    keeping the two apps' statuses in separate subfolders.
    """
    items = []
    for install in installs:
        dest_subdir = os.path.join(dest_dir, install.label, "Statuses")
        for status in list_statuses(client, serial, install):
            dest = os.path.join(dest_subdir, PurePosixPath(status.path).name)
            items.append(
                transfer_module._classify(
                    status.path, dest, status.size, conflict, os.path.exists, os.path.getsize
                )
            )

    return transfer_module.TransferPlan(direction="pull", items=items)


def plan_restore(client, serial, install, src_dir, conflict=transfer_module.CONFLICT_SKIP):
    """Build a push plan to restore a `plan_backup` folder onto `install`'s media path.

    `src_dir` is the destination passed to `plan_backup`, containing
    `<src_dir>/<label>/Media/...`. Pushes that folder's contents back onto
    `install.media_path`, preserving the structure (spec §4.9). Returns an
    empty plan if `<src_dir>/<label>/Media` doesn't exist.
    """
    local_media = os.path.join(src_dir, install.label, "Media")
    if not os.path.isdir(local_media):
        return transfer_module.TransferPlan(direction="push", items=[])

    return transfer_module.plan_push(client, serial, local_media, install.base_path, conflict=conflict)


# "01-Jan", "02-Feb", ... "12-Dec" - month folder labels for organize-by-date (spec §4.4).
_MONTH_LABELS = {m: f"{m:02d}-{calendar.month_abbr[m]}" for m in range(1, 13)}


@dataclass
class OrganizeItem:
    """A single local file move planned by `plan_organize_by_date`."""

    source: str
    dest: str


@dataclass
class OrganizePlan:
    """A plan to reorganize local backup files into a clean folder structure (spec §4.4)."""

    items: list = field(default_factory=list)

    @property
    def total_files(self):
        return len(self.items)


def _organized_dest_root(src_dir):
    src_dir = src_dir.rstrip(os.sep)
    parent = os.path.dirname(src_dir)
    name = os.path.basename(src_dir).replace(" ", "_")
    return os.path.join(parent, f"{name}_Organized")


def plan_organize_by_date(src_dir, sectioned=True):
    """Plan reorganizing files under `src_dir` by year/month (spec §4.4).

    If `sectioned`, groups Received/Sent/Private files separately (Images,
    Video, ...); otherwise (Voice Notes) groups directly by date. Files with
    no parseable WhatsApp-style date go to an "Unknown" folder. Plans moves
    into `<parent of src_dir>/<src_dir's name>_Organized/`, resolving
    destination filename collisions with `_1`, `_2`, ... suffixes.
    """
    dest_root = _organized_dest_root(src_dir)
    claimed = set()

    def dest_taken(path):
        return path in claimed or os.path.exists(path)

    items = []
    for root, dirs, files in os.walk(src_dir):
        dirs.sort()
        rel_parts = PurePosixPath(os.path.relpath(root, src_dir).replace(os.sep, "/")).parts

        if sectioned:
            if SECTION_SENT in rel_parts:
                section = SECTION_SENT
            elif SECTION_PRIVATE in rel_parts:
                section = SECTION_PRIVATE
            else:
                section = SECTION_RECEIVED

        for fname in sorted(files):
            source = os.path.join(root, fname)

            file_date = _parse_date(fname)
            if file_date is None:
                date_parts = ("Unknown",)
            else:
                date_parts = (f"{file_date.year:04d}", _MONTH_LABELS[file_date.month])

            if sectioned:
                dest = os.path.join(dest_root, section, *date_parts, fname)
            else:
                dest = os.path.join(dest_root, *date_parts, fname)

            dest = transfer_module.resolve_conflict_path(dest, dest_taken)
            claimed.add(dest)

            if os.path.abspath(source) != os.path.abspath(dest):
                items.append(OrganizeItem(source=source, dest=dest))

    return OrganizePlan(items=items)


# File extension -> Documents category, for `plan_organize_documents` (spec
# §4.4 Documents structure). Extensions not listed here fall back to "Other".
DOCUMENT_CATEGORIES = {
    "pdf": "PDFs",
    "zip": "Archives",
    "rar": "Archives",
    "7z": "Archives",
    "tar": "Archives",
    "gz": "Archives",
    "jpg": "Images",
    "jpeg": "Images",
    "png": "Images",
    "gif": "Images",
    "webp": "Images",
    "heic": "Images",
    "bmp": "Images",
    "mp4": "Videos",
    "mov": "Videos",
    "mkv": "Videos",
    "avi": "Videos",
    "3gp": "Videos",
    "py": "Source_Code",
    "java": "Source_Code",
    "c": "Source_Code",
    "cpp": "Source_Code",
    "h": "Source_Code",
    "js": "Source_Code",
    "ts": "Source_Code",
    "html": "Source_Code",
    "css": "Source_Code",
    "json": "Source_Code",
    "xml": "Source_Code",
    "sh": "Source_Code",
    "kt": "Source_Code",
    "go": "Source_Code",
    "rb": "Source_Code",
    "php": "Source_Code",
    "dwg": "Engineering",
    "dxf": "Engineering",
    "skp": "Engineering",
    "step": "Engineering",
    "stp": "Engineering",
    "iges": "Engineering",
    "igs": "Engineering",
    "stl": "Engineering",
    "sldprt": "Engineering",
    "sldasm": "Engineering",
    "ppt": "Presentations",
    "pptx": "Presentations",
    "key": "Presentations",
    "odp": "Presentations",
    "doc": "Word_Documents",
    "docx": "Word_Documents",
    "odt": "Word_Documents",
    "rtf": "Word_Documents",
    "xls": "Spreadsheets",
    "xlsx": "Spreadsheets",
    "csv": "Spreadsheets",
    "ods": "Spreadsheets",
    "exe": "Executables",
    "apk": "Executables",
    "msi": "Executables",
    "deb": "Executables",
    "dmg": "Executables",
}


# Magic-byte signatures -> file extension, for `fix_filenames` (spec §4.5).
_MAGIC_SIGNATURES = (
    (b"%PDF", "pdf"),
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"PK\x03\x04", "zip"),
    (b"OggS", "ogg"),
    (b"ID3", "mp3"),
)


def _sniff_extension(path):
    """Sniff a file's extension from its magic bytes, or None if unrecognized (spec §4.5)."""
    try:
        with open(path, "rb") as f:
            header = f.read(16)
    except OSError:
        return None

    for signature, ext in _MAGIC_SIGNATURES:
        if header.startswith(signature):
            return ext

    if len(header) >= 8 and header[4:8] == b"ftyp":
        return "mp4"

    return None


# Collapses runs of 2+ dots (e.g. "Sheet..pdf" -> "Sheet.pdf"), spec §4.5.
_DOUBLE_DOT_RE = re.compile(r"\.{2,}")


def fix_filenames(src_dir):
    """Fix filenames under `src_dir` in place (spec §4.5).

    Collapses double-dot filenames (`Sheet..pdf` -> `Sheet.pdf`) and adds a
    sniffed extension to extensionless files (`DOC-20220310-WA0001.` ->
    `DOC-20220310-WA0001.pdf`), resolving any resulting collisions with `_1`,
    `_2`, ... suffixes. Returns a list of `(old_path, new_path)` renames
    performed.
    """
    renames = []
    for root, dirs, files in os.walk(src_dir):
        dirs.sort()
        for fname in sorted(files):
            new_name = _DOUBLE_DOT_RE.sub(".", fname)

            if not PurePosixPath(new_name).suffix:
                ext = _sniff_extension(os.path.join(root, fname))
                if ext:
                    new_name = f"{new_name.rstrip('.')}.{ext}"

            if new_name == fname:
                continue

            old_path = os.path.join(root, fname)
            new_path = transfer_module.resolve_conflict_path(os.path.join(root, new_name), os.path.exists)
            os.rename(old_path, new_path)
            renames.append((old_path, new_path))

    return renames


def plan_organize_documents(src_dir):
    """Plan reorganizing Documents files under `src_dir` by section, category, then date (spec §4.4).

    Groups files into Received/Sent/Private (same convention as
    `plan_organize_by_date`), then by category based on file extension
    (`DOCUMENT_CATEGORIES`, default "Other"). Files with a parseable
    WhatsApp-style date are further grouped by year/month; files without one
    go to an `Original_Files/` subfolder within their category (spec §4.5) -
    this is the common case for Source_Code and Engineering files, which
    rarely carry WhatsApp-style dated filenames.
    """
    dest_root = _organized_dest_root(src_dir)
    claimed = set()

    def dest_taken(path):
        return path in claimed or os.path.exists(path)

    items = []
    for root, dirs, files in os.walk(src_dir):
        dirs.sort()
        rel_parts = PurePosixPath(os.path.relpath(root, src_dir).replace(os.sep, "/")).parts

        if SECTION_SENT in rel_parts:
            section = SECTION_SENT
        elif SECTION_PRIVATE in rel_parts:
            section = SECTION_PRIVATE
        else:
            section = SECTION_RECEIVED

        for fname in sorted(files):
            source = os.path.join(root, fname)

            ext = PurePosixPath(fname).suffix.lstrip(".").lower()
            category = DOCUMENT_CATEGORIES.get(ext, "Other")

            file_date = _parse_date(fname)
            if file_date is None:
                dest = os.path.join(dest_root, section, category, "Original_Files", fname)
            else:
                dest = os.path.join(
                    dest_root,
                    section,
                    category,
                    f"{file_date.year:04d}",
                    _MONTH_LABELS[file_date.month],
                    fname,
                )

            dest = transfer_module.resolve_conflict_path(dest, dest_taken)
            claimed.add(dest)

            if os.path.abspath(source) != os.path.abspath(dest):
                items.append(OrganizeItem(source=source, dest=dest))

    return OrganizePlan(items=items)


def execute_organize_plan(plan):
    """Move each item in `plan` to its destination, creating folders as needed."""
    for item in plan.items:
        os.makedirs(os.path.dirname(item.dest), exist_ok=True)
        shutil.move(item.source, item.dest)


# `whatsapp organize --type` names mapped to whether `plan_organize_by_date`
# should group by Received/Sent/Private section (spec §4.4). Voice Notes have
# no section subfolders (spec §4.2), so they're organized by date alone.
ORGANIZE_DATE_TYPES = {
    "voice_notes": False,
    "images": True,
    "video": True,
    "video_notes": True,
    "audio": True,
    "animated_gifs": True,
}


# CLI-friendly --type names (snake_case) mapped to the folder_type values
# produced by scan_media() / _classify() (spec §4.2 folder coverage table).
BACKUP_TYPES = {
    "images": "Images",
    "video": "Video",
    "video_notes": "Video Notes",
    "voice_notes": "Voice Notes",
    "audio": "Audio",
    "documents": "Documents",
    "stickers": "Stickers",
    "sticker_packs": "Sticker Packs",
    "backup_excluded_stickers": "Backup Excluded Stickers",
    "animated_gifs": "Animated Gifs",
    "profile_photos": "Profile Photos",
    "wallpaper": "WallPaper",
    "other": "Other",
}


@dataclass
class DeletePlan:
    """A plan for `whatsapp delete`: which files to remove and which to keep (spec §4.6)."""

    to_delete: list = field(default_factory=list)
    kept: list = field(default_factory=list)

    @property
    def total_files(self):
        return len(self.to_delete)

    @property
    def total_bytes(self):
        return sum(media_file.size for media_file in self.to_delete)


def verify_backup_exists(install, backup_dir, media_files):
    """Check that each of `media_files` has a matching copy under `backup_dir`.

    Mirrors the destination layout written by `plan_backup`/`execute_transfer_plan`
    (`<backup_dir>/<install.label>/Media/...`). Returns the `MediaFile`s that are
    missing from the backup or whose on-disk size doesn't match (spec §4.6 -
    deletion must be blocked unless a verified backup exists).
    """
    missing = []
    for media_file in media_files:
        rel_parts = PurePosixPath(media_file.path).relative_to(install.media_path).parts
        backup_path = os.path.join(backup_dir, install.label, "Media", *rel_parts)
        if not os.path.exists(backup_path) or os.path.getsize(backup_path) != media_file.size:
            missing.append(media_file)

    return missing


def plan_delete(media_files, before, keep_types=None):
    """Plan deletion of media dated before `before` (spec §4.6).

    `before` is a `datetime.date` cutoff; files with `.date < before` are
    slated for deletion. Files with no parseable date are always kept, since
    their age can't be determined. `keep_types`, if given, is a set of
    `folder_type` values to always keep regardless of date.
    """
    to_delete = []
    kept = []
    for media_file in media_files:
        if keep_types is not None and media_file.folder_type in keep_types:
            kept.append(media_file)
            continue

        file_date = media_file.date
        if file_date is not None and file_date < before:
            to_delete.append(media_file)
        else:
            kept.append(media_file)

    return DeletePlan(to_delete=to_delete, kept=kept)


# Files per `rm -f` command - batching is 10-20x faster than one adb shell
# call per file (spec §4.6).
_DELETE_BATCH_SIZE = 500


def execute_delete_plan(client, serial, plan, batch_size=_DELETE_BATCH_SIZE):
    """Delete every file in `plan.to_delete` from the device, `batch_size` at a time."""
    paths = [media_file.path for media_file in plan.to_delete]
    for i in range(0, len(paths), batch_size):
        batch = paths[i : i + batch_size]
        quoted = " ".join(shlex.quote(path) for path in batch)
        client.shell(serial, f"rm -f {quoted}")


@dataclass
class DeleteVerification:
    """Result of rescanning the device after `execute_delete_plan` (spec §4.6)."""

    deleted: int
    remaining: list
    after_files: list = field(default_factory=list)


def verify_delete(client, serial, install, plan):
    """Rescan `install`'s media and check which of `plan.to_delete` are gone.

    Files still present after deletion count as `remaining` (failed); the
    rest count as `deleted`. Since this is a fresh scan, re-running
    `plan_delete` on its results naturally resumes an interrupted deletion.
    """
    rescanned = scan_media(client, serial, install)
    still_present = {media_file.path for media_file in rescanned}

    remaining = [media_file for media_file in plan.to_delete if media_file.path in still_present]
    deleted = len(plan.to_delete) - len(remaining)

    return DeleteVerification(deleted=deleted, remaining=remaining, after_files=rescanned)


def plan_backup(client, serial, installs, dest_dir, types=None, conflict=transfer_module.CONFLICT_SKIP):
    """Build a transfer plan to back up media for `installs` into `dest_dir`.

    Each install's media is pulled into `<dest_dir>/<label>/Media/`, mirroring
    the on-device folder structure so the result can be pushed back with
    `whatsapp restore` (spec §4.9). `types`, if given, is a set of
    `folder_type` values (e.g. {"Images", "Voice Notes"}) to back up
    selectively; omit (or None) for a full backup of all scanned media.
    """
    items = []
    for install in installs:
        for media_file in scan_media(client, serial, install):
            if types is not None and media_file.folder_type not in types:
                continue

            rel_parts = PurePosixPath(media_file.path).relative_to(install.media_path).parts
            dest = os.path.join(dest_dir, install.label, "Media", *rel_parts)
            items.append(
                transfer_module._classify(
                    media_file.path, dest, media_file.size, conflict, os.path.exists, os.path.getsize
                )
            )

    return transfer_module.TransferPlan(direction="pull", items=items)


# Folders backed up by `whatsapp backup-db` (spec §4.8): the active message
# database, local encrypted chat backups, and account/session metadata. All
# are siblings of Media/ under each install's base_path.
DB_BACKUP_FOLDERS = ("Databases", "Backups", "accounts")

# Extensions WhatsApp uses for its local encrypted database backups
# (spec §4.8 - note the encryption status of database files).
_CRYPT_EXTENSIONS = (".crypt12", ".crypt14", ".crypt15")

# Printed by `whatsapp backup-db` - msgstore.db.crypt* holds the active chat
# history and is the most important file in the backup (spec §4.8).
MSGSTORE_WARNING = (
    "msgstore.db.crypt* contains your active chat history - it is the most "
    "important file in this backup. This tool cannot restore databases: "
    "WhatsApp only accepts a restored msgstore.db.crypt* during a fresh "
    "install/login, not on an already-configured account."
)


def is_encrypted_db_file(path):
    """Return True if `path` has a WhatsApp database-encryption extension."""
    return path.endswith(_CRYPT_EXTENSIONS)


def plan_backup_db(client, serial, installs, dest_dir, conflict=transfer_module.CONFLICT_SKIP):
    """Build a transfer plan to back up Databases/, Backups/, and accounts/ for `installs`.

    Each existing folder is pulled into `<dest_dir>/<label>/<folder>/`,
    mirroring the on-device structure (spec §4.8). A folder that doesn't
    exist on a given install (e.g. accounts/ before first login) is skipped.
    Database *restore* is intentionally out of scope (spec §4.9/§16 3.5) -
    this plan is for backup only.
    """
    items = []
    for install in installs:
        for folder in DB_BACKUP_FOLDERS:
            remote_path = f"{install.base_path}/{folder}"
            exists = client.shell(serial, f"[ -d {shlex.quote(remote_path)} ] && echo 1 || echo 0").strip()
            if exists != "1":
                continue

            for result in search_module.search_files(client, serial, remote_path):
                rel_parts = PurePosixPath(result.path).relative_to(remote_path).parts
                dest = os.path.join(dest_dir, install.label, folder, *rel_parts)
                items.append(
                    transfer_module._classify(
                        result.path, dest, result.size, conflict, os.path.exists, os.path.getsize
                    )
                )

    return transfer_module.TransferPlan(direction="pull", items=items)

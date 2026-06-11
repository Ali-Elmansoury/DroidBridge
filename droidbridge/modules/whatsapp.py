"""Module 4 - WhatsApp Toolkit: analysis, backup, organization, cleanup, database."""

import os
import shlex
from dataclasses import dataclass
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

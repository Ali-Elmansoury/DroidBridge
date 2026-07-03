# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Module 10 - Data Recovery & Restoration: soft-delete scanning and backup-based restore."""

import csv
import re
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from droidbridge.core.adb import AdbError

_SCAN_PATHS = [
    ("/sdcard/.trash/", "Generic", True),
    ("/sdcard/.Trash-1000/", "Generic", True),
    ("/sdcard/.RecycleBin/", "Generic", True),
    ("/sdcard/DCIM/.trash/", "Samsung Gallery", True),
    ("/sdcard/Android/data/com.google.android.apps.photos/cache/", "Google Photos", True),
    ("/sdcard/WhatsApp/Media/WhatsApp Images/Sent/", "WhatsApp", False),
    ("/sdcard/WhatsApp/Media/WhatsApp Video/Sent/", "WhatsApp", False),
    ("/sdcard/WhatsApp/Media/.Statuses/", "WhatsApp", False),
    ("/sdcard/Download/.trash/", "Downloads", True),
]

_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "heic", "heif", "tif", "tiff", "raw", "cr2", "nef"}
_VIDEO_EXTS = {"mp4", "mkv", "avi", "mov", "3gp", "webm", "flv", "m4v", "ts", "mpg", "mpeg"}
_AUDIO_EXTS = {"mp3", "aac", "flac", "ogg", "wav", "m4a", "opus", "wma", "amr"}
_DOC_EXTS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "odt", "ods"}

# Matches Android toybox `ls -la` ISO-format lines:
# -rw-rw-r-- 1 u0_a143 u0_a143 1048576 2026-06-10 12:30 filename.jpg
_LS_LINE_RE = re.compile(
    r"^(-[rwxsStT\-]{9})\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.+)$"
)


def _classify_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _DOC_EXTS:
        return "document"
    return "other"


@dataclass
class RecoveredFile:
    remote_path: str
    filename: str
    size_bytes: int
    modified_date: str
    file_type: str
    source_app: str
    is_true_trash: bool


@dataclass
class BackupInfo:
    path: Path
    date: str
    contacts_count: int
    calls_count: int


@dataclass
class DiffResult:
    backup_count: int
    phone_count: int
    estimated_missing: int


@dataclass
class RestoreResult:
    total: int
    succeeded: int
    failed: int
    skipped: int
    errors: list = field(default_factory=list)


class SoftDeleteScanner:
    def scan(self, client, serial) -> list:
        results = []
        for path, source_app, is_true_trash in _SCAN_PATHS:
            results.extend(self._scan_path(client, serial, path, source_app, is_true_trash))
        results.extend(self._scan_dcim_trashed(client, serial))
        return results

    def _scan_dcim_trashed(self, client, serial) -> list:
        try:
            out = client.shell(serial, "find /sdcard/DCIM -maxdepth 1 -name '.trashed-*' -type d 2>/dev/null")
        except AdbError:
            return []
        results = []
        for line in out.splitlines():
            line = line.strip()
            if line:
                results.extend(self._scan_path(client, serial, line + "/", "DCIM", True))
        return results

    def _scan_path(self, client, serial, path, source_app, is_true_trash) -> list:
        try:
            output = client.shell(serial, f"ls -la {shlex.quote(path)} 2>/dev/null")
        except AdbError:
            return []
        return self._parse_ls_output(output, path, source_app, is_true_trash)

    def _parse_ls_output(self, output, base_path, source_app, is_true_trash) -> list:
        results = []
        for line in output.splitlines():
            m = _LS_LINE_RE.match(line.strip())
            if not m:
                continue
            perms, size_str, date, time_str, name = m.groups()
            if name in (".", ".."):
                continue
            remote_path = base_path.rstrip("/") + "/" + name
            results.append(RecoveredFile(
                remote_path=remote_path,
                filename=name,
                size_bytes=int(size_str),
                modified_date=f"{date}T{time_str}",
                file_type=_classify_type(name),
                source_app=source_app,
                is_true_trash=is_true_trash,
            ))
        return results

    def pull_to_pc(self, client, serial, remote_path, dest_dir) -> bool:
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        filename = remote_path.rsplit("/", 1)[-1]
        local_path = dest / filename
        try:
            client.pull(serial, remote_path, str(local_path))
            return True
        except AdbError:
            return False

    def push_back_to_phone(self, client, serial, remote_path, original_path) -> bool:
        # Pull to a temp file locally, then push to the original location.
        # This avoids needing shell `mv` which may fail on cross-partition moves.
        import tempfile
        suffix = Path(remote_path).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
        try:
            client.pull(serial, remote_path, tmp_path)
            client.push(serial, tmp_path, original_path)
            return True
        except AdbError:
            return False
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass


class BackupRestorer:
    def list_backups(self, backup_dir: Path) -> list:
        raise NotImplementedError  # implemented in Task 3

    def diff_contacts(self, client, serial, vcf_path: Path) -> "DiffResult":
        raise NotImplementedError  # implemented in Task 3

    def diff_calls(self, client, serial, csv_path: Path) -> "DiffResult":
        raise NotImplementedError  # implemented in Task 3

    def restore_contacts(self, client, serial, vcf_path: Path, dest: str) -> "RestoreResult":
        raise NotImplementedError  # implemented in Task 4

    def restore_calls(self, client, serial, csv_path: Path, dest: str) -> "RestoreResult":
        raise NotImplementedError  # implemented in Task 4

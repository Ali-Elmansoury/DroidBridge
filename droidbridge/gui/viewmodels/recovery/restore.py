# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""RestoreViewModel for backup-based contacts/call log restoration (Module 10)."""

import functools
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui.workers import Worker
from droidbridge.modules.recovery import BackupRestorer


class RestoreViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)
    backupsChanged = pyqtSignal(list)
    diffChanged = pyqtSignal(dict)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []
        self._restorer = BackupRestorer()

    def load_backups(self, backup_dir: str):
        self.logMessage.emit(f"Scanning {backup_dir} for backups...", "INFO")
        fn = functools.partial(self._restorer.list_backups, Path(backup_dir))
        self._run(fn, self._on_backups_loaded)

    def compute_diff(self, backup_info):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Computing diff against phone...", "INFO")
        fn = functools.partial(self._compute_diff_fn, client, serial, backup_info)
        self._run(fn, self._on_diff_done)

    def restore(self, backup_info, restore_contacts: bool, restore_calls: bool, dest: str, output_dir: str):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Starting restore...", "INFO")
        fn = functools.partial(
            self._restore_fn, client, serial, backup_info,
            restore_contacts, restore_calls, dest, output_dir,
        )
        self._run(fn, self._on_restore_done)

    def _compute_diff_fn(self, client, serial, backup_info):
        result = {}
        backup_path = Path(backup_info.path)
        vcf_files = list(backup_path.glob("contacts_*.vcf"))
        if vcf_files:
            result["contacts"] = self._restorer.diff_contacts(client, serial, vcf_files[0])
        csv_path = backup_path / "call_log.csv"
        if csv_path.exists():
            result["calls"] = self._restorer.diff_calls(client, serial, csv_path)
        return result

    def _restore_fn(self, client, serial, backup_info, restore_contacts, restore_calls, dest, output_dir):
        backup_path = Path(backup_info.path)
        contacts_result = None
        calls_result = None
        actual_dest = dest if dest == "phone" else output_dir
        if restore_contacts:
            vcf_files = list(backup_path.glob("contacts_*.vcf"))
            if vcf_files:
                contacts_result = self._restorer.restore_contacts(client, serial, vcf_files[0], actual_dest)
        if restore_calls:
            csv_path = backup_path / "call_log.csv"
            if csv_path.exists():
                calls_result = self._restorer.restore_calls(client, serial, csv_path, actual_dest)
        return {"contacts": contacts_result, "calls": calls_result}

    def _on_backups_loaded(self, backups):
        self.backupsChanged.emit(backups)
        self.statusChanged.emit(
            f"{len(backups)} backup(s) found." if backups else "No DroidBridge backups found in selected directory."
        )

    def _on_diff_done(self, diff):
        self.diffChanged.emit(diff)
        parts = []
        if "contacts" in diff:
            d = diff["contacts"]
            parts.append(f"Contacts: backup={d.backup_count}, phone={d.phone_count}, ~{d.estimated_missing} may be missing")
        if "calls" in diff:
            d = diff["calls"]
            parts.append(f"Calls: backup={d.backup_count}, phone={d.phone_count}, ~{d.estimated_missing} may be missing")
        self.statusChanged.emit("; ".join(parts) if parts else "Diff complete.")

    def _on_restore_done(self, summary):
        parts = []
        if summary.get("contacts"):
            r = summary["contacts"]
            parts.append(f"Contacts: {r.succeeded}/{r.total} restored")
        if summary.get("calls"):
            r = summary["calls"]
            parts.append(f"Calls: {r.succeeded}/{r.total} restored")
        msg = "; ".join(parts) if parts else "Restore complete."
        self.statusChanged.emit(msg)
        self.logMessage.emit(msg, "INFO")

    def _run(self, fn, on_finished):
        self.busyChanged.emit(True)
        worker = self._worker_factory(fn)
        self._workers.append(worker)
        worker.finished.connect(lambda result: self._finish(worker, on_finished, result))
        worker.error.connect(lambda exc: self._finish(worker, self._on_error, exc))
        worker.start()

    def _finish(self, worker, callback, payload):
        worker.wait()
        self._workers.remove(worker)
        callback(payload)
        if not self._workers:
            self.busyChanged.emit(False)

    def _on_error(self, exc):
        self.statusChanged.emit(str(exc))
        self.logMessage.emit(str(exc), "ERROR")

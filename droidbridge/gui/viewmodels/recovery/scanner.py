# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""ScannerViewModel for soft-delete scan (Module 10)."""

import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui.workers import Worker
from droidbridge.modules.recovery import SoftDeleteScanner


class ScannerViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)
    scanResultsChanged = pyqtSignal(list)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []
        self._scanner = SoftDeleteScanner()

    def scan(self):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Scanning soft-delete locations...", "INFO")
        fn = functools.partial(self._scanner.scan, client, serial)
        self._run(fn, self._on_scan_done)

    def pull_to_pc(self, files, dest_dir):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit(f"Saving {len(files)} file(s) to PC...", "INFO")
        fn = functools.partial(self._pull_all, client, serial, files, dest_dir)
        self._run(fn, self._on_pull_done)

    def push_to_phone(self, files):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit(f"Restoring {len(files)} file(s) to phone...", "INFO")
        fn = functools.partial(self._push_all, client, serial, files)
        self._run(fn, self._on_push_done)

    def _pull_all(self, client, serial, files, dest_dir):
        succeeded = failed = 0
        for f in files:
            ok = self._scanner.pull_to_pc(client, serial, f.remote_path, dest_dir)
            if ok:
                succeeded += 1
            else:
                failed += 1
        return {"succeeded": succeeded, "failed": failed, "total": len(files)}

    def _push_all(self, client, serial, files):
        succeeded = failed = 0
        for f in files:
            ok = self._scanner.push_back_to_phone(client, serial, f.remote_path, f.remote_path)
            if ok:
                succeeded += 1
            else:
                failed += 1
        return {"succeeded": succeeded, "failed": failed, "total": len(files)}

    def _on_scan_done(self, results):
        self.scanResultsChanged.emit(results)
        self.statusChanged.emit(f"Scan complete — {len(results)} file(s) found.")
        self.logMessage.emit(f"Scan complete — {len(results)} file(s) found.", "INFO")

    def _on_pull_done(self, summary):
        msg = f"Saved {summary['succeeded']}/{summary['total']} file(s) to PC, {summary['failed']} failed."
        self.statusChanged.emit(msg)
        self.logMessage.emit(msg, "INFO")

    def _on_push_done(self, summary):
        msg = f"Restored {summary['succeeded']}/{summary['total']} file(s) to phone, {summary['failed']} failed."
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

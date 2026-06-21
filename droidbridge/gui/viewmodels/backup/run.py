import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import backup_ops
from droidbridge.gui.workers import Worker


class RunViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    progressChanged = pyqtSignal(int, int)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def run_backup(self, profile_name, no_verify):
        self.logMessage.emit(f"Running backup for profile {profile_name!r}...", "INFO")
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(backup_ops.run_backup, client, serial, profile_name, no_verify)
        self._run(fn, self._on_done, report_progress=True)

    def _on_done(self, result):
        parts = [f"{result['done']}/{result['total']} files"]
        if result["failed"]:
            parts.append(f"{result['failed']} failed")
        if result["verified"] is True:
            parts.append("verified ✓")
        message = "Backup complete — " + ", ".join(parts) + "."
        self.statusChanged.emit(message)
        self.logMessage.emit(message, "INFO")

    def _on_progress(self, progress):
        self.progressChanged.emit(progress.done_files, progress.total_files)

    def _run(self, fn, on_finished, report_progress=False):
        self.busyChanged.emit(True)
        worker = self._worker_factory(fn, report_progress=report_progress)
        self._workers.append(worker)
        if report_progress:
            worker.progress.connect(self._on_progress)
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

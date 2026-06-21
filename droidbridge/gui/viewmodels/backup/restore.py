import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import backup_ops
from droidbridge.gui.workers import Worker


class RestoreViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def list_sources(self, profile_name):
        profile = backup_ops.get_profile(profile_name)
        return profile.sources if profile else []

    def run_restore(self, profile_name, sources, after, before, conflict, no_verify):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit(f"Restoring profile {profile_name!r}...", "INFO")
        fn = functools.partial(
            backup_ops.run_restore, client, serial, profile_name, sources, after, before, conflict, no_verify,
        )
        self._run(fn, self._on_done)

    def _on_done(self, results):
        self.resultsChanged.emit(results)
        total_done = sum(r["done"] for r in results)
        total_failed = sum(r["failed"] for r in results)
        message = f"Restore complete — {total_done} files restored across {len(results)} source(s)"
        if total_failed:
            message += f", {total_failed} failed"
        message += "."
        self.statusChanged.emit(message)
        self.logMessage.emit(message, "INFO")

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

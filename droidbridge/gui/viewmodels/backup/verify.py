import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import backup_ops
from droidbridge.gui.workers import Worker


class VerifyViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    resultChanged = pyqtSignal(dict)
    logMessage = pyqtSignal(str, str)

    def __init__(self, worker_factory=Worker):
        super().__init__()
        self._worker_factory = worker_factory
        self._workers = []

    def run_verify(self, profile_name):
        self.logMessage.emit(f"Verifying profile {profile_name!r}...", "INFO")
        fn = functools.partial(backup_ops.run_verify, profile_name)
        self._run(fn, self._on_done)

    def _on_done(self, result):
        self.resultChanged.emit(result)
        status = "Verification OK" if result["ok"] else "Verification MISMATCH"
        message = (
            f"{status} — expected {result['expected_files']} files / {result['expected_bytes']} bytes, "
            f"found {result['actual_files']} files / {result['actual_bytes']} bytes."
        )
        self.statusChanged.emit(message)
        self.logMessage.emit(message, "INFO" if result["ok"] else "ERROR")

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

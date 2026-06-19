import functools
from PyQt6.QtCore import QObject, pyqtSignal
from droidbridge.gui import whatsapp_ops
from droidbridge.gui.workers import Worker


class SaveStatusViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    progressChanged = pyqtSignal(int, int)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def load_statuses(self, app):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Loading statuses...", "INFO")
        fn = functools.partial(whatsapp_ops.pull_statuses_to_temp, client, serial, app)
        self._run(fn, self._on_loaded, report_progress=True)

    def save_selected(self, app, dest, remote_paths, conflict, verify):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Saving selected statuses...", "INFO")
        fn = functools.partial(whatsapp_ops.save_statuses, client, serial, app, dest, remote_paths, conflict, verify)
        self._run(fn, self._on_saved, report_progress=True)

    def _on_loaded(self, result):
        temp_dir, items = result
        self.resultsChanged.emit(items)
        if items:
            message = f"Loaded {len(items)} status file(s). Select files to save."
        else:
            message = "No status files found."
        self.statusChanged.emit(message)
        self.logMessage.emit(message, "INFO")

    def _on_saved(self, result):
        message = f"Saved {result['done']}/{result['total']} status file(s)."
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

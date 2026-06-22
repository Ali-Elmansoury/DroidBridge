import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import apps_ops
from droidbridge.gui.workers import Worker


class ListingViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def load(self, filter_kind="all", sort_by="name", reverse=False):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(
            apps_ops.get_apps, client, serial,
            filter_kind=filter_kind, sort_by=sort_by, reverse=reverse,
        )
        self._run(fn, self._on_results)

    def _on_results(self, rows):
        self.resultsChanged.emit(rows)
        self.statusChanged.emit(f"Loaded {len(rows)} app(s).")

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

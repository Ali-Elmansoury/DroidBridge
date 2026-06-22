import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import apps_ops
from droidbridge.gui.workers import Worker


class CacheViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    estimateChanged = pyqtSignal(dict)
    appInfoChanged = pyqtSignal(object)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def set_all_apps(self, rows):
        self.estimateChanged.emit(apps_ops.estimate_cache_clear(rows))

    def set_current_app(self, package):
        if not package:
            self.appInfoChanged.emit(None)
            return
        self.load_app_info(package)

    def load_app_info(self, package):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(apps_ops.get_app_info, client, serial, package)
        self._run(fn, self.appInfoChanged.emit)

    def trim_caches(self, estimate_bytes):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(apps_ops.trim_caches, client, serial, estimate_bytes)
        self._run(fn, self._on_trim_done)

    def _on_trim_done(self, _result):
        self.statusChanged.emit("Caches trimmed.")
        self.logMessage.emit("Caches trimmed.", "INFO")

    def reset_app_data(self, package):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(apps_ops.reset_app_data, client, serial, package)
        self._run(fn, lambda _result: self._on_reset_done(package))

    def _on_reset_done(self, package):
        self.statusChanged.emit(f"Reset app data for {package}.")
        self.logMessage.emit(f"Reset app data for {package}.", "INFO")
        self.load_app_info(package)

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

# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import apps_ops
from droidbridge.gui.workers import Worker


class ApkExtractionViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    apkInfoChanged = pyqtSignal(object)
    extractionFinished = pyqtSignal(list)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []
        self._current_package = None

    def set_current_app(self, package):
        self._current_package = package or None
        if not self._current_package:
            self.apkInfoChanged.emit(None)
            return
        self.load_apk_info(self._current_package)

    def load_apk_info(self, package):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(apps_ops.get_apk_info, client, serial, package)
        self._run(fn, self.apkInfoChanged.emit)

    def extract(self, dest_dir):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(apps_ops.extract_apk, client, serial, self._current_package, dest_dir)
        self._run(fn, self.extractionFinished.emit, report_progress=True)

    def _run(self, fn, on_finished, report_progress=False):
        self.busyChanged.emit(True)
        worker = self._worker_factory(fn, report_progress=report_progress)
        self._workers.append(worker)
        if report_progress:
            worker.progress.connect(self._on_progress)
        worker.finished.connect(lambda result: self._finish(worker, on_finished, result))
        worker.error.connect(lambda exc: self._finish(worker, self._on_error, exc))
        worker.start()

    def _on_progress(self, message):
        self.logMessage.emit(message, "INFO")

    def _finish(self, worker, callback, payload):
        worker.wait()
        self._workers.remove(worker)
        callback(payload)
        if not self._workers:
            self.busyChanged.emit(False)

    def _on_error(self, exc):
        self.statusChanged.emit(str(exc))
        self.logMessage.emit(str(exc), "ERROR")

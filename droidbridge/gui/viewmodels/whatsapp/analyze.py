# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtCore import QObject, pyqtSignal
from droidbridge.gui import whatsapp_ops
from droidbridge.gui.workers import Worker


class AnalyzeViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def analyze(self, app, cutoff):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Analyzing...", "INFO")
        self._run(lambda: whatsapp_ops.run_analyze(client, serial, app, cutoff), self._on_done)

    def _on_done(self, rows):
        self.resultsChanged.emit(rows)
        self.statusChanged.emit(f"Analysis complete — {len(rows)} folder type(s).")
        self.logMessage.emit(f"Analysis complete — {len(rows)} folder type(s).", "INFO")

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

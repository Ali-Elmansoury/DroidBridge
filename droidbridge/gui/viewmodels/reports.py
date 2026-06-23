from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import reports_ops
from droidbridge.gui.workers import Worker


class ReportsViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)
    reportGenerated = pyqtSignal(dict)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def generate(self, report_type, report_format, **params):
        if reports_ops.REPORT_TYPES_BY_ID[report_type]["needs_device"]:
            client, serial = self.context.client, self.context.serial
        else:
            client, serial = None, None

        def on_finished(result):
            self._on_generated(result, report_format)

        self._run(
            lambda: reports_ops.generate_report(client, serial, report_type, report_format, **params),
            on_finished,
        )

    def _on_generated(self, result, report_format):
        payload = dict(result)
        payload["format"] = report_format
        self.reportGenerated.emit(payload)
        self.statusChanged.emit(f"Generated {report_format} report.")

    def save(self, content, path):
        try:
            reports_ops.save_report(content, path)
        except Exception as exc:
            self.logMessage.emit(str(exc), "ERROR")
            return
        self.statusChanged.emit(f"Saved to {path}")

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

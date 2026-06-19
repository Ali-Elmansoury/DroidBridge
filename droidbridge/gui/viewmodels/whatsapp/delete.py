from PyQt6.QtCore import QObject, pyqtSignal
from droidbridge.gui import whatsapp_ops
from droidbridge.gui.workers import Worker


class DeleteViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []
        self._plans = []

    def preview(self, app, before, keep_types, backup_dir):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Previewing delete...", "INFO")
        self._run(
            lambda: whatsapp_ops.build_delete_preview(client, serial, app, before, keep_types, backup_dir),
            self._on_preview_done,
        )

    def execute(self):
        if not self._plans:
            return
        client, serial = self.context.client, self.context.serial
        plans = self._plans
        self.logMessage.emit("Deleting...", "INFO")
        self._run(
            lambda: whatsapp_ops.execute_delete(client, serial, plans),
            self._on_execute_done,
        )

    def _on_preview_done(self, result):
        if result["error"]:
            self.statusChanged.emit(result["error"])
            self.logMessage.emit(result["error"], "ERROR")
            self.resultsChanged.emit([])
            return
        self._plans = result["plans"]
        self.resultsChanged.emit(result["rows"])
        message = f"Preview: {len(result['rows'])} file(s) to delete."
        self.statusChanged.emit(message)
        self.logMessage.emit(message, "INFO")

    def _on_execute_done(self, result):
        self._plans = []
        message = f"Deleted {result['deleted']} file(s)."
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

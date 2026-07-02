# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import phone_data_ops
from droidbridge.gui.workers import Worker


class ContactsCallLogViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def export_contacts(self, sources, dest):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit(f"Exporting contacts ({', '.join(sources)})...", "INFO")
        fn = functools.partial(phone_data_ops.run_export_contacts, client, serial, sources, dest)
        self._run(fn, self._on_contacts_done)

    def export_call_log(self, dest):
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Exporting call log...", "INFO")
        fn = functools.partial(phone_data_ops.run_export_call_log, client, serial, dest)
        self._run(fn, self._on_call_log_done)

    def _on_contacts_done(self, result):
        parts = [f"{source}: {counts['exported']} exported, {counts['skipped']} skipped" for source, counts in result.items()]
        message = ("Contacts export complete — " + "; ".join(parts) + ".") if parts else "Contacts export complete."
        self.statusChanged.emit(message)
        self.logMessage.emit(message, "INFO")

    def _on_call_log_done(self, result):
        message = f"Call log export complete — {result['exported']} exported, {result['skipped']} skipped."
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

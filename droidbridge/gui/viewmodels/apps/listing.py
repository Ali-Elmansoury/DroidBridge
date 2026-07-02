# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import apps_ops
from droidbridge.gui.workers import Worker


class ListingViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    logMessage = pyqtSignal(str, str)
    labelsResolved = pyqtSignal(dict)

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

    def resolve_labels(self, packages):
        """Start background aapt2 label resolution; emits labelsResolved when done."""
        client, serial = self.context.client, self.context.serial

        def _progress(done, total):
            self.statusChanged.emit(f"Resolving app names... {done}/{total}")

        fn = functools.partial(
            apps_ops.resolve_app_labels, client, serial, list(packages),
            progress_callback=_progress,
        )
        self._run(fn, self._on_labels_resolved)

    def _on_labels_resolved(self, labels):
        resolved = sum(1 for p, v in labels.items() if v and not p == v)
        self.statusChanged.emit(f"Ready. Resolved {resolved} display name(s).")
        self.labelsResolved.emit(labels)

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

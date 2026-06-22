import functools

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import apps_ops
from droidbridge.gui.workers import Worker


class BackupRestoreViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    appInfoChanged = pyqtSignal(object)
    backupFinished = pyqtSignal(str)
    manifestChanged = pyqtSignal(object)
    restoreFinished = pyqtSignal(object)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

    def set_current_app(self, package):
        if not package:
            self.appInfoChanged.emit(None)
            return
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(apps_ops.get_app_info, client, serial, package)
        self._run(fn, self.appInfoChanged.emit)

    def backup(self, package, version_name, version_code, dest_dir):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(
            apps_ops.backup_apk, client, serial, package, version_name, version_code, dest_dir,
        )
        self._run(fn, self.backupFinished.emit, report_progress=True)

    def load_manifest(self, bundle_dir):
        fn = functools.partial(apps_ops.read_manifest, bundle_dir)
        self._run(fn, self.manifestChanged.emit)

    def restore(self, bundle_dir, allow_downgrade=False):
        client, serial = self.context.client, self.context.serial
        fn = functools.partial(apps_ops.restore_apk, client, serial, bundle_dir, allow_downgrade=allow_downgrade)
        self._run(fn, self.restoreFinished.emit)

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

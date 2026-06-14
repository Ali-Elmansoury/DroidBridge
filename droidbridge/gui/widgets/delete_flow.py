"""Shared rename/delete dialog flows for FilesPage and SearchPage (Phase 6.3).

Both pages need the same "scan -> confirm -> delete -> verify" and "rename"
flows; living here keeps that logic out of the page classes.
"""

from PyQt6.QtCore import QEventLoop, Qt
from PyQt6.QtWidgets import QMessageBox, QProgressDialog

from droidbridge.gui.workers import Worker


def _run_with_progress(parent, fn, *args, title="Working...", worker_factory=Worker, report_progress=False, **kwargs):
    """Run `fn(*args, **kwargs)` on a worker thread, showing a modal progress
    dialog until it finishes.

    Returns the result of `fn`, or None if `fn` raised (a warning dialog is
    shown with the exception's message in that case).
    """
    dialog = QProgressDialog(title, None, 0, 0, parent)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setCancelButton(None)
    dialog.setMinimumDuration(0)

    result = {}

    def on_finished(value):
        result["value"] = value
        loop.quit()

    def on_error(exc):
        result["error"] = exc
        loop.quit()

    def on_progress(value):
        dialog.setLabelText(str(value))

    if report_progress:
        kwargs = dict(kwargs)
        kwargs["report_progress"] = True

    worker = worker_factory(fn, *args, **kwargs)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    if report_progress:
        worker.progress.connect(on_progress)

    loop = QEventLoop()
    dialog.show()
    # `worker` was moved to its own QThread via moveToThread, so deferring
    # start() via QTimer.singleShot would queue the call onto that
    # not-yet-running thread's event loop and deadlock. Call it directly;
    # synchronous worker_factory implementations (e.g. tests' FakeWorker) may
    # already populate `result` and call loop.quit() here, before loop.exec()
    # has started - quit() on a not-yet-running loop is a no-op, so skip
    # exec() entirely in that case to avoid hanging forever.
    worker.start()
    if not result:
        loop.exec()

    dialog.close()
    worker.wait()

    if "error" in result:
        QMessageBox.warning(parent, title, str(result["error"]))
        return None

    return result.get("value")

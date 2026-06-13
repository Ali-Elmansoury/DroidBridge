"""Generic background worker (Phase 6.1): runs a plain function on a QThread and reports
the result or exception back to the calling thread via Qt signals.
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class Worker(QObject):
    """Runs `fn(*args, **kwargs)` on its own QThread.

    Connect to `finished`/`error`, then call `start()`. Emits exactly one of
    `finished(result)` or `error(exception)`, after which its QThread exits.

    If `report_progress=True`, `fn` is called with an extra `progress_callback`
    keyword argument; calling it from `fn` (on the worker thread) emits the
    `progress` signal, received on the calling thread like `finished`/`error`.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(object)
    progress = pyqtSignal(object)

    def __init__(self, fn, *args, report_progress=False, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._report_progress = report_progress
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        self.finished.connect(self._thread.quit)
        self.error.connect(self._thread.quit)

    def _run(self):
        if self._report_progress:
            self._kwargs["progress_callback"] = self.progress.emit
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - reported via signal, not raised
            self.error.emit(exc)
        else:
            self.finished.emit(result)

    def start(self):
        self._thread.start()

    def wait(self):
        """Block until this worker's QThread has fully exited.

        `finished`/`error` trigger `QThread.quit()`, which is asynchronous - the thread
        may still be shutting down when the signal is received. Call `wait()` after
        receiving `finished`/`error` (or in teardown) before dropping the last reference
        to this Worker, otherwise Qt may destroy the QThread while it's still running.
        """
        self._thread.wait()

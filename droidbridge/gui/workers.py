"""Generic background worker (Phase 6.1): runs a plain function on a QThread and reports
the result or exception back to the calling thread via Qt signals.
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class Worker(QObject):
    """Runs `fn(*args, **kwargs)` on its own QThread.

    Connect to `finished`/`error`, then call `start()`. Emits exactly one of
    `finished(result)` or `error(exception)`, after which its QThread exits.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        self.finished.connect(self._thread.quit)
        self.error.connect(self._thread.quit)

    def _run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - reported via signal, not raised
            self.error.emit(exc)
        else:
            self.finished.emit(result)

    def start(self):
        self._thread.start()

    def wait(self):
        """Wait for the thread to fully finish. For testing."""
        self._thread.wait()

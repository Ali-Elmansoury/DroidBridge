"""ViewModel for the Search module screen (Phase 6.2).

Owns Workers, parses the search form's size fields, runs gui.search_ops.run_search,
and supports client-side re-sorting of the last result set.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import files_ops, search_ops
from droidbridge.gui.workers import Worker
from droidbridge.modules import search as search_module
from droidbridge.utils import format as format_utils


def _format_result(result):
    return {
        "result": result,
        "name": result.name,
        "path": result.path,
        "size": result.size,
        "mtime": result.mtime,
        "extension": result.extension,
    }


class SearchViewModel(QObject):
    """Drives the Search page: runs `files search`-equivalent queries and re-sorts results."""

    resultsChanged = pyqtSignal(list)
    rootSubdirsChanged = pyqtSignal(str, list)
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []
        self._results = []

    def search(self, root, name, extensions, min_size_str, max_size_str, after, before, preset, sort_by, reverse):
        """Parse the size fields, then run search_ops.run_search via a Worker.

        A ValueError from parse_size (invalid size string) is reported via
        statusChanged/logMessage without starting a Worker.
        """
        try:
            min_size = format_utils.parse_size(min_size_str) if min_size_str else None
            max_size = format_utils.parse_size(max_size_str) if max_size_str else None
        except ValueError as exc:
            self._on_error(exc)
            return

        client, serial = self.context.client, self.context.serial
        self.logMessage.emit("Searching...", "INFO")
        self._run(
            lambda: search_ops.run_search(
                client, serial, root, name=name, extensions=extensions, min_size=min_size,
                max_size=max_size, after=after, before=before, preset=preset, sort_by=sort_by, reverse=reverse,
            ),
            self._on_searched,
        )

    def browse_root(self, path):
        """Fetch `path`'s subdirectories for the Root-path browse combo."""
        client, serial = self.context.client, self.context.serial
        self._run(
            lambda: files_ops.list_path(client, serial, path, show_hidden=False),
            lambda entries: self._on_root_browsed(path, entries),
        )

    def _on_root_browsed(self, path, entries):
        self.rootSubdirsChanged.emit(path, [e.name for e in entries if e.is_dir])

    def set_sort(self, by, reverse):
        """Re-sort the last result set client-side and re-emit resultsChanged."""
        self._results = search_module.sort_results(self._results, by=by, reverse=reverse)
        self._emit_results()

    def _on_searched(self, results):
        self._results = results
        self._emit_results()
        self.logMessage.emit(f"Found {len(results)} result{'s' if len(results) != 1 else ''}.", "INFO")

    def _emit_results(self):
        self.resultsChanged.emit([_format_result(r) for r in self._results])

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

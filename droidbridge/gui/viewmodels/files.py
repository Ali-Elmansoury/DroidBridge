"""ViewModel for the Files module screen (Phase 6.2).

Owns Workers, formats FileEntry rows for display, tracks the current directory and
sort/filter state, and drives the on-demand image preview panel. Calls
droidbridge.gui.files_ops/preview_ops as module attributes (not direct
import-bindings) so tests can monkeypatch their functions.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import files_ops, preview_ops
from droidbridge.gui.workers import Worker
from droidbridge.modules import files as files_module


def _format_entry(entry):
    return {
        "entry": entry,
        "name": entry.name,
        "type": "dir" if entry.is_dir else "file",
        "size": entry.size,
        "mtime": entry.mtime,
        "is_dir": entry.is_dir,
        "path": entry.path,
        "extension": entry.extension,
    }


class FilesViewModel(QObject):
    """Drives the Files page: browse, sort/filter, and preview a selected file."""

    entriesChanged = pyqtSignal(list)
    pathChanged = pyqtSignal(str)
    previewChanged = pyqtSignal(object)
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []

        self.current_path = files_ops.QUICK_JUMP_PATHS["Root"]
        self._entries = []
        self._sort_by = "name"
        self._reverse = False
        self._show_hidden = False
        self._extensions = None
        self._dirs_pass_extension_filter = True
        self._preview_generation = 0

    def navigate(self, path):
        """Load `path`'s full directory listing and make it current."""
        client, serial = self.context.client, self.context.serial
        self.logMessage.emit(f"Listing {path}...", "INFO")
        self._run(
            lambda: files_ops.list_path(client, serial, path, show_hidden=True),
            lambda entries: self._on_navigated(path, entries),
        )

    def go_up(self):
        """Navigate to the parent of the current directory."""
        self.navigate(files_ops.parent_path(self.current_path))

    def set_sort(self, by, reverse):
        """Re-sort the already-fetched entries client-side and re-emit entriesChanged."""
        self._sort_by = by
        self._reverse = reverse
        self._refilter_and_resort()

    def set_show_hidden(self, show_hidden):
        """Re-filter the already-fetched entries client-side and re-emit entriesChanged."""
        self._show_hidden = show_hidden
        self._refilter_and_resort()

    def set_extension_filter(self, extensions):
        """Re-filter the already-fetched entries client-side and re-emit entriesChanged."""
        self._extensions = extensions
        self._refilter_and_resort()

    def set_dirs_pass_extension_filter(self, dirs_pass_extension_filter):
        """Re-filter the already-fetched entries client-side and re-emit entriesChanged."""
        self._dirs_pass_extension_filter = dirs_pass_extension_filter
        self._refilter_and_resort()

    def select_entry(self, entry_or_none):
        """Called on selection change; updates the preview panel.

        `entry_or_none` is a single FileEntry (exactly one row selected) or None
        (zero or multiple rows selected) - the page resolves multi-select to None.
        """
        self._preview_generation += 1
        generation = self._preview_generation

        if entry_or_none is not None and preview_ops.is_previewable(entry_or_none):
            entry = entry_or_none
            client, serial = self.context.client, self.context.serial
            self._run(
                lambda: preview_ops.fetch_preview(client, serial, entry),
                lambda local_path: self._on_preview_fetched(generation, local_path),
            )
        else:
            self.previewChanged.emit({"kind": "info", "entry": entry_or_none})

    def _on_navigated(self, path, entries):
        self.current_path = path
        self._entries = entries
        self.pathChanged.emit(path)
        self._refilter_and_resort()
        self.logMessage.emit(f"Listed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}.", "INFO")

    def _on_preview_fetched(self, generation, local_path):
        if generation != self._preview_generation:
            return
        self.previewChanged.emit({"kind": "image", "local_path": local_path})

    def _refilter_and_resort(self):
        entries = files_module.filter_entries(
            self._entries,
            extensions=self._extensions,
            include_hidden=self._show_hidden,
            dirs_pass_extension_filter=self._dirs_pass_extension_filter,
        )
        entries = files_module.sort_entries(entries, by=self._sort_by, reverse=self._reverse)
        self.entriesChanged.emit([_format_entry(e) for e in entries])

    def _run(self, fn, on_finished):
        self.busyChanged.emit(True)
        worker = self._worker_factory(fn)
        self._workers.append(worker)
        worker.finished.connect(lambda result: self._finish(worker, on_finished, result))
        worker.error.connect(lambda exc: self._finish(worker, self._on_error, exc))
        worker.start()

    def _finish(self, worker, callback, payload):
        """Run `callback(payload)`, then release `worker` once its thread has exited.

        See droidbridge.gui.viewmodels.device.DeviceViewModel._finish for the full
        worker-lifetime rationale (kept identical here).
        """
        worker.wait()
        self._workers.remove(worker)
        callback(payload)
        if not self._workers:
            self.busyChanged.emit(False)

    def _on_error(self, exc):
        self.statusChanged.emit(str(exc))
        self.logMessage.emit(str(exc), "ERROR")

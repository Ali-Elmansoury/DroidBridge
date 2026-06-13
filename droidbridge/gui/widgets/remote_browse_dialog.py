"""Modal dialog for picking a path on the connected Android device, reusing
the same listing logic as the Files page browser."""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from droidbridge.core.adb import AdbError
from droidbridge.gui import files_ops

_COLUMNS = ("Name", "Type")

_DIRECTORY_MODE_HINT = "Only folders can be selected here; files are shown for navigation."


class RemoteBrowseDialog(QDialog):
    """`mode="any"` allows selecting a file or directory (pull source).
    `mode="directory"` restricts selection to directories (push destination).
    Selecting nothing and clicking OK picks the *current* directory."""

    def __init__(self, client, serial, start_path, mode="any", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse Device")
        self._client = client
        self._serial = serial
        self._mode = mode
        self._current_path = start_path
        self._entries = []
        self._selected_path = None

        self.path_label = QLabel()
        self.up_button = QPushButton("Up")
        self.hint_label = QLabel(_DIRECTORY_MODE_HINT if mode == "directory" else "")
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.path_label)
        top_bar.addStretch()
        top_bar.addWidget(self.up_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.table)
        layout.addWidget(button_box)

        self.up_button.clicked.connect(self._on_up)
        self.table.itemDoubleClicked.connect(self._on_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

        self._load(start_path, is_initial=True)

    def _load(self, path, is_initial=False):
        try:
            entries = files_ops.list_path(self._client, self._serial, path, show_hidden=False)
        except AdbError as exc:
            if is_initial:
                # `path` may be a file (e.g. seeded from a previously-picked
                # file path) - fall back to its parent directory rather than
                # opening an empty dialog with an error popup.
                self._load(files_ops.parent_path(path))
                return
            QMessageBox.warning(self, "Browse Device", str(exc))
            return
        self._current_path = path
        self._entries = entries
        self._selected_path = None
        self.path_label.setText(path)
        self.table.clearSelection()
        self.table.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            self.table.setItem(i, 0, QTableWidgetItem(entry.name))
            self.table.setItem(i, 1, QTableWidgetItem("dir" if entry.is_dir else "file"))

    def _on_up(self):
        self._load(files_ops.parent_path(self._current_path))

    def _on_double_clicked(self, item):
        entry = self._entries[item.row()]
        if entry.is_dir:
            self._load(entry.path)

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._selected_path = None
            return
        entry = self._entries[rows[0].row()]
        if self._mode == "directory" and not entry.is_dir:
            self.table.clearSelection()
            self._selected_path = None
            return
        self._selected_path = entry.path

    def _on_accept(self):
        self.accept()

    def selected_path(self):
        """Return the chosen path: the selected entry, or the current
        directory if nothing is selected."""
        return self._selected_path or self._current_path

    @staticmethod
    def get_remote_path(parent, client, serial, start_path, mode="any"):
        """Show the dialog modally; return the chosen path, or None if cancelled."""
        dialog = RemoteBrowseDialog(client, serial, start_path, mode=mode, parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_path()
        return None

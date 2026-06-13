"""Files module screen (Phase 6.2): directory browser with a sort/filter/hidden-files
toolbar, multi-select table, and an on-demand preview panel. Purely declarative -
binds to FilesViewModel signals/slots, no ADB calls or business logic of its own.
"""

from PyQt6.QtCore import QItemSelectionModel, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from droidbridge.gui import files_ops
from droidbridge.gui.widgets.deselectable_table import DeselectableTableWidget
from droidbridge.modules import files as files_module
from droidbridge.utils.format import format_bytes

_COLUMNS = ("Name", "Type", "Size", "Date Modified")

PREVIEW_MAX_DIMENSION = 240  # px - caps preview image size so it can't grow the window


class FilesPage(QWidget):
    """Directory browser bound to FilesViewModel."""

    pullRequested = pyqtSignal(list, str)

    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.viewmodel = viewmodel
        self._rows = []

        self.path_edit = QLineEdit(viewmodel.current_path)
        self.go_button = QPushButton("Go")
        self.up_button = QPushButton("Up")

        path_bar = QHBoxLayout()
        path_bar.addWidget(self.path_edit)
        path_bar.addWidget(self.go_button)
        path_bar.addWidget(self.up_button)

        self.quick_jump_buttons = {}
        quick_jump_bar = QHBoxLayout()
        for label, path in files_ops.QUICK_JUMP_PATHS.items():
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, p=path: self.viewmodel.navigate(p))
            self.quick_jump_buttons[label] = button
            quick_jump_bar.addWidget(button)
        quick_jump_bar.addStretch()

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(files_module.SORT_KEYS)
        self.reverse_checkbox = QCheckBox("Reverse")
        self.show_hidden_checkbox = QCheckBox("Show hidden")
        self.extension_edit = QLineEdit()
        self.extension_edit.setPlaceholderText("Extensions (comma-separated)")

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Sort by:"))
        toolbar.addWidget(self.sort_combo)
        toolbar.addWidget(self.reverse_checkbox)
        toolbar.addWidget(self.show_hidden_checkbox)
        toolbar.addWidget(self.extension_edit)

        self.table = DeselectableTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.select_all_button = QPushButton("Select All")
        self.deselect_all_button = QPushButton("Deselect All")
        self.invert_selection_button = QPushButton("Invert Selection")
        self.pull_selected_button = QPushButton("Pull Selected...")
        self.pull_selected_button.setEnabled(False)

        selection_bar = QHBoxLayout()
        selection_bar.addWidget(self.select_all_button)
        selection_bar.addWidget(self.deselect_all_button)
        selection_bar.addWidget(self.invert_selection_button)
        selection_bar.addStretch()
        selection_bar.addWidget(self.pull_selected_button)

        self.preview_image_label = QLabel()
        self.preview_image_label.setVisible(False)
        self.preview_info_label = QLabel("No selection.")
        self.preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(self.preview_group)
        preview_layout.addWidget(self.preview_image_label)
        preview_layout.addWidget(self.preview_info_label)

        layout = QVBoxLayout(self)
        layout.addLayout(path_bar)
        layout.addLayout(quick_jump_bar)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)
        layout.addLayout(selection_bar)
        layout.addWidget(self.preview_group)

        self.path_edit.returnPressed.connect(self._on_path_entered)
        self.go_button.clicked.connect(self._on_path_entered)
        self.up_button.clicked.connect(self.viewmodel.go_up)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        self.reverse_checkbox.toggled.connect(self._on_sort_changed)
        self.show_hidden_checkbox.toggled.connect(self.viewmodel.set_show_hidden)
        self.extension_edit.textChanged.connect(self._on_extension_filter_changed)
        self.select_all_button.clicked.connect(self.table.selectAll)
        self.deselect_all_button.clicked.connect(self.table.clearSelection)
        self.invert_selection_button.clicked.connect(self._on_invert_selection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)
        self.pull_selected_button.clicked.connect(self._on_pull_selected)

        self.viewmodel.entriesChanged.connect(self._on_entries_changed)
        self.viewmodel.pathChanged.connect(self._on_path_changed)
        self.viewmodel.previewChanged.connect(self._on_preview_changed)

    def _on_path_entered(self):
        self.viewmodel.navigate(self.path_edit.text())

    def _on_sort_changed(self, *_args):
        self.viewmodel.set_sort(self.sort_combo.currentText(), self.reverse_checkbox.isChecked())

    def _on_extension_filter_changed(self):
        text = self.extension_edit.text().strip()
        extensions = [e.strip().lower() for e in text.split(",") if e.strip()] if text else None
        self.viewmodel.set_extension_filter(extensions)

    def _on_entries_changed(self, rows):
        self._rows = rows
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(row["type"]))
            self.table.setItem(i, 2, QTableWidgetItem(format_bytes(row["size"])))
            self.table.setItem(i, 3, QTableWidgetItem(row["mtime"].strftime("%Y-%m-%d %H:%M")))

    def _on_path_changed(self, path):
        self.path_edit.setText(path)

    def _on_selection_changed(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        self.pull_selected_button.setEnabled(bool(selected_rows))
        if len(selected_rows) == 1:
            self.viewmodel.select_entry(self._rows[selected_rows[0]]["entry"])
        else:
            self.viewmodel.select_entry(None)

    def _on_row_double_clicked(self, item):
        row = self._rows[item.row()]
        if row["is_dir"]:
            self.viewmodel.navigate(row["path"])

    def _on_invert_selection(self):
        selection_model = self.table.selectionModel()
        for row in range(self.table.rowCount()):
            index = self.table.model().index(row, 0)
            selection_model.select(
                index, QItemSelectionModel.SelectionFlag.Toggle | QItemSelectionModel.SelectionFlag.Rows
            )

    def _on_preview_changed(self, payload):
        if payload["kind"] == "image":
            pixmap = QPixmap(payload["local_path"])
            if pixmap.width() > PREVIEW_MAX_DIMENSION or pixmap.height() > PREVIEW_MAX_DIMENSION:
                pixmap = pixmap.scaled(
                    PREVIEW_MAX_DIMENSION, PREVIEW_MAX_DIMENSION,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
                )
            self.preview_image_label.setPixmap(pixmap)
            self.preview_image_label.setVisible(True)
            self.preview_info_label.setVisible(False)
            return

        entry = payload["entry"]
        self.preview_image_label.setVisible(False)
        self.preview_info_label.setVisible(True)
        if entry is None:
            self.preview_info_label.setText("No selection.")
        else:
            kind = "Directory" if entry.is_dir else (entry.extension or "File")
            self.preview_info_label.setText(
                f"Name: {entry.name}\n"
                f"Type: {kind}\n"
                f"Size: {format_bytes(entry.size)}\n"
                f"Modified: {entry.mtime.strftime('%Y-%m-%d %H:%M')}"
            )

    def _on_pull_selected(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows:
            return
        remote_paths = [self._rows[r]["path"] for r in selected_rows]
        local_dir = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if not local_dir:
            return
        self.pullRequested.emit(remote_paths, local_dir)

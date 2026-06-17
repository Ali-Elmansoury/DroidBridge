"""Files module screen (Phase 6.2): directory browser with a sort/filter/hidden-files
toolbar, multi-select table, and an on-demand preview panel. Purely declarative -
binds to FilesViewModel signals/slots, no ADB calls or business logic of its own.
"""

from PyQt6.QtCore import QItemSelectionModel, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from droidbridge.gui import files_ops
from droidbridge.gui.widgets import delete_flow
from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
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

        self.breadcrumb = BreadcrumbBar()
        self.breadcrumb.set_path(viewmodel.current_path)
        self.breadcrumb.pathRequested.connect(viewmodel.navigate)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(files_module.SORT_KEYS)
        self.reverse_checkbox = QCheckBox("Reverse")
        self.show_hidden_checkbox = QCheckBox("Show hidden")
        self.extension_edit = QLineEdit()
        self.extension_edit.setPlaceholderText("Extensions (comma-separated)")
        self.extension_edit.setMinimumWidth(
            self.extension_edit.fontMetrics().horizontalAdvance(self.extension_edit.placeholderText()) + 20
        )
        self.dirs_pass_filter_checkbox = QCheckBox("Show folders when filtering")
        self.dirs_pass_filter_checkbox.setChecked(True)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Sort by:"))
        toolbar.addWidget(self.sort_combo)
        toolbar.addWidget(self.reverse_checkbox)
        toolbar.addWidget(self.show_hidden_checkbox)
        toolbar.addWidget(self.extension_edit, 1)
        toolbar.addWidget(self.dirs_pass_filter_checkbox)

        self.table = DeselectableTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.select_all_button = QPushButton("Select All")
        self.deselect_all_button = QPushButton("Deselect All")
        self.invert_selection_button = QPushButton("Invert Selection")
        self.rename_button = QPushButton("Rename")
        self.rename_button.setEnabled(False)
        self.delete_button = QPushButton("Delete...")
        self.delete_button.setEnabled(False)
        self.pull_selected_button = QPushButton("Pull Selected...")
        self.pull_selected_button.setEnabled(False)

        selection_bar = QHBoxLayout()
        selection_bar.addWidget(self.select_all_button)
        selection_bar.addWidget(self.deselect_all_button)
        selection_bar.addWidget(self.invert_selection_button)
        selection_bar.addStretch()
        selection_bar.addWidget(self.rename_button)
        selection_bar.addWidget(self.delete_button)
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
        layout.addWidget(self.breadcrumb)
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
        self.dirs_pass_filter_checkbox.toggled.connect(self.viewmodel.set_dirs_pass_extension_filter)
        self.select_all_button.clicked.connect(self.table.selectAll)
        self.deselect_all_button.clicked.connect(self.table.clearSelection)
        self.invert_selection_button.clicked.connect(self._on_invert_selection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)
        self.pull_selected_button.clicked.connect(self._on_pull_selected)
        self.rename_button.clicked.connect(self._on_rename)
        self.delete_button.clicked.connect(self._on_delete)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

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
        self.breadcrumb.set_path(path)

    def _on_selection_changed(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        self.pull_selected_button.setEnabled(bool(selected_rows))
        self.rename_button.setEnabled(len(selected_rows) == 1)
        self.delete_button.setEnabled(bool(selected_rows))
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
            entry = payload.get("entry")
            if entry is not None:
                kind = "Directory" if entry.is_dir else (entry.extension or "File")
                self.preview_info_label.setText(
                    f"Path: {entry.path}\n"
                    f"Name: {entry.name}\n"
                    f"Type: {kind}\n"
                    f"Size: {format_bytes(entry.size)}\n"
                    f"Modified: {entry.mtime.strftime('%Y-%m-%d %H:%M')}"
                )
                self.preview_info_label.setVisible(True)
            else:
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
                f"Path: {entry.path}\n"
                f"Name: {entry.name}\n"
                f"Type: {kind}\n"
                f"Size: {format_bytes(entry.size)}\n"
                f"Modified: {entry.mtime.strftime('%Y-%m-%d %H:%M')}"
            )

    def _on_context_menu(self, pos):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        single = len(selected_rows) == 1
        multi = bool(selected_rows)

        menu = QMenu(self)
        pull_action = menu.addAction("Pull to Laptop...")
        pull_action.setEnabled(multi)
        rename_action = menu.addAction("Rename...")
        rename_action.setEnabled(single)
        delete_action = menu.addAction("Delete...")
        delete_action.setEnabled(multi)
        menu.addSeparator()
        copy_path_action = menu.addAction("Copy Path to Clipboard")
        copy_path_action.setEnabled(single)

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == pull_action:
            self._on_pull_selected()
        elif action == rename_action:
            self._on_rename()
        elif action == delete_action:
            self._on_delete()
        elif action == copy_path_action and single:
            path = self._rows[selected_rows[0]]["path"]
            QApplication.clipboard().setText(path)

    def _on_pull_selected(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows:
            return
        remote_paths = [self._rows[r]["path"] for r in selected_rows]
        local_dir = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if not local_dir:
            return
        self.pullRequested.emit(remote_paths, local_dir)

    def _on_rename(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if len(selected_rows) != 1:
            return
        path = self._rows[selected_rows[0]]["path"]
        new_path = delete_flow.run_rename_flow(
            self, self.viewmodel.context.client, self.viewmodel.context.serial, path,
        )
        if new_path is not None:
            self.viewmodel.navigate(self.viewmodel.current_path)

    def _on_delete(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows:
            return
        paths = [self._rows[r]["path"] for r in selected_rows]
        deleted = delete_flow.run_delete_flow(
            self, self.viewmodel.context.client, self.viewmodel.context.serial, paths,
        )
        if deleted:
            self.viewmodel.navigate(self.viewmodel.current_path)

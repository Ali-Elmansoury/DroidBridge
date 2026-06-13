"""Search module screen (Phase 6.2): search form (root/name/extensions/size/date/preset),
results table, and pull-selected. Purely declarative - binds to SearchViewModel
signals/slots, no ADB calls or business logic of its own.
"""

from PyQt6.QtCore import QDate, QItemSelectionModel, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
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
from droidbridge.modules import search as search_module
from droidbridge.utils.format import format_bytes

_COLUMNS = ("Path", "Size", "Date Modified")


class SearchPage(QWidget):
    """Search form + results table bound to SearchViewModel."""

    pullRequested = pyqtSignal(list, str)

    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.viewmodel = viewmodel
        self._rows = []

        self.root_edit = QLineEdit(search_module.DEFAULT_ROOT)
        self._root_browse_path = search_module.DEFAULT_ROOT
        self.root_browse_label = QLabel("Browse:")
        self.root_browse_combo = QComboBox()
        self.root_browse_combo.setToolTip(
            "Browse subfolders of the root path: pick one to search inside it, "
            "or '..' to go up a level."
        )
        self.name_edit = QLineEdit()
        self.extensions_edit = QLineEdit()
        self.extensions_edit.setPlaceholderText("Extensions (comma-separated)")
        self.min_size_edit = QLineEdit()
        self.min_size_edit.setPlaceholderText("e.g. 10MB")
        self.max_size_edit = QLineEdit()
        self.max_size_edit.setPlaceholderText("e.g. 1GB")

        self.after_checkbox = QCheckBox("After")
        self.after_date_edit = QDateEdit(QDate.currentDate())
        self.after_date_edit.setCalendarPopup(True)
        self.after_date_edit.setEnabled(False)

        self.before_checkbox = QCheckBox("Before")
        self.before_date_edit = QDateEdit(QDate.currentDate())
        self.before_date_edit.setCalendarPopup(True)
        self.before_date_edit.setEnabled(False)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["None"] + list(search_module.PRESET_NAMES))

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(search_module.SORT_KEYS)
        self.reverse_checkbox = QCheckBox("Reverse")

        self.search_button = QPushButton("Search")

        form = QFormLayout()
        root_row = QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(self.root_browse_label)
        root_row.addWidget(self.root_browse_combo)
        form.addRow("Root path:", root_row)
        form.addRow("Name pattern:", self.name_edit)
        form.addRow("Extensions:", self.extensions_edit)
        form.addRow("Min size:", self.min_size_edit)
        form.addRow("Max size:", self.max_size_edit)

        after_row = QHBoxLayout()
        after_row.addWidget(self.after_checkbox)
        after_row.addWidget(self.after_date_edit)
        form.addRow(after_row)

        before_row = QHBoxLayout()
        before_row.addWidget(self.before_checkbox)
        before_row.addWidget(self.before_date_edit)
        form.addRow(before_row)

        form.addRow("Preset:", self.preset_combo)

        sort_row = QHBoxLayout()
        sort_row.addWidget(self.sort_combo)
        sort_row.addWidget(self.reverse_checkbox)
        form.addRow("Sort by:", sort_row)

        form.addRow(self.search_button)

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

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.table)
        layout.addLayout(selection_bar)

        self.after_checkbox.toggled.connect(self.after_date_edit.setEnabled)
        self.before_checkbox.toggled.connect(self.before_date_edit.setEnabled)
        self.search_button.clicked.connect(self._on_search_clicked)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        self.reverse_checkbox.toggled.connect(self._on_sort_changed)
        self.select_all_button.clicked.connect(self.table.selectAll)
        self.deselect_all_button.clicked.connect(self.table.clearSelection)
        self.invert_selection_button.clicked.connect(self._on_invert_selection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.pull_selected_button.clicked.connect(self._on_pull_selected)

        self.root_browse_combo.activated.connect(self._on_root_browse_selected)
        self.root_edit.editingFinished.connect(self._on_root_edit_finished)
        self.viewmodel.context.connectionChanged.connect(self._on_connection_changed)

        self.viewmodel.resultsChanged.connect(self._on_results_changed)
        self.viewmodel.rootSubdirsChanged.connect(self._on_root_subdirs_changed)

        self.viewmodel.browse_root(self.root_edit.text().strip())

    def _on_search_clicked(self):
        preset = self.preset_combo.currentText()
        preset = None if preset == "None" else preset

        extensions_text = self.extensions_edit.text().strip()
        extensions = (
            [e.strip().lower() for e in extensions_text.split(",") if e.strip()]
            if extensions_text
            else None
        )

        after = self.after_date_edit.date().toPyDate() if self.after_checkbox.isChecked() else None
        before = self.before_date_edit.date().toPyDate() if self.before_checkbox.isChecked() else None

        self.viewmodel.search(
            root=self.root_edit.text().strip(),
            name=self.name_edit.text().strip() or None,
            extensions=extensions,
            min_size_str=self.min_size_edit.text().strip(),
            max_size_str=self.max_size_edit.text().strip(),
            after=after,
            before=before,
            preset=preset,
            sort_by=self.sort_combo.currentText(),
            reverse=self.reverse_checkbox.isChecked(),
        )

    def _on_root_subdirs_changed(self, path, subdirs):
        self._root_browse_path = path
        self.root_browse_combo.blockSignals(True)
        self.root_browse_combo.clear()
        if path not in ("/", search_module.DEFAULT_ROOT):
            self.root_browse_combo.addItem("..")
        self.root_browse_combo.addItems(subdirs)
        self.root_browse_combo.setCurrentIndex(-1)
        self.root_browse_combo.blockSignals(False)

    def _on_root_browse_selected(self, index):
        name = self.root_browse_combo.itemText(index)
        if name == "..":
            new_path = files_ops.parent_path(self._root_browse_path)
        elif self._root_browse_path == "/":
            new_path = f"/{name}"
        else:
            new_path = f"{self._root_browse_path}/{name}"
        self.root_edit.setText(new_path)
        self.viewmodel.browse_root(new_path)

    def _on_root_edit_finished(self):
        self.viewmodel.browse_root(self.root_edit.text().strip())

    def _on_connection_changed(self, connected, _serial, _model):
        if connected:
            self.viewmodel.browse_root(self.root_edit.text().strip())

    def _on_sort_changed(self, *_args):
        self.viewmodel.set_sort(self.sort_combo.currentText(), self.reverse_checkbox.isChecked())

    def _on_results_changed(self, rows):
        self._rows = rows
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["path"]))
            self.table.setItem(i, 1, QTableWidgetItem(format_bytes(row["size"])))
            self.table.setItem(i, 2, QTableWidgetItem(row["mtime"].strftime("%Y-%m-%d %H:%M")))
        self.pull_selected_button.setEnabled(False)

    def _on_selection_changed(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        self.pull_selected_button.setEnabled(bool(selected_rows))

    def _on_invert_selection(self):
        selection_model = self.table.selectionModel()
        for row in range(self.table.rowCount()):
            index = self.table.model().index(row, 0)
            selection_model.select(
                index, QItemSelectionModel.SelectionFlag.Toggle | QItemSelectionModel.SelectionFlag.Rows
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

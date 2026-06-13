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
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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
        form.addRow("Root path:", self.root_edit)
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

        self.table = QTableWidget(0, len(_COLUMNS))
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

        self.viewmodel.resultsChanged.connect(self._on_results_changed)

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

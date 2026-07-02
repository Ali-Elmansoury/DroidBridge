# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Search module screen (Phase 6.2): search form (root/name/extensions/size/date/preset),
results table, and pull-selected. Purely declarative - binds to SearchViewModel
signals/slots, no ADB calls or business logic of its own.
"""

from PyQt6.QtCore import QDate, QEvent, QItemSelectionModel, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from datetime import datetime

from droidbridge.gui import files_ops
from droidbridge.gui.widgets import delete_flow
from droidbridge.gui.widgets.export_button import export_report
from droidbridge.gui.widgets.deselectable_table import DeselectableTableWidget
from droidbridge.modules import search as search_module
from droidbridge.reports.generators import Report, ReportSection
from droidbridge.utils.format import format_bytes

_COLUMNS = ("Path", "Size", "Date Modified", "Extension")


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
        self.name_mode_combo = QComboBox()
        self.name_mode_combo.addItems(["Glob", "Regex"])
        self.name_mode_combo.setToolTip(
            "Choose whether to treat the name field as a glob pattern or a Python regular expression."
        )
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. *.jpg")
        self.name_edit.setToolTip(
            "Filename glob pattern. * matches any characters, ? matches one. "
            "Case-insensitive. Leave blank to match all names."
        )
        self.mime_combo = QComboBox()
        self.mime_combo.addItems(["—", "image", "video", "audio", "document", "archive"])
        self.mime_combo.setToolTip(
            "Filter by file type group. 'image' matches jpg/png/gif/etc., "
            "'video' matches mp4/mkv/etc., 'audio' matches mp3/aac/etc., "
            "'document' matches pdf/docx/etc., 'archive' matches zip/tar/etc. "
            "Mutually exclusive with Extensions — clear Extensions before using this."
        )
        self.extensions_edit = QLineEdit()
        self.extensions_edit.setPlaceholderText("Extensions (comma-separated)")
        self.extensions_edit.setToolTip(
            "Filter by file extension(s), e.g. jpg, png. Leave blank for all types. "
            "Mutually exclusive with MIME type."
        )
        self.min_size_edit = QLineEdit()
        self.min_size_edit.setPlaceholderText("e.g. 10MB")
        self.min_size_edit.setToolTip(
            "Minimum file size, e.g. 10MB, 1.5GB. Leave blank for no minimum."
        )
        self.max_size_edit = QLineEdit()
        self.max_size_edit.setPlaceholderText("e.g. 1GB")
        self.max_size_edit.setToolTip("Maximum file size, e.g. 500MB. Leave blank for no maximum.")

        self.after_checkbox = QCheckBox("After")
        self.after_checkbox.setToolTip("Include only files modified after the date on the right.")
        self.after_date_edit = QDateEdit(QDate.currentDate())
        self.after_date_edit.setCalendarPopup(True)
        self.after_date_edit.setEnabled(False)
        self.after_date_edit.setToolTip("Earliest modification date to include in results.")

        self.before_checkbox = QCheckBox("Before")
        self.before_checkbox.setToolTip("Include only files modified before the date on the right.")
        self.before_date_edit = QDateEdit(QDate.currentDate())
        self.before_date_edit.setCalendarPopup(True)
        self.before_date_edit.setEnabled(False)
        self.before_date_edit.setToolTip("Latest modification date to include in results.")

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["None"] + list(search_module.PRESET_NAMES))
        self.preset_combo.setToolTip(
            "Load a predefined search configuration (e.g. Large Files, WhatsApp Images). "
            "Overwrites the current fields."
        )

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(search_module.SORT_KEYS)
        self.sort_combo.setToolTip("Sort search results by this field.")
        self.reverse_checkbox = QCheckBox("Reverse")
        self.reverse_checkbox.setToolTip("Sort results in descending order.")

        self.search_button = QPushButton("Search")
        self.search_button.setToolTip("Run the search with the current filters. Shortcut: F5.")

        form = QFormLayout()
        root_row = QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(self.root_browse_label)
        root_row.addWidget(self.root_browse_combo)
        form.addRow("Root path:", root_row)
        name_row = QHBoxLayout()
        name_row.addWidget(self.name_mode_combo)
        name_row.addWidget(self.name_edit, 1)
        form.addRow("Name:", name_row)
        form.addRow("Extensions:", self.extensions_edit)
        form.addRow("MIME type:", self.mime_combo)
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
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setToolTip("Select all search results. Shortcut: Ctrl+A.")
        self.deselect_all_button = QPushButton("Deselect All")
        self.deselect_all_button.setToolTip("Clear the selection. Shortcut: Escape.")
        self.invert_selection_button = QPushButton("Invert Selection")
        self.invert_selection_button.setToolTip(
            "Select unselected results and deselect selected ones."
        )
        self.clear_results_button = QPushButton("Clear Results")
        self.clear_results_button.setToolTip("Clear the results table.")
        self.rename_button = QPushButton("Rename")
        self.rename_button.setEnabled(False)
        self.rename_button.setToolTip(
            "Rename the selected file or folder (single selection only). Shortcut: F2."
        )
        self.delete_button = QPushButton("Delete...")
        self.delete_button.setEnabled(False)
        self.delete_button.setToolTip(
            "Delete selected items with backup option and 'YES DELETE' confirmation. "
            "Shortcut: Delete."
        )
        self.pull_selected_button = QPushButton("Pull Selected...")
        self.pull_selected_button.setEnabled(False)
        self.pull_selected_button.setToolTip(
            "Download selected files and folders to your computer."
        )
        self.export_button = QPushButton("Export...")
        self.export_button.setEnabled(False)
        self.export_button.setToolTip("Export the search results to TXT, CSV, HTML, or JSON.")

        selection_bar = QHBoxLayout()
        selection_bar.addWidget(self.select_all_button)
        selection_bar.addWidget(self.deselect_all_button)
        selection_bar.addWidget(self.invert_selection_button)
        selection_bar.addWidget(self.clear_results_button)
        selection_bar.addStretch()
        selection_bar.addWidget(self.rename_button)
        selection_bar.addWidget(self.delete_button)
        selection_bar.addWidget(self.pull_selected_button)
        selection_bar.addWidget(self.export_button)

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
        self.clear_results_button.clicked.connect(self._on_clear_results)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.pull_selected_button.clicked.connect(self._on_pull_selected)
        self.export_button.clicked.connect(self._on_export_clicked)
        self.rename_button.clicked.connect(self._on_rename)
        self.delete_button.clicked.connect(self._on_delete)

        self.name_mode_combo.currentTextChanged.connect(self._on_name_mode_changed)
        self.root_browse_combo.activated.connect(self._on_root_browse_selected)
        self.root_edit.editingFinished.connect(self._on_root_edit_finished)
        self.viewmodel.context.connectionChanged.connect(self._on_connection_changed)

        self.viewmodel.resultsChanged.connect(self._on_results_changed)
        self.viewmodel.rootSubdirsChanged.connect(self._on_root_subdirs_changed)

        self.viewmodel.browse_root(self.root_edit.text().strip())

        def _sc(key, slot, *, target=None, ctx=Qt.ShortcutContext.WidgetWithChildrenShortcut):
            s = QShortcut(QKeySequence(key), target or self)
            s.setContext(ctx)
            s.activated.connect(slot)

        _sc("F5", self.search_button.click)
        _sc("Escape", self.table.clearSelection)
        _sc("Ctrl+Shift+C", self._copy_path_shortcut)
        _sc("F2", self._on_rename, target=self.table, ctx=Qt.ShortcutContext.WidgetShortcut)
        _sc("Delete", self._on_delete, target=self.table, ctx=Qt.ShortcutContext.WidgetShortcut)

        self.table.installEventFilter(self)
        self.table.viewport().installEventFilter(self)

    def _copy_path_shortcut(self):
        selected = sorted({index.row() for index in self.table.selectedIndexes()})
        if len(selected) == 1:
            QApplication.clipboard().setText(self._rows[selected[0]]["path"])

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_F5 and not mods:
            self.search_button.click()
            event.accept()
            return
        if key == Qt.Key.Key_Escape and not mods:
            self.table.clearSelection()
            event.accept()
            return
        if (key == Qt.Key.Key_C and
                mods == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
            self._copy_path_shortcut()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if (obj is self.table or obj is self.table.viewport()) and \
                event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key == Qt.Key.Key_F2 and not mods:
                self._on_rename()
                return True
            if key == Qt.Key.Key_Delete and not mods:
                self._on_delete()
                return True
        return super().eventFilter(obj, event)

    def _on_search_clicked(self):
        preset = self.preset_combo.currentText()
        preset = None if preset == "None" else preset

        if self.name_mode_combo.currentText() == "Regex":
            name_regex = self.name_edit.text() or None
            name = None
        else:
            name = self.name_edit.text().strip() or None
            name_regex = None

        mime = self.mime_combo.currentText()
        mime = None if mime == "—" else mime

        extensions_text = self.extensions_edit.text().strip()
        extensions = (
            [e.strip().lower() for e in extensions_text.split(",") if e.strip()]
            if extensions_text
            else None
        )

        if extensions and mime:
            self.viewmodel.statusChanged.emit(
                "Error: Extensions and MIME type are mutually exclusive — clear one before searching."
            )
            return

        if mime and preset in search_module.PRESET_EXTENSIONS:
            self.viewmodel.statusChanged.emit(
                f"Error: MIME type and preset '{preset}' are mutually exclusive "
                f"— both filter by file extension. Clear one before searching."
            )
            return

        after = self.after_date_edit.date().toPyDate() if self.after_checkbox.isChecked() else None
        before = self.before_date_edit.date().toPyDate() if self.before_checkbox.isChecked() else None

        self.viewmodel.search(
            root=self.root_edit.text().strip(),
            name=name,
            extensions=extensions,
            min_size_str=self.min_size_edit.text().strip(),
            max_size_str=self.max_size_edit.text().strip(),
            after=after,
            before=before,
            preset=preset,
            sort_by=self.sort_combo.currentText(),
            reverse=self.reverse_checkbox.isChecked(),
            name_regex=name_regex,
            mime=mime,
        )

    def _on_name_mode_changed(self, text):
        if text == "Regex":
            self.name_edit.setPlaceholderText('e.g. IMG_.*\\.jpg')
            self.name_edit.setToolTip(
                "Python regular expression matched case-insensitively against the full "
                "file path. A leading .* is added automatically if the pattern does not "
                "start with it."
            )
        else:
            self.name_edit.setPlaceholderText("e.g. *.jpg")
            self.name_edit.setToolTip(
                "Filename glob pattern. * matches any characters, ? matches one. "
                "Case-insensitive. Leave blank to match all names."
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
        self._populate_table()
        self.pull_selected_button.setEnabled(False)
        self.rename_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.export_button.setEnabled(bool(rows))

    def _populate_table(self):
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            path_item = QTableWidgetItem(row["path"])
            path_item.setToolTip(row["path"])
            self.table.setItem(i, 0, path_item)
            self.table.setItem(i, 1, QTableWidgetItem(format_bytes(row["size"])))
            self.table.setItem(i, 2, QTableWidgetItem(row["mtime"].strftime("%Y-%m-%d %H:%M")))
            self.table.setItem(i, 3, QTableWidgetItem(row.get("extension") or "(none)"))

    def _on_selection_changed(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        self.pull_selected_button.setEnabled(bool(selected_rows))
        self.rename_button.setEnabled(len(selected_rows) == 1)
        self.delete_button.setEnabled(bool(selected_rows))

    def _on_clear_results(self):
        self._rows = []
        self.table.setRowCount(0)
        self.pull_selected_button.setEnabled(False)
        self.rename_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.export_button.setEnabled(False)

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

    def _on_rename(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if len(selected_rows) != 1:
            return
        row_index = selected_rows[0]
        path = self._rows[row_index]["path"]
        new_path = delete_flow.run_rename_flow(
            self, self.viewmodel.context.client, self.viewmodel.context.serial, path,
        )
        if new_path is not None:
            self._update_row_path(row_index, new_path)

    def _update_row_path(self, row_index, new_path):
        self._rows[row_index]["path"] = new_path
        self._populate_table()

    def _on_delete(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows:
            return
        paths = [self._rows[r]["path"] for r in selected_rows]
        deleted = delete_flow.run_delete_flow(
            self, self.viewmodel.context.client, self.viewmodel.context.serial, paths,
        )
        if deleted:
            self._remove_deleted_rows(deleted)

    def _remove_deleted_rows(self, deleted_paths):
        self._rows = [row for row in self._rows if row["path"] not in deleted_paths]
        self._populate_table()
        self.pull_selected_button.setEnabled(False)
        self.rename_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def _on_export_clicked(self):
        if not self._rows:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        section = ReportSection(
            title="Search Results",
            headers=["Path", "Size", "Date", "Extension"],
            rows=[
                [
                    row["path"],
                    format_bytes(row["size"]),
                    row["mtime"].strftime("%Y-%m-%d %H:%M"),
                    row.get("extension") or "",
                ]
                for row in self._rows
            ],
        )
        export_report(
            self, "Export Search Results", f"search_results_{ts}.txt",
            Report(title="Search Results", sections=[section]),
        )

# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Soft-Delete Scanner panel (Module 10 — Recovery page, tab 1)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from droidbridge.utils.format import format_bytes


class ScannerPanel(QWidget):
    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.viewmodel = viewmodel
        self._results = []
        self._build_ui()
        self._connect_signals()

    @property
    def viewmodels(self):
        return [self.viewmodel]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton("Scan Device")
        self.scan_btn.setToolTip("Scan all known soft-delete trash locations on the connected device.")
        btn_row.addWidget(self.scan_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Filename", "Size", "Date Modified", "Type", "Source App"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setToolTip("Files found in soft-delete trash locations. Select rows to save or restore.")
        root.addWidget(self.table)

        action_row = QHBoxLayout()
        self.save_btn = QPushButton("Save to PC")
        self.save_btn.setToolTip("Pull selected files to a local folder on this computer.")
        self.save_btn.setEnabled(False)
        self.restore_btn = QPushButton("Restore to Phone")
        self.restore_btn.setToolTip(
            "Push selected files back to their original location on the device.\n"
            "Only available for files from true trash folders."
        )
        self.restore_btn.setEnabled(False)
        action_row.addWidget(self.save_btn)
        action_row.addWidget(self.restore_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        self.status_label = QLabel("")
        root.addWidget(self.status_label)

    def _connect_signals(self):
        self.scan_btn.clicked.connect(self.viewmodel.scan)
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.restore_btn.clicked.connect(self._on_restore_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.scanResultsChanged.connect(self._on_results)
        self.viewmodel.statusChanged.connect(self.status_label.setText)

    def _on_busy(self, busy):
        self.progress.setVisible(busy)
        self.scan_btn.setEnabled(not busy)

    def _on_results(self, results):
        self._results = results
        self.table.setRowCount(0)
        for f in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f.filename))
            self.table.setItem(row, 1, QTableWidgetItem(format_bytes(f.size_bytes)))
            self.table.setItem(row, 2, QTableWidgetItem(f.modified_date))
            self.table.setItem(row, 3, QTableWidgetItem(f.file_type))
            self.table.setItem(row, 4, QTableWidgetItem(f.source_app))
        self._on_selection_changed()

    def _on_selection_changed(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        selected = [self._results[r] for r in rows if r < len(self._results)]
        self.save_btn.setEnabled(bool(selected))
        has_true_trash = any(f.is_true_trash for f in selected)
        self.restore_btn.setEnabled(has_true_trash)

    def _on_save_clicked(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        selected = [self._results[r] for r in rows if r < len(self._results)]
        if not selected:
            return
        dest = QFileDialog.getExistingDirectory(self, "Save recovered files to...")
        if dest:
            self.viewmodel.pull_to_pc(selected, dest)

    def _on_restore_clicked(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        selected = [f for r in rows if r < len(self._results) for f in [self._results[r]] if f.is_true_trash]
        if selected:
            self.viewmodel.push_to_phone(selected)

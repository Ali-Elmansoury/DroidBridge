# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Backup Restore panel (Module 10 — Recovery page, tab 2)."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class RestorePanel(QWidget):
    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.viewmodel = viewmodel
        self._backups = []
        self._diff = {}
        self._build_ui()
        self._connect_signals()

    @property
    def viewmodels(self):
        return [self.viewmodel]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        # Backup directory selector
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("Select the folder containing a DroidBridge backup...")
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setToolTip("Folder containing contacts_*.vcf and/or call_log.csv from a prior DroidBridge backup.")
        browse_btn = QPushButton("Browse...")
        browse_btn.setToolTip("Open a folder picker to select the backup directory.")
        browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(QLabel("Backup folder:"))
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse_btn)
        root.addLayout(dir_row)

        # Backup selector dropdown
        combo_row = QHBoxLayout()
        self.backup_combo = QComboBox()
        self.backup_combo.setToolTip("Select a backup to restore from.")
        self.backup_combo.setEnabled(False)
        combo_row.addWidget(QLabel("Backup:"))
        combo_row.addWidget(self.backup_combo, 1)
        root.addLayout(combo_row)

        # Diff panel
        self.diff_group = QGroupBox("Estimated Missing Data")
        diff_layout = QFormLayout(self.diff_group)
        self.contacts_diff_label = QLabel("—")
        self.calls_diff_label = QLabel("—")
        diff_layout.addRow("Contacts:", self.contacts_diff_label)
        diff_layout.addRow("Call log:", self.calls_diff_label)
        root.addWidget(self.diff_group)

        # Restore options
        options_group = QGroupBox("Restore Options")
        options_layout = QVBoxLayout(options_group)
        self.contacts_check = QCheckBox("Restore Contacts")
        self.contacts_check.setToolTip("Restore contacts from the selected backup.")
        self.calls_check = QCheckBox("Restore Call Log")
        self.calls_check.setToolTip("Restore call log entries from the selected backup.")
        options_layout.addWidget(self.contacts_check)
        options_layout.addWidget(self.calls_check)

        dest_row = QHBoxLayout()
        self.dest_phone_radio = QRadioButton("Restore to phone")
        self.dest_phone_radio.setToolTip("Push data back to the phone via ADB.")
        self.dest_pc_radio = QRadioButton("Save to PC")
        self.dest_pc_radio.setChecked(True)
        self.dest_pc_radio.setToolTip("Save the backup file to a local folder on this computer.")
        dest_row.addWidget(self.dest_phone_radio)
        dest_row.addWidget(self.dest_pc_radio)
        dest_row.addStretch()
        options_layout.addLayout(dest_row)

        pc_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Output folder (for Save to PC)...")
        self.output_edit.setReadOnly(True)
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self._browse_output)
        pc_row.addWidget(self.output_edit, 1)
        pc_row.addWidget(output_browse_btn)
        options_layout.addLayout(pc_row)
        root.addWidget(options_group)

        self.phone_note = QLabel(
            "Your phone's Contacts app will open to confirm the import.\n"
            "Please accept it on your device."
        )
        self.phone_note.setVisible(False)
        root.addWidget(self.phone_note)

        self.restore_btn = QPushButton("Restore")
        self.restore_btn.setToolTip("Start the restore operation with the selected options.")
        self.restore_btn.setEnabled(False)
        root.addWidget(self.restore_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status_label = QLabel("")
        root.addWidget(self.status_label)
        root.addStretch()

    def _connect_signals(self):
        self.backup_combo.currentIndexChanged.connect(self._on_backup_selected)
        self.contacts_check.toggled.connect(self._update_restore_btn)
        self.calls_check.toggled.connect(self._update_restore_btn)
        self.dest_phone_radio.toggled.connect(self._on_dest_changed)
        self.restore_btn.clicked.connect(self._on_restore_clicked)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.backupsChanged.connect(self._on_backups)
        self.viewmodel.diffChanged.connect(self._on_diff)
        self.viewmodel.statusChanged.connect(self.status_label.setText)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select DroidBridge backup folder...")
        if path:
            self.dir_edit.setText(path)
            self.viewmodel.load_backups(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select output folder...")
        if path:
            self.output_edit.setText(path)

    def _on_backups(self, backups):
        self._backups = backups
        self.backup_combo.clear()
        for b in backups:
            label = f"{b.date} — {b.contacts_count} contacts, {b.calls_count} calls ({Path(b.path).name})"
            self.backup_combo.addItem(label)
        self.backup_combo.setEnabled(bool(backups))
        if backups:
            self._on_backup_selected(0)

    def _on_backup_selected(self, index):
        if 0 <= index < len(self._backups):
            self.viewmodel.compute_diff(self._backups[index])
            self._update_restore_btn()

    def _on_diff(self, diff):
        self._diff = diff
        if "contacts" in diff:
            d = diff["contacts"]
            self.contacts_diff_label.setText(
                f"Backup: {d.backup_count} · Phone: {d.phone_count} · ~{d.estimated_missing} may be missing"
            )
        if "calls" in diff:
            d = diff["calls"]
            self.calls_diff_label.setText(
                f"Backup: {d.backup_count} · Phone: {d.phone_count} · ~{d.estimated_missing} may be missing"
            )

    def _on_dest_changed(self, phone_checked):
        self.phone_note.setVisible(phone_checked and self.contacts_check.isChecked())

    def _update_restore_btn(self):
        has_selection = self.contacts_check.isChecked() or self.calls_check.isChecked()
        has_backup = bool(self._backups)
        self.restore_btn.setEnabled(has_selection and has_backup)

    def _on_restore_clicked(self):
        index = self.backup_combo.currentIndex()
        if index < 0 or index >= len(self._backups):
            return
        info = self._backups[index]
        dest = "phone" if self.dest_phone_radio.isChecked() else "pc"
        output_dir = self.output_edit.text() or "."
        self.viewmodel.restore(
            info,
            restore_contacts=self.contacts_check.isChecked(),
            restore_calls=self.calls_check.isChecked(),
            dest=dest,
            output_dir=output_dir,
        )

    def _on_busy(self, busy):
        self.progress.setVisible(busy)
        self.restore_btn.setEnabled(not busy)

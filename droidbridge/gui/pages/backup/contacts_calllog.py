# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from droidbridge.gui.viewmodels.backup.contacts_calllog import ContactsCallLogViewModel


class ContactsCallLogPanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = ContactsCallLogViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destination:"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setToolTip("Local folder on your computer where the export will be saved.")
        dest_row.addWidget(self.dest_edit)
        self.browse_dest_button = QPushButton("Browse…")
        self.browse_dest_button.setToolTip("Browse your computer for an export destination folder.")
        dest_row.addWidget(self.browse_dest_button)
        layout.addLayout(dest_row)

        sources_row = QHBoxLayout()
        self.phone_checkbox = QCheckBox("Phone")
        self.phone_checkbox.setChecked(True)
        self.phone_checkbox.setToolTip("Include contacts stored on the phone account.")
        self.accounts_checkbox = QCheckBox("Accounts")
        self.accounts_checkbox.setChecked(True)
        self.accounts_checkbox.setToolTip("Include contacts synced from other accounts (e.g. Google).")
        self.sim_checkbox = QCheckBox("SIM")
        self.sim_checkbox.setChecked(True)
        self.sim_checkbox.setToolTip("Include contacts stored on the SIM card.")
        sources_row.addWidget(self.phone_checkbox)
        sources_row.addWidget(self.accounts_checkbox)
        sources_row.addWidget(self.sim_checkbox)
        sources_row.addStretch()
        layout.addLayout(sources_row)

        btn_row = QHBoxLayout()
        self.export_contacts_button = QPushButton("Export Contacts")
        self.export_contacts_button.setToolTip("Export contacts from the checked sources to the destination folder.")
        self.export_call_log_button = QPushButton("Export Call Log")
        self.export_call_log_button.setToolTip("Export the device's call log to the destination folder.")
        btn_row.addWidget(self.export_contacts_button)
        btn_row.addWidget(self.export_call_log_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.browse_dest_button.clicked.connect(self._browse_dest)
        self.export_contacts_button.clicked.connect(self._on_export_contacts)
        self.export_call_log_button.clicked.connect(self._on_export_call_log)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)

    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select export destination")
        if path:
            self.dest_edit.setText(path)

    def _selected_sources(self):
        sources = []
        if self.phone_checkbox.isChecked():
            sources.append("phone")
        if self.accounts_checkbox.isChecked():
            sources.append("accounts")
        if self.sim_checkbox.isChecked():
            sources.append("sim")
        return sources

    def _on_export_contacts(self):
        self.viewmodel.export_contacts(self._selected_sources(), self.dest_edit.text())

    def _on_export_call_log(self):
        self.viewmodel.export_call_log(self.dest_edit.text())

    def _on_busy(self, busy):
        self.export_contacts_button.setEnabled(not busy)
        self.export_call_log_button.setEnabled(not busy)

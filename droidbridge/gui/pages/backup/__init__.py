"""Backup Manager page coordinator (sub-phase 6.4)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QListWidget,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from droidbridge.gui.pages.backup.contacts_calllog import ContactsCallLogPanel
from droidbridge.gui.pages.backup.history import HistoryPanel
from droidbridge.gui.pages.backup.profiles import ProfilesPanel
from droidbridge.gui.pages.backup.restore import RestorePanel
from droidbridge.gui.pages.backup.run import RunPanel
from droidbridge.gui.pages.backup.verify import VerifyPanel

_OPS = ["Profiles", "Run", "Verify", "History", "Restore", "Contacts/Call Log"]


class BackupManagerPage(QWidget):
    def __init__(self, device_context, parent=None):
        super().__init__(parent)
        self._context = device_context
        self._build_ui()

    def selected_profile(self):
        text = self.profile_combo.currentText()
        return text or None

    @property
    def viewmodels(self):
        return [p.viewmodel for p in self._panels]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        top = QHBoxLayout()
        top.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("Select a saved backup profile for Run/Verify/History/Restore.")
        top.addWidget(self.profile_combo)
        top.addStretch()
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        self.op_list = QListWidget()
        self.op_list.setFixedWidth(160)
        self.op_list.addItems(_OPS)
        splitter.addWidget(self.op_list)

        get_profile = lambda: self.selected_profile()
        self._profiles_panel = ProfilesPanel(on_profiles_changed=self._on_profiles_changed)
        self._run_panel = RunPanel(self._context, get_profile)
        self._verify_panel = VerifyPanel(get_profile)
        self._history_panel = HistoryPanel(get_profile)
        self._restore_panel = RestorePanel(self._context, get_profile)
        self._contacts_calllog_panel = ContactsCallLogPanel(self._context)

        self._panels = [
            self._profiles_panel, self._run_panel, self._verify_panel,
            self._history_panel, self._restore_panel, self._contacts_calllog_panel,
        ]
        self.stack = QStackedWidget()
        for panel in self._panels:
            self.stack.addWidget(panel)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        self.op_list.currentRowChanged.connect(self._on_row_changed)
        self.op_list.setCurrentRow(0)
        self._profiles_panel.refresh()

    def _on_row_changed(self, row):
        self.stack.setCurrentIndex(row)
        if self._panels[row] is self._restore_panel:
            self._restore_panel.refresh_sources()

    def _on_profiles_changed(self, names):
        current = self.profile_combo.currentText()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        if current in names:
            self.profile_combo.setCurrentText(current)
        self.profile_combo.blockSignals(False)

"""WhatsApp Toolkit page coordinator (sub-phase 6.3)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QListWidget,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from droidbridge.gui.pages.whatsapp.analyze import AnalyzePanel
from droidbridge.gui.pages.whatsapp.backup import BackupPanel
from droidbridge.gui.pages.whatsapp.backup_db import BackupDbPanel
from droidbridge.gui.pages.whatsapp.delete import DeletePanel
from droidbridge.gui.pages.whatsapp.organize import OrganizePanel
from droidbridge.gui.pages.whatsapp.restore import RestorePanel
from droidbridge.gui.pages.whatsapp.save_status import SaveStatusPanel
from droidbridge.gui.pages.whatsapp.scan import ScanPanel

_APP_LABELS = ["WhatsApp", "WhatsApp Business", "Both"]
_APP_VALUES = ["whatsapp", "business", "all"]
_OPS = ["Scan", "Analyze", "Backup", "Restore", "Organize", "Delete", "Save Status", "Backup DB"]


class WhatsAppPage(QWidget):
    def __init__(self, device_context, parent=None):
        super().__init__(parent)
        self._context = device_context
        self._build_ui()

    def selected_app(self):
        return _APP_VALUES[self.app_combo.currentIndex()]

    @property
    def viewmodels(self):
        return [p.viewmodel for p in self._panels]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        top = QHBoxLayout()
        top.addWidget(QLabel("App:"))
        self.app_combo = QComboBox()
        self.app_combo.setToolTip("Select which WhatsApp installation to target.")
        self.app_combo.addItems(_APP_LABELS)
        top.addWidget(self.app_combo)
        top.addStretch()
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        self.op_list = QListWidget()
        self.op_list.setFixedWidth(160)
        self.op_list.addItems(_OPS)
        splitter.addWidget(self.op_list)

        get_app = lambda: self.selected_app()
        self._panels = [
            ScanPanel(self._context, get_app),
            AnalyzePanel(self._context, get_app),
            BackupPanel(self._context, get_app),
            RestorePanel(self._context, get_app),
            OrganizePanel(get_app),
            DeletePanel(self._context, get_app),
            SaveStatusPanel(self._context, get_app),
            BackupDbPanel(self._context, get_app),
        ]
        self.stack = QStackedWidget()
        for panel in self._panels:
            self.stack.addWidget(panel)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        self.op_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.op_list.setCurrentRow(0)

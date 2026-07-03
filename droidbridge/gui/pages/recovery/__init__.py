# droidbridge/gui/pages/recovery/__init__.py
# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Recovery page coordinator (Module 10): disclaimer banner + Scanner/Restore tabs."""

from PyQt6.QtWidgets import (
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from droidbridge.gui.pages.recovery.scanner import ScannerPanel
from droidbridge.gui.pages.recovery.restore import RestorePanel
from droidbridge.gui.viewmodels.recovery.scanner import ScannerViewModel
from droidbridge.gui.viewmodels.recovery.restore import RestoreViewModel

_DISCLAIMER = (
    "DroidBridge can only recover files that apps have soft-deleted (moved to a trash folder) "
    "and data backed up by DroidBridge. Files permanently deleted without root access cannot be "
    "recovered. Results are not guaranteed."
)


class RecoveryPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._context = context
        self.scanner_viewmodel = ScannerViewModel(context)
        self.restore_viewmodel = RestoreViewModel(context)
        self._build_ui()

    @property
    def viewmodels(self):
        return [self.scanner_viewmodel, self.restore_viewmodel]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        disclaimer = QLabel(_DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(
            "background: #fff3cd; color: #856404; border: 1px solid #ffc107;"
            " border-radius: 4px; padding: 6px 8px; font-style: italic;"
        )
        disclaimer.setToolTip("Recovery is limited to soft-deleted files and DroidBridge backups. Root is not used.")
        root.addWidget(disclaimer)

        tabs = QTabWidget()
        tabs.addTab(ScannerPanel(self.scanner_viewmodel), "Soft-Delete Scanner")
        tabs.addTab(RestorePanel(self.restore_viewmodel), "Backup Restore")
        root.addWidget(tabs)

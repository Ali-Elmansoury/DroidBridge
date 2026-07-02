# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Storage Analyzer page coordinator (sub-phase 6.5 part 1, Task 7)."""

from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QStackedWidget, QWidget

from droidbridge.gui.pages.storage.apps import AppsPanel
from droidbridge.gui.pages.storage.cleanup import CleanupPanel
from droidbridge.gui.pages.storage.large_files import LargeFilesPanel
from droidbridge.gui.pages.storage.media import MediaPanel
from droidbridge.gui.pages.storage.overview import OverviewPanel

_TAB_LABELS = ["Overview", "Apps", "Media", "Large Files", "Cleanup"]


class StoragePage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._panels = [
            OverviewPanel(context),
            AppsPanel(context),
            MediaPanel(context),
            LargeFilesPanel(context),
            CleanupPanel(context),
        ]
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        self.op_list = QListWidget()
        self.op_list.setFixedWidth(160)
        self.op_list.addItems(_TAB_LABELS)
        layout.addWidget(self.op_list)

        self.stack = QStackedWidget()
        for panel in self._panels:
            self.stack.addWidget(panel)
        layout.addWidget(self.stack)

        self.op_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.op_list.setCurrentRow(0)

    @property
    def viewmodels(self):
        return [panel.viewmodel for panel in self._panels]

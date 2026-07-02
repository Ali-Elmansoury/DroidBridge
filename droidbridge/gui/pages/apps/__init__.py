# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Apps GUI page coordinator (sub-phase 6.5 part 2, Module 8)."""

from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QStackedWidget, QWidget

from droidbridge.gui.pages.apps.apk_extraction import ApkExtractionPanel
from droidbridge.gui.pages.apps.backup_restore import BackupRestorePanel
from droidbridge.gui.pages.apps.bloatware import BloatwarePanel
from droidbridge.gui.pages.apps.cache import CachePanel
from droidbridge.gui.pages.apps.listing import ListingPanel
from droidbridge.gui.pages.apps.uninstall import UninstallPanel

_TAB_LABELS = ["Listing", "Cache Management", "Uninstall", "APK Extraction", "Bloatware Manager", "Backup & Restore"]


class AppsPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.listing_panel = ListingPanel(context)
        self.cache_panel = CachePanel(context)
        self.uninstall_panel = UninstallPanel(context)
        self.apk_extraction_panel = ApkExtractionPanel(context)
        self.bloatware_panel = BloatwarePanel(context)
        self.backup_restore_panel = BackupRestorePanel(context)
        self._panels = [
            self.listing_panel, self.cache_panel, self.uninstall_panel,
            self.apk_extraction_panel, self.bloatware_panel, self.backup_restore_panel,
        ]
        self._build_ui()
        self._connect()

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

    def _connect(self):
        self.listing_panel.appSelected.connect(self._on_app_selected)
        self.listing_panel.viewmodel.resultsChanged.connect(self._on_results_changed)
        self.uninstall_panel.appUninstalled.connect(self._on_app_uninstalled)
        self.bloatware_panel.appStatusChanged.connect(self._on_app_status_changed)

    def _on_app_selected(self, package):
        self.cache_panel.set_current_app(package)
        self.uninstall_panel.set_current_app(package)
        self.apk_extraction_panel.set_current_app(package)
        self.bloatware_panel.set_current_app(package)
        self.backup_restore_panel.set_current_app(package)

    def _on_results_changed(self, rows):
        self.cache_panel.set_all_apps(rows)

    def _on_app_uninstalled(self):
        self.listing_panel.clear_selection()
        self.listing_panel.refresh()

    def _on_app_status_changed(self, package, is_disabled):
        self.listing_panel.update_row_status(package, is_disabled)

    @property
    def viewmodels(self):
        return [panel.viewmodel for panel in self._panels]

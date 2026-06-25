from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from droidbridge.gui.viewmodels.apps.uninstall import UninstallViewModel
from droidbridge.gui.widgets import uninstall_flow

_NO_SELECTION_TEXT = "No app selected — select one in the Listing tab."


class UninstallPanel(QWidget):
    appUninstalled = pyqtSignal()

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = UninstallViewModel(context)
        self._current_app = None
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.acting_on_label = QLabel(_NO_SELECTION_TEXT)
        self.acting_on_label.setWordWrap(True)
        layout.addWidget(self.acting_on_label)

        self.keep_data_checkbox = QCheckBox("Keep data and cache (-k)")
        self.keep_data_checkbox.setToolTip("Keep the app's data and cache so they're restored if it's reinstalled.")
        layout.addWidget(self.keep_data_checkbox)

        row = QHBoxLayout()
        self.uninstall_button = QPushButton("Uninstall App")
        self.uninstall_button.setEnabled(False)
        self.uninstall_button.setToolTip("Uninstall the selected app. Disabled for system apps.")
        row.addWidget(self.uninstall_button)
        row.addStretch()
        layout.addLayout(row)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.uninstall_button.clicked.connect(self._on_uninstall)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.appInfoChanged.connect(self._on_app_info)

    def set_current_app(self, package):
        self.viewmodel.set_current_app(package or None)

    def _on_app_info(self, app):
        self._current_app = app
        if app is None:
            self.acting_on_label.setText(_NO_SELECTION_TEXT)
            self.uninstall_button.setEnabled(False)
            return
        self.acting_on_label.setText(
            f"Acting on: {app['package']} (v{app['version_name']}, {app['total_size_str']})"
        )
        self.uninstall_button.setEnabled(not app["is_system"])

    def _on_uninstall(self):
        if self._current_app is None:
            return
        client, serial = self.viewmodel.context.client, self.viewmodel.context.serial
        keep_data = self.keep_data_checkbox.isChecked()
        uninstalled = uninstall_flow.run_uninstall_flow(
            self, client, serial, self._current_app, keep_data=keep_data,
        )
        if uninstalled:
            self.appUninstalled.emit()

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        can_uninstall = self._current_app is not None and not self._current_app["is_system"]
        self.uninstall_button.setEnabled(not busy and can_uninstall)

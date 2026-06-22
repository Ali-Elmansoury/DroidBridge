from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from droidbridge.gui.viewmodels.apps.bloatware import BloatwareViewModel

_NO_SELECTION_TEXT = "No app selected — select one in the Listing tab."
_SYSTEM_APP_WARNING = "Disabling a system app can affect device functionality. This can be undone with Enable."


class BloatwarePanel(QWidget):
    appStatusChanged = pyqtSignal(str, bool)

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = BloatwareViewModel(context)
        self._current_app = None
        self._awaiting_status_update = False
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.acting_on_label = QLabel(_NO_SELECTION_TEXT)
        layout.addWidget(self.acting_on_label)

        row = QHBoxLayout()
        self.disable_button = QPushButton("Disable")
        self.disable_button.setVisible(False)
        self.enable_button = QPushButton("Enable")
        self.enable_button.setVisible(False)
        row.addWidget(self.disable_button)
        row.addWidget(self.enable_button)
        row.addStretch()
        layout.addLayout(row)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.disable_button.clicked.connect(self._on_disable)
        self.enable_button.clicked.connect(self._on_enable)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.appInfoChanged.connect(self._on_app_info)

    def set_current_app(self, package):
        self.viewmodel.set_current_app(package or None)

    def _on_app_info(self, app):
        self._current_app = app
        if app is None:
            self.acting_on_label.setText(_NO_SELECTION_TEXT)
            self.disable_button.setVisible(False)
            self.enable_button.setVisible(False)
            self._awaiting_status_update = False
            return
        self.acting_on_label.setText(
            f"Acting on: {app['package']} ({app['kind'].capitalize()}, {app['status']})"
        )
        self.disable_button.setVisible(not app["is_disabled"])
        self.enable_button.setVisible(app["is_disabled"])
        if self._awaiting_status_update:
            self._awaiting_status_update = False
            self.appStatusChanged.emit(app["package"], app["is_disabled"])

    def _on_disable(self):
        if self._current_app is None:
            return
        text = f"Disable {self._current_app['package']}?"
        if self._current_app["is_system"]:
            text = f"{_SYSTEM_APP_WARNING}\n\n{text}"
        confirm = QMessageBox.question(
            self, "Disable App", text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._awaiting_status_update = True
        self.viewmodel.disable_app(self._current_app["package"])

    def _on_enable(self):
        if self._current_app is None:
            return
        self._awaiting_status_update = True
        self.viewmodel.enable_app(self._current_app["package"])

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)

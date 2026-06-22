from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from droidbridge.gui.viewmodels.apps.cache import CacheViewModel

_RESET_WARNING = (
    "This wipes ALL data for {package} — logins, settings, and cache — "
    "same as Settings > Clear Storage. There is no way to clear only the "
    "cache for a single app without root."
)
_NO_SELECTION_TEXT = "No app selected — select one in the Listing tab."


class CachePanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = CacheViewModel(context)
        self._current_app = None
        self._estimate_bytes = 0
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        trim_box = QGroupBox("Trim All Caches")
        trim_layout = QVBoxLayout(trim_box)
        self.estimate_label = QLabel("Estimated reclaimable: 0 B")
        trim_layout.addWidget(self.estimate_label)
        trim_row = QHBoxLayout()
        self.trim_button = QPushButton("Trim Caches Now")
        trim_row.addWidget(self.trim_button)
        trim_row.addStretch()
        trim_layout.addLayout(trim_row)
        layout.addWidget(trim_box)

        reset_box = QGroupBox("Reset App Data")
        reset_layout = QVBoxLayout(reset_box)
        self.acting_on_label = QLabel(_NO_SELECTION_TEXT)
        reset_layout.addWidget(self.acting_on_label)
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        reset_layout.addWidget(self.warning_label)
        reset_row = QHBoxLayout()
        self.reset_button = QPushButton("Reset App Data")
        self.reset_button.setEnabled(False)
        reset_row.addWidget(self.reset_button)
        reset_row.addStretch()
        reset_layout.addLayout(reset_row)
        layout.addWidget(reset_box)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.trim_button.clicked.connect(self._on_trim)
        self.reset_button.clicked.connect(self._on_reset)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.estimateChanged.connect(self._on_estimate)
        self.viewmodel.appInfoChanged.connect(self._on_app_info)

    def set_all_apps(self, rows):
        self.viewmodel.set_all_apps(rows)

    def set_current_app(self, package):
        self.viewmodel.set_current_app(package or None)

    def _on_estimate(self, estimate):
        self._estimate_bytes = estimate["estimate_bytes"]
        self.estimate_label.setText(f"Estimated reclaimable: {estimate['estimate_str']}")

    def _on_trim(self):
        self.viewmodel.trim_caches(self._estimate_bytes)

    def _on_app_info(self, app):
        self._current_app = app
        if app is None:
            self.acting_on_label.setText(_NO_SELECTION_TEXT)
            self.warning_label.setText("")
            self.reset_button.setEnabled(False)
            return
        self.acting_on_label.setText(
            f"Acting on: {app['package']} — Data: {app['data_size_str']}, Cache: {app['cache_size_str']}"
        )
        self.warning_label.setText(_RESET_WARNING.format(package=app["package"]))
        self.reset_button.setEnabled(not app["is_system"])

    def _on_reset(self):
        if self._current_app is None:
            return
        text, ok = QInputDialog.getText(
            self, "Confirm Reset",
            "This will permanently wipe app data and cache.\nType 'YES DELETE' to confirm:",
        )
        if not ok or text != "YES DELETE":
            return
        self.viewmodel.reset_app_data(self._current_app["package"])

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.trim_button.setEnabled(not busy)
        can_reset = self._current_app is not None and not self._current_app["is_system"]
        self.reset_button.setEnabled(not busy and can_reset)

"""Device module screen (Phase 6.1): connect + info, mirroring `device connect`/`device
info`. Purely declarative — binds to DeviceViewModel signals/slots, no formatting or
AdbClient calls of its own.
"""

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DevicePage(QWidget):
    """Connect/Refresh buttons plus a read-only summary of the connected device."""

    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.viewmodel = viewmodel

        self.connect_button = QPushButton("Connect")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setEnabled(viewmodel.context.is_connected)

        self.serial_label = QLabel("-")
        self.model_label = QLabel("-")
        self.manufacturer_label = QLabel("-")
        self.android_label = QLabel("-")
        self.build_label = QLabel("-")
        self.battery_label = QLabel("-")
        self.storage_label = QLabel("-")
        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)

        form = QFormLayout()
        form.addRow("Serial:", self.serial_label)
        form.addRow("Model:", self.model_label)
        form.addRow("Manufacturer:", self.manufacturer_label)
        form.addRow("Android:", self.android_label)
        form.addRow("Build:", self.build_label)
        form.addRow("Battery:", self.battery_label)
        form.addRow("Storage:", self.storage_label)
        form.addRow("", self.storage_bar)

        buttons = QHBoxLayout()
        buttons.addWidget(self.connect_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addLayout(form)
        layout.addStretch()

        self.connect_button.clicked.connect(self.viewmodel.connect_device)
        self.refresh_button.clicked.connect(self.viewmodel.refresh)
        self.viewmodel.infoChanged.connect(self._on_info_changed)
        self.viewmodel.busyChanged.connect(self._on_busy_changed)
        self.viewmodel.context.connectionChanged.connect(self._on_connection_changed)

    def _on_info_changed(self, info):
        self.serial_label.setText(info["serial"])
        self.model_label.setText(info["model"])
        self.manufacturer_label.setText(info["manufacturer"])
        self.android_label.setText(info["android"])
        self.build_label.setText(info["build"])
        self.battery_label.setText(info["battery"])
        self.storage_label.setText(
            f"{info['storage_used']} used of {info['storage_total']} "
            f"({info['storage_free']} free)"
        )
        self.storage_bar.setValue(int(info["storage_used_percent"]))

    def _on_busy_changed(self, busy):
        self.connect_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy and self.viewmodel.context.is_connected)

    def _on_connection_changed(self, connected, _serial, _model):
        self.refresh_button.setEnabled(connected)

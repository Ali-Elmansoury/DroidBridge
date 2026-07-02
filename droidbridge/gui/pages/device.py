# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Device module screen (Phase 6.1): connect + info, mirroring `device connect`/`device
info`. Purely declarative — binds to DeviceViewModel signals/slots, no formatting or
AdbClient calls of its own.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
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

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setEnabled(viewmodel.context.is_connected)

        self.auto_refresh_checkbox = QCheckBox("Auto-refresh")
        self.auto_refresh_checkbox.setChecked(True)

        self.refresh_button.setToolTip(
            "Reload device info, battery, and storage from the connected device. Shortcut: F5."
        )
        self.auto_refresh_checkbox.setToolTip(
            "Automatically reload device info every 15 seconds while a device is connected."
        )

        # F5 shortcut: both QShortcut (for when child widgets have focus) and
        # keyPressEvent (ensures qtbot.keyClick works in tests).
        _f5 = QShortcut(QKeySequence("F5"), self)
        _f5.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        _f5.activated.connect(self._on_refresh_shortcut)

        self._busy = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(15000)
        self._refresh_timer.timeout.connect(self._on_refresh_timer)

        self.serial_label = QLabel("-")
        self.model_label = QLabel("-")
        self.manufacturer_label = QLabel("-")
        self.android_label = QLabel("-")
        self.build_label = QLabel("-")
        self.battery_label = QLabel("-")
        self.storage_label = QLabel("-")
        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.usb_speed_label = QLabel("-")
        self.usb_mode_label = QLabel("-")

        form = QFormLayout()
        form.addRow("Serial:", self.serial_label)
        form.addRow("Model:", self.model_label)
        form.addRow("Manufacturer:", self.manufacturer_label)
        form.addRow("Android:", self.android_label)
        form.addRow("Build:", self.build_label)
        form.addRow("Battery:", self.battery_label)
        form.addRow("Storage:", self.storage_label)
        form.addRow("", self.storage_bar)
        form.addRow("USB Speed:", self.usb_speed_label)
        form.addRow("USB Mode:", self.usb_mode_label)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.auto_refresh_checkbox)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addLayout(form)
        layout.addStretch()

        self.refresh_button.clicked.connect(self.viewmodel.refresh)
        self.viewmodel.infoChanged.connect(self._on_info_changed)
        self.viewmodel.busyChanged.connect(self._on_busy_changed)
        self.viewmodel.context.connectionChanged.connect(self._on_connection_changed)
        self.auto_refresh_checkbox.toggled.connect(self._update_timer_state)

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
        self.usb_speed_label.setText(info.get("usb_speed", "Unknown"))
        self.usb_mode_label.setText(info.get("usb_mode", "Unknown"))

    def _on_busy_changed(self, busy):
        self._busy = busy
        self.refresh_button.setEnabled(not busy and self.viewmodel.context.is_connected)

    def _on_refresh_timer(self):
        if not self._busy:
            self.viewmodel.poll()

    def _update_timer_state(self):
        if self.viewmodel.context.is_connected and self.auto_refresh_checkbox.isChecked():
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

    def _on_connection_changed(self, connected, _serial, _model):
        self.refresh_button.setEnabled(connected)
        self._update_timer_state()

    def _on_refresh_shortcut(self):
        if self.refresh_button.isEnabled():
            self.viewmodel.refresh()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F5:
            self._on_refresh_shortcut()
            event.accept()
        else:
            super().keyPressEvent(event)

"""ViewModel for the Device module screen (Phase 6.1).

Owns Workers, formats DeviceInfo for display, and exposes Qt signals for the View.
Calls droidbridge.gui.device_ops as a module attribute (not a direct import-binding) so
tests can monkeypatch device_ops.connect / device_ops.refresh_info.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import device_ops
from droidbridge.gui.workers import Worker
from droidbridge.utils.format import format_bytes


class DeviceViewModel(QObject):
    """Drives the Device page: connect to a device, then refresh its info."""

    infoChanged = pyqtSignal(dict)
    statusChanged = pyqtSignal(str)
    busyChanged = pyqtSignal(bool)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory

    def connect_device(self):
        """Build a client, ensure the adb server is running, and pick a device."""
        self.logMessage.emit("Connecting to device...", "INFO")
        self._run(device_ops.connect, self._on_connect_finished)

    def refresh(self):
        """Reload device info for the currently connected device."""
        self.logMessage.emit("Refreshing device info...", "INFO")
        client, serial = self.context.client, self.context.serial
        self._run(lambda: device_ops.refresh_info(client, serial), self._on_refresh_finished)

    def _run(self, fn, on_finished):
        self.busyChanged.emit(True)
        worker = self._worker_factory(fn)
        worker.finished.connect(on_finished)
        worker.finished.connect(lambda _result: self.busyChanged.emit(False))
        worker.error.connect(self._on_error)
        worker.error.connect(lambda _exc: self.busyChanged.emit(False))
        worker.start()

    def _on_connect_finished(self, result):
        client, serial, model, messages = result
        self.context.set_connected(client, serial, model)
        for message in messages:
            self.logMessage.emit(message, "INFO")
        self.logMessage.emit(f"Connected to {serial} ({model})", "INFO")
        self.refresh()

    def _on_refresh_finished(self, info):
        data = {
            "serial": info.serial,
            "model": info.model,
            "manufacturer": info.manufacturer,
            "android": f"{info.android_version} (SDK {info.sdk_version})",
            "build": info.build_number,
            "battery": f"{info.battery_level}% ({info.battery_status})",
            "storage_total": format_bytes(info.storage.total_kb * 1024),
            "storage_used": format_bytes(info.storage.used_kb * 1024),
            "storage_free": format_bytes(info.storage.free_kb * 1024),
            "storage_used_percent": info.storage.used_percent,
        }
        self.infoChanged.emit(data)
        self.logMessage.emit("Device info refreshed.", "INFO")

    def _on_error(self, exc):
        self.statusChanged.emit(str(exc))
        self.logMessage.emit(str(exc), "ERROR")

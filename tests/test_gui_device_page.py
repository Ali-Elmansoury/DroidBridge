"""Tests for droidbridge.gui.pages.device.DevicePage (Phase 6.1)."""

from unittest.mock import MagicMock

from PyQt6.QtCore import Qt

from droidbridge.gui import device_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.device import DevicePage
from droidbridge.gui.viewmodels.device import DeviceViewModel
from tests.test_gui_viewmodels_device import SAMPLE_INFO, FakeWorker


def _make_page():
    context = DeviceContext()
    vm = DeviceViewModel(context, worker_factory=FakeWorker)
    page = DevicePage(vm)
    return page, vm, context


class TestDevicePage:
    def test_refresh_disabled_until_connected(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.refresh_button.isEnabled() is False

    def test_info_changed_populates_labels(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.infoChanged.emit(
            {
                "serial": "SERIAL123",
                "model": "Pixel 7",
                "manufacturer": "Google",
                "android": "14 (SDK 34)",
                "build": "UQ1A.240205.004",
                "battery": "85% (charging)",
                "storage_total": "1000.0 KB",
                "storage_used": "500.0 KB",
                "storage_free": "500.0 KB",
                "storage_used_percent": 50.0,
            }
        )

        assert page.serial_label.text() == "SERIAL123"
        assert page.model_label.text() == "Pixel 7"
        assert page.android_label.text() == "14 (SDK 34)"
        assert page.storage_bar.value() == 50

    def test_busy_changed_disables_connect_button(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.busyChanged.emit(True)
        assert page.connect_button.isEnabled() is False

        vm.busyChanged.emit(False)
        assert page.connect_button.isEnabled() is True

    def test_connection_changed_enables_refresh(self, qtbot):
        page, _vm, context = _make_page()
        qtbot.addWidget(page)

        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")

        assert page.refresh_button.isEnabled() is True

    def test_clicking_connect_runs_full_flow(self, qtbot, monkeypatch):
        page, vm, context = _make_page()
        qtbot.addWidget(page)

        fake_client = MagicMock()
        monkeypatch.setattr(
            device_ops, "connect",
            lambda: (fake_client, "SERIAL123", "Pixel 7", ["SERIAL123: Device connected and ready."]),
        )
        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)

        qtbot.mouseClick(page.connect_button, Qt.MouseButton.LeftButton)

        assert context.is_connected is True
        assert page.serial_label.text() == "SERIAL123"
        assert page.refresh_button.isEnabled() is True

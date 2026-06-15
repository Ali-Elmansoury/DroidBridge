"""Tests for droidbridge.gui.device_ops (Phase 6.1) — plain functions, no Qt."""

from unittest.mock import MagicMock

import pytest

from droidbridge.core.adb import Device
from droidbridge.gui import device_ops
from droidbridge.modules import device as device_module
from droidbridge.modules.device import DeviceInfo, StorageInfo


class TestConnect:
    def test_no_ready_devices_raises_device_selection_error(self, monkeypatch):
        client = MagicMock()
        client.devices.return_value = []
        monkeypatch.setattr(device_ops, "AdbClient", lambda: client)

        with pytest.raises(device_module.DeviceSelectionError):
            device_ops.connect()

    def test_single_ready_device_returns_client_serial_model_and_messages(self, monkeypatch):
        client = MagicMock()
        client.devices.return_value = [Device(serial="SERIAL123", state="device", model="Pixel 7")]
        monkeypatch.setattr(device_ops, "AdbClient", lambda: client)

        result_client, serial, model, messages = device_ops.connect()

        assert result_client is client
        assert serial == "SERIAL123"
        assert model == "Pixel 7"
        assert any("SERIAL123" in m and "connected" in m.lower() for m in messages)
        client.start_server.assert_called_once()

    def test_multiple_ready_devices_raises_device_selection_error(self, monkeypatch):
        client = MagicMock()
        client.devices.return_value = [
            Device(serial="A", state="device", model="Pixel 7"),
            Device(serial="B", state="device", model="Pixel 8"),
        ]
        monkeypatch.setattr(device_ops, "AdbClient", lambda: client)

        with pytest.raises(device_module.DeviceSelectionError):
            device_ops.connect()

    def test_unauthorized_device_raises_with_unauthorized_guidance(self, monkeypatch):
        client = MagicMock()
        client.devices.return_value = [Device(serial="SERIAL123", state="unauthorized")]
        monkeypatch.setattr(device_ops, "AdbClient", lambda: client)

        with pytest.raises(device_module.DeviceSelectionError) as exc_info:
            device_ops.connect()

        assert "allow" in str(exc_info.value).lower()


class TestRefreshInfo:
    def test_delegates_to_get_device_info(self, monkeypatch):
        client = MagicMock()
        expected = DeviceInfo(
            serial="SERIAL123",
            model="Pixel 7",
            manufacturer="Google",
            android_version="14",
            sdk_version="34",
            build_number="UQ1A.240205.004",
            battery_level=85,
            battery_status="charging",
            storage=StorageInfo(total_kb=1000, used_kb=500, free_kb=500),
        )
        monkeypatch.setattr(device_module, "get_device_info", lambda c, s: expected)

        result = device_ops.refresh_info(client, "SERIAL123")

        assert result is expected

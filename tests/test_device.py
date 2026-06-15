"""Tests for droidbridge.modules.device - Module 1: Device Manager."""

from unittest.mock import MagicMock

import pytest

from droidbridge.core.adb import AdbError, Device
from droidbridge.modules import device


DF_OUTPUT = (
    "Filesystem     1K-blocks     Used Available Use% Mounted on\n"
    "/dev/fuse      120000000 80000000  40000000  67% /storage/emulated/0\n"
)

BATTERY_OUTPUT_CHARGING = (
    "Current Battery Service state:\n"
    "  AC powered: false\n"
    "  USB powered: true\n"
    "  Wireless powered: false\n"
    "  status: 2\n"
    "  health: 2\n"
    "  present: true\n"
    "  level: 85\n"
    "  scale: 100\n"
    "  voltage: 4200\n"
)

BATTERY_OUTPUT_DISCHARGING = BATTERY_OUTPUT_CHARGING.replace("status: 2", "status: 3")

PROP_VALUES = {
    "ro.product.model": "Pixel 7\n",
    "ro.product.manufacturer": "Google\n",
    "ro.build.version.release": "14\n",
    "ro.build.version.sdk": "34\n",
    "ro.build.display.id": "UQ1A.240205.004\n",
}


def make_fake_client(battery_output=BATTERY_OUTPUT_CHARGING, df_output=DF_OUTPUT):
    client = MagicMock()

    def fake_shell(serial, command, timeout=None):
        assert serial == "SERIAL123"
        if command[0] == "getprop":
            return PROP_VALUES[command[1]]
        if command[:2] == ["dumpsys", "battery"]:
            return battery_output
        if command[0] == "df":
            return df_output
        raise AssertionError(f"Unexpected shell command: {command}")

    client.shell.side_effect = fake_shell
    return client


class TestStorageBreakdown:
    def test_parses_df_output(self):
        client = make_fake_client()

        storage = device.get_storage_breakdown(client, "SERIAL123")

        assert storage.total_kb == 120000000
        assert storage.used_kb == 80000000
        assert storage.free_kb == 40000000

    def test_used_percent_is_computed(self):
        client = make_fake_client()

        storage = device.get_storage_breakdown(client, "SERIAL123")

        assert storage.used_percent == pytest.approx(66.7, abs=0.05)

    def test_raises_on_unexpected_df_output(self):
        client = make_fake_client(df_output="weird output\n")

        with pytest.raises(ValueError):
            device.get_storage_breakdown(client, "SERIAL123")


class TestBatteryInfo:
    def test_parses_charging_status(self):
        client = make_fake_client(battery_output=BATTERY_OUTPUT_CHARGING)

        level, status = device.get_battery_info(client, "SERIAL123")

        assert level == 85
        assert status == "charging"

    def test_parses_discharging_status(self):
        client = make_fake_client(battery_output=BATTERY_OUTPUT_DISCHARGING)

        level, status = device.get_battery_info(client, "SERIAL123")

        assert level == 85
        assert status == "discharging"


class TestUsbModeInfo:
    def test_mtp_present_has_no_guidance(self):
        client = MagicMock()
        client.shell.return_value = "mtp,adb\n"

        info = device.get_usb_mode_info(client, "SERIAL123")

        assert info.functions == ["mtp", "adb"]
        assert info.mtp_enabled is True
        assert info.guidance is None

    def test_mtp_absent_has_guidance(self):
        client = MagicMock()
        client.shell.return_value = "adb\n"

        info = device.get_usb_mode_info(client, "SERIAL123")

        assert info.functions == ["adb"]
        assert info.mtp_enabled is False
        assert "File Transfer" in info.guidance


class TestUsbSpeedInfo:
    def test_recognized_value_maps_to_type_and_estimate(self):
        client = MagicMock()
        client.shell.return_value = "480\n"

        info = device.get_usb_speed_info(client, "SERIAL123")

        assert info.raw == "480"
        assert info.usb_type == "USB 2.0 (High Speed)"
        assert info.estimated_speed == "~30-40 MB/s"

    def test_unrecognized_value_sets_raw_only(self):
        client = MagicMock()
        client.shell.return_value = "9999\n"

        info = device.get_usb_speed_info(client, "SERIAL123")

        assert info.raw == "9999"
        assert info.usb_type == "Unknown"
        assert info.estimated_speed == "Unknown"

    def test_adb_error_falls_back_to_unknown(self):
        client = MagicMock()
        client.shell.side_effect = AdbError("no such file")

        info = device.get_usb_speed_info(client, "SERIAL123")

        assert info.raw is None
        assert info.usb_type == "Unknown"
        assert info.estimated_speed == "Unknown"

    def test_empty_output_falls_through_to_next_path(self):
        client = MagicMock()
        client.shell.side_effect = ["\n", "480\n"]

        info = device.get_usb_speed_info(client, "SERIAL123")

        assert info.raw == "480"
        assert info.usb_type == "USB 2.0 (High Speed)"


class TestGetDeviceInfo:
    def test_aggregates_all_fields(self):
        client = make_fake_client()

        info = device.get_device_info(client, "SERIAL123")

        assert info.serial == "SERIAL123"
        assert info.model == "Pixel 7"
        assert info.manufacturer == "Google"
        assert info.android_version == "14"
        assert info.sdk_version == "34"
        assert info.build_number == "UQ1A.240205.004"
        assert info.battery_level == 85
        assert info.battery_status == "charging"
        assert info.storage.total_kb == 120000000


class TestListDevices:
    def test_list_devices_returns_all_states(self):
        client = MagicMock()
        client.devices.return_value = [
            Device(serial="A", state="device"),
            Device(serial="B", state="unauthorized"),
        ]

        result = device.list_devices(client)

        assert [d.serial for d in result] == ["A", "B"]

    def test_get_ready_devices_filters_to_device_state(self):
        client = MagicMock()
        client.devices.return_value = [
            Device(serial="A", state="device"),
            Device(serial="B", state="unauthorized"),
            Device(serial="C", state="offline"),
        ]

        result = device.get_ready_devices(client)

        assert [d.serial for d in result] == ["A"]


class TestConnectionGuidance:
    def test_guidance_for_ready_device(self):
        message = device.connection_guidance("device")

        assert "connected" in message.lower()

    def test_guidance_for_unauthorized_mentions_allow_prompt(self):
        message = device.connection_guidance("unauthorized")

        assert "allow" in message.lower()

    def test_guidance_for_offline_mentions_reconnect(self):
        message = device.connection_guidance("offline")

        assert "reconnect" in message.lower() or "cable" in message.lower()

    def test_guidance_for_no_device_mentions_usb_debugging(self):
        message = device.connection_guidance("no device")

        assert "usb debugging" in message.lower()


class TestConnectionHealth:
    def test_check_connection_health_no_devices(self):
        client = MagicMock()
        client.devices.return_value = []

        devices, messages = device.check_connection_health(client)

        assert devices == []
        assert any("usb debugging" in m.lower() for m in messages)

    def test_check_connection_health_with_ready_device(self):
        client = MagicMock()
        client.devices.return_value = [Device(serial="A", state="device")]

        devices, messages = device.check_connection_health(client)

        assert len(devices) == 1
        assert any("A" in m and "connected" in m.lower() for m in messages)


class TestRestartAdbServer:
    def test_restart_adb_server_calls_client_restart(self):
        client = MagicMock()

        device.restart_adb_server(client)

        client.restart_server.assert_called_once()

    def test_ensure_adb_server_running_starts_server(self):
        client = MagicMock()

        device.ensure_adb_server_running(client)

        client.start_server.assert_called_once()


class TestWaitForDevice:
    def test_delegates_to_client_wait_for_device(self):
        client = MagicMock()

        device.wait_for_device(client, serial="SERIAL123", timeout=5)

        client.wait_for_device.assert_called_once_with(serial="SERIAL123", timeout=5)

    def test_defaults_to_no_serial_and_no_timeout(self):
        client = MagicMock()

        device.wait_for_device(client)

        client.wait_for_device.assert_called_once_with(serial=None, timeout=None)


class TestResolveReadyDevice:
    def test_no_ready_devices_raises_with_no_device_guidance(self):
        client = MagicMock()
        client.devices.return_value = []

        with pytest.raises(device.DeviceSelectionError) as exc_info:
            device.resolve_ready_device(client)

        assert "usb debugging" in str(exc_info.value).lower()

    def test_single_ready_device_serial_none_returns_its_serial(self):
        client = MagicMock()
        client.devices.return_value = [Device(serial="A", state="device", model="Pixel 7")]

        assert device.resolve_ready_device(client) == "A"

    def test_multiple_ready_devices_serial_none_lists_candidates(self):
        client = MagicMock()
        client.devices.return_value = [
            Device(serial="A", state="device", model="Pixel 7"),
            Device(serial="B", state="device", model="Pixel 8"),
        ]

        with pytest.raises(device.DeviceSelectionError) as exc_info:
            device.resolve_ready_device(client)

        message = str(exc_info.value)
        assert "Multiple devices connected" in message
        assert "A  (Pixel 7)" in message
        assert "B  (Pixel 8)" in message

    def test_explicit_serial_matching_ready_device_is_returned(self):
        client = MagicMock()
        client.devices.return_value = [
            Device(serial="A", state="device", model="Pixel 7"),
            Device(serial="B", state="device", model="Pixel 8"),
        ]

        assert device.resolve_ready_device(client, serial="B") == "B"

    def test_explicit_serial_not_ready_raises(self):
        client = MagicMock()
        client.devices.return_value = [Device(serial="A", state="device", model="Pixel 7")]

        with pytest.raises(device.DeviceSelectionError) as exc_info:
            device.resolve_ready_device(client, serial="Z")

        assert "Z" in str(exc_info.value)
        assert "not found or not ready" in str(exc_info.value)

    def test_unauthorized_device_raises_with_unauthorized_guidance(self):
        client = MagicMock()
        client.devices.return_value = [Device(serial="A", state="unauthorized")]

        with pytest.raises(device.DeviceSelectionError) as exc_info:
            device.resolve_ready_device(client)

        message = str(exc_info.value)
        assert "allow" in message.lower()
        assert "A" in message

    def test_offline_device_raises_with_offline_guidance(self):
        client = MagicMock()
        client.devices.return_value = [Device(serial="A", state="offline")]

        with pytest.raises(device.DeviceSelectionError) as exc_info:
            device.resolve_ready_device(client)

        assert "Device is offline" in str(exc_info.value)

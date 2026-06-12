"""Tests for droidbridge.gui.device_context.DeviceContext (Phase 6.1)."""

from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext


class TestDeviceContext:
    def test_starts_disconnected(self, qtbot):
        context = DeviceContext()

        assert context.is_connected is False
        assert context.client is None
        assert context.serial is None

    def test_set_connected_updates_state_and_emits_signal(self, qtbot):
        context = DeviceContext()
        client = MagicMock()
        events = []
        context.connectionChanged.connect(lambda *a: events.append(a))

        context.set_connected(client, "SERIAL123", "Pixel 7")

        assert context.is_connected is True
        assert context.client is client
        assert context.serial == "SERIAL123"
        assert context.model == "Pixel 7"
        assert events == [(True, "SERIAL123", "Pixel 7")]

    def test_clear_resets_state_and_emits_signal(self, qtbot):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        events = []
        context.connectionChanged.connect(lambda *a: events.append(a))

        context.clear()

        assert context.is_connected is False
        assert context.client is None
        assert context.serial is None
        assert context.model is None
        assert events == [(False, "", "")]

# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import pytest
from droidbridge.utils.errors import friendly_error


class TestFriendlyError:
    def test_device_unauthorized(self):
        msg = friendly_error(Exception("error: device unauthorized"))
        assert "Allow" in msg or "authorized" in msg.lower()

    def test_no_devices_found(self):
        msg = friendly_error(Exception("error: no devices/emulators found"))
        assert "No device found" in msg

    def test_device_offline(self):
        msg = friendly_error(Exception("error: device offline"))
        assert "offline" in msg.lower()

    def test_permission_denied(self):
        msg = friendly_error(Exception("ls: /init: Permission denied"))
        assert "Permission denied" in msg

    def test_no_such_file(self):
        msg = friendly_error(Exception("ls: /sdcard/Nope: No such file or directory"))
        assert "not found" in msg.lower()

    def test_find_bad_arg(self):
        msg = friendly_error(Exception("find: bad arg '-printf'"))
        assert "not supported" in msg.lower() or "shell command" in msg.lower()

    def test_connection_lost(self):
        msg = friendly_error(Exception("error: closed"))
        assert "lost" in msg.lower() or "disconnect" in msg.lower()

    def test_no_space_left(self):
        msg = friendly_error(Exception("failed to copy: No space left on device"))
        assert "storage" in msg.lower() or "space" in msg.lower()

    def test_unknown_error_passes_through(self):
        raw = "some totally unknown error xyz"
        assert friendly_error(Exception(raw)) == raw

    def test_case_insensitive_matching(self):
        msg = friendly_error(Exception("DEVICE UNAUTHORIZED"))
        assert "Allow" in msg or "authorized" in msg.lower()

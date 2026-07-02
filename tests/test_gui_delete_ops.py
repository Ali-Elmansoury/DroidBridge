# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.delete_ops (Phase 6.3) — plain functions, no Qt."""

from unittest.mock import MagicMock

from droidbridge.gui import delete_ops


def make_fake_client(output):
    client = MagicMock()
    client.shell.return_value = output
    return client


class TestRenamePath:
    def test_delegates_to_files_module(self):
        client = make_fake_client("")

        delete_ops.rename_path(client, "SERIAL", "/sdcard/old.txt", "/sdcard/new.txt")

        client.shell.assert_called_once_with(
            "SERIAL",
            "if [ -e /sdcard/new.txt ]; then echo EXISTS; "
            "else mv /sdcard/old.txt /sdcard/new.txt; fi",
        )


class TestBuildDeletePlan:
    def test_single_file_returns_plan(self):
        client = make_fake_client("100")

        plan = delete_ops.build_delete_plan(client, "SERIAL", ["/sdcard/old.jpg"])

        assert plan.paths == ["/sdcard/old.jpg"]
        assert plan.file_count == 1
        assert plan.total_size == 100


class TestDeletePaths:
    def test_delegates_to_files_module(self):
        client = MagicMock()
        client.shell.side_effect = ["100", ""]

        delete_ops.delete_paths(client, "SERIAL", ["/sdcard/old.jpg"])

        assert client.shell.call_count == 2
        assert client.shell.call_args_list[1].args == ("SERIAL", "rm -f /sdcard/old.jpg")


class TestVerifyDeletion:
    def test_returns_verification(self):
        client = make_fake_client("NO\n")

        verification = delete_ops.verify_deletion(client, "SERIAL", ["/sdcard/old.jpg"])

        assert verification.deleted == ["/sdcard/old.jpg"]
        assert verification.remaining == []

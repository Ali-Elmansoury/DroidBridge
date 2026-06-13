"""Tests for droidbridge.gui.files_ops (Phase 6.2) — plain functions, no Qt."""

from unittest.mock import MagicMock

from droidbridge.gui import files_ops
from droidbridge.modules import search as search_module

LS_OUTPUT = (
    "total 12\n"
    "drwxrwx---  2 root everybody    4096 2023-08-05 22:56 Camera\n"
    "-rw-rw----  1 root everybody   24647 2023-08-01 10:00 photo.jpg\n"
    "-rw-rw----  1 root everybody     512 2023-08-02 11:00 .hidden.txt\n"
    "-rw-rw----  1 root everybody    2048 2023-08-03 12:00 notes.txt\n"
)


def make_fake_client(output):
    client = MagicMock()
    client.shell.return_value = output
    return client


class TestListPath:
    def test_default_sort_and_hidden_filtering(self):
        client = make_fake_client(LS_OUTPUT)

        entries = files_ops.list_path(client, "SERIAL", "/sdcard")

        assert [e.name for e in entries] == ["Camera", "notes.txt", "photo.jpg"]

    def test_show_hidden_includes_dotfiles(self):
        client = make_fake_client(LS_OUTPUT)

        entries = files_ops.list_path(client, "SERIAL", "/sdcard", show_hidden=True)

        assert ".hidden.txt" in [e.name for e in entries]

    def test_extension_filter(self):
        client = make_fake_client(LS_OUTPUT)

        entries = files_ops.list_path(client, "SERIAL", "/sdcard", extensions=["jpg"])

        assert [e.name for e in entries] == ["Camera", "photo.jpg"]

    def test_sort_by_size_reverse(self):
        client = make_fake_client(LS_OUTPUT)

        entries = files_ops.list_path(client, "SERIAL", "/sdcard", sort_by="size", reverse=True)

        assert [e.name for e in entries] == ["photo.jpg", "Camera", "notes.txt"]


class TestParentPath:
    def test_returns_parent_directory(self):
        assert files_ops.parent_path("/sdcard/DCIM") == "/sdcard"

    def test_top_level_dir_returns_root(self):
        assert files_ops.parent_path("/sdcard") == "/"

    def test_root_stays_root(self):
        assert files_ops.parent_path("/") == "/"


class TestJoinPath:
    def test_joins_dir_and_name(self):
        assert files_ops.join_path("/sdcard", "New Folder") == "/sdcard/New Folder"

    def test_root_dir_does_not_double_slash(self):
        assert files_ops.join_path("/", "New Folder") == "/New Folder"


class TestMakeDirectory:
    def test_delegates_to_files_module(self):
        client = make_fake_client("")

        files_ops.make_directory(client, "SERIAL", "/sdcard/New Folder")

        client.shell.assert_called_once_with("SERIAL", "mkdir -p '/sdcard/New Folder'")


class TestQuickJumpPaths:
    def test_contains_expected_entries(self):
        assert files_ops.QUICK_JUMP_PATHS == {
            "Root": "/sdcard",
            "DCIM": "/sdcard/DCIM",
            "Downloads": "/sdcard/Download",
            "Pictures": "/sdcard/Pictures",
            "WhatsApp Media": search_module.WHATSAPP_MEDIA_PATH,
        }

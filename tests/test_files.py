"""Tests for droidbridge.modules.files - Module 2: File Browser."""

from datetime import datetime
from unittest.mock import MagicMock

from droidbridge.modules import files

LS_OUTPUT_DCIM = (
    "total 2464\n"
    "-rw-rw----  1 root everybody      89 2026-02-24 22:58 .319e7450d45d5b00.cfg\n"
    "drwxrwx---  3 root everybody    4096 2021-10-11 10:51 .Save Stickers\n"
    "-rw-rw----  1 root everybody   24647 2021-10-03 00:57 12qj1lm88zmui6jf70yc1wk2u.jpg\n"
    "drwxrwx---  2 root everybody    4096 2023-08-05 22:56 Bills\n"
)

LS_OUTPUT_EMPTY = "total 0\n"

LS_OUTPUT_SYMLINK = (
    "total 4\n"
    "lrwxrwxrwx  1 root root  10 2024-01-01 00:00 link -> /sdcard/Bills\n"
)


def make_fake_client(output):
    client = MagicMock()
    client.shell.return_value = output
    return client


class TestListDirectory:
    def test_parses_files_and_directories(self):
        client = make_fake_client(LS_OUTPUT_DCIM)

        entries = files.list_directory(client, "SERIAL", "/sdcard/DCIM")

        assert [e.name for e in entries] == [
            ".319e7450d45d5b00.cfg",
            ".Save Stickers",
            "12qj1lm88zmui6jf70yc1wk2u.jpg",
            "Bills",
        ]

        cfg, stickers, jpg, bills = entries

        assert cfg.is_dir is False
        assert cfg.is_symlink is False
        assert cfg.size == 89
        assert cfg.mtime == datetime(2026, 2, 24, 22, 58)
        assert cfg.path == "/sdcard/DCIM/.319e7450d45d5b00.cfg"
        assert cfg.extension == "cfg"

        assert stickers.is_dir is True
        assert stickers.size == 4096
        assert stickers.extension == ""
        assert stickers.path == "/sdcard/DCIM/.Save Stickers"

        assert jpg.extension == "jpg"
        assert jpg.size == 24647

        assert bills.is_dir is True
        assert bills.path == "/sdcard/DCIM/Bills"

    def test_empty_directory_returns_no_entries(self):
        client = make_fake_client(LS_OUTPUT_EMPTY)

        entries = files.list_directory(client, "SERIAL", "/sdcard/DCIM/EmptyDir")

        assert entries == []

    def test_parses_symlink_with_target(self):
        client = make_fake_client(LS_OUTPUT_SYMLINK)

        entries = files.list_directory(client, "SERIAL", "/sdcard")

        assert len(entries) == 1
        link = entries[0]
        assert link.name == "link"
        assert link.is_symlink is True
        assert link.is_dir is False
        assert link.link_target == "/sdcard/Bills"

    def test_runs_ls_la_with_trailing_slash_and_quoting(self):
        client = make_fake_client(LS_OUTPUT_EMPTY)

        files.list_directory(client, "SERIAL", "/sdcard/DCIM/Auto Background Changer")

        client.shell.assert_called_once_with(
            "SERIAL", "ls -la '/sdcard/DCIM/Auto Background Changer/'"
        )

    def test_root_path_does_not_get_double_slash(self):
        client = make_fake_client(LS_OUTPUT_EMPTY)

        files.list_directory(client, "SERIAL", "/")

        client.shell.assert_called_once_with("SERIAL", "ls -la /")


class TestSortEntries:
    def _entries(self):
        return [
            files.FileEntry(
                name="b.txt", path="/b.txt", is_dir=False, is_symlink=False,
                size=200, mtime=datetime(2024, 1, 2),
            ),
            files.FileEntry(
                name="A.jpg", path="/A.jpg", is_dir=False, is_symlink=False,
                size=100, mtime=datetime(2024, 1, 3),
            ),
            files.FileEntry(
                name="Folder", path="/Folder", is_dir=True, is_symlink=False,
                size=4096, mtime=datetime(2024, 1, 1),
            ),
        ]

    def test_sort_by_name_is_case_insensitive(self):
        result = files.sort_entries(self._entries(), by="name")

        assert [e.name for e in result] == ["A.jpg", "b.txt", "Folder"]

    def test_sort_by_size(self):
        result = files.sort_entries(self._entries(), by="size")

        assert [e.name for e in result] == ["A.jpg", "b.txt", "Folder"]

    def test_sort_by_date(self):
        result = files.sort_entries(self._entries(), by="date")

        assert [e.name for e in result] == ["Folder", "b.txt", "A.jpg"]

    def test_sort_by_type_directories_first(self):
        result = files.sort_entries(self._entries(), by="type")

        assert result[0].name == "Folder"

    def test_reverse_order(self):
        result = files.sort_entries(self._entries(), by="name", reverse=True)

        assert [e.name for e in result] == ["Folder", "b.txt", "A.jpg"]


class TestFilterEntries:
    def _entries(self):
        return [
            files.FileEntry(
                name=".hidden", path="/.hidden", is_dir=False, is_symlink=False,
                size=10, mtime=datetime(2020, 1, 1),
            ),
            files.FileEntry(
                name="photo.jpg", path="/photo.jpg", is_dir=False, is_symlink=False,
                size=2_000_000, mtime=datetime(2024, 6, 1),
            ),
            files.FileEntry(
                name="doc.pdf", path="/doc.pdf", is_dir=False, is_symlink=False,
                size=500_000, mtime=datetime(2023, 1, 1),
            ),
            files.FileEntry(
                name="Folder", path="/Folder", is_dir=True, is_symlink=False,
                size=4096, mtime=datetime(2024, 1, 1),
            ),
        ]

    def test_filter_by_extension_keeps_directories(self):
        result = files.filter_entries(self._entries(), extensions=["jpg"])

        assert [e.name for e in result] == ["photo.jpg", "Folder"]

    def test_filter_by_min_size(self):
        result = files.filter_entries(self._entries(), min_size=1_000_000)

        assert [e.name for e in result] == ["photo.jpg", "Folder"]

    def test_filter_by_max_size(self):
        result = files.filter_entries(self._entries(), max_size=1000)

        assert [e.name for e in result] == [".hidden", "Folder"]

    def test_filter_by_date_range(self):
        result = files.filter_entries(
            self._entries(),
            after=datetime(2023, 6, 1),
            before=datetime(2024, 12, 31),
        )

        assert [e.name for e in result] == ["photo.jpg", "Folder"]

    def test_exclude_hidden(self):
        result = files.filter_entries(self._entries(), include_hidden=False)

        assert ".hidden" not in [e.name for e in result]
        assert len(result) == 3

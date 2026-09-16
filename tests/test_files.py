# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.modules.files - Module 2: File Browser."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from droidbridge.core.adb import AdbCommandError
from droidbridge.modules import files
from droidbridge.modules import search as search_module
from droidbridge.modules.search import SearchResult

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
            "SERIAL", "ls -la '/sdcard/DCIM/Auto Background Changer/' 2>/dev/null; true"
        )

    def test_root_path_does_not_get_double_slash(self):
        client = make_fake_client(LS_OUTPUT_EMPTY)

        files.list_directory(client, "SERIAL", "/")

        client.shell.assert_called_once_with("SERIAL", "ls -la / 2>/dev/null; true")


class TestMakeDirectory:
    def test_runs_mkdir_p_with_quoting(self):
        client = make_fake_client("")

        files.make_directory(client, "SERIAL", "/sdcard/New Folder")

        client.shell.assert_called_once_with("SERIAL", "mkdir -p '/sdcard/New Folder'")


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

    def test_filter_by_extension_can_exclude_directories(self):
        result = files.filter_entries(
            self._entries(), extensions=["jpg"], dirs_pass_extension_filter=False
        )

        assert [e.name for e in result] == ["photo.jpg"]

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


class TestRenamePath:
    def test_success_runs_check_and_move(self):
        client = make_fake_client("")

        files.rename_path(client, "SERIAL", "/sdcard/old.txt", "/sdcard/new.txt")

        client.shell.assert_called_once_with(
            "SERIAL",
            "if [ -e /sdcard/new.txt ]; then echo EXISTS; "
            "else mv /sdcard/old.txt /sdcard/new.txt; fi",
        )

    def test_existing_target_raises_without_calling_mv(self):
        client = make_fake_client("EXISTS\n")

        with pytest.raises(AdbCommandError) as exc_info:
            files.rename_path(client, "SERIAL", "/sdcard/old.txt", "/sdcard/new.txt")

        assert "already exists" in str(exc_info.value)


class TestStatPath:
    def test_file_returns_size(self):
        client = make_fake_client("12345")

        kind, size = files._stat_path(client, "SERIAL", "/sdcard/photo.jpg")

        assert kind == "file"
        assert size == 12345
        client.shell.assert_called_once_with(
            "SERIAL",
            "if [ -d /sdcard/photo.jpg ]; then echo DIR; "
            "elif [ -e /sdcard/photo.jpg ]; then stat -c '%s' /sdcard/photo.jpg; "
            "else echo MISSING; fi",
        )

    def test_directory_returns_dir(self):
        client = make_fake_client("DIR\n")

        kind, size = files._stat_path(client, "SERIAL", "/sdcard/DCIM")

        assert kind == "dir"
        assert size is None

    def test_missing_path_returns_missing(self):
        client = make_fake_client("MISSING\n")

        kind, size = files._stat_path(client, "SERIAL", "/sdcard/nope.txt")

        assert kind == "missing"
        assert size is None


class TestBuildDeletePlan:
    def test_single_file(self):
        client = make_fake_client("100")

        plan = files.build_delete_plan(client, "SERIAL", ["/sdcard/a.jpg"])

        assert plan.paths == ["/sdcard/a.jpg"]
        assert plan.file_count == 1
        assert plan.total_size == 100

    def test_single_directory_sums_search_results(self, monkeypatch):
        client = make_fake_client("DIR\n")
        results = [
            SearchResult(path="/sdcard/DCIM/a.jpg", size=100, mtime=datetime(2024, 1, 1)),
            SearchResult(path="/sdcard/DCIM/b.jpg", size=200, mtime=datetime(2024, 1, 2)),
        ]
        monkeypatch.setattr(search_module, "search_files", lambda c, s, p: results)

        plan = files.build_delete_plan(client, "SERIAL", ["/sdcard/DCIM"])

        assert plan.file_count == 2
        assert plan.total_size == 300

    def test_mixed_paths_totals_combine(self, monkeypatch):
        client = MagicMock()
        client.shell.side_effect = ["100", "DIR\n"]
        results = [SearchResult(path="/sdcard/DCIM/a.jpg", size=200, mtime=datetime(2024, 1, 1))]
        monkeypatch.setattr(search_module, "search_files", lambda c, s, p: results)

        plan = files.build_delete_plan(client, "SERIAL", ["/sdcard/a.jpg", "/sdcard/DCIM"])

        assert plan.paths == ["/sdcard/a.jpg", "/sdcard/DCIM"]
        assert plan.file_count == 2
        assert plan.total_size == 300

    def test_missing_path_contributes_nothing(self):
        client = make_fake_client("MISSING\n")

        plan = files.build_delete_plan(client, "SERIAL", ["/sdcard/nope.txt"])

        assert plan.paths == ["/sdcard/nope.txt"]
        assert plan.file_count == 0
        assert plan.total_size == 0


class TestDeletePaths:
    def test_directory_removed_with_rm_rf(self):
        client = MagicMock()
        client.shell.side_effect = ["DIR\n", ""]

        files.delete_paths(client, "SERIAL", ["/sdcard/DCIM"])

        assert client.shell.call_args_list[1].args == ("SERIAL", "rm -rf /sdcard/DCIM")

    def test_files_batched_into_single_rm_f_call(self):
        client = MagicMock()
        client.shell.side_effect = ["100", "200", ""]

        files.delete_paths(client, "SERIAL", ["/sdcard/a.jpg", "/sdcard/b.jpg"])

        assert client.shell.call_args_list[-1].args == (
            "SERIAL", "rm -f /sdcard/a.jpg /sdcard/b.jpg",
        )

    def test_more_than_batch_size_splits_into_multiple_rm_calls(self):
        client = MagicMock()
        paths = [f"/sdcard/f{i}.jpg" for i in range(501)]
        client.shell.side_effect = ["1"] * 501 + ["", ""]

        files.delete_paths(client, "SERIAL", paths)

        rm_calls = [c for c in client.shell.call_args_list if c.args[1].startswith("rm -f")]
        assert len(rm_calls) == 2
        assert len(rm_calls[0].args[1].split()[2:]) == 500
        assert len(rm_calls[1].args[1].split()[2:]) == 1

    def test_mixed_dirs_and_files(self):
        client = MagicMock()
        client.shell.side_effect = ["DIR\n", "100", "", ""]

        files.delete_paths(client, "SERIAL", ["/sdcard/DCIM", "/sdcard/a.jpg"])

        rm_rf_calls = [c.args[1] for c in client.shell.call_args_list if c.args[1].startswith("rm -rf")]
        rm_f_calls = [c.args[1] for c in client.shell.call_args_list if c.args[1].startswith("rm -f")]
        assert rm_rf_calls == ["rm -rf /sdcard/DCIM"]
        assert rm_f_calls == ["rm -f /sdcard/a.jpg"]

    def test_missing_path_is_skipped(self):
        client = MagicMock()
        client.shell.side_effect = ["MISSING\n"]

        files.delete_paths(client, "SERIAL", ["/sdcard/nope.txt"])

        assert client.shell.call_count == 1


class TestVerifyDeletion:
    def test_mixed_deleted_and_remaining(self):
        client = MagicMock()
        client.shell.side_effect = ["NO\n", "YES\n"]

        result = files.verify_deletion(client, "SERIAL", ["/sdcard/a.jpg", "/sdcard/b.jpg"])

        assert result.deleted == ["/sdcard/a.jpg"]
        assert result.remaining == ["/sdcard/b.jpg"]

    def test_all_deleted(self):
        client = MagicMock()
        client.shell.side_effect = ["NO\n", "NO\n"]

        result = files.verify_deletion(client, "SERIAL", ["/sdcard/a.jpg", "/sdcard/b.jpg"])

        assert result.deleted == ["/sdcard/a.jpg", "/sdcard/b.jpg"]
        assert result.remaining == []


class TestVerifyBackup:
    def test_file_present_with_matching_size_is_not_missing(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x" * 100)
        client = make_fake_client("100")

        missing = files.verify_backup(client, "SERIAL", ["/sdcard/a.jpg"], str(tmp_path))

        assert missing == []

    def test_file_missing_is_reported(self, tmp_path):
        client = make_fake_client("100")

        missing = files.verify_backup(client, "SERIAL", ["/sdcard/a.jpg"], str(tmp_path))

        assert missing == ["/sdcard/a.jpg"]

    def test_file_size_mismatch_is_reported(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x" * 50)
        client = make_fake_client("100")

        missing = files.verify_backup(client, "SERIAL", ["/sdcard/a.jpg"], str(tmp_path))

        assert missing == ["/sdcard/a.jpg"]

    def test_directory_present_with_matching_files_is_not_missing(self, tmp_path, monkeypatch):
        client = make_fake_client("DIR\n")
        backup_dcim = tmp_path / "DCIM"
        backup_dcim.mkdir()
        (backup_dcim / "a.jpg").write_bytes(b"x" * 100)
        results = [SearchResult(path="/sdcard/DCIM/a.jpg", size=100, mtime=datetime(2024, 1, 1))]
        monkeypatch.setattr(search_module, "search_files", lambda c, s, p: results)

        missing = files.verify_backup(client, "SERIAL", ["/sdcard/DCIM"], str(tmp_path))

        assert missing == []

    def test_directory_missing_file_is_reported(self, tmp_path, monkeypatch):
        client = make_fake_client("DIR\n")
        backup_dcim = tmp_path / "DCIM"
        backup_dcim.mkdir()
        results = [SearchResult(path="/sdcard/DCIM/a.jpg", size=100, mtime=datetime(2024, 1, 1))]
        monkeypatch.setattr(search_module, "search_files", lambda c, s, p: results)

        missing = files.verify_backup(client, "SERIAL", ["/sdcard/DCIM"], str(tmp_path))

        assert missing == ["/sdcard/DCIM/a.jpg"]

    def test_missing_source_path_is_skipped(self, tmp_path):
        client = make_fake_client("MISSING\n")

        missing = files.verify_backup(client, "SERIAL", ["/sdcard/nope.txt"], str(tmp_path))

        assert missing == []


class TestGetDirectorySize:
    def test_returns_summed_size(self):
        client = make_fake_client("2621440000\n")
        size = files.get_directory_size(client, "SERIAL", "/sdcard/Movies")
        assert size == 2621440000

    def test_empty_directory_returns_zero(self):
        client = make_fake_client("0\n")
        size = files.get_directory_size(client, "SERIAL", "/sdcard/Empty")
        assert size == 0

    def test_error_returns_none(self):
        client = MagicMock()
        client.shell.side_effect = Exception("timeout")
        size = files.get_directory_size(client, "SERIAL", "/sdcard/Movies")
        assert size is None

    def test_non_numeric_output_returns_none(self):
        client = make_fake_client("bad output\n")
        size = files.get_directory_size(client, "SERIAL", "/sdcard/Movies")
        assert size is None

    def test_does_not_use_exec_plus_batching(self):
        # Regression: `find -exec stat ... {} +` batches ALL matched paths
        # into as few `stat` invocations as possible; Android toybox `find`
        # doesn't respect the device's real ARG_MAX when doing this, so a
        # large directory (e.g. WhatsApp Media, /sdcard/Android) fails with
        # "Argument list too long" (E2BIG). `-print0 | xargs -0 stat ...`
        # lets xargs chunk correctly (verified on-device: same command
        # pattern returned all 62780 files intact vs exit 126 before).
        client = make_fake_client("123\n")
        files.get_directory_size(client, "SERIAL", "/sdcard/Movies")
        cmd = client.shell.call_args[0][1]
        assert "-exec" not in cmd
        assert "-print0" in cmd
        assert "xargs -0" in cmd


class TestListStorageVolumes:
    def test_no_sd_card_returns_internal_only(self):
        client = make_fake_client("emulated\nself\n")

        volumes = files.list_storage_volumes(client, "SERIAL")

        assert len(volumes) == 1
        assert volumes[0]["label"] == "Internal Storage"
        assert volumes[0]["path"] == "/sdcard"
        assert volumes[0]["removable"] is False

    def test_sd_card_label_pattern_is_detected(self):
        client = make_fake_client("emulated\nself\n1A2B-3C4D\n")

        volumes = files.list_storage_volumes(client, "SERIAL")

        assert len(volumes) == 2
        sd = volumes[1]
        assert sd["label"] == "SD Card (1A2B-3C4D)"
        assert sd["path"] == "/storage/1A2B-3C4D"
        assert sd["removable"] is True

    def test_multiple_sd_cards_all_detected(self):
        client = make_fake_client("emulated\n1A2B-3C4D\nAABB-CCDD\n")

        volumes = files.list_storage_volumes(client, "SERIAL")

        assert len(volumes) == 3

    def test_shell_error_returns_internal_only(self):
        client = MagicMock()
        client.shell.side_effect = Exception("connection lost")

        volumes = files.list_storage_volumes(client, "SERIAL")

        assert len(volumes) == 1
        assert volumes[0]["path"] == "/sdcard"

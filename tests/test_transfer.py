"""Tests for droidbridge.modules.transfer - Module 3: Smart Transfer Engine."""

from unittest.mock import MagicMock

import pytest

from droidbridge.core.adb import AdbError
from droidbridge.modules import transfer
from droidbridge.modules import search as search_module
from droidbridge.modules.search import SearchResult

DIR_FIND_OUTPUT = (
    "/sdcard/Camera/photo1.jpg\t1000\t1700000000.0\n"
    "/sdcard/Camera/photo2.jpg\t2000\t1700000100.0\n"
)


def make_client(*shell_outputs):
    client = MagicMock()
    client.shell.side_effect = list(shell_outputs)
    return client


class TestTransferProgress:
    def test_percent(self):
        progress = transfer.TransferProgress(total_files=4, total_bytes=1000, done_files=1, done_bytes=250)
        assert progress.percent == 25.0

    def test_percent_zero_total_is_complete(self):
        progress = transfer.TransferProgress(total_files=0, total_bytes=0)
        assert progress.percent == 100.0

    def test_speed_and_eta(self, monkeypatch):
        progress = transfer.TransferProgress(
            total_files=2, total_bytes=1000, done_files=1, done_bytes=500, start_time=0.0
        )
        monkeypatch.setattr(transfer.time, "monotonic", lambda: 10.0)

        assert progress.speed_bps == 50.0
        assert progress.eta_seconds == 10.0

    def test_eta_none_when_no_progress(self, monkeypatch):
        progress = transfer.TransferProgress(
            total_files=2, total_bytes=1000, done_files=0, done_bytes=0, start_time=0.0
        )
        monkeypatch.setattr(transfer.time, "monotonic", lambda: 10.0)

        assert progress.eta_seconds is None


class TestResolveConflictPath:
    def test_returns_original_if_no_conflict(self):
        assert transfer.resolve_conflict_path("/tmp/photo.jpg", lambda p: False) == "/tmp/photo.jpg"

    def test_appends_suffix_on_conflict(self):
        existing = {"/tmp/photo.jpg"}
        assert transfer.resolve_conflict_path("/tmp/photo.jpg", lambda p: p in existing) == "/tmp/photo_1.jpg"

    def test_increments_suffix_until_free(self):
        existing = {"/tmp/photo.jpg", "/tmp/photo_1.jpg", "/tmp/photo_2.jpg"}
        assert transfer.resolve_conflict_path("/tmp/photo.jpg", lambda p: p in existing) == "/tmp/photo_3.jpg"


class TestExecutePlanRetry:
    def test_success_on_second_attempt(self, tmp_path):
        dest = tmp_path / "photo.jpg"
        call_count = [0]

        def fake_pull(serial, remote, local):
            call_count[0] += 1
            if call_count[0] < 2:
                raise AdbError("timeout")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x" * 1000)

        client = MagicMock()
        client.pull.side_effect = fake_pull
        plan = transfer.TransferPlan(
            direction="pull",
            items=[transfer.TransferItem(
                source="/sdcard/photo.jpg", dest=str(dest), size=1000, action=transfer.ACTION_COPY,
            )],
        )
        sleep_calls = []
        progress = transfer.execute_plan(client, "SERIAL", plan, sleep_fn=sleep_calls.append)

        assert progress.done_files == 1
        assert progress.failed == []
        assert sleep_calls == [1.0]

    def test_all_attempts_fail_item_goes_to_failed(self):
        client = MagicMock()
        client.pull.side_effect = AdbError("connection reset")
        plan = transfer.TransferPlan(
            direction="pull",
            items=[transfer.TransferItem(
                source="/sdcard/photo.jpg", dest="/tmp/photo.jpg", size=1000,
                action=transfer.ACTION_COPY,
            )],
        )
        progress = transfer.execute_plan(
            client, "SERIAL", plan, retry_count=2, sleep_fn=lambda _: None,
        )

        assert progress.done_files == 0
        assert len(progress.failed) == 1
        assert progress.failed[0].item.source == "/sdcard/photo.jpg"
        assert "connection reset" in progress.failed[0].error

    def test_failed_item_does_not_halt_transfer(self, tmp_path):
        dest2 = tmp_path / "photo2.jpg"
        call_count = [0]

        def fake_pull(serial, remote, local):
            call_count[0] += 1
            if "photo1" in remote:
                raise AdbError("permission denied")
            dest2.parent.mkdir(parents=True, exist_ok=True)
            dest2.write_bytes(b"x" * 500)

        client = MagicMock()
        client.pull.side_effect = fake_pull
        plan = transfer.TransferPlan(
            direction="pull",
            items=[
                transfer.TransferItem(
                    source="/sdcard/photo1.jpg", dest=str(tmp_path / "photo1.jpg"),
                    size=1000, action=transfer.ACTION_COPY,
                ),
                transfer.TransferItem(
                    source="/sdcard/photo2.jpg", dest=str(dest2),
                    size=500, action=transfer.ACTION_COPY,
                ),
            ],
        )
        progress = transfer.execute_plan(
            client, "SERIAL", plan, retry_count=0, sleep_fn=lambda _: None,
        )

        assert progress.done_files == 1
        assert len(progress.failed) == 1
        assert progress.failed[0].item.source == "/sdcard/photo1.jpg"

    def test_retry_count_zero_no_sleep(self):
        client = MagicMock()
        client.pull.side_effect = AdbError("timeout")
        plan = transfer.TransferPlan(
            direction="pull",
            items=[transfer.TransferItem(
                source="/sdcard/a.jpg", dest="/tmp/a.jpg", size=100, action=transfer.ACTION_COPY,
            )],
        )
        sleep_calls = []
        transfer.execute_plan(
            client, "SERIAL", plan, retry_count=0, sleep_fn=sleep_calls.append,
        )

        assert sleep_calls == []

    def test_progress_callback_fires_after_failed_item(self):
        client = MagicMock()
        client.pull.side_effect = AdbError("error")
        plan = transfer.TransferPlan(
            direction="pull",
            items=[transfer.TransferItem(
                source="/sdcard/a.jpg", dest="/tmp/a.jpg", size=100, action=transfer.ACTION_COPY,
            )],
        )
        callbacks = []
        transfer.execute_plan(
            client, "SERIAL", plan, retry_count=0, sleep_fn=lambda _: None,
            progress_callback=callbacks.append,
        )

        assert len(callbacks) == 1
        assert len(callbacks[0].failed) == 1


class TestPlanPull:
    def test_single_file_no_conflict(self, tmp_path):
        client = make_client("1000")

        plan = transfer.plan_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path))

        assert plan.direction == "pull"
        assert len(plan.items) == 1
        item = plan.items[0]
        assert item.source == "/sdcard/photo.jpg"
        assert item.dest == str(tmp_path / "photo.jpg")
        assert item.size == 1000
        assert item.action == transfer.ACTION_COPY
        assert plan.total_files == 1
        assert plan.total_bytes == 1000

    def test_single_file_already_present_same_size(self, tmp_path):
        dest = tmp_path / "photo.jpg"
        dest.write_bytes(b"x" * 1000)
        client = make_client("1000")

        plan = transfer.plan_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path))

        item = plan.items[0]
        assert item.action == transfer.ACTION_SKIP_EXISTING
        assert plan.total_files == 0
        assert plan.already_present == [item]

    def test_single_file_conflict_skip(self, tmp_path):
        dest = tmp_path / "photo.jpg"
        dest.write_bytes(b"x" * 500)
        client = make_client("1000")

        plan = transfer.plan_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path), conflict="skip")

        item = plan.items[0]
        assert item.action == transfer.ACTION_SKIP_CONFLICT
        assert plan.conflicts_skipped == [item]
        assert plan.total_files == 0

    def test_single_file_conflict_overwrite(self, tmp_path):
        dest = tmp_path / "photo.jpg"
        dest.write_bytes(b"x" * 500)
        client = make_client("1000")

        plan = transfer.plan_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path), conflict="overwrite")

        item = plan.items[0]
        assert item.action == transfer.ACTION_OVERWRITE
        assert item.dest == str(dest)
        assert plan.total_files == 1

    def test_single_file_conflict_rename(self, tmp_path):
        dest = tmp_path / "photo.jpg"
        dest.write_bytes(b"x" * 500)
        client = make_client("1000")

        plan = transfer.plan_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path), conflict="rename")

        item = plan.items[0]
        assert item.action == transfer.ACTION_RENAME
        assert item.dest == str(tmp_path / "photo_1.jpg")
        assert plan.total_files == 1

    def test_invalid_conflict_mode_raises(self, tmp_path):
        client = make_client("1000")

        with pytest.raises(ValueError):
            transfer.plan_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path), conflict="bogus")

    def test_directory_recurses_with_relative_paths(self, tmp_path):
        client = make_client("DIR\n", DIR_FIND_OUTPUT)

        plan = transfer.plan_pull(client, "SERIAL", "/sdcard/Camera", str(tmp_path))

        assert len(plan.items) == 2
        paths = {item.source: item.dest for item in plan.items}
        assert paths["/sdcard/Camera/photo1.jpg"] == str(tmp_path / "Camera" / "photo1.jpg")
        assert paths["/sdcard/Camera/photo2.jpg"] == str(tmp_path / "Camera" / "photo2.jpg")
        assert all(item.action == transfer.ACTION_COPY for item in plan.items)
        assert plan.total_files == 2
        assert plan.total_bytes == 3000

    def test_directory_skips_already_present_files(self, tmp_path):
        camera_dir = tmp_path / "Camera"
        camera_dir.mkdir()
        (camera_dir / "photo1.jpg").write_bytes(b"x" * 1000)
        client = make_client("DIR\n", DIR_FIND_OUTPUT)

        plan = transfer.plan_pull(client, "SERIAL", "/sdcard/Camera", str(tmp_path))

        actions = {item.source: item.action for item in plan.items}
        assert actions["/sdcard/Camera/photo1.jpg"] == transfer.ACTION_SKIP_EXISTING
        assert actions["/sdcard/Camera/photo2.jpg"] == transfer.ACTION_COPY
        assert plan.total_files == 1
        assert plan.total_bytes == 2000


class TestPlanPush:
    def test_single_file_no_conflict(self, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)
        client = make_client("NO\n")

        plan = transfer.plan_push(client, "SERIAL", str(local_file), "/sdcard/Download")

        assert plan.direction == "push"
        item = plan.items[0]
        assert item.source == str(local_file)
        assert item.dest == "/sdcard/Download/report.pdf"
        assert item.size == 100
        assert item.action == transfer.ACTION_COPY

    def test_directory_recurses_with_relative_paths(self, tmp_path):
        local_dir = tmp_path / "myfolder"
        local_dir.mkdir()
        (local_dir / "a.txt").write_bytes(b"a" * 5)
        (local_dir / "b.txt").write_bytes(b"b" * 10)
        client = make_client("NO\n")

        plan = transfer.plan_push(client, "SERIAL", str(local_dir), "/sdcard/Backup")

        dests = {item.source: item.dest for item in plan.items}
        assert dests[str(local_dir / "a.txt")] == "/sdcard/Backup/myfolder/a.txt"
        assert dests[str(local_dir / "b.txt")] == "/sdcard/Backup/myfolder/b.txt"
        assert all(item.action == transfer.ACTION_COPY for item in plan.items)
        assert plan.total_files == 2
        assert plan.total_bytes == 15

    def test_directory_resume_skips_existing_with_matching_size(self, tmp_path):
        local_dir = tmp_path / "myfolder"
        local_dir.mkdir()
        (local_dir / "a.txt").write_bytes(b"a" * 5)
        (local_dir / "b.txt").write_bytes(b"b" * 10)

        existing_output = "/sdcard/Backup/myfolder/a.txt\t5\t1700000000.0\n"
        client = make_client("DIR\n", existing_output)

        plan = transfer.plan_push(client, "SERIAL", str(local_dir), "/sdcard/Backup")

        actions = {item.source: item.action for item in plan.items}
        assert actions[str(local_dir / "a.txt")] == transfer.ACTION_SKIP_EXISTING
        assert actions[str(local_dir / "b.txt")] == transfer.ACTION_COPY
        assert plan.total_files == 1
        assert plan.total_bytes == 10

    def test_directory_push_manifests_only_the_destination_subtree(self, tmp_path):
        """The remote manifest scan must stay scoped to remote_dir/base_name, not
        all of remote_dir - remote_dir can be a large, unrelated directory (e.g.
        a restore's source parent, often /sdcard itself), and recursively
        `find`-ing it is what made real-device restores take well over 30s."""
        local_dir = tmp_path / "myfolder"
        local_dir.mkdir()
        (local_dir / "a.txt").write_bytes(b"a" * 5)
        client = make_client("DIR\n", "")

        transfer.plan_push(client, "SERIAL", str(local_dir), "/sdcard")

        exists_call, find_call = client.shell.call_args_list
        assert "/sdcard/myfolder" in exists_call.args[1]
        assert "/sdcard/myfolder" in find_call.args[1]

    def test_conflict_overwrite(self, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_output = "/sdcard/Download/report.pdf\t50\t1700000000.0\n"
        client = make_client("DIR\n", existing_output)

        plan = transfer.plan_push(client, "SERIAL", str(local_file), "/sdcard/Download", conflict="overwrite")

        item = plan.items[0]
        assert item.action == transfer.ACTION_OVERWRITE
        assert item.dest == "/sdcard/Download/report.pdf"

    def test_conflict_rename(self, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_output = "/sdcard/Download/report.pdf\t50\t1700000000.0\n"
        client = make_client("DIR\n", existing_output)

        plan = transfer.plan_push(client, "SERIAL", str(local_file), "/sdcard/Download", conflict="rename")

        item = plan.items[0]
        assert item.action == transfer.ACTION_RENAME
        assert item.dest == "/sdcard/Download/report_1.pdf"

    def test_conflict_skip(self, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_output = "/sdcard/Download/report.pdf\t50\t1700000000.0\n"
        client = make_client("DIR\n", existing_output)

        plan = transfer.plan_push(client, "SERIAL", str(local_file), "/sdcard/Download", conflict="skip")

        item = plan.items[0]
        assert item.action == transfer.ACTION_SKIP_CONFLICT
        assert plan.conflicts_skipped == [item]
        assert plan.total_files == 0


class TestExecutePlan:
    def test_pull_calls_client_pull_for_each_item(self, tmp_path):
        client = MagicMock()
        plan = transfer.TransferPlan(
            direction="pull",
            items=[
                transfer.TransferItem(
                    source="/sdcard/Camera/photo1.jpg",
                    dest=str(tmp_path / "Camera" / "photo1.jpg"),
                    size=1000,
                    action=transfer.ACTION_COPY,
                ),
                transfer.TransferItem(
                    source="/sdcard/Camera/photo2.jpg",
                    dest=str(tmp_path / "Camera" / "photo2.jpg"),
                    size=2000,
                    action=transfer.ACTION_SKIP_EXISTING,
                ),
            ],
        )

        progress = transfer.execute_plan(client, "SERIAL", plan)

        client.pull.assert_called_once_with(
            "SERIAL", "/sdcard/Camera/photo1.jpg", str(tmp_path / "Camera" / "photo1.jpg")
        )
        assert (tmp_path / "Camera").is_dir()
        assert progress.done_files == 1
        assert progress.done_bytes == 1000
        assert progress.total_files == 1
        assert progress.total_bytes == 1000

    def test_push_calls_mkdir_and_client_push(self, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)
        client = MagicMock()
        plan = transfer.TransferPlan(
            direction="push",
            items=[
                transfer.TransferItem(
                    source=str(local_file),
                    dest="/sdcard/Download/report.pdf",
                    size=100,
                    action=transfer.ACTION_COPY,
                ),
            ],
        )

        progress = transfer.execute_plan(client, "SERIAL", plan)

        client.shell.assert_called_once_with("SERIAL", "mkdir -p /sdcard/Download")
        client.push.assert_called_once_with("SERIAL", str(local_file), "/sdcard/Download/report.pdf")
        assert progress.done_files == 1
        assert progress.done_bytes == 100

    def test_progress_callback_invoked_per_item(self):
        client = MagicMock()
        plan = transfer.TransferPlan(
            direction="push",
            items=[
                transfer.TransferItem(source="/a", dest="/sdcard/a", size=10, action=transfer.ACTION_COPY),
                transfer.TransferItem(source="/b", dest="/sdcard/b", size=20, action=transfer.ACTION_COPY),
            ],
        )

        seen = []
        transfer.execute_plan(client, "SERIAL", plan, progress_callback=lambda p: seen.append(p.done_bytes))

        assert seen == [10, 30]


class TestVerifyPull:
    def test_ok_when_files_match(self, tmp_path):
        f1 = tmp_path / "a.jpg"
        f1.write_bytes(b"x" * 100)
        f2 = tmp_path / "b.jpg"
        f2.write_bytes(b"x" * 200)

        plan = transfer.TransferPlan(
            direction="pull",
            items=[
                transfer.TransferItem(source="/sdcard/a.jpg", dest=str(f1), size=100, action=transfer.ACTION_COPY),
                transfer.TransferItem(
                    source="/sdcard/b.jpg", dest=str(f2), size=200, action=transfer.ACTION_SKIP_EXISTING
                ),
            ],
        )

        result = transfer.verify_pull(plan)

        assert result.ok
        assert result.expected_files == 2
        assert result.expected_bytes == 300
        assert result.actual_files == 2
        assert result.actual_bytes == 300

    def test_not_ok_when_file_missing(self, tmp_path):
        f1 = tmp_path / "a.jpg"
        f1.write_bytes(b"x" * 100)
        missing = tmp_path / "b.jpg"

        plan = transfer.TransferPlan(
            direction="pull",
            items=[
                transfer.TransferItem(source="/sdcard/a.jpg", dest=str(f1), size=100, action=transfer.ACTION_COPY),
                transfer.TransferItem(
                    source="/sdcard/b.jpg", dest=str(missing), size=200, action=transfer.ACTION_COPY
                ),
            ],
        )

        result = transfer.verify_pull(plan)

        assert not result.ok
        assert result.expected_files == 2
        assert result.actual_files == 1

    def test_conflict_skipped_items_excluded(self, tmp_path):
        missing = tmp_path / "b.jpg"
        plan = transfer.TransferPlan(
            direction="pull",
            items=[
                transfer.TransferItem(
                    source="/sdcard/b.jpg", dest=str(missing), size=200, action=transfer.ACTION_SKIP_CONFLICT
                ),
            ],
        )

        result = transfer.verify_pull(plan)

        assert result.ok
        assert result.expected_files == 0


class TestVerifyPush:
    def test_ok_when_remote_files_match(self):
        existing_output = (
            "/sdcard/Backup/a.txt\t100\t1700000000.0\n"
            "/sdcard/Backup/b.txt\t200\t1700000000.0\n"
        )
        client = make_client("DIR\n", existing_output)
        plan = transfer.TransferPlan(
            direction="push",
            items=[
                transfer.TransferItem(source="/local/a.txt", dest="/sdcard/Backup/a.txt", size=100, action=transfer.ACTION_COPY),
                transfer.TransferItem(source="/local/b.txt", dest="/sdcard/Backup/b.txt", size=200, action=transfer.ACTION_SKIP_EXISTING),
            ],
        )

        result = transfer.verify_push(client, "SERIAL", plan, "/sdcard/Backup")

        assert result.ok
        assert result.expected_files == 2
        assert result.actual_files == 2

    def test_not_ok_when_remote_file_missing(self):
        existing_output = "/sdcard/Backup/a.txt\t100\t1700000000.0\n"
        client = make_client("DIR\n", existing_output)
        plan = transfer.TransferPlan(
            direction="push",
            items=[
                transfer.TransferItem(source="/local/a.txt", dest="/sdcard/Backup/a.txt", size=100, action=transfer.ACTION_COPY),
                transfer.TransferItem(source="/local/b.txt", dest="/sdcard/Backup/b.txt", size=200, action=transfer.ACTION_COPY),
            ],
        )

        result = transfer.verify_push(client, "SERIAL", plan, "/sdcard/Backup")

        assert not result.ok
        assert result.expected_files == 2
        assert result.actual_files == 1


class TestExecutePlanCancellation:
    def test_should_cancel_stops_after_first_item(self, tmp_path):
        items = [
            transfer.TransferItem(
                source="/sdcard/a.jpg", dest=str(tmp_path / "a.jpg"), size=100, action=transfer.ACTION_COPY
            ),
            transfer.TransferItem(
                source="/sdcard/b.jpg", dest=str(tmp_path / "b.jpg"), size=100, action=transfer.ACTION_COPY
            ),
            transfer.TransferItem(
                source="/sdcard/c.jpg", dest=str(tmp_path / "c.jpg"), size=100, action=transfer.ACTION_COPY
            ),
        ]
        plan = transfer.TransferPlan(direction="pull", items=items)
        client = MagicMock()

        pulled = []

        def fake_pull(serial, source, dest):
            pulled.append(source)
            with open(dest, "wb") as f:
                f.write(b"x" * 100)

        client.pull.side_effect = fake_pull

        calls = []

        def should_cancel():
            calls.append(True)
            return len(calls) > 1

        progress = transfer.execute_plan(client, "SERIAL", plan, should_cancel=should_cancel)

        assert pulled == ["/sdcard/a.jpg"]
        assert progress.done_files == 1
        assert progress.done_bytes == 100

    def test_should_cancel_none_preserves_existing_behavior(self, tmp_path):
        items = [
            transfer.TransferItem(
                source="/sdcard/a.jpg", dest=str(tmp_path / "a.jpg"), size=100, action=transfer.ACTION_COPY
            ),
        ]
        plan = transfer.TransferPlan(direction="pull", items=items)
        client = MagicMock()

        def fake_pull(serial, source, dest):
            with open(dest, "wb") as f:
                f.write(b"x" * 100)

        client.pull.side_effect = fake_pull

        progress = transfer.execute_plan(client, "SERIAL", plan)

        assert progress.done_files == 1


class TestTransferPlanExtras:
    def test_extra_items_defaults_to_empty(self):
        plan = transfer.TransferPlan(direction="pull", items=[])
        assert plan.extra_items == []
        assert plan.extra_files == 0
        assert plan.extra_bytes == 0

    def test_extra_files_and_bytes_properties(self):
        plan = transfer.TransferPlan(
            direction="pull",
            items=[],
            extra_items=[
                transfer.ExtraItem(path="/tmp/a.jpg", size=100),
                transfer.ExtraItem(path="/tmp/b.jpg", size=200),
            ],
        )
        assert plan.extra_files == 2
        assert plan.extra_bytes == 300


class TestLocalManifest:
    def test_non_existent_dir_returns_empty(self, tmp_path):
        assert transfer._local_manifest(str(tmp_path / "missing")) == {}

    def test_empty_dir_returns_empty(self, tmp_path):
        (tmp_path / "empty").mkdir()
        assert transfer._local_manifest(str(tmp_path / "empty")) == {}

    def test_single_file(self, tmp_path):
        (tmp_path / "photo.jpg").write_bytes(b"x" * 1000)
        assert transfer._local_manifest(str(tmp_path)) == {"photo.jpg": 1000}

    def test_nested_files_use_posix_paths(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.jpg").write_bytes(b"x" * 500)
        assert transfer._local_manifest(str(tmp_path)) == {"sub/a.jpg": 500}


class TestPlanMirrorPull:
    def test_uses_conflict_overwrite(self, monkeypatch, tmp_path):
        captured = []
        original = transfer.plan_pull
        monkeypatch.setattr(
            transfer, "plan_pull",
            lambda client, serial, rp, ld, conflict=None: (
                captured.append(conflict) or original(client, serial, rp, ld, conflict=conflict)
            ),
        )
        # Shell calls: explicit _stat_remote_path → "1000", plan_pull's _stat_remote_path → "1000"
        client = make_client("1000", "1000")  # stat → single file
        transfer.plan_mirror_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path))
        assert captured == [transfer.CONFLICT_OVERWRITE]

    def test_single_file_source_has_no_extra_items(self, tmp_path):
        # Shell calls: explicit _stat_remote_path → "1000", plan_pull's _stat_remote_path → "1000"
        client = make_client("1000", "1000")
        plan = transfer.plan_mirror_pull(client, "SERIAL", "/sdcard/photo.jpg", str(tmp_path))
        assert plan.extra_items == []

    def test_extra_items_are_local_only_files(self, monkeypatch, tmp_path):
        local_camera = tmp_path / "Camera"
        local_camera.mkdir()
        (local_camera / "photo.jpg").write_bytes(b"x" * 1000)
        (local_camera / "extra.jpg").write_bytes(b"x" * 500)

        remote_files = [SearchResult(path="/sdcard/Camera/photo.jpg", size=1000, mtime=None)]
        monkeypatch.setattr(search_module, "search_files", lambda *a, **k: remote_files)
        # shell calls: explicit _stat_remote_path ("DIR"), plan_pull's _stat_remote_path ("DIR"), _remote_dir_exists in _remote_manifest ("DIR")
        client = make_client("DIR\n", "DIR\n", "DIR\n")

        plan = transfer.plan_mirror_pull(client, "SERIAL", "/sdcard/Camera", str(tmp_path))

        extra_paths = [e.path for e in plan.extra_items]
        assert str(local_camera / "extra.jpg") in extra_paths
        assert str(local_camera / "photo.jpg") not in extra_paths

    def test_no_extras_when_local_matches_remote(self, monkeypatch, tmp_path):
        local_camera = tmp_path / "Camera"
        local_camera.mkdir()
        (local_camera / "photo.jpg").write_bytes(b"x" * 1000)

        remote_files = [SearchResult(path="/sdcard/Camera/photo.jpg", size=1000, mtime=None)]
        monkeypatch.setattr(search_module, "search_files", lambda *a, **k: remote_files)
        # Shell calls: explicit _stat_remote_path ("DIR"), plan_pull's _stat_remote_path ("DIR"), _remote_dir_exists in _remote_manifest ("DIR")
        client = make_client("DIR\n", "DIR\n", "DIR\n")

        plan = transfer.plan_mirror_pull(client, "SERIAL", "/sdcard/Camera", str(tmp_path))

        assert plan.extra_items == []

    def test_extra_items_when_remote_dir_empty(self, monkeypatch, tmp_path):
        """When remote dir has zero files, local-only files must still appear in extra_items."""
        local_camera = tmp_path / "Camera"
        local_camera.mkdir()
        (local_camera / "photo.jpg").write_bytes(b"x" * 1000)

        # Remote dir exists but is empty
        # Shell calls:
        #   1. plan_mirror_pull explicit _stat_remote_path → "DIR\n"
        #   2. plan_pull calls _stat_remote_path → "DIR\n"
        #   3. _remote_manifest calls _remote_dir_exists → "DIR\n"
        # search_files returns [] (empty remote dir)
        client = make_client("DIR\n", "DIR\n", "DIR\n")
        monkeypatch.setattr(search_module, "search_files", lambda *a, **k: [])

        plan = transfer.plan_mirror_pull(client, "SERIAL", "/sdcard/Camera", str(tmp_path))

        extra_paths = [e.path for e in plan.extra_items]
        assert str(local_camera / "photo.jpg") in extra_paths


class TestPlanMirrorPush:
    def test_uses_conflict_overwrite(self, monkeypatch, tmp_path):
        local_dir = tmp_path / "Camera"
        local_dir.mkdir()
        (local_dir / "photo.jpg").write_bytes(b"x" * 1000)

        captured = []
        original = transfer.plan_push
        monkeypatch.setattr(
            transfer, "plan_push",
            lambda client, serial, lp, rd, conflict=None: (
                captured.append(conflict) or original(client, serial, lp, rd, conflict=conflict)
            ),
        )
        # shell: _remote_dir_exists for plan_push's _remote_manifest (NO → empty), then for remote_root (NO → empty)
        client = make_client("NO\n", "NO\n")
        transfer.plan_mirror_push(client, "SERIAL", str(local_dir), "/sdcard/Backup")
        assert captured == [transfer.CONFLICT_OVERWRITE]

    def test_single_file_source_has_no_extra_items(self, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)
        client = make_client("NO\n")  # plan_push's _remote_manifest: dir doesn't exist
        plan = transfer.plan_mirror_push(client, "SERIAL", str(local_file), "/sdcard/Download")
        assert plan.extra_items == []

    def test_extra_items_are_remote_only_files(self, monkeypatch, tmp_path):
        local_dir = tmp_path / "Camera"
        local_dir.mkdir()
        (local_dir / "photo.jpg").write_bytes(b"x" * 1000)

        def fake_search_files(client, serial, path):
            if path == "/sdcard/Backup/Camera":
                return [
                    SearchResult(path="/sdcard/Backup/Camera/photo.jpg", size=1000, mtime=None),
                    SearchResult(path="/sdcard/Backup/Camera/extra.jpg", size=500, mtime=None),
                ]
            return []

        # shell: _remote_dir_exists for plan_push (NO), then _remote_dir_exists for remote_root (DIR)
        client = make_client("NO\n", "DIR\n")
        monkeypatch.setattr(search_module, "search_files", fake_search_files)

        plan = transfer.plan_mirror_push(client, "SERIAL", str(local_dir), "/sdcard/Backup")

        extra_paths = [e.path for e in plan.extra_items]
        assert "/sdcard/Backup/Camera/extra.jpg" in extra_paths
        assert "/sdcard/Backup/Camera/photo.jpg" not in extra_paths


class TestExecuteMirror:
    def _make_plan(self, direction="pull", extra_items=None):
        return transfer.TransferPlan(
            direction=direction,
            items=[],
            extra_items=extra_items or [],
        )

    def test_delete_extras_false_does_not_delete(self, tmp_path):
        extra_file = tmp_path / "extra.jpg"
        extra_file.write_bytes(b"x" * 100)
        plan = self._make_plan("pull", [transfer.ExtraItem(path=str(extra_file), size=100)])
        client = MagicMock()

        result = transfer.execute_mirror(client, "SERIAL", plan, delete_extras=False)

        assert extra_file.exists()
        assert result.deleted_files == 0
        assert result.failed_deletions == []

    def test_delete_extras_true_removes_local_file_for_pull(self, tmp_path):
        extra_file = tmp_path / "extra.jpg"
        extra_file.write_bytes(b"x" * 100)
        plan = self._make_plan("pull", [transfer.ExtraItem(path=str(extra_file), size=100)])
        client = MagicMock()

        result = transfer.execute_mirror(client, "SERIAL", plan, delete_extras=True)

        assert not extra_file.exists()
        assert result.deleted_files == 1
        assert result.deleted_bytes == 100
        assert result.failed_deletions == []

    def test_delete_extras_true_shells_rm_for_push(self):
        plan = self._make_plan("push", [transfer.ExtraItem(path="/sdcard/extra.jpg", size=200)])
        client = MagicMock()

        result = transfer.execute_mirror(client, "SERIAL", plan, delete_extras=True)

        client.shell.assert_called_once_with("SERIAL", "rm /sdcard/extra.jpg")
        assert result.deleted_files == 1
        assert result.deleted_bytes == 200

    def test_failed_deletion_collected_not_raised(self, tmp_path):
        missing_file = tmp_path / "gone.jpg"  # doesn't exist — os.remove will raise
        plan = self._make_plan("pull", [transfer.ExtraItem(path=str(missing_file), size=50)])
        client = MagicMock()

        result = transfer.execute_mirror(client, "SERIAL", plan, delete_extras=True)

        assert result.deleted_files == 0
        assert len(result.failed_deletions) == 1
        assert result.failed_deletions[0].item.path == str(missing_file)

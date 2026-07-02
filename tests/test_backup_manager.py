# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.modules.backup_manager - Module 6: Backup Manager."""

import os
from unittest.mock import MagicMock, patch

from droidbridge.modules import backup_manager
from droidbridge.modules.backup_manager import BackupProfile, load_profiles, save_profile, plan_backup
from droidbridge.modules import transfer as transfer_module


def make_client(*shell_outputs):
    client = MagicMock()
    client.shell.side_effect = list(shell_outputs)
    return client


class TestProfileStorage:
    def test_save_and_load_profile(self, tmp_path):
        path = tmp_path / "profiles.json"
        profile = backup_manager.BackupProfile(
            name="whatsapp_full",
            sources=["/sdcard/WhatsApp/Media"],
            dest="/backups/whatsapp",
        )

        backup_manager.save_profile(path, profile)
        profiles = backup_manager.load_profiles(path)

        assert profiles["whatsapp_full"] == profile

    def test_load_profiles_missing_file_returns_empty_dict(self, tmp_path):
        path = tmp_path / "does_not_exist.json"

        assert backup_manager.load_profiles(path) == {}

    def test_get_profile_returns_none_if_missing(self, tmp_path):
        path = tmp_path / "profiles.json"

        assert backup_manager.get_profile(path, "nope") is None

    def test_delete_profile(self, tmp_path):
        path = tmp_path / "profiles.json"
        profile = backup_manager.BackupProfile(name="docs", sources=["/sdcard/Documents"], dest="/backups/docs")
        backup_manager.save_profile(path, profile)

        assert backup_manager.delete_profile(path, "docs") is True
        assert backup_manager.load_profiles(path) == {}

    def test_delete_profile_returns_false_if_missing(self, tmp_path):
        path = tmp_path / "profiles.json"

        assert backup_manager.delete_profile(path, "nope") is False

    def test_save_profile_default_conflict_is_skip(self, tmp_path):
        path = tmp_path / "profiles.json"
        profile = backup_manager.BackupProfile(name="docs", sources=["/sdcard/Documents"], dest="/backups/docs")

        assert profile.conflict == "skip"

    def test_save_overwrites_existing_profile_with_same_name(self, tmp_path):
        path = tmp_path / "profiles.json"
        backup_manager.save_profile(
            path, backup_manager.BackupProfile(name="docs", sources=["/sdcard/A"], dest="/backups/docs")
        )
        backup_manager.save_profile(
            path, backup_manager.BackupProfile(name="docs", sources=["/sdcard/B"], dest="/backups/docs")
        )

        profiles = backup_manager.load_profiles(path)
        assert len(profiles) == 1
        assert profiles["docs"].sources == ["/sdcard/B"]


class TestPlanBackup:
    def test_combines_plans_for_each_source(self, tmp_path):
        client = make_client("1000", "2000")
        profile = backup_manager.BackupProfile(
            name="test",
            sources=["/sdcard/a.jpg", "/sdcard/b.jpg"],
            dest=str(tmp_path),
        )

        plan = backup_manager.plan_backup(client, "SERIAL", profile)

        assert plan.direction == "pull"
        assert [i.source for i in plan.items] == ["/sdcard/a.jpg", "/sdcard/b.jpg"]
        assert plan.total_bytes == 3000

    def test_uses_profile_conflict_mode(self, tmp_path):
        dest = tmp_path / "a.jpg"
        dest.write_bytes(b"x" * 500)
        client = make_client("1000")
        profile = backup_manager.BackupProfile(
            name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path), conflict="overwrite"
        )

        plan = backup_manager.plan_backup(client, "SERIAL", profile)

        assert plan.items[0].action == transfer_module.ACTION_OVERWRITE


class TestMeasureDestination:
    def test_empty_directory_returns_zero(self, tmp_path):
        file_count, total_bytes = backup_manager.measure_destination(str(tmp_path))

        assert file_count == 0
        assert total_bytes == 0

    def test_sums_files_across_nested_directories(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x" * 1000)
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "b.jpg").write_bytes(b"y" * 500)

        file_count, total_bytes = backup_manager.measure_destination(str(tmp_path))

        assert file_count == 2
        assert total_bytes == 1500


class TestHistory:
    def test_append_and_load_history(self, tmp_path):
        path = tmp_path / "history.json"
        record = backup_manager.BackupRecord(
            profile="whatsapp_full",
            timestamp="2026-06-12T10:00:00+00:00",
            file_count=10,
            total_bytes=1000,
            duration_seconds=5.0,
            destination="/backups/wa",
            verified=True,
        )

        backup_manager.append_history(path, record)

        assert backup_manager.load_history(path) == [record]

    def test_load_history_missing_file_returns_empty_list(self, tmp_path):
        path = tmp_path / "does_not_exist.json"

        assert backup_manager.load_history(path) == []

    def test_last_backup_returns_most_recent_for_profile(self, tmp_path):
        path = tmp_path / "history.json"
        older = backup_manager.BackupRecord("p", "2026-06-01T00:00:00+00:00", 1, 100, 1.0, "/dest", True)
        newer = backup_manager.BackupRecord("p", "2026-06-10T00:00:00+00:00", 2, 200, 2.0, "/dest", True)
        other_profile = backup_manager.BackupRecord("other", "2026-06-11T00:00:00+00:00", 3, 300, 3.0, "/dest", True)
        backup_manager.append_history(path, older)
        backup_manager.append_history(path, newer)
        backup_manager.append_history(path, other_profile)

        history = backup_manager.load_history(path)

        assert backup_manager.last_backup(history, "p") == newer

    def test_last_backup_returns_none_if_no_history(self):
        assert backup_manager.last_backup([], "p") is None

    def test_is_outdated_true_if_never_backed_up(self):
        assert backup_manager.is_outdated([], "p", max_age_days=7) is True

    def test_is_outdated_false_if_recent(self):
        from datetime import datetime, timezone

        record = backup_manager.BackupRecord("p", "2026-06-10T00:00:00+00:00", 1, 100, 1.0, "/dest", True)
        now = datetime(2026, 6, 12, tzinfo=timezone.utc)

        assert backup_manager.is_outdated([record], "p", max_age_days=7, now=now) is False

    def test_is_outdated_true_if_old(self):
        from datetime import datetime, timezone

        record = backup_manager.BackupRecord("p", "2026-06-01T00:00:00+00:00", 1, 100, 1.0, "/dest", True)
        now = datetime(2026, 6, 12, tzinfo=timezone.utc)

        assert backup_manager.is_outdated([record], "p", max_age_days=7, now=now) is True

    def test_compare_backups_returns_none_with_fewer_than_two(self):
        record = backup_manager.BackupRecord("p", "2026-06-01T00:00:00+00:00", 1, 100, 1.0, "/dest", True)

        assert backup_manager.compare_backups([record], "p") is None

    def test_compare_backups_returns_deltas(self):
        prev = backup_manager.BackupRecord("p", "2026-06-01T00:00:00+00:00", 10, 1000, 1.0, "/dest", True)
        latest = backup_manager.BackupRecord("p", "2026-06-10T00:00:00+00:00", 15, 1500, 2.0, "/dest", True)

        result = backup_manager.compare_backups([prev, latest], "p")

        assert result["file_count_delta"] == 5
        assert result["total_bytes_delta"] == 500
        assert result["previous"] == prev
        assert result["latest"] == latest


class TestPlanRestore:
    def test_builds_push_plan_for_file_source(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x" * 1000)
        profile = backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path))
        client = make_client("NO")

        targets = backup_manager.plan_restore(client, "SERIAL", profile)

        assert len(targets) == 1
        target = targets[0]
        assert target.source == "/sdcard/a.jpg"
        assert target.remote_dir == "/sdcard"
        assert target.local_path == str(tmp_path / "a.jpg")
        assert target.plan.direction == "push"
        assert target.plan.items[0].dest == "/sdcard/a.jpg"

    def test_builds_push_plan_for_directory_source(self, tmp_path):
        media_dir = tmp_path / "Media"
        media_dir.mkdir()
        (media_dir / "image.jpg").write_bytes(b"x" * 500)
        profile = backup_manager.BackupProfile(name="test", sources=["/sdcard/WhatsApp/Media"], dest=str(tmp_path))
        client = make_client("NO")

        targets = backup_manager.plan_restore(client, "SERIAL", profile)

        assert targets[0].remote_dir == "/sdcard/WhatsApp"
        assert targets[0].local_path == str(media_dir)
        assert targets[0].plan.items[0].dest == "/sdcard/WhatsApp/Media/image.jpg"

    def test_sources_filter_restricts_to_named_sources(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x" * 100)
        (tmp_path / "b.jpg").write_bytes(b"x" * 100)
        profile = backup_manager.BackupProfile(
            name="test", sources=["/sdcard/a.jpg", "/sdcard/b.jpg"], dest=str(tmp_path)
        )
        client = make_client("NO")

        targets = backup_manager.plan_restore(client, "SERIAL", profile, sources=["/sdcard/b.jpg"])

        assert [t.source for t in targets] == ["/sdcard/b.jpg"]

    def test_conflict_override(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x" * 1000)
        profile = backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path))
        client = make_client("DIR", "/sdcard/a.jpg\t500\t1700000000\n")

        targets = backup_manager.plan_restore(client, "SERIAL", profile, conflict="overwrite")

        assert targets[0].plan.items[0].action == transfer_module.ACTION_OVERWRITE


class TestFilterPlanByDate:
    def test_filters_by_after_and_before(self, tmp_path):
        from datetime import date, datetime as dt

        old_file = tmp_path / "old.jpg"
        new_file = tmp_path / "new.jpg"
        old_file.write_bytes(b"x")
        new_file.write_bytes(b"x")
        os.utime(old_file, (dt(2025, 1, 1).timestamp(),) * 2)
        os.utime(new_file, (dt(2026, 6, 1).timestamp(),) * 2)

        item_old = transfer_module.TransferItem(
            source=str(old_file), dest="/sdcard/old.jpg", size=1, action=transfer_module.ACTION_COPY
        )
        item_new = transfer_module.TransferItem(
            source=str(new_file), dest="/sdcard/new.jpg", size=1, action=transfer_module.ACTION_COPY
        )
        plan = transfer_module.TransferPlan(direction="push", items=[item_old, item_new])

        after_only = backup_manager.filter_plan_by_date(plan, after=date(2026, 1, 1))
        assert [i.source for i in after_only.items] == [str(new_file)]

        before_only = backup_manager.filter_plan_by_date(plan, before=date(2025, 12, 31))
        assert [i.source for i in before_only.items] == [str(old_file)]

    def test_no_filters_returns_all_items(self, tmp_path):
        f = tmp_path / "a.jpg"
        f.write_bytes(b"x")
        item = transfer_module.TransferItem(source=str(f), dest="/sdcard/a.jpg", size=1, action=transfer_module.ACTION_COPY)
        plan = transfer_module.TransferPlan(direction="push", items=[item])

        result = backup_manager.filter_plan_by_date(plan)

        assert result.items == [item]


class TestFindFailedPullItems:
    def test_returns_items_missing_or_wrong_size_locally(self, tmp_path):
        ok_dest = tmp_path / "a.jpg"
        ok_dest.write_bytes(b"data")
        item_ok = transfer_module.TransferItem(
            source="/sdcard/a.jpg", dest=str(ok_dest), size=4, action=transfer_module.ACTION_COPY
        )
        item_missing = transfer_module.TransferItem(
            source="/sdcard/b.jpg", dest=str(tmp_path / "b.jpg"), size=4, action=transfer_module.ACTION_COPY
        )
        plan = transfer_module.TransferPlan(direction="pull", items=[item_ok, item_missing])

        failed = backup_manager.find_failed_pull_items(plan)

        assert failed == [item_missing]

    def test_excludes_conflict_skipped_items(self, tmp_path):
        item_skipped = transfer_module.TransferItem(
            source="/sdcard/c.jpg",
            dest=str(tmp_path / "c.jpg"),
            size=4,
            action=transfer_module.ACTION_SKIP_CONFLICT,
        )
        plan = transfer_module.TransferPlan(direction="pull", items=[item_skipped])

        assert backup_manager.find_failed_pull_items(plan) == []


class TestBackupProfileExcludes:
    def test_profile_stores_excludes(self):
        profile = BackupProfile(
            name="test",
            sources=["/sdcard/DCIM"],
            dest="/tmp/backup",
            excludes=["/sdcard/DCIM/thumbnails"],
        )
        assert profile.excludes == ["/sdcard/DCIM/thumbnails"]

    def test_profile_excludes_defaults_to_empty(self):
        profile = BackupProfile(name="test", sources=["/sdcard/DCIM"], dest="/tmp/backup")
        assert profile.excludes == []

    def test_load_profile_without_excludes_key(self, tmp_path):
        """Old profile files without 'excludes' key load without error."""
        profiles_path = tmp_path / "profiles.json"
        profiles_path.write_text(
            '{"test": {"name": "test", "sources": ["/sdcard/DCIM"], "dest": "/tmp/b", "conflict": "skip"}}',
            encoding="utf-8",
        )
        profiles = load_profiles(profiles_path)
        assert "test" in profiles
        assert profiles["test"].excludes == []

    def test_save_and_load_profile_with_excludes(self, tmp_path):
        profiles_path = tmp_path / "profiles.json"
        profile = BackupProfile(
            name="test",
            sources=["/sdcard/DCIM"],
            dest="/tmp/backup",
            excludes=["/sdcard/DCIM/thumbnails"],
        )
        save_profile(profiles_path, profile)
        loaded = load_profiles(profiles_path)
        assert loaded["test"].excludes == ["/sdcard/DCIM/thumbnails"]


class TestPlanBackupExcludes:
    def test_plan_backup_excludes_paths(self):
        """Items whose source starts with an excluded path are dropped from the plan."""
        from droidbridge.modules.transfer import TransferPlan, TransferItem, ACTION_COPY

        thumb_item = TransferItem(
            source="/sdcard/DCIM/thumbnails/thumb.jpg",
            dest="/tmp/backup/thumbnails/thumb.jpg",
            size=512,
            action=ACTION_COPY,
        )
        regular_item = TransferItem(
            source="/sdcard/DCIM/photo.jpg",
            dest="/tmp/backup/photo.jpg",
            size=2048,
            action=ACTION_COPY,
        )
        fake_plan = TransferPlan(direction="pull", items=[thumb_item, regular_item])

        profile = BackupProfile(
            name="test",
            sources=["/sdcard/DCIM"],
            dest="/tmp/backup",
            excludes=["/sdcard/DCIM/thumbnails"],
        )

        with patch("droidbridge.modules.backup_manager.transfer_module.plan_pull", return_value=fake_plan):
            result = plan_backup(MagicMock(), "SERIAL", profile)

        assert len(result.items) == 1
        assert result.items[0].source == "/sdcard/DCIM/photo.jpg"

    def test_plan_backup_no_excludes_includes_all(self):
        """With empty excludes, all items pass through."""
        from droidbridge.modules.transfer import TransferPlan, TransferItem, ACTION_COPY

        items = [
            TransferItem(source="/sdcard/DCIM/a.jpg", dest="/tmp/a.jpg", size=1, action=ACTION_COPY),
            TransferItem(source="/sdcard/DCIM/b.jpg", dest="/tmp/b.jpg", size=1, action=ACTION_COPY),
        ]
        fake_plan = TransferPlan(direction="pull", items=items)
        profile = BackupProfile(name="test", sources=["/sdcard/DCIM"], dest="/tmp/backup")

        with patch("droidbridge.modules.backup_manager.transfer_module.plan_pull", return_value=fake_plan):
            result = plan_backup(MagicMock(), "SERIAL", profile)

        assert len(result.items) == 2

    def test_plan_backup_exclude_trailing_slash_normalized(self):
        """Excludes with trailing slash still match correctly."""
        from droidbridge.modules.transfer import TransferPlan, TransferItem, ACTION_COPY

        thumb_item = TransferItem(
            source="/sdcard/DCIM/thumbnails/t.jpg",
            dest="/tmp/t.jpg",
            size=1,
            action=ACTION_COPY,
        )
        fake_plan = TransferPlan(direction="pull", items=[thumb_item])
        profile = BackupProfile(
            name="test",
            sources=["/sdcard/DCIM"],
            dest="/tmp/backup",
            excludes=["/sdcard/DCIM/thumbnails/"],  # trailing slash
        )

        with patch("droidbridge.modules.backup_manager.transfer_module.plan_pull", return_value=fake_plan):
            result = plan_backup(MagicMock(), "SERIAL", profile)

        assert len(result.items) == 0

    def test_plan_backup_exclude_does_not_match_path_prefix(self):
        """Exclude '/sdcard/DCIM/thumb' must NOT exclude '/sdcard/DCIM/thumbnails/...'."""
        from droidbridge.modules.transfer import TransferPlan, TransferItem, ACTION_COPY

        thumbnails_item = TransferItem(
            source="/sdcard/DCIM/thumbnails/t.jpg",
            dest="/tmp/t.jpg",
            size=1,
            action=ACTION_COPY,
        )
        thumb_item = TransferItem(
            source="/sdcard/DCIM/thumb.jpg",
            dest="/tmp/thumb.jpg",
            size=1,
            action=ACTION_COPY,
        )
        fake_plan = TransferPlan(direction="pull", items=[thumbnails_item, thumb_item])
        profile = BackupProfile(
            name="test",
            sources=["/sdcard/DCIM"],
            dest="/tmp/backup",
            excludes=["/sdcard/DCIM/thumb.jpg"],  # exact file, not a prefix
        )

        with patch("droidbridge.modules.backup_manager.transfer_module.plan_pull", return_value=fake_plan):
            result = plan_backup(MagicMock(), "SERIAL", profile)

        # Only the exact file should be excluded, not the thumbnails/ directory
        assert len(result.items) == 1
        assert result.items[0].source == "/sdcard/DCIM/thumbnails/t.jpg"

    def test_plan_backup_exclude_directory_does_not_match_longer_sibling(self):
        """Exclude '/sdcard/DCIM/thumb' (bare dir) must NOT exclude '/sdcard/DCIM/thumbnails/...'."""
        from droidbridge.modules.transfer import TransferPlan, TransferItem, ACTION_COPY

        thumbnails_item = TransferItem(
            source="/sdcard/DCIM/thumbnails/img.jpg",
            dest="/tmp/thumbnails/img.jpg",
            size=1,
            action=ACTION_COPY,
        )
        thumb_dir_item = TransferItem(
            source="/sdcard/DCIM/thumb/t.jpg",
            dest="/tmp/thumb/t.jpg",
            size=1,
            action=ACTION_COPY,
        )
        fake_plan = TransferPlan(direction="pull", items=[thumbnails_item, thumb_dir_item])
        profile = BackupProfile(
            name="test",
            sources=["/sdcard/DCIM"],
            dest="/tmp/backup",
            excludes=["/sdcard/DCIM/thumb"],  # bare directory name — must NOT match thumbnails/
        )

        with patch("droidbridge.modules.backup_manager.transfer_module.plan_pull", return_value=fake_plan):
            result = plan_backup(MagicMock(), "SERIAL", profile)

        # Only items under /sdcard/DCIM/thumb/ should be excluded
        assert len(result.items) == 1
        assert result.items[0].source == "/sdcard/DCIM/thumbnails/img.jpg"

    def test_plan_backup_exclude_slash_root_does_not_exclude_everything(self):
        """Exclude '/' must not silently wipe the entire backup."""
        from droidbridge.modules.transfer import TransferPlan, TransferItem, ACTION_COPY

        item = TransferItem(
            source="/sdcard/DCIM/photo.jpg",
            dest="/tmp/photo.jpg",
            size=1,
            action=ACTION_COPY,
        )
        fake_plan = TransferPlan(direction="pull", items=[item])
        profile = BackupProfile(
            name="test",
            sources=["/sdcard/DCIM"],
            dest="/tmp/backup",
            excludes=["/"],  # slash root — must be ignored
        )

        with patch("droidbridge.modules.backup_manager.transfer_module.plan_pull", return_value=fake_plan):
            result = plan_backup(MagicMock(), "SERIAL", profile)

        assert len(result.items) == 1

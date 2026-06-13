"""Tests for droidbridge.gui.transfer_ops (Phase 6.2) — plain functions, no Qt."""

from unittest.mock import MagicMock

from droidbridge.gui import transfer_ops
from droidbridge.modules import transfer as transfer_module


def make_item(source, dest, size, action=transfer_module.ACTION_COPY):
    return transfer_module.TransferItem(source=source, dest=dest, size=size, action=action)


class TestPlanPullMany:
    def test_builds_one_plan_per_path(self, monkeypatch):
        client = MagicMock()
        calls = []

        def fake_plan_pull(client_, serial, remote_path, local_dir, conflict):
            calls.append((remote_path, local_dir, conflict))
            return transfer_module.TransferPlan(direction="pull", items=[])

        monkeypatch.setattr(transfer_module, "plan_pull", fake_plan_pull)

        plans = transfer_ops.plan_pull_many(client, "SERIAL", ["/sdcard/a.jpg", "/sdcard/b.jpg"], "/tmp/out")

        assert len(plans) == 2
        assert calls == [
            ("/sdcard/a.jpg", "/tmp/out", transfer_module.CONFLICT_SKIP),
            ("/sdcard/b.jpg", "/tmp/out", transfer_module.CONFLICT_SKIP),
        ]


class TestPlanPushMany:
    def test_builds_one_plan_per_path(self, monkeypatch):
        client = MagicMock()
        calls = []

        def fake_plan_push(client_, serial, local_path, remote_dir, conflict):
            calls.append((local_path, remote_dir, conflict))
            return transfer_module.TransferPlan(direction="push", items=[])

        monkeypatch.setattr(transfer_module, "plan_push", fake_plan_push)

        plans = transfer_ops.plan_push_many(
            client, "SERIAL", ["/tmp/a.jpg", "/tmp/b.jpg"], "/sdcard/Pictures",
            conflict=transfer_module.CONFLICT_OVERWRITE,
        )

        assert len(plans) == 2
        assert calls == [
            ("/tmp/a.jpg", "/sdcard/Pictures", transfer_module.CONFLICT_OVERWRITE),
            ("/tmp/b.jpg", "/sdcard/Pictures", transfer_module.CONFLICT_OVERWRITE),
        ]


class TestExecutePlans:
    def test_reports_combined_progress_across_plans(self, tmp_path):
        plan1 = transfer_module.TransferPlan(
            direction="pull", items=[make_item("/sdcard/a.jpg", str(tmp_path / "a.jpg"), 100)]
        )
        plan2 = transfer_module.TransferPlan(
            direction="pull", items=[make_item("/sdcard/b.jpg", str(tmp_path / "b.jpg"), 200)]
        )
        client = MagicMock()

        def fake_pull(serial, remote, local):
            size = 100 if "a.jpg" in remote else 200
            with open(local, "wb") as f:
                f.write(b"x" * size)

        client.pull.side_effect = fake_pull

        progress_events = []
        result = transfer_ops.execute_plans(
            client, "SERIAL", [plan1, plan2], progress_callback=progress_events.append
        )

        assert result.total_files == 2
        assert result.total_bytes == 300
        assert result.done_files == 2
        assert result.done_bytes == 300
        assert [p.done_files for p in progress_events] == [1, 2]
        assert [p.done_bytes for p in progress_events] == [100, 300]

    def test_should_cancel_stops_between_plans(self, tmp_path):
        plan1 = transfer_module.TransferPlan(
            direction="pull", items=[make_item("/sdcard/a.jpg", str(tmp_path / "a.jpg"), 100)]
        )
        plan2 = transfer_module.TransferPlan(
            direction="pull", items=[make_item("/sdcard/b.jpg", str(tmp_path / "b.jpg"), 200)]
        )
        client = MagicMock()

        def fake_pull(serial, remote, local):
            with open(local, "wb") as f:
                f.write(b"x" * 100)

        client.pull.side_effect = fake_pull

        calls = []

        def should_cancel():
            calls.append(True)
            return len(calls) > 2

        result = transfer_ops.execute_plans(client, "SERIAL", [plan1, plan2], should_cancel=should_cancel)

        assert result.done_files == 1
        assert result.done_bytes == 100
        assert client.pull.call_count == 1


class TestVerifyPlans:
    def test_pull_sums_results_across_plans(self, tmp_path):
        dest1 = tmp_path / "a.jpg"
        dest1.write_bytes(b"x" * 100)
        dest2 = tmp_path / "b.jpg"
        dest2.write_bytes(b"x" * 200)

        plan1 = transfer_module.TransferPlan(direction="pull", items=[make_item("/sdcard/a.jpg", str(dest1), 100)])
        plan2 = transfer_module.TransferPlan(direction="pull", items=[make_item("/sdcard/b.jpg", str(dest2), 200)])
        client = MagicMock()

        result = transfer_ops.verify_plans(client, "SERIAL", [plan1, plan2], direction="pull")

        assert result.ok is True
        assert result.expected_files == 2
        assert result.actual_files == 2
        assert result.expected_bytes == 300
        assert result.actual_bytes == 300

    def test_push_sums_results_across_plans(self, monkeypatch):
        plan1 = transfer_module.TransferPlan(
            direction="push", items=[make_item("/tmp/a.jpg", "/sdcard/Pictures/a.jpg", 100)]
        )
        plan2 = transfer_module.TransferPlan(
            direction="push", items=[make_item("/tmp/b.jpg", "/sdcard/Pictures/b.jpg", 200)]
        )
        client = MagicMock()

        def fake_verify_push(client_, serial, plan, remote_dir):
            relevant = [i for i in plan.items if i.action != transfer_module.ACTION_SKIP_CONFLICT]
            total = sum(i.size for i in relevant)
            return transfer_module.VerificationResult(
                expected_files=len(relevant), expected_bytes=total,
                actual_files=len(relevant), actual_bytes=total,
            )

        monkeypatch.setattr(transfer_module, "verify_push", fake_verify_push)

        result = transfer_ops.verify_plans(
            client, "SERIAL", [plan1, plan2], direction="push", remote_dir="/sdcard/Pictures"
        )

        assert result.ok is True
        assert result.expected_files == 2
        assert result.expected_bytes == 300

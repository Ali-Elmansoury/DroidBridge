# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for `droidbridge transfer pull/push` (Module 3 CLI)."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]

DIR_FIND_OUTPUT = (
    "/sdcard/Camera/photo1.jpg\t1000\t1700000000.0\n"
    "/sdcard/Camera/photo2.jpg\t2000\t1700000100.0\n"
)


@contextmanager
def _noop_inhibitor(*args, **kwargs):
    yield


def make_fake_client(devices, shell_side_effect=None):
    client = MagicMock()
    client.devices.return_value = devices
    if shell_side_effect is not None:
        client.shell.side_effect = shell_side_effect
    return client


class TestTransferPull:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_pulls_single_file_and_verifies(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])

        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pulling 1 file" in result.output
        assert "Verified: 1 file" in result.output
        assert (tmp_path / "photo.jpg").read_bytes() == b"x" * 1000

    def test_pulls_directory_and_verifies(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["DIR\n", DIR_FIND_OUTPUT])

        def fake_pull(serial, remote, local):
            size = 1000 if remote.endswith("photo1.jpg") else 2000
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * size)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/Camera", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pulling 2 files" in result.output
        assert "Verified: 2 file" in result.output
        assert (tmp_path / "Camera" / "photo1.jpg").exists()
        assert (tmp_path / "Camera" / "photo2.jpg").exists()

    def test_already_present_files_are_skipped(self, monkeypatch, tmp_path):
        (tmp_path / "photo.jpg").write_bytes(b"x" * 1000)
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 0
        assert "Skipping 1 file" in result.output
        assert "Nothing to transfer." in result.output
        client.pull.assert_not_called()

    def test_verification_failure_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        # client.pull does nothing, so the destination file never appears.
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 1
        assert "Verification FAILED" in result.output

    def test_no_verify_flag_skips_verification(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(
            main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path), "--no-verify"]
        )

        assert result.exit_code == 0
        assert "Verified" not in result.output
        assert "Verification" not in result.output

    def test_failed_items_printed_and_exits_1(self, monkeypatch, tmp_path):
        from droidbridge.core.adb import AdbError
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        client.pull.side_effect = AdbError("timeout")
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(
            main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path), "--retry", "0"]
        )

        assert result.exit_code == 1
        assert "file(s) failed" in result.output

    def test_transfer_report_written(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        def fake_pull(serial, remote, local):
            from pathlib import Path
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)
        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        reports = list((tmp_path / "session_logs" / "reports").glob("transfer-pull_*.txt"))
        assert len(reports) == 1


class TestTransferPush:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_local_path_must_exist(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        missing = tmp_path / "does-not-exist.pdf"
        result = CliRunner().invoke(main.cli, ["transfer", "push", str(missing), "/sdcard/Download"])

        assert result.exit_code == 2

    def test_pushes_single_file_and_verifies(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_after_push = "/sdcard/Download/report.pdf\t100\t1700000000.0\n"
        client = make_fake_client(
            READY_DEVICE,
            shell_side_effect=["NO\n", "", "DIR\n", existing_after_push],
        )
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 0
        assert "Pushing 1 file" in result.output
        assert "Verified: 1 file" in result.output
        client.push.assert_called_once_with("SERIAL123", str(local_file), "/sdcard/Download/report.pdf")

    def test_already_present_files_are_skipped(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_output = "/sdcard/Download/report.pdf\t100\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_side_effect=["DIR\n", existing_output])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 0
        assert "Skipping 1 file" in result.output
        assert "Nothing to transfer." in result.output
        client.push.assert_not_called()

    def test_conflict_skip_message(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_output = "/sdcard/Download/report.pdf\t50\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_side_effect=["DIR\n", existing_output])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 0
        assert "conflict" in result.output.lower()
        assert "Nothing to transfer." in result.output

    def test_failed_items_printed_and_exits_1(self, monkeypatch, tmp_path):
        from droidbridge.core.adb import AdbError
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)
        client = make_fake_client(READY_DEVICE, shell_side_effect=["NO\n", ""])
        client.push.side_effect = AdbError("timeout")
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(
            main.cli,
            ["transfer", "push", str(local_file), "/sdcard/Download", "--retry", "0"],
        )

        assert result.exit_code == 1
        assert "file(s) failed" in result.output

    def test_transfer_report_written(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)
        existing_after = "/sdcard/Download/report.pdf\t100\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_side_effect=["NO\n", "", "DIR\n", existing_after])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        reports = list((tmp_path / "session_logs" / "reports").glob("transfer-push_*.txt"))
        assert len(reports) == 1


class TestTransferMirrorPull:
    def test_mirror_pull_happy_path(self, monkeypatch, tmp_path):
        from droidbridge.modules import transfer as transfer_module

        client = make_fake_client(READY_DEVICE)
        local_camera = tmp_path / "Camera"

        def fake_plan_mirror_pull(client_, serial, remote_path, local_dir):
            local_camera.mkdir(exist_ok=True)
            (local_camera / "photo.jpg").write_bytes(b"x" * 1000)
            return transfer_module.TransferPlan(
                direction="pull",
                items=[transfer_module.TransferItem(
                    source="/sdcard/Camera/photo.jpg",
                    dest=str(local_camera / "photo.jpg"),
                    size=1000, action=transfer_module.ACTION_COPY,
                )],
            )

        def fake_execute_mirror(client_, serial, plan, **kwargs):
            return transfer_module.MirrorResult(
                progress=transfer_module.TransferProgress(1, 1000, 1, 1000),
            )

        def fake_verify_pull(plan):
            return transfer_module.VerificationResult(1, 1000, 1, 1000)

        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.setattr(transfer_module, "plan_mirror_pull", fake_plan_mirror_pull)
        monkeypatch.setattr(transfer_module, "execute_mirror", fake_execute_mirror)
        monkeypatch.setattr(transfer_module, "verify_pull", fake_verify_pull)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(
            main.cli, ["transfer", "mirror", "pull", "/sdcard/Camera", str(tmp_path)]
        )

        assert result.exit_code == 0
        assert "Verified" in result.output
        reports = list((tmp_path / "session_logs" / "reports").glob("transfer-mirror-pull_*.txt"))
        assert len(reports) == 1

    def test_delete_extras_confirmed(self, monkeypatch, tmp_path):
        from droidbridge.modules import transfer as transfer_module

        extra_file = tmp_path / "extra.jpg"
        extra_file.write_bytes(b"x" * 100)

        client = make_fake_client(READY_DEVICE)

        def fake_plan_mirror_pull(client_, serial, remote_path, local_dir):
            return transfer_module.TransferPlan(
                direction="pull",
                items=[],
                extra_items=[transfer_module.ExtraItem(path=str(extra_file), size=100)],
            )

        captured_delete_extras = []

        def fake_execute_mirror(client_, serial, plan, delete_extras=False, **kwargs):
            captured_delete_extras.append(delete_extras)
            return transfer_module.MirrorResult(
                progress=transfer_module.TransferProgress(0, 0),
                deleted_files=1 if delete_extras else 0,
                deleted_bytes=100 if delete_extras else 0,
            )

        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.setattr(transfer_module, "plan_mirror_pull", fake_plan_mirror_pull)
        monkeypatch.setattr(transfer_module, "execute_mirror", fake_execute_mirror)
        monkeypatch.setattr(transfer_module, "verify_pull", lambda p: transfer_module.VerificationResult(0, 0, 0, 0))
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(
            main.cli,
            ["transfer", "mirror", "pull", "/sdcard/Camera", str(tmp_path), "--delete-extras", "--yes"],
        )

        assert result.exit_code == 0
        assert captured_delete_extras == [True]

    def test_no_delete_extras_by_default(self, monkeypatch, tmp_path):
        from droidbridge.modules import transfer as transfer_module

        extra_file = tmp_path / "extra.jpg"
        extra_file.write_bytes(b"x" * 100)
        client = make_fake_client(READY_DEVICE)

        def fake_plan_mirror_pull(client_, serial, remote_path, local_dir):
            return transfer_module.TransferPlan(
                direction="pull",
                items=[],
                extra_items=[transfer_module.ExtraItem(path=str(extra_file), size=100)],
            )

        captured_delete_extras = []

        def fake_execute_mirror(client_, serial, plan, delete_extras=False, **kwargs):
            captured_delete_extras.append(delete_extras)
            return transfer_module.MirrorResult(progress=transfer_module.TransferProgress(0, 0))

        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.setattr(transfer_module, "plan_mirror_pull", fake_plan_mirror_pull)
        monkeypatch.setattr(transfer_module, "execute_mirror", fake_execute_mirror)
        monkeypatch.setattr(transfer_module, "verify_pull", lambda p: transfer_module.VerificationResult(0, 0, 0, 0))
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(
            main.cli, ["transfer", "mirror", "pull", "/sdcard/Camera", str(tmp_path)]
        )

        assert result.exit_code == 0
        assert captured_delete_extras == [False]
        assert "use --delete-extras" in result.output


class TestTransferMirrorPush:
    def test_mirror_push_happy_path(self, monkeypatch, tmp_path):
        from droidbridge.modules import transfer as transfer_module

        local_dir = tmp_path / "Camera"
        local_dir.mkdir()
        (local_dir / "photo.jpg").write_bytes(b"x" * 1000)
        client = make_fake_client(READY_DEVICE)

        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.setattr(
            transfer_module, "plan_mirror_push",
            lambda *a, **k: transfer_module.TransferPlan(direction="push", items=[]),
        )
        monkeypatch.setattr(
            transfer_module, "execute_mirror",
            lambda *a, **k: transfer_module.MirrorResult(progress=transfer_module.TransferProgress(0, 0)),
        )
        monkeypatch.setattr(
            transfer_module, "verify_push",
            lambda *a, **k: transfer_module.VerificationResult(0, 0, 0, 0),
        )
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(
            main.cli, ["transfer", "mirror", "push", str(local_dir), "/sdcard/Backup"]
        )

        assert result.exit_code == 0
        reports = list((tmp_path / "session_logs" / "reports").glob("transfer-mirror-push_*.txt"))
        assert len(reports) == 1

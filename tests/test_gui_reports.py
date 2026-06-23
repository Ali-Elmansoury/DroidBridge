from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.reports import ReportsViewModel
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _disconnected_ctx():
    return DeviceContext()


class TestReportsViewModelGenerate:
    def test_generate_emits_report_generated_with_format(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.reports.reports_ops.generate_report",
            lambda *a, **kw: {"content": "hello", "default_filename": "storage_20260101_000000.txt"},
        )
        results = []
        vm.reportGenerated.connect(results.append)

        vm.generate("storage", "txt")

        assert results == [{"content": "hello", "default_filename": "storage_20260101_000000.txt", "format": "txt"}]

    def test_generate_passes_client_serial_for_device_needing_type(self, qtbot, monkeypatch):
        ctx = _connected_ctx()
        vm = ReportsViewModel(ctx, worker_factory=FakeWorker)
        captured = {}

        def fake_generate_report(client, serial, report_type, report_format, **params):
            captured["client"] = client
            captured["serial"] = serial
            return {"content": "x", "default_filename": "f.txt"}

        monkeypatch.setattr("droidbridge.gui.viewmodels.reports.reports_ops.generate_report", fake_generate_report)

        vm.generate("storage", "txt")

        assert captured["client"] is ctx.client
        assert captured["serial"] == "S1"

    def test_generate_passes_none_client_serial_for_local_only_type_even_when_disconnected(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_disconnected_ctx(), worker_factory=FakeWorker)
        captured = {}

        def fake_generate_report(client, serial, report_type, report_format, **params):
            captured["client"] = client
            captured["serial"] = serial
            return {"content": "x", "default_filename": "f.txt"}

        monkeypatch.setattr("droidbridge.gui.viewmodels.reports.reports_ops.generate_report", fake_generate_report)

        vm.generate("storage-trend", "txt")

        assert captured["client"] is None
        assert captured["serial"] is None

    def test_generate_passes_extra_params_through(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx(), worker_factory=FakeWorker)
        captured = {}

        def fake_generate_report(client, serial, report_type, report_format, **params):
            captured["params"] = params
            return {"content": "x", "default_filename": "f.txt"}

        monkeypatch.setattr("droidbridge.gui.viewmodels.reports.reports_ops.generate_report", fake_generate_report)

        vm.generate("top-apps", "txt", top_n=5)

        assert captured["params"] == {"top_n": 5}

    def test_generate_emits_busy_changed(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.reports.reports_ops.generate_report",
            lambda *a, **kw: {"content": "x", "default_filename": "f.txt"},
        )
        busy = []
        vm.busyChanged.connect(busy.append)

        vm.generate("storage", "txt")

        assert busy == [True, False]

    def test_generate_error_emits_status_and_log_message(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx(), worker_factory=FakeWorker)

        def boom(*a, **kw):
            raise ValueError("no history")

        monkeypatch.setattr("droidbridge.gui.viewmodels.reports.reports_ops.generate_report", boom)
        statuses = []
        logs = []
        vm.statusChanged.connect(statuses.append)
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))

        vm.generate("storage-trend", "txt")

        assert statuses == ["no history"]
        assert logs == [("no history", "ERROR")]


class TestReportsViewModelSave:
    def test_save_writes_and_emits_status(self, qtbot, tmp_path, monkeypatch):
        vm = ReportsViewModel(_connected_ctx())
        calls = []
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.reports.reports_ops.save_report",
            lambda content, path: calls.append((content, path)),
        )
        statuses = []
        vm.statusChanged.connect(statuses.append)

        out = str(tmp_path / "report.txt")
        vm.save("hello", out)

        assert calls == [("hello", out)]
        assert statuses == [f"Saved to {out}"]

    def test_save_error_emits_log_message(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx())

        def boom(content, path):
            raise PermissionError("denied")

        monkeypatch.setattr("droidbridge.gui.viewmodels.reports.reports_ops.save_report", boom)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))

        vm.save("hello", "/no/such/dir/report.txt")

        assert logs == [("denied", "ERROR")]

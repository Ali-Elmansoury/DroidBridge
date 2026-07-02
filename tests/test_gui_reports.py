# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from unittest.mock import MagicMock

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QFileDialog

from droidbridge.gui import reports_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.reports import ReportsPage
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


class TestReportsPageSkeleton:
    def test_type_combo_has_thirteen_items_matching_labels(self, qtbot):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)

        assert panel.type_combo.count() == 13
        assert panel.type_combo.itemText(0) == reports_ops.REPORT_TYPES[0]["label"]
        assert panel.type_combo.itemText(1) == reports_ops.REPORT_TYPES[1]["label"]

    def test_format_combo_has_four_items(self, qtbot):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)

        assert panel.format_combo.count() == 4

    def test_save_button_disabled_until_report_generated(self, qtbot):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)

        assert not panel.save_button.isEnabled()

    def test_generate_button_calls_viewmodel_with_selected_type_and_format(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)
        panel.type_combo.setCurrentIndex(1)  # "storage", the first type with empty params
        panel.format_combo.setCurrentIndex(2)  # "csv"
        calls = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: calls.append((a, kw)))

        qtbot.mouseClick(panel.generate_button, Qt.MouseButton.LeftButton)

        assert calls == [(("storage", "csv"), {})]

    def test_busy_shows_hides_progress_bar_and_disables_generate(self, qtbot):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)
        panel.show()

        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        assert not panel.generate_button.isEnabled()

        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
        assert panel.generate_button.isEnabled()

    def test_report_generated_with_txt_format_sets_plain_text_and_enables_save(self, qtbot):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)

        panel.viewmodel.reportGenerated.emit({"content": "hello", "default_filename": "f.txt", "format": "txt"})

        assert panel.preview_text.toPlainText() == "hello"
        assert panel.save_button.isEnabled()

    def test_report_generated_with_html_format_calls_set_html(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.preview_text, "setHtml", lambda html: calls.append(html))

        panel.viewmodel.reportGenerated.emit({"content": "<p>hi</p>", "default_filename": "f.html", "format": "html"})

        assert calls == ["<p>hi</p>"]

    def test_save_button_does_nothing_before_any_report_generated(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)
        panel.save_button.setEnabled(True)  # force-enable to exercise the guard directly
        calls = []
        monkeypatch.setattr(panel.viewmodel, "save", lambda *a, **kw: calls.append((a, kw)))

        panel._on_save()

        assert calls == []

    def test_save_button_opens_dialog_and_calls_viewmodel_save(self, qtbot, monkeypatch, tmp_path):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)
        panel.viewmodel.reportGenerated.emit({"content": "hello", "default_filename": "f.txt", "format": "txt"})

        chosen_path = str(tmp_path / "f.txt")
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (chosen_path, ""))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "save", lambda content, path: calls.append((content, path)))

        qtbot.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)

        assert calls == [("hello", chosen_path)]

    def test_save_button_does_nothing_when_dialog_cancelled(self, qtbot, monkeypatch):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)
        panel.viewmodel.reportGenerated.emit({"content": "hello", "default_filename": "f.txt", "format": "txt"})

        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: ("", ""))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "save", lambda *a, **kw: calls.append((a, kw)))

        qtbot.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)

        assert calls == []

    def test_status_changed_updates_status_label(self, qtbot):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)

        panel.viewmodel.statusChanged.emit("Generated txt report.")

        assert panel.status_label.text() == "Generated txt report."

    def test_all_interactive_widgets_have_tooltips(self, qtbot):
        vm = ReportsViewModel(_connected_ctx())
        panel = ReportsPage(vm)
        qtbot.addWidget(panel)

        for widget in (panel.type_combo, panel.format_combo, panel.generate_button, panel.save_button):
            assert widget.toolTip() != ""


class TestReportsPageDynamicParams:
    def _select_type(self, panel, type_id):
        index = [t["id"] for t in reports_ops.REPORT_TYPES].index(type_id)
        panel.type_combo.setCurrentIndex(index)

    def test_storage_type_hides_all_param_widgets(self, qtbot):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "storage")

        assert not panel.top_spin.isVisible()
        assert not panel.min_size_edit.isVisible()
        assert not panel.cutoff_date_edit.isVisible()
        assert not panel.app_combo.isVisible()
        assert not panel.profile_combo.isVisible()

    def test_full_type_shows_top_n_and_app_only(self, qtbot):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        panel.show()
        self._select_type(panel, "full")

        assert panel.top_spin.isVisible()
        assert panel.app_combo.isVisible()
        assert not panel.min_size_edit.isVisible()
        assert not panel.cutoff_date_edit.isVisible()
        assert not panel.profile_combo.isVisible()

    def test_large_files_type_shows_min_size_only(self, qtbot):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        panel.show()
        self._select_type(panel, "large-files")

        assert panel.min_size_edit.isVisible()
        assert not panel.top_spin.isVisible()
        assert not panel.app_combo.isVisible()

    def test_whatsapp_cutoff_type_shows_cutoff_and_app(self, qtbot):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        panel.show()
        self._select_type(panel, "whatsapp-cutoff")

        assert panel.cutoff_date_edit.isVisible()
        assert panel.app_combo.isVisible()
        assert not panel.top_spin.isVisible()

    def test_app_combo_has_three_items(self, qtbot):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)

        assert panel.app_combo.count() == 3
        assert panel.app_combo.itemText(0) == "WhatsApp"
        assert panel.app_combo.itemText(2) == "Both"

    def test_backup_history_profile_combo_includes_sentinel(self, qtbot, monkeypatch):
        monkeypatch.setattr(reports_ops, "list_profile_names", lambda: ["nightly"])
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        panel.show()
        self._select_type(panel, "backup-history")

        assert panel.profile_combo.isVisible()
        items = [panel.profile_combo.itemText(i) for i in range(panel.profile_combo.count())]
        assert items == ["(all profiles)", "nightly"]

    def test_backup_summary_profile_combo_omits_sentinel(self, qtbot, monkeypatch):
        monkeypatch.setattr(reports_ops, "list_profile_names", lambda: ["nightly"])
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "backup-summary")

        items = [panel.profile_combo.itemText(i) for i in range(panel.profile_combo.count())]
        assert items == ["nightly"]

    def test_show_event_refreshes_profile_combo(self, qtbot, monkeypatch):
        names = ["nightly"]
        monkeypatch.setattr(reports_ops, "list_profile_names", lambda: list(names))
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "backup-history")
        names.append("weekly")

        panel.show()

        items = [panel.profile_combo.itemText(i) for i in range(panel.profile_combo.count())]
        assert items == ["(all profiles)", "nightly", "weekly"]

    def test_generate_collects_top_n_and_app_for_full(self, qtbot, monkeypatch):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "full")
        panel.top_spin.setValue(5)
        panel.app_combo.setCurrentIndex(1)  # WhatsApp Business
        calls = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: calls.append((a, kw)))

        panel._on_generate()

        assert calls == [(("full", "txt"), {"top_n": 5, "app": "business"})]

    def test_generate_omits_min_size_when_blank(self, qtbot, monkeypatch):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "large-files")
        calls = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: calls.append((a, kw)))

        panel._on_generate()

        assert calls == [(("large-files", "txt"), {})]

    def test_generate_includes_min_size_when_filled(self, qtbot, monkeypatch):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "large-files")
        panel.min_size_edit.setText("50MB")
        calls = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: calls.append((a, kw)))

        panel._on_generate()

        assert calls == [(("large-files", "txt"), {"min_size": "50MB"})]

    def test_generate_formats_cutoff_as_iso_date(self, qtbot, monkeypatch):
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "whatsapp-cutoff")
        panel.cutoff_date_edit.setDate(QDate(2026, 1, 15))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: calls.append((a, kw)))

        panel._on_generate()

        assert calls == [(("whatsapp-cutoff", "txt"), {"cutoff": "2026-01-15", "app": "whatsapp"})]

    def test_generate_maps_sentinel_profile_to_none(self, qtbot, monkeypatch):
        monkeypatch.setattr(reports_ops, "list_profile_names", lambda: ["nightly"])
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "backup-history")
        panel.profile_combo.setCurrentIndex(0)  # "(all profiles)"
        calls = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: calls.append((a, kw)))

        panel._on_generate()

        assert calls == [(("backup-history", "txt"), {"profile": None})]

    def test_generate_passes_named_profile(self, qtbot, monkeypatch):
        monkeypatch.setattr(reports_ops, "list_profile_names", lambda: ["nightly"])
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "backup-summary")
        calls = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: calls.append((a, kw)))

        panel._on_generate()

        assert calls == [(("backup-summary", "txt"), {"profile": "nightly"})]

    def test_generate_warns_and_skips_when_required_profile_missing(self, qtbot, monkeypatch):
        monkeypatch.setattr(reports_ops, "list_profile_names", lambda: [])
        panel = ReportsPage(ReportsViewModel(_connected_ctx()))
        qtbot.addWidget(panel)
        self._select_type(panel, "backup-summary")
        generate_calls = []
        warnings = []
        monkeypatch.setattr(panel.viewmodel, "generate", lambda *a, **kw: generate_calls.append((a, kw)))
        panel.viewmodel.logMessage.connect(lambda msg, level: warnings.append((msg, level)))

        panel._on_generate()

        assert generate_calls == []
        assert len(warnings) == 1
        assert warnings[0][1] == "WARNING"
        assert "Backup Summary" in warnings[0][0]

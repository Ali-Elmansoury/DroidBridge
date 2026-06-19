from datetime import date
from unittest.mock import MagicMock, patch, call
import pytest
from droidbridge.gui import whatsapp_ops
from droidbridge.modules.whatsapp import (
    WhatsAppInstall, DeletePlan, OrganizePlan, OrganizeItem,
)
from droidbridge.modules.transfer import TransferPlan, TransferItem, TransferProgress, VerificationResult

_WA = WhatsAppInstall(package="com.whatsapp", label="WhatsApp", base_path="/sdcard/WhatsApp")
_BIZ = WhatsAppInstall(package="com.whatsapp.w4b", label="WhatsApp Business", base_path="/sdcard/WhatsApp Business")


def _make_plan(n=2):
    items = [TransferItem(source=f"/remote/f{i}", dest=f"/local/f{i}", size=100, action="copy") for i in range(n)]
    return TransferPlan(direction="pull", items=items)


def _make_progress(done=2, total=2):
    p = TransferProgress(total_files=total, total_bytes=total * 100)
    p.done_files = done
    return p


class TestSelectInstalls:
    def test_all_returns_all(self):
        assert whatsapp_ops._select_installs([_WA, _BIZ], "all") == [_WA, _BIZ]

    def test_whatsapp_filters_by_package(self):
        assert whatsapp_ops._select_installs([_WA, _BIZ], "whatsapp") == [_WA]

    def test_business_filters_by_package(self):
        assert whatsapp_ops._select_installs([_WA, _BIZ], "business") == [_BIZ]


class TestRunScan:
    def test_folder_breakdown_calls_summarize_by_folder(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        mock_summary = MagicMock(folder_type="Images", section="Received", file_count=5, total_size=1024)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.scan_media", lambda c, s, i: ["dummy"])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.summarize_by_folder", lambda m: [mock_summary])
        rows = whatsapp_ops.run_scan(client, serial, "whatsapp", "folder")
        assert rows[0]["folder_type"] == "Images"
        assert rows[0]["file_count"] == 5

    def test_year_breakdown_calls_summarize_by_year_month(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        mock_summary = MagicMock(year_month="2024-01", file_count=3, total_size=512)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.scan_media", lambda c, s, i: [])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.summarize_by_year_month", lambda m: [mock_summary])
        rows = whatsapp_ops.run_scan(client, serial, "whatsapp", "year")
        assert rows[0]["year_month"] == "2024-01"

    def test_extension_breakdown_calls_summarize_by_extension(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        mock_summary = MagicMock(extension="jpg", file_count=10, total_size=2048)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.scan_media", lambda c, s, i: [])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.summarize_by_extension", lambda m: [mock_summary])
        rows = whatsapp_ops.run_scan(client, serial, "whatsapp", "extension")
        assert rows[0]["extension"] == "jpg"


class TestRunAnalyze:
    def test_calls_summarize_by_cutoff(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        cutoff = date(2024, 9, 1)
        mock_s = MagicMock(folder_type="Images", pre_count=2, pre_size=100,
                           post_count=3, post_size=200, unknown_count=1, unknown_size=50)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.scan_media", lambda c, s, i: [])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.summarize_by_cutoff", lambda m, c: [mock_s])
        rows = whatsapp_ops.run_analyze(client, serial, "whatsapp", cutoff)
        assert rows[0]["folder_type"] == "Images"
        assert rows[0]["pre_count"] == 2
        assert rows[0]["post_count"] == 3


class TestRunBackup:
    def test_calls_plan_backup_and_execute(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        plan = _make_plan()
        progress = _make_progress()
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.plan_backup",
                            lambda c, s, installs, dest, types, conflict: plan)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.transfer_module.execute_plan",
                            lambda c, s, p, progress_callback: progress)
        result = whatsapp_ops.run_backup(client, serial, "whatsapp", "/dest", None, "skip", False)
        assert result["done"] == 2
        assert result["total"] == 2
        assert result["verified"] is None

    def test_verify_calls_verify_pull(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        plan = _make_plan()
        progress = _make_progress()
        vr = VerificationResult(expected_files=2, expected_bytes=200, actual_files=2, actual_bytes=200)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.plan_backup",
                            lambda c, s, installs, dest, types, conflict: plan)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.transfer_module.execute_plan",
                            lambda c, s, p, progress_callback: progress)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.transfer_module.verify_pull", lambda p: vr)
        result = whatsapp_ops.run_backup(client, serial, "whatsapp", "/dest", None, "skip", True)
        assert result["verified"] is True


class TestBuildDeletePreview:
    def test_returns_rows_and_plans(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        mf = MagicMock(path="/sdcard/WhatsApp/f.jpg", folder_type="Images", size=100)
        plan = DeletePlan(to_delete=[mf], kept=[])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.scan_media", lambda c, s, i: [mf])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.plan_delete",
                            lambda media, before, keep_types: plan)
        result = whatsapp_ops.build_delete_preview(client, serial, "whatsapp",
                                                    date(2024, 1, 1), None, "")
        assert result["error"] is None
        assert len(result["rows"]) == 1
        assert result["rows"][0]["folder_type"] == "Images"

    def test_backup_verification_failure_returns_error(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        mf = MagicMock(path="/sdcard/f.jpg", folder_type="Images", size=100)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.detect_installs", lambda c, s: [_WA])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.scan_media", lambda c, s, i: [mf])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.verify_backup_exists",
                            lambda install, bd, media: [mf])
        result = whatsapp_ops.build_delete_preview(client, serial, "whatsapp",
                                                    date(2024, 1, 1), None, "/backup")
        assert result["error"] is not None
        assert "missing" in result["error"]


class TestExecuteDelete:
    def test_calls_execute_delete_plan(self, monkeypatch):
        client, serial = MagicMock(), "S1"
        mf = MagicMock()
        plan = DeletePlan(to_delete=[mf, mf], kept=[])
        called = []
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.execute_delete_plan",
                            lambda c, s, p: called.append(p))
        result = whatsapp_ops.execute_delete(client, serial, [{"install": _WA, "plan": plan}])
        assert result["deleted"] == 2
        assert called[0] is plan


class TestRunOrganize:
    def test_calls_fix_filenames_and_plan_organize_by_date(self, monkeypatch, tmp_path):
        src = str(tmp_path)
        plan = OrganizePlan(items=[OrganizeItem(source="/a", dest="/b")])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.fix_filenames", lambda s: [("a", "b")])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.plan_organize_by_date",
                            lambda s, sectioned: plan)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.execute_organize_plan", lambda p: None)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module._organized_dest_root", lambda s: "/dest")
        result = whatsapp_ops.run_organize(src, "images")
        assert result["organized"] == 1
        assert result["fixed"] == 1
        assert result["dest"] == "/dest"

    def test_documents_type_uses_plan_organize_documents(self, monkeypatch, tmp_path):
        src = str(tmp_path)
        plan = OrganizePlan(items=[])
        doc_calls = []
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.fix_filenames", lambda s: [])
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.plan_organize_documents",
                            lambda s: doc_calls.append(s) or plan)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module.execute_organize_plan", lambda p: None)
        monkeypatch.setattr("droidbridge.gui.whatsapp_ops.wa_module._organized_dest_root", lambda s: "/dest")
        whatsapp_ops.run_organize(src, "documents")
        assert doc_calls == [src]

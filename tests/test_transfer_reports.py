"""Tests for droidbridge.reports.transfer_reports."""

from droidbridge.modules.transfer import (
    ACTION_COPY, ACTION_SKIP_CONFLICT, ExtraItem, FailedExtraItem,
    FailedTransferItem, MirrorResult, TransferItem, TransferPlan, TransferProgress,
    VerificationResult,
)
from droidbridge.reports.generators import to_txt
from droidbridge.reports import transfer_reports


def _make_plan(direction="pull", n_items=2, n_skip_conflict=0, n_extra=0):
    items = [
        TransferItem(source=f"/sdcard/{i}.jpg", dest=f"/tmp/{i}.jpg", size=1000, action=ACTION_COPY)
        for i in range(n_items)
    ] + [
        TransferItem(source=f"/sdcard/c{i}.jpg", dest=f"/tmp/c{i}.jpg", size=500, action=ACTION_SKIP_CONFLICT)
        for i in range(n_skip_conflict)
    ]
    extra_items = [ExtraItem(path=f"/tmp/extra{i}.jpg", size=200) for i in range(n_extra)]
    return TransferPlan(direction=direction, items=items, extra_items=extra_items)


def _make_progress(done=2, failed_count=0):
    failed = [
        FailedTransferItem(
            item=TransferItem(source=f"/sdcard/f{i}.jpg", dest=f"/tmp/f{i}.jpg", size=100, action=ACTION_COPY),
            error="timeout",
        )
        for i in range(failed_count)
    ]
    return TransferProgress(total_files=2, total_bytes=2000, done_files=done, done_bytes=done * 1000, failed=failed)


class TestBuildTransferReport:
    def test_pull_report_has_correct_title(self):
        report = transfer_reports.build_transfer_report("pull", _make_plan("pull"), _make_progress())
        assert "Pull" in report.title

    def test_push_report_has_correct_title(self):
        report = transfer_reports.build_transfer_report("push", _make_plan("push"), _make_progress())
        assert "Push" in report.title

    def test_mirror_pull_title(self):
        report = transfer_reports.build_transfer_report("mirror-pull", _make_plan(), _make_progress())
        assert "Mirror" in report.title

    def test_summary_section_includes_key_metrics(self):
        plan = _make_plan()
        progress = _make_progress(done=2, failed_count=0)
        report = transfer_reports.build_transfer_report("pull", plan, progress)
        txt = to_txt(report)
        assert "Transferred files" in txt
        assert "Failed" in txt

    def test_no_failed_section_when_all_succeed(self):
        report = transfer_reports.build_transfer_report("pull", _make_plan(), _make_progress(failed_count=0))
        titles = [s.title for s in report.sections]
        assert "Failed Items" not in titles

    def test_failed_section_included_when_failures_exist(self):
        report = transfer_reports.build_transfer_report("pull", _make_plan(), _make_progress(failed_count=1))
        titles = [s.title for s in report.sections]
        assert "Failed Items" in titles

    def test_no_verification_section_when_none(self):
        report = transfer_reports.build_transfer_report("pull", _make_plan(), _make_progress(), verification=None)
        titles = [s.title for s in report.sections]
        assert "Verification" not in titles

    def test_verification_section_included_when_given(self):
        v = VerificationResult(expected_files=2, expected_bytes=2000, actual_files=2, actual_bytes=2000)
        report = transfer_reports.build_transfer_report("pull", _make_plan(), _make_progress(), verification=v)
        titles = [s.title for s in report.sections]
        assert "Verification" in titles

    def test_mirror_extras_section_included_when_mirror_result_given(self):
        mr = MirrorResult(progress=_make_progress(), deleted_files=1, deleted_bytes=200, failed_deletions=[])
        report = transfer_reports.build_transfer_report(
            "mirror-pull", _make_plan(n_extra=1), _make_progress(), mirror_result=mr,
        )
        titles = [s.title for s in report.sections]
        assert "Mirror Extras" in titles

    def test_failed_deletions_section_when_deletions_failed(self):
        extra = ExtraItem(path="/tmp/gone.jpg", size=200)
        mr = MirrorResult(
            progress=_make_progress(),
            deleted_files=0,
            deleted_bytes=0,
            failed_deletions=[FailedExtraItem(item=extra, error="FileNotFoundError")],
        )
        report = transfer_reports.build_transfer_report(
            "mirror-pull", _make_plan(), _make_progress(), mirror_result=mr,
        )
        titles = [s.title for s in report.sections]
        assert "Failed Deletions" in titles

# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.reports.generators - generic Report/ReportSection model
and TXT/HTML/CSV/JSON generators (spec §9.5)."""

import csv
import io
import json

from droidbridge.reports.generators import Report, ReportSection, to_csv, to_html, to_json, to_txt


def _sample_report():
    return Report(
        title="Storage Breakdown",
        sections=[
            ReportSection(
                title="Overview",
                text="Device is 80% full.",
            ),
            ReportSection(
                title="Categories",
                headers=["Category", "Size"],
                rows=[["Apps", "1.5 GB"], ["Photos", "3.2 GB"]],
            ),
        ],
        generated_at="2026-06-12T00:00:00+00:00",
    )


class TestReportModel:
    def test_generated_at_defaults_to_now(self):
        report = Report(title="Empty Report")

        assert report.generated_at != ""
        assert report.sections == []


class TestToJson:
    def test_round_trips_title_and_sections(self):
        report = _sample_report()

        data = json.loads(to_json(report))

        assert data["title"] == "Storage Breakdown"
        assert data["generated_at"] == "2026-06-12T00:00:00+00:00"
        assert data["sections"][0]["title"] == "Overview"
        assert data["sections"][0]["text"] == "Device is 80% full."
        assert data["sections"][1]["headers"] == ["Category", "Size"]
        assert data["sections"][1]["rows"] == [["Apps", "1.5 GB"], ["Photos", "3.2 GB"]]


class TestToTxt:
    def test_includes_title_and_section_content(self):
        report = _sample_report()

        text = to_txt(report)

        assert "Storage Breakdown" in text
        assert "2026-06-12T00:00:00+00:00" in text
        assert "Overview" in text
        assert "Device is 80% full." in text
        assert "Category" in text and "Size" in text
        assert "Apps" in text and "1.5 GB" in text

    def test_empty_report_does_not_crash(self):
        report = Report(title="Empty", generated_at="2026-06-12T00:00:00+00:00")

        text = to_txt(report)

        assert "Empty" in text


class TestToCsv:
    def test_table_rows_are_parseable(self):
        report = _sample_report()

        csv_text = to_csv(report)
        rows = list(csv.reader(io.StringIO(csv_text)))
        flattened = [cell for row in rows for cell in row]

        assert "Storage Breakdown" in flattened
        assert "Category" in flattened and "Size" in flattened
        assert "Apps" in flattened and "1.5 GB" in flattened


class TestToHtml:
    def test_produces_self_contained_html_with_table(self):
        report = _sample_report()

        html = to_html(report)

        assert "<html" in html
        assert "<table" in html
        assert "Storage Breakdown" in html
        assert "Apps" in html
        assert "1.5 GB" in html

    def test_escapes_special_characters(self):
        report = Report(
            title="Test",
            sections=[ReportSection(title="<script>alert(1)</script>", text="a & b")],
            generated_at="2026-06-12T00:00:00+00:00",
        )

        html = to_html(report)

        assert "<script>alert(1)</script>" not in html
        assert "&amp; b" in html

# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.core.session - session_logs/ structure and logging."""

import json

from droidbridge.core import session


class TestSessionStart:
    def test_creates_session_logs_directory_structure(self, tmp_path):
        base_dir = tmp_path / "session_logs"

        session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        assert (base_dir / "scripts" / "analysis").is_dir()
        assert (base_dir / "scripts" / "organization").is_dir()
        assert (base_dir / "scripts" / "deletion").is_dir()
        assert (base_dir / "reports").is_dir()

    def test_logs_session_started_message(self, tmp_path):
        base_dir = tmp_path / "session_logs"

        logger = session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        log_contents = logger.log_file.read_text()
        assert "Session 20260611_120000 started" in log_contents

    def test_default_session_id_is_timestamp_like(self, tmp_path):
        base_dir = tmp_path / "session_logs"

        logger = session.SessionLogger.start(base_dir=base_dir)

        assert len(logger.session_id) == 22  # YYYYMMDD_HHMMSS_ffffff
        assert "_" in logger.session_id


class TestSessionLog:
    def test_log_appends_timestamped_entry(self, tmp_path):
        base_dir = tmp_path / "session_logs"
        logger = session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        logger.log("Pulled 42 files")

        log_contents = logger.log_file.read_text()
        assert "Pulled 42 files" in log_contents
        assert "[INFO]" in log_contents

    def test_log_supports_custom_level(self, tmp_path):
        base_dir = tmp_path / "session_logs"
        logger = session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        logger.log("Something went wrong", level="ERROR")

        log_contents = logger.log_file.read_text()
        assert "[ERROR] Something went wrong" in log_contents

    def test_log_records_event_for_summary(self, tmp_path):
        base_dir = tmp_path / "session_logs"
        logger = session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        logger.log("Pulled 42 files")
        summary_path = logger.write_summary()

        data = json.loads(summary_path.read_text())
        assert data["session_id"] == "20260611_120000"
        messages = [e["message"] for e in data["events"]]
        assert "Pulled 42 files" in messages


class TestScriptDir:
    def test_returns_path_for_known_category(self, tmp_path):
        base_dir = tmp_path / "session_logs"
        logger = session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        assert logger.script_dir("analysis") == base_dir / "scripts" / "analysis"

    def test_raises_for_unknown_category(self, tmp_path):
        base_dir = tmp_path / "session_logs"
        logger = session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        try:
            logger.script_dir("bogus")
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestReportsDir:
    def test_reports_dir_path(self, tmp_path):
        base_dir = tmp_path / "session_logs"
        logger = session.SessionLogger.start(base_dir=base_dir, session_id="20260611_120000")

        assert logger.reports_dir == base_dir / "reports"

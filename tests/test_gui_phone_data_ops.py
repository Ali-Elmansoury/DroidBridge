# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from unittest.mock import MagicMock, patch

from droidbridge.gui import phone_data_ops


class TestRunExportContacts:
    def test_creates_dest_dir_and_delegates(self, tmp_path):
        dest = tmp_path / "exports"
        with patch("droidbridge.gui.phone_data_ops.phone_data_module.export_contacts") as mock_export:
            mock_export.return_value = {"phone": {"exported": 1, "skipped": 0}}
            result = phone_data_ops.run_export_contacts(MagicMock(), "SERIAL", ["phone"], str(dest))
        assert dest.exists()
        mock_export.assert_called_once_with(mock_export.call_args.args[0], "SERIAL", ["phone"], str(dest))
        assert result == {"phone": {"exported": 1, "skipped": 0}}


class TestRunExportCallLog:
    def test_creates_dest_dir_and_delegates(self, tmp_path):
        dest = tmp_path / "exports"
        with patch("droidbridge.gui.phone_data_ops.phone_data_module.export_call_log") as mock_export:
            mock_export.return_value = {"exported": 3, "skipped": 0}
            result = phone_data_ops.run_export_call_log(MagicMock(), "SERIAL", str(dest))
        assert dest.exists()
        mock_export.assert_called_once_with(mock_export.call_args.args[0], "SERIAL", str(dest))
        assert result == {"exported": 3, "skipped": 0}

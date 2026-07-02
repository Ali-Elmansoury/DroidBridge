# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from droidbridge.modules.phone_data import (
    CallLogEntry,
    Contact,
    _parse_rows,
    export_call_log,
    export_contacts,
    query_account_contacts,
    query_call_log,
    query_phone_contacts,
    query_sim_contacts,
)


def _client_with_shell_outputs(*outputs):
    client = MagicMock()
    client.shell.side_effect = list(outputs)
    return client


_PHONES_OUTPUT = (
    "Row: 0 display_name=John Doe, data1=+15551234567, raw_contact_id=3\n"
    "Row: 1 display_name=Smith, John, data1=+15559876543, raw_contact_id=7\n"
)
_RAW_CONTACTS_OUTPUT = (
    "Row: 0 _id=3, account_type=NULL\n"
    "Row: 1 _id=7, account_type=com.google\n"
)


class TestParseRows:
    def test_parses_simple_rows(self):
        output = (
            "Row: 0 display_name=John Doe, data1=+15551234567, raw_contact_id=3\n"
            "Row: 1 display_name=Jane Roe, data1=+15559876543, raw_contact_id=7\n"
        )
        rows, skipped = _parse_rows(output)
        assert skipped == 0
        assert rows == [
            {"display_name": "John Doe", "data1": "+15551234567", "raw_contact_id": "3"},
            {"display_name": "Jane Roe", "data1": "+15559876543", "raw_contact_id": "7"},
        ]

    def test_value_containing_comma_is_not_split(self):
        output = "Row: 0 display_name=Smith, John, data1=+15559876543, raw_contact_id=7\n"
        rows, skipped = _parse_rows(output)
        assert skipped == 0
        assert rows == [{"display_name": "Smith, John", "data1": "+15559876543", "raw_contact_id": "7"}]

    def test_no_result_found_yields_no_rows_and_no_skips(self):
        rows, skipped = _parse_rows("No result found.\n")
        assert rows == []
        assert skipped == 0

    def test_malformed_row_is_skipped_and_counted(self):
        output = "Row: 0 display_name=John, data1=+15551234567\nRow: 1 \n"
        rows, skipped = _parse_rows(output)
        assert len(rows) == 1
        assert skipped == 1


class TestQueryPhoneContacts:
    def test_returns_only_local_contacts(self):
        client = _client_with_shell_outputs(_PHONES_OUTPUT, _RAW_CONTACTS_OUTPUT)
        contacts, skipped = query_phone_contacts(client, "SERIAL")
        assert contacts == [Contact(display_name="John Doe", number="+15551234567")]
        assert skipped == 0

    def test_issues_expected_shell_commands(self):
        client = _client_with_shell_outputs(_PHONES_OUTPUT, _RAW_CONTACTS_OUTPUT)
        query_phone_contacts(client, "SERIAL")
        first_call, second_call = client.shell.call_args_list
        assert first_call.args[0] == "SERIAL"
        assert "content://com.android.contacts/data/phones" in first_call.args[1]
        assert second_call.args[0] == "SERIAL"
        assert "content://com.android.contacts/raw_contacts" in second_call.args[1]


class TestQueryAccountContacts:
    def test_returns_only_synced_contacts(self):
        client = _client_with_shell_outputs(_PHONES_OUTPUT, _RAW_CONTACTS_OUTPUT)
        contacts, skipped = query_account_contacts(client, "SERIAL")
        assert contacts == [Contact(display_name="Smith, John", number="+15559876543")]
        assert skipped == 0

    def test_missing_name_or_number_is_skipped(self):
        phones_output = "Row: 0 display_name=No Number, data1=, raw_contact_id=9\n"
        raw_output = "Row: 0 _id=9, account_type=com.google\n"
        client = _client_with_shell_outputs(phones_output, raw_output)
        contacts, skipped = query_account_contacts(client, "SERIAL")
        assert contacts == []
        assert skipped == 1


class TestQuerySimContacts:
    def test_parses_sim_contacts(self):
        client = _client_with_shell_outputs("Row: 0 name=Sim Contact, number=+15550001111\n")
        contacts, skipped = query_sim_contacts(client, "SERIAL")
        assert contacts == [Contact(display_name="Sim Contact", number="+15550001111")]
        assert skipped == 0

    def test_no_sim_returns_empty_not_error(self):
        client = _client_with_shell_outputs("No result found.\n")
        contacts, skipped = query_sim_contacts(client, "SERIAL")
        assert contacts == []
        assert skipped == 0

    def test_provider_exception_returns_empty_not_raised(self):
        client = MagicMock()
        client.shell.side_effect = RuntimeError("no such provider")
        contacts, skipped = query_sim_contacts(client, "SERIAL")
        assert contacts == []
        assert skipped == 0


class TestQueryCallLog:
    def test_parses_call_log_rows(self):
        output = (
            "Row: 0 name=Jane Roe, number=+15551112222, date=1750000000000, duration=42, type=1\n"
            "Row: 1 name=NULL, number=+15553334444, date=1750000100000, duration=0, type=3\n"
        )
        client = _client_with_shell_outputs(output)
        entries, skipped = query_call_log(client, "SERIAL")
        assert skipped == 0
        expected_ts_0 = datetime.fromtimestamp(1750000000000 / 1000, tz=timezone.utc).isoformat(timespec="seconds")
        expected_ts_1 = datetime.fromtimestamp(1750000100000 / 1000, tz=timezone.utc).isoformat(timespec="seconds")
        assert entries == [
            CallLogEntry(name="Jane Roe", number="+15551112222", timestamp=expected_ts_0,
                         duration_seconds="42", call_type="incoming"),
            CallLogEntry(name="", number="+15553334444", timestamp=expected_ts_1,
                         duration_seconds="0", call_type="missed"),
        ]

    def test_unknown_call_type_falls_back(self):
        output = "Row: 0 name=X, number=+15550000000, date=1750000000000, duration=1, type=99\n"
        client = _client_with_shell_outputs(output)
        entries, skipped = query_call_log(client, "SERIAL")
        assert entries[0].call_type == "unknown"

    def test_missing_number_or_date_is_skipped(self):
        output = "Row: 0 name=X, number=, date=1750000000000, duration=1, type=1\n"
        client = _client_with_shell_outputs(output)
        entries, skipped = query_call_log(client, "SERIAL")
        assert entries == []
        assert skipped == 1

    def test_permission_denial_raises_instead_of_returning_empty(self):
        output = (
            "Error while accessing provider:call_log\n"
            "java.lang.SecurityException: Permission Denial: opening provider "
            "com.android.providers.contacts.CallLogProvider from (null) (pid=2267, uid=2000) "
            "requires android.permission.READ_CALL_LOG or android.permission.WRITE_CALL_LOG\n"
        )
        client = _client_with_shell_outputs(output)
        try:
            query_call_log(client, "SERIAL")
            assert False, "expected PermissionError"
        except PermissionError as exc:
            assert "call_log" in str(exc)
            assert "SecurityException" in str(exc) or "Permission Denial" in str(exc)


class TestExportContacts:
    def test_writes_one_vcf_and_json_pair_per_source(self, tmp_path):
        client = _client_with_shell_outputs(
            _PHONES_OUTPUT, _RAW_CONTACTS_OUTPUT,  # query_phone_contacts
        )
        summary = export_contacts(client, "SERIAL", ["phone"], str(tmp_path))
        assert summary == {"phone": {"exported": 1, "skipped": 0}}

        vcf_text = (tmp_path / "contacts_phone.vcf").read_text(encoding="utf-8")
        assert "BEGIN:VCARD" in vcf_text
        assert "FN:John Doe" in vcf_text
        assert "TEL:+15551234567" in vcf_text
        assert "END:VCARD" in vcf_text

        json_data = json.loads((tmp_path / "contacts_phone.json").read_text(encoding="utf-8"))
        assert json_data == [{"display_name": "John Doe", "number": "+15551234567"}]

    def test_vcard_preserves_comma_in_name(self, tmp_path):
        client = _client_with_shell_outputs(_PHONES_OUTPUT, _RAW_CONTACTS_OUTPUT)
        export_contacts(client, "SERIAL", ["accounts"], str(tmp_path))
        vcf_text = (tmp_path / "contacts_accounts.vcf").read_text(encoding="utf-8")
        assert "FN:Smith, John" in vcf_text

    def test_multiple_sources_write_separate_files(self, tmp_path):
        client = _client_with_shell_outputs(
            _PHONES_OUTPUT, _RAW_CONTACTS_OUTPUT,  # query_phone_contacts
            "No result found.\n",                  # query_sim_contacts
        )
        summary = export_contacts(client, "SERIAL", ["phone", "sim"], str(tmp_path))
        assert summary["phone"]["exported"] == 1
        assert summary["sim"] == {"exported": 0, "skipped": 0}
        assert (tmp_path / "contacts_phone.vcf").exists()
        assert (tmp_path / "contacts_sim.vcf").exists()


class TestExportCallLog:
    def test_writes_csv_and_json(self, tmp_path):
        output = "Row: 0 name=Jane Roe, number=+15551112222, date=1750000000000, duration=42, type=1\n"
        client = _client_with_shell_outputs(output)
        summary = export_call_log(client, "SERIAL", str(tmp_path))
        assert summary == {"exported": 1, "skipped": 0}

        csv_text = (tmp_path / "call_log.csv").read_text(encoding="utf-8")
        assert "Jane Roe" in csv_text
        assert "+15551112222" in csv_text
        assert "incoming" in csv_text

        json_data = json.loads((tmp_path / "call_log.json").read_text(encoding="utf-8"))
        assert json_data[0]["number"] == "+15551112222"
        assert json_data[0]["call_type"] == "incoming"

    def test_permission_denial_propagates_instead_of_writing_empty_files(self, tmp_path):
        output = "java.lang.SecurityException: Permission Denial: requires android.permission.READ_CALL_LOG\n"
        client = _client_with_shell_outputs(output)
        try:
            export_call_log(client, "SERIAL", str(tmp_path))
            assert False, "expected PermissionError"
        except PermissionError:
            pass
        assert not (tmp_path / "call_log.csv").exists()

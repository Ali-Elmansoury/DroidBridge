from datetime import datetime, timezone
from unittest.mock import MagicMock

from droidbridge.modules.phone_data import (
    CallLogEntry,
    Contact,
    _parse_rows,
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

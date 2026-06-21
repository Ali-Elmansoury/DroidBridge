from droidbridge.modules.phone_data import _parse_rows


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

"""Tests for droidbridge.utils.format - size formatting helpers."""

import pytest

from droidbridge.utils.format import format_bytes, format_size_kb, parse_size


class TestFormatBytes:
    @pytest.mark.parametrize(
        "num_bytes, expected",
        [
            (0, "0 B"),
            (512, "512 B"),
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (1024 ** 2, "1.0 MB"),
            (1024 ** 3, "1.0 GB"),
            (1024 ** 4, "1.0 TB"),
        ],
    )
    def test_formats_expected_units(self, num_bytes, expected):
        assert format_bytes(num_bytes) == expected


class TestFormatSizeKb:
    def test_one_mb_in_kb(self):
        assert format_size_kb(1024) == "1.0 MB"

    def test_one_gb_in_kb(self):
        assert format_size_kb(1024 * 1024) == "1.0 GB"


class TestParseSize:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("100", 100),
            ("100B", 100),
            ("1K", 1024),
            ("1KB", 1024),
            ("1.5KB", 1536),
            ("10MB", 10 * 1024 ** 2),
            ("50 MB", 50 * 1024 ** 2),
            ("2GB", 2 * 1024 ** 3),
            ("1TB", 1024 ** 4),
            ("1mb", 1024 ** 2),
        ],
    )
    def test_parses_human_readable_sizes(self, value, expected):
        assert parse_size(value) == expected

    def test_invalid_size_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_size("not-a-size")

    def test_unknown_unit_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_size("10XB")

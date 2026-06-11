"""Tests for droidbridge.utils.format - size formatting helpers."""

import pytest

from droidbridge.utils.format import format_bytes, format_size_kb


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

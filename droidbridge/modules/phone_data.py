"""Contacts and Call Log export via adb content-provider queries (sub-phase 6.4)."""

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_ROW_PREFIX = "Row:"
_FIELD_PATTERN = re.compile(r"(\w+)=(.*?)(?=, \w+=|$)")

_CALL_TYPES = {
    "1": "incoming",
    "2": "outgoing",
    "3": "missed",
    "4": "voicemail",
    "5": "rejected",
    "6": "blocked",
}


@dataclass
class Contact:
    """One exported contact: display name + phone number."""

    display_name: str
    number: str


@dataclass
class CallLogEntry:
    """One exported call log entry."""

    name: str
    number: str
    timestamp: str
    duration_seconds: str
    call_type: str


def _parse_rows(output):
    """Parse `adb shell content query` text output into a list of dicts.

    Each "Row: N key=value, key2=value2, ..." line becomes one dict. Values
    may contain commas (e.g. "Smith, John") - _FIELD_PATTERN matches up to
    the next ", word=" boundary rather than splitting on every comma. Lines
    that aren't data rows (e.g. "No result found.") are silently ignored.
    A "Row:" line with no parseable fields is skipped and counted, so one
    bad row doesn't lose the rest of the export.
    """
    rows = []
    skipped = 0
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith(_ROW_PREFIX):
            continue
        parts = line.split(" ", 2)
        if len(parts) < 3:
            skipped += 1
            continue
        fields = _FIELD_PATTERN.findall(parts[2])
        if not fields:
            skipped += 1
            continue
        rows.append(dict(fields))
    return rows, skipped

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


def _query(client, serial, uri, projection, where=None):
    command = f"content query --uri {uri} --projection {projection}"
    if where:
        command += f' --where "{where}"'
    output = client.shell(serial, command)
    return _parse_rows(output)


def _contacts_by_account(client, serial, want_local):
    phone_rows, skipped_a = _query(
        client, serial,
        "content://com.android.contacts/data/phones",
        "display_name:data1:raw_contact_id",
    )
    account_rows, skipped_b = _query(
        client, serial,
        "content://com.android.contacts/raw_contacts",
        "_id:account_type",
    )
    account_by_id = {row.get("_id"): row.get("account_type") for row in account_rows}

    contacts = []
    skipped = skipped_a + skipped_b
    for row in phone_rows:
        raw_id = row.get("raw_contact_id")
        account_type = account_by_id.get(raw_id)
        is_local = account_type in (None, "NULL")
        if is_local != want_local:
            continue
        name = row.get("display_name")
        number = row.get("data1")
        if not name or not number:
            skipped += 1
            continue
        contacts.append(Contact(display_name=name, number=number))
    return contacts, skipped


def query_phone_contacts(client, serial):
    """Contacts with no synced account (account_type is NULL) - phone-local contacts only."""
    return _contacts_by_account(client, serial, want_local=True)


def query_account_contacts(client, serial):
    """Contacts belonging to any synced account (Google, Samsung, etc.), merged into one bucket."""
    return _contacts_by_account(client, serial, want_local=False)

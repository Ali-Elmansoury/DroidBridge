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


def query_sim_contacts(client, serial):
    """SIM card contacts via content://icc/adn - a separate, simpler provider.

    Returns ([], 0) if the SIM provider is absent or the device has no SIM -
    that's a successful empty export, not an error.
    """
    try:
        rows, skipped = _query(client, serial, "content://icc/adn", "name:number")
    except Exception:
        return [], 0
    contacts = []
    for row in rows:
        name = row.get("name")
        number = row.get("number")
        if not name or not number:
            skipped += 1
            continue
        contacts.append(Contact(display_name=name, number=number))
    return contacts, skipped


def query_call_log(client, serial):
    rows, skipped = _query(
        client, serial,
        "content://call_log/calls",
        "name:number:date:duration:type",
    )
    entries = []
    for row in rows:
        number = row.get("number")
        date_ms = row.get("date")
        if not number or not date_ms:
            skipped += 1
            continue
        try:
            timestamp = datetime.fromtimestamp(int(date_ms) / 1000, tz=timezone.utc).isoformat(timespec="seconds")
        except (ValueError, TypeError):
            skipped += 1
            continue
        name = row.get("name") or ""
        if name == "NULL":
            name = ""
        duration = row.get("duration") or "0"
        call_type = _CALL_TYPES.get(row.get("type"), "unknown")
        entries.append(CallLogEntry(
            name=name, number=number, timestamp=timestamp,
            duration_seconds=duration, call_type=call_type,
        ))
    return entries, skipped


def _write_vcard(contacts, path):
    lines = []
    for contact in contacts:
        lines.append("BEGIN:VCARD")
        lines.append("VERSION:3.0")
        lines.append(f"FN:{contact.display_name}")
        lines.append(f"TEL:{contact.number}")
        lines.append("END:VCARD")
    Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_json(items, path):
    Path(path).write_text(json.dumps([asdict(item) for item in items], indent=2), encoding="utf-8")


def _write_call_log_csv(entries, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "number", "timestamp", "duration_seconds", "call_type"])
        for entry in entries:
            writer.writerow([entry.name, entry.number, entry.timestamp, entry.duration_seconds, entry.call_type])


_CONTACT_QUERIES = {
    "phone": query_phone_contacts,
    "accounts": query_account_contacts,
    "sim": query_sim_contacts,
}


def export_contacts(client, serial, sources, dest):
    """Export each requested contact source to its own vCard + JSON file pair.

    `sources` is an iterable of "phone"/"accounts"/"sim". `dest` is a local
    directory that must already exist. Returns {source: {"exported": N, "skipped": M}}.
    """
    dest_dir = Path(dest)
    summary = {}
    for source in sources:
        query_fn = _CONTACT_QUERIES[source]
        contacts, skipped = query_fn(client, serial)
        _write_vcard(contacts, dest_dir / f"contacts_{source}.vcf")
        _write_json(contacts, dest_dir / f"contacts_{source}.json")
        summary[source] = {"exported": len(contacts), "skipped": skipped}
    return summary


def export_call_log(client, serial, dest):
    """Export the call log to call_log.csv + call_log.json. Returns {"exported": N, "skipped": M}."""
    dest_dir = Path(dest)
    entries, skipped = query_call_log(client, serial)
    _write_call_log_csv(entries, dest_dir / "call_log.csv")
    _write_json(entries, dest_dir / "call_log.json")
    return {"exported": len(entries), "skipped": skipped}

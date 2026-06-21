"""Plain-Python Contacts/Call Log GUI operations (sub-phase 6.4) — no Qt imports."""

import os

from droidbridge.modules import phone_data as phone_data_module


def run_export_contacts(client, serial, sources, dest):
    os.makedirs(dest, exist_ok=True)
    return phone_data_module.export_contacts(client, serial, sources, dest)


def run_export_call_log(client, serial, dest):
    os.makedirs(dest, exist_ok=True)
    return phone_data_module.export_call_log(client, serial, dest)

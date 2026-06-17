"""Click-based CLI entry point for DroidBridge."""

import csv
import importlib.util
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from droidbridge.core.adb import AdbClient, AdbError, AdbTimeoutError
from droidbridge.core.platform import get_sleep_inhibitor
from droidbridge.modules import apps as apps_module
from droidbridge.modules import backup_manager as backup_module
from droidbridge.modules import device as device_module
from droidbridge.modules import files as files_module
from droidbridge.modules import search as search_module
from droidbridge.modules import storage as storage_module
from droidbridge.modules import transfer as transfer_module
from droidbridge.modules import whatsapp as whatsapp_module
from droidbridge.reports import backup_reports, deletion_reports, storage_reports, transfer_reports, whatsapp_reports
from droidbridge.reports.generators import Report, to_csv, to_html, to_json, to_txt
from droidbridge.utils.format import format_bar, format_bytes, format_duration, format_size_kb, parse_size


def _build_client():
    """Construct the AdbClient. Patched in tests to avoid touching real adb."""
    return AdbClient()


def _resolve_serial(client, serial):
    """Resolve a device serial, exiting with guidance if missing/ambiguous/unknown."""
    try:
        return device_module.resolve_ready_device(client, serial)
    except device_module.DeviceSelectionError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


@click.group()
def cli():
    """DroidBridge - ADB-powered Android device management tool."""


@cli.group("device")
def device_cmd():
    """Device detection, info, and connection management."""


@device_cmd.command("connect")
def device_connect():
    """Check ADB connection status and guide setup if needed."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    device_module.ensure_adb_server_running(client)
    devices, messages = device_module.check_connection_health(client)

    if any(d.state == "offline" for d in devices):
        click.echo("Offline device detected; restarting ADB server...")
        device_module.restart_adb_server(client)
        devices, messages = device_module.check_connection_health(client)

    for message in messages:
        click.echo(message)

    ready = [d for d in devices if d.is_ready]
    if not ready:
        sys.exit(1)

    if len(ready) == 1:
        mode_info = device_module.get_usb_mode_info(client, ready[0].serial)
        if mode_info.guidance:
            click.echo(mode_info.guidance)


@device_cmd.command("info")
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
def device_info(serial):
    """Show device info and storage breakdown."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    info = device_module.get_device_info(client, serial)

    click.echo(f"Serial:        {info.serial}")
    click.echo(f"Model:         {info.model}")
    click.echo(f"Manufacturer:  {info.manufacturer}")
    click.echo(f"Android:       {info.android_version} (SDK {info.sdk_version})")
    click.echo(f"Build:         {info.build_number}")
    click.echo(f"Battery:       {info.battery_level}% ({info.battery_status})")
    click.echo("Storage:")
    click.echo(f"  Total:  {format_size_kb(info.storage.total_kb)}")
    click.echo(
        f"  Used:   {format_size_kb(info.storage.used_kb)} "
        f"({info.storage.used_percent}%)"
    )
    click.echo(f"  Free:   {format_size_kb(info.storage.free_kb)}")
    click.echo(f"USB type:      {info.usb_speed.usb_type}")
    click.echo(f"Est. speed:    {info.usb_speed.estimated_speed}")
    if info.usb_mode.mtp_enabled:
        click.echo(f"USB mode:      {', '.join(info.usb_mode.functions)} (File Transfer enabled)")
    else:
        click.echo(f"USB mode:      {', '.join(info.usb_mode.functions)} (not File Transfer/MTP)")


@device_cmd.command("wait")
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Wait for a specific device serial (default: any device).",
)
@click.option(
    "--timeout",
    default=None,
    type=int,
    help="Maximum seconds to wait (default: wait indefinitely).",
)
def device_wait(serial, timeout):
    """Block until a device is connected and ready (spec §1.1)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Waiting for device...")
    try:
        device_module.wait_for_device(client, serial=serial, timeout=timeout)
    except AdbTimeoutError:
        click.echo("Timed out waiting for device.", err=True)
        sys.exit(1)

    devices, messages = device_module.check_connection_health(client)
    for message in messages:
        click.echo(message)
    if not any(d.is_ready for d in devices):
        sys.exit(1)
    click.echo("Device ready.")


@cli.group("files")
def files_cmd():
    """Browse and search files on the device."""


def _entry_type_char(entry):
    if entry.is_symlink:
        return "l"
    if entry.is_dir:
        return "d"
    return "-"


def _format_entry_line(entry):
    type_char = _entry_type_char(entry)
    size = format_bytes(entry.size)
    date = entry.mtime.strftime("%Y-%m-%d %H:%M")
    name = entry.name
    if entry.is_symlink and entry.link_target:
        name = f"{name} -> {entry.link_target}"
    return f"{type_char}  {size:>10}  {date}  {name}"


@files_cmd.command("browse")
@click.argument("path", default="/sdcard")
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
@click.option(
    "--sort",
    "-S",
    "sort_by",
    type=click.Choice(files_module.SORT_KEYS),
    default="name",
    help="Sort by name, size, date, or type.",
)
@click.option("--reverse", "-r", is_flag=True, help="Reverse the sort order.")
@click.option("--all", "-a", "show_hidden", is_flag=True, help="Show hidden files.")
@click.option(
    "--ext",
    "-e",
    "extensions",
    multiple=True,
    help="Only show files with this extension (repeatable).",
)
def files_browse(path, serial, sort_by, reverse, show_hidden, extensions):
    """List files at PATH on the device (default: /sdcard)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        entries = files_module.list_directory(client, serial, path)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    extensions_filter = [e.lower().lstrip(".") for e in extensions] or None
    entries = files_module.filter_entries(
        entries, extensions=extensions_filter, include_hidden=show_hidden
    )
    entries = files_module.sort_entries(entries, by=sort_by, reverse=reverse)

    if not entries:
        click.echo("(empty)")
        return

    for entry in entries:
        click.echo(_format_entry_line(entry))


def _format_result_line(result):
    size = format_bytes(result.size)
    date = result.mtime.strftime("%Y-%m-%d %H:%M")
    ext = result.extension or "(none)"
    return f"{size:>10}  {date}  {ext:<10}  {result.path}"


def _write_search_export(results, fmt, path):
    """Write search results to a file in 'csv' or 'txt' format."""
    if fmt == "csv":
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "size", "date", "extension"])
            for r in results:
                writer.writerow([r.path, r.size, r.mtime.strftime("%Y-%m-%d %H:%M"), r.extension or ""])
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("      size  date                ext         path\n")
            for r in results:
                f.write(_format_result_line(r) + "\n")


def _search_results_to_plan(results, dest_dir, conflict):
    """Build a TransferPlan from search results without extra ADB stat calls.

    Files are flattened into dest_dir by filename; same-filename collisions
    within the results get _1/_2/... suffixes.
    """
    items = []
    claimed = set()
    for r in results:
        dest = os.path.join(dest_dir, os.path.basename(r.path))
        if dest in claimed:
            dest = transfer_module.resolve_conflict_path(dest, lambda p: p in claimed or os.path.exists(p))
        claimed.add(dest)

        if os.path.exists(dest) and os.path.getsize(dest) == r.size:
            action = transfer_module.ACTION_SKIP_EXISTING
        elif os.path.exists(dest):
            if conflict == transfer_module.CONFLICT_SKIP:
                action = transfer_module.ACTION_SKIP_CONFLICT
            elif conflict == transfer_module.CONFLICT_OVERWRITE:
                action = transfer_module.ACTION_OVERWRITE
            else:
                dest = transfer_module.resolve_conflict_path(dest, lambda p: p in claimed or os.path.exists(p))
                claimed.add(dest)
                action = transfer_module.ACTION_RENAME
        else:
            action = transfer_module.ACTION_COPY

        items.append(transfer_module.TransferItem(source=r.path, dest=dest, size=r.size, action=action))
    return transfer_module.TransferPlan(direction="pull", items=items)


@files_cmd.command("search")
@click.argument("path", default=None, required=False)
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
@click.option("--name", default=None, help="Filter by filename (partial match or glob pattern).")
@click.option(
    "--ext",
    "-e",
    "--type",
    "extensions",
    multiple=True,
    help="Only show files with this extension (repeatable).",
)
@click.option("--min-size", default=None, help="Minimum file size, e.g. 10MB.")
@click.option("--max-size", default=None, help="Maximum file size, e.g. 100MB.")
@click.option(
    "--after",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only files modified on or after this date (YYYY-MM-DD).",
)
@click.option(
    "--before",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only files modified on or before this date (YYYY-MM-DD).",
)
@click.option(
    "--preset",
    type=click.Choice(search_module.PRESET_NAMES),
    default=None,
    help="Quick discovery preset.",
)
@click.option(
    "--sort",
    "-S",
    "sort_by",
    type=click.Choice(search_module.SORT_KEYS),
    default="path",
    help="Sort by name, size, date, or path.",
)
@click.option("--reverse", "-r", is_flag=True, help="Reverse the sort order.")
@click.option("--regex", "name_regex", default=None, help="Regex filename match (cannot combine with --name).")
@click.option("--mime", default=None, help="MIME category filter: image|video|audio|document|archive (cannot combine with --ext/--type).")
@click.option("--limit", type=int, default=None, help="Cap results at N entries (applied after sorting).")
@click.option("--output", "output_path", default=None, help="Write results to FILE.")
@click.option(
    "--format", "output_format",
    type=click.Choice(["csv", "txt"]),
    default=None,
    help="Output format for --output: csv or txt.",
)
@click.option("--pull-to", "pull_to_dir", default=None, help="Pull all matching files to DIR.")
@click.option(
    "--pull-conflict",
    type=click.Choice([transfer_module.CONFLICT_SKIP, transfer_module.CONFLICT_OVERWRITE, transfer_module.CONFLICT_RENAME]),
    default=transfer_module.CONFLICT_SKIP,
    help="Conflict resolution for --pull-to (default: skip).",
)
@click.option("--no-verify", "pull_no_verify", is_flag=True, help="Skip verification after --pull-to.")
def files_search(path, serial, name, extensions, min_size, max_size, after, before, preset, sort_by, reverse, name_regex, mime, limit, output_path, output_format, pull_to_dir, pull_conflict, pull_no_verify):
    """Search for files on the device (default root: /sdcard)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    if name and name_regex:
        click.echo("Error: --name and --regex are mutually exclusive.", err=True)
        sys.exit(1)
    if extensions and mime:
        click.echo("Error: --ext/--type and --mime are mutually exclusive.", err=True)
        sys.exit(1)
    if (output_path is None) != (output_format is None):
        missing = "--format" if output_path is not None else "--output"
        click.echo(f"Error: {missing} is required when using --output/--format together.", err=True)
        sys.exit(1)

    kwargs = {}
    root = path
    if preset:
        preset_root, preset_kwargs = search_module.preset_filters(preset)
        kwargs.update(preset_kwargs)
        if root is None:
            root = preset_root

    if root is None:
        root = search_module.DEFAULT_ROOT

    if name:
        if "*" not in name and "?" not in name:
            name = f"*{name}*"
        kwargs["name_pattern"] = name

    if extensions:
        kwargs["extensions"] = [e.lower().lstrip(".") for e in extensions]

    if name_regex:
        kwargs["name_regex"] = name_regex

    if mime:
        try:
            kwargs["extensions"] = search_module.mime_to_extensions(mime)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    if min_size:
        kwargs["min_size"] = parse_size(min_size)

    if max_size:
        kwargs["max_size"] = parse_size(max_size)

    if after:
        kwargs["after"] = after

    if before:
        kwargs["before"] = before

    try:
        results = search_module.search_files(client, serial, root, **kwargs)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    results = search_module.sort_results(results, by=sort_by, reverse=reverse)

    if limit is not None:
        results = results[:limit]

    if not results:
        click.echo("No files found.")
        return

    for result in results:
        click.echo(_format_result_line(result))

    if output_path:
        _write_search_export(results, output_format, output_path)
        click.echo(f"Results exported to {output_path}.")

    if pull_to_dir:
        os.makedirs(pull_to_dir, exist_ok=True)
        plan = _search_results_to_plan(results, pull_to_dir, pull_conflict)
        _print_plan_summary(plan)
        if not plan.to_transfer:
            return
        click.echo(f"Pulling {plan.total_files} file(s), {format_bytes(plan.total_bytes)}...")

        def on_progress(progress):
            click.echo(_format_progress_line(progress), nl=False)

        try:
            with get_sleep_inhibitor("DroidBridge file search pull"):
                progress = transfer_module.execute_plan(
                    client, serial, plan, progress_callback=on_progress
                )
        except AdbError as exc:
            click.echo(f"\nError during pull: {exc}", err=True)
            sys.exit(1)
        click.echo()
        _report_failed_items(progress.failed)
        if not pull_no_verify:
            verification = transfer_module.verify_pull(plan)
            if not _report_verification(verification):
                sys.exit(1)
        if progress.failed:
            sys.exit(1)


@files_cmd.command("rename")
@click.argument("old_path")
@click.argument("new_path")
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
def files_rename(old_path, new_path, serial):
    """Rename/move OLD_PATH to NEW_PATH on the device."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        files_module.rename_path(client, serial, old_path, new_path)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Renamed {old_path} -> {new_path}")


@files_cmd.command("delete")
@click.argument("paths", nargs=-1, required=True)
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
@click.option(
    "--backup-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Verify a backup of PATHS exists here before allowing deletion.",
)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def files_delete(paths, serial, backup_dir, yes):
    """Permanently delete one or more files/folders from the device."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        plan = files_module.build_delete_plan(client, serial, list(paths))
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if plan.file_count == 0:
        click.echo("Nothing to delete.")
        return

    for path in plan.paths:
        click.echo(f"  {path}")
    file_word = "file" if plan.file_count == 1 else "files"
    click.echo(f"This will permanently delete {plan.file_count} {file_word}, {format_bytes(plan.total_size)}.")

    if backup_dir:
        missing = files_module.verify_backup(client, serial, plan.paths, backup_dir)
        if missing:
            click.echo(
                f"Error: {len(missing)} file(s) are not backed up at {backup_dir}.",
                err=True,
            )
            sys.exit(1)

    if not yes:
        confirm = click.prompt("Type 'YES DELETE' to confirm", default="", show_default=False)
        if confirm != "YES DELETE":
            click.echo("Aborted.")
            return

    files_module.delete_paths(client, serial, plan.paths)

    verification = files_module.verify_deletion(client, serial, plan.paths)
    if verification.remaining:
        click.echo(f"Warning: {len(verification.remaining)} path(s) could not be deleted:", err=True)
        for path in verification.remaining:
            click.echo(f"  {path}", err=True)
        sys.exit(1)

    click.echo(f"Deleted {len(verification.deleted)} path(s), {format_bytes(plan.total_size)}.")


@cli.group("transfer")
def transfer_cmd():
    """Transfer files between this computer and the device."""


def _print_plan_summary(plan):
    if plan.already_present:
        click.echo(f"Skipping {len(plan.already_present)} file(s) already present (resume).")
    if plan.conflicts_skipped:
        click.echo(
            f"Skipping {len(plan.conflicts_skipped)} file(s) due to conflicts "
            "(use --conflict overwrite or --conflict rename to transfer them)."
        )


def _format_progress_line(progress):
    return (
        f"\r  {progress.done_files}/{progress.total_files} files | "
        f"{format_bytes(progress.done_bytes)} / {format_bytes(progress.total_bytes)} | "
        f"{format_bytes(progress.speed_bps)}/s | ETA {format_duration(progress.eta_seconds)}"
    )


def _report_verification(result):
    if result.ok:
        click.echo(f"Verified: {result.actual_files} file(s), {format_bytes(result.actual_bytes)}.")
        return True

    click.echo(
        f"Verification FAILED: expected {result.expected_files} file(s) "
        f"({format_bytes(result.expected_bytes)}), found {result.actual_files} file(s) "
        f"({format_bytes(result.actual_bytes)}).",
        err=True,
    )
    return False


def _write_report(report, filename_stem):
    content = to_txt(report)
    out = Path("session_logs") / "reports" / f"{filename_stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def _report_failed_items(failed):
    if not failed:
        return
    click.echo(f"{len(failed)} file(s) failed:", err=True)
    for f in failed:
        click.echo(f"  {f.item.source} -> {f.item.dest}: {f.error}", err=True)


def _slug(label):
    return label.lower().replace(" ", "_")


def _build_backup_verification(profile_name):
    """Build a backup-verification report and result for `profile_name` (spec §6.3).

    Compares the profile's last recorded `BackupRecord` against a fresh walk of
    its destination folder. Exits 1 with an error message if the profile or its
    history is missing.
    """
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, profile_name)
    if profile is None:
        click.echo(f"Error: profile {profile_name!r} not found.", err=True)
        sys.exit(1)

    history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
    record = backup_module.last_backup(history, profile_name)
    if record is None:
        click.echo(
            f"No backups recorded for profile {profile_name!r}. Run `backup run --profile {profile_name}` first.",
            err=True,
        )
        sys.exit(1)

    actual_files, actual_bytes = backup_module.measure_destination(record.destination)
    result = transfer_module.VerificationResult(
        expected_files=record.file_count,
        expected_bytes=record.total_bytes,
        actual_files=actual_files,
        actual_bytes=actual_bytes,
    )
    report = backup_reports.build_backup_verification_report(profile_name, result)
    return report, result


_CONFLICT_OPTION = click.option(
    "--conflict",
    type=click.Choice(transfer_module.CONFLICT_MODES),
    default=transfer_module.CONFLICT_SKIP,
    help="How to handle files that already exist with different content (default: skip).",
)
_NO_VERIFY_OPTION = click.option(
    "--no-verify", is_flag=True, help="Skip post-transfer verification."
)
_RETRY_OPTION = click.option(
    "--retry",
    type=int,
    default=3,
    help="Retries for a failed file before giving up (default: 3, 0 to disable).",
)
_SERIAL_OPTION = click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
_DELETE_EXTRAS_OPTION = click.option(
    "--delete-extras",
    is_flag=True,
    help="Remove destination files not present on the source (requires confirmation unless --yes).",
)
_YES_OPTION = click.option(
    "--yes", is_flag=True, help="Skip the 'YES DELETE' confirmation for --delete-extras.",
)


def _confirm_extras(plan, delete_extras, yes, dest_label):
    """List extra_items in dest_label; if --delete-extras, prompt for YES DELETE (unless --yes).
    Returns True if deletion should proceed, False otherwise."""
    if not plan.extra_items:
        return False

    click.echo(
        f"{plan.extra_files} extra file(s) ({format_bytes(plan.extra_bytes)}) in "
        f"{dest_label} not present on the source:"
    )
    for item in plan.extra_items[:20]:
        click.echo(f"  {item.path} ({format_bytes(item.size)})")
    if plan.extra_files > 20:
        click.echo(f"  ... and {plan.extra_files - 20} more")

    if not delete_extras:
        click.echo("(use --delete-extras to remove these)")
        return False

    if yes:
        return True

    confirm = click.prompt(
        "Type 'YES DELETE' to remove these files, or press Enter to keep them",
        default="",
        show_default=False,
    )
    if confirm != "YES DELETE":
        click.echo("Skipping deletion of extra files.")
        return False
    return True


def _report_failed_deletions(failed_deletions):
    for f in failed_deletions:
        click.echo(f"  Failed to delete {f.item.path}: {f.error}", err=True)


@transfer_cmd.command("pull")
@click.argument("remote_path")
@click.argument("local_dir", default=".")
@_SERIAL_OPTION
@_CONFLICT_OPTION
@_NO_VERIFY_OPTION
@_RETRY_OPTION
def transfer_pull(remote_path, local_dir, serial, conflict, no_verify, retry):
    """Pull REMOTE_PATH (a file or folder) from the device into LOCAL_DIR (default: current directory)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        plan = transfer_module.plan_pull(client, serial, remote_path, local_dir, conflict=conflict)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    _print_plan_summary(plan)

    if not plan.to_transfer:
        click.echo("Nothing to transfer.")
        return

    file_word = "file" if plan.total_files == 1 else "files"
    click.echo(f"Pulling {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

    def on_progress(progress):
        click.echo(_format_progress_line(progress), nl=False)

    with get_sleep_inhibitor("DroidBridge file transfer"):
        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress, retry_count=retry)
    click.echo()

    _report_failed_items(progress.failed)

    verification = None
    verified = True
    if not no_verify:
        verification = transfer_module.verify_pull(plan)
        verified = _report_verification(verification)

    report = transfer_reports.build_transfer_report("pull", plan, progress, verification=verification)
    _write_report(report, f"transfer-pull_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    if progress.failed or not verified:
        sys.exit(1)


@transfer_cmd.command("push")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_dir")
@_SERIAL_OPTION
@_CONFLICT_OPTION
@_NO_VERIFY_OPTION
@_RETRY_OPTION
def transfer_push(local_path, remote_dir, serial, conflict, no_verify, retry):
    """Push LOCAL_PATH (a file or folder) to REMOTE_DIR on the device."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        plan = transfer_module.plan_push(client, serial, local_path, remote_dir, conflict=conflict)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    _print_plan_summary(plan)

    if not plan.to_transfer:
        click.echo("Nothing to transfer.")
        return

    file_word = "file" if plan.total_files == 1 else "files"
    click.echo(f"Pushing {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

    def on_progress(progress):
        click.echo(_format_progress_line(progress), nl=False)

    with get_sleep_inhibitor("DroidBridge file transfer"):
        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress, retry_count=retry)
    click.echo()

    _report_failed_items(progress.failed)

    verification = None
    verified = True
    if not no_verify:
        verification = transfer_module.verify_push(client, serial, plan, remote_dir)
        verified = _report_verification(verification)

    report = transfer_reports.build_transfer_report("push", plan, progress, verification=verification)
    _write_report(report, f"transfer-push_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    if progress.failed or not verified:
        sys.exit(1)


@transfer_cmd.group("mirror")
def transfer_mirror():
    """Sync (mirror) a folder between this computer and the device."""


@transfer_mirror.command("pull")
@click.argument("remote_path")
@click.argument("local_dir", default=".")
@_SERIAL_OPTION
@_RETRY_OPTION
@_NO_VERIFY_OPTION
@_DELETE_EXTRAS_OPTION
@_YES_OPTION
def transfer_mirror_pull(remote_path, local_dir, serial, retry, no_verify, delete_extras, yes):
    """Mirror REMOTE_PATH (a device folder) into LOCAL_DIR (default: current directory).

    Pulls new/changed files (always overwriting), and optionally removes local files
    that no longer exist on the device (--delete-extras requires 'YES DELETE' confirmation).
    """
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        plan = transfer_module.plan_mirror_pull(client, serial, remote_path, local_dir)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    _print_plan_summary(plan)
    do_delete = _confirm_extras(plan, delete_extras, yes, local_dir)

    if not plan.to_transfer and not plan.extra_items:
        click.echo("Nothing to transfer or mirror.")
        report = transfer_reports.build_transfer_report(
            "mirror-pull", plan, transfer_module.TransferProgress(0, 0),
        )
        _write_report(report, f"transfer-mirror-pull_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        return

    if plan.to_transfer:
        file_word = "file" if plan.total_files == 1 else "files"
        click.echo(f"Pulling {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

    def on_progress(progress):
        click.echo(_format_progress_line(progress), nl=False)

    with get_sleep_inhibitor("DroidBridge file transfer"):
        result = transfer_module.execute_mirror(
            client, serial, plan,
            progress_callback=on_progress if plan.to_transfer else None,
            retry_count=retry,
            delete_extras=do_delete,
        )
    if plan.to_transfer:
        click.echo()

    _report_failed_items(result.progress.failed)

    if do_delete:
        click.echo(f"Deleted {result.deleted_files} extra file(s), {format_bytes(result.deleted_bytes)}.")
        _report_failed_deletions(result.failed_deletions)

    verification = None
    verified = True
    if not no_verify:
        verification = transfer_module.verify_pull(plan)
        verified = _report_verification(verification)

    report = transfer_reports.build_transfer_report(
        "mirror-pull", plan, result.progress, verification=verification, mirror_result=result,
    )
    _write_report(report, f"transfer-mirror-pull_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    if result.progress.failed or result.failed_deletions or not verified:
        sys.exit(1)


@transfer_mirror.command("push")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_dir")
@_SERIAL_OPTION
@_RETRY_OPTION
@_NO_VERIFY_OPTION
@_DELETE_EXTRAS_OPTION
@_YES_OPTION
def transfer_mirror_push(local_path, remote_dir, serial, retry, no_verify, delete_extras, yes):
    """Mirror LOCAL_PATH (a local folder) to REMOTE_DIR on the device.

    Pushes new/changed files (always overwriting), and optionally removes device files
    that no longer exist locally (--delete-extras requires 'YES DELETE' confirmation).
    """
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        plan = transfer_module.plan_mirror_push(client, serial, local_path, remote_dir)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    _print_plan_summary(plan)
    do_delete = _confirm_extras(plan, delete_extras, yes, remote_dir)

    if not plan.to_transfer and not plan.extra_items:
        click.echo("Nothing to transfer or mirror.")
        report = transfer_reports.build_transfer_report(
            "mirror-push", plan, transfer_module.TransferProgress(0, 0),
        )
        _write_report(report, f"transfer-mirror-push_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        return

    if plan.to_transfer:
        file_word = "file" if plan.total_files == 1 else "files"
        click.echo(f"Pushing {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

    def on_progress(progress):
        click.echo(_format_progress_line(progress), nl=False)

    with get_sleep_inhibitor("DroidBridge file transfer"):
        result = transfer_module.execute_mirror(
            client, serial, plan,
            progress_callback=on_progress if plan.to_transfer else None,
            retry_count=retry,
            delete_extras=do_delete,
        )
    if plan.to_transfer:
        click.echo()

    _report_failed_items(result.progress.failed)

    if do_delete:
        click.echo(f"Deleted {result.deleted_files} extra file(s), {format_bytes(result.deleted_bytes)}.")
        _report_failed_deletions(result.failed_deletions)

    verification = None
    verified = True
    if not no_verify:
        verification = transfer_module.verify_push(client, serial, plan, remote_dir)
        verified = _report_verification(verification)

    report = transfer_reports.build_transfer_report(
        "mirror-push", plan, result.progress, verification=verification, mirror_result=result,
    )
    _write_report(report, f"transfer-mirror-push_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    if result.progress.failed or result.failed_deletions or not verified:
        sys.exit(1)


@cli.group("whatsapp")
def whatsapp_cmd():
    """WhatsApp / WhatsApp Business media analysis, backup, and cleanup."""


_APP_OPTION = click.option(
    "--app",
    type=click.Choice(("whatsapp", "business", "all")),
    default="all",
    help="Which app to scan: whatsapp, business, or all (default: all).",
)


def _select_installs(installs, app):
    if app == "all":
        return installs
    package = "com.whatsapp" if app == "whatsapp" else "com.whatsapp.w4b"
    return [install for install in installs if install.package == package]


_BY_OPTION = click.option(
    "--by",
    "group_by",
    type=click.Choice(("folder", "year", "extension")),
    default="folder",
    help="How to group the report: folder (default), year (year-month), or extension.",
)


@whatsapp_cmd.command("scan")
@_SERIAL_OPTION
@_APP_OPTION
@_BY_OPTION
def whatsapp_scan(serial, app, group_by):
    """Scan WhatsApp media folders and report file counts/sizes."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)

    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    for install in installs:
        click.echo(f"{install.label} ({install.package}) -- {install.media_path}")

        media_files = whatsapp_module.scan_media(client, serial, install)
        if not media_files:
            click.echo("  (no media found)")
            click.echo()
            continue

        if group_by == "year":
            summary = whatsapp_module.summarize_by_year_month(media_files)
            for group in summary:
                click.echo(
                    f"  {group.year_month:<10} {group.file_count:>6} files  "
                    f"{format_bytes(group.total_size):>10}"
                )

            total_files = sum(group.file_count for group in summary)
            total_size = sum(group.total_size for group in summary)
            click.echo(f"  {'TOTAL':<10} {total_files:>6} files  {format_bytes(total_size):>10}")
        elif group_by == "extension":
            summary = whatsapp_module.summarize_by_extension(media_files)
            for group in summary:
                click.echo(
                    f"  {group.extension:<10} {group.file_count:>6} files  "
                    f"{format_bytes(group.total_size):>10}"
                )

            total_files = sum(group.file_count for group in summary)
            total_size = sum(group.total_size for group in summary)
            click.echo(f"  {'TOTAL':<10} {total_files:>6} files  {format_bytes(total_size):>10}")
        else:
            summary = whatsapp_module.summarize_by_folder(media_files)
            for group in summary:
                click.echo(
                    f"  {group.folder_type:<28} {group.section:<10} "
                    f"{group.file_count:>6} files  {format_bytes(group.total_size):>10}"
                )

            total_files = sum(group.file_count for group in summary)
            total_size = sum(group.total_size for group in summary)
            click.echo(
                f"  {'TOTAL':<28} {'':<10} {total_files:>6} files  {format_bytes(total_size):>10}"
            )

        report = whatsapp_reports.build_media_inventory_report(media_files)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _write_report(report, f"whatsapp-scan_{_slug(install.label)}_{timestamp}")
        click.echo("Report saved to session_logs/reports/")
        click.echo()


_DEFAULT_CUTOFF = "2024-09-01"


@whatsapp_cmd.command("analyze")
@_SERIAL_OPTION
@_APP_OPTION
@click.option(
    "--cutoff",
    default=_DEFAULT_CUTOFF,
    show_default=True,
    help="Cutoff date (YYYY-MM-DD) for pre/post comparison.",
)
def whatsapp_analyze(serial, app, cutoff):
    """Analyze WhatsApp media with a pre/post cutoff-date comparison."""
    try:
        cutoff_date = datetime.strptime(cutoff, "%Y-%m-%d").date()
    except ValueError:
        click.echo(f"Error: invalid --cutoff date {cutoff!r}, expected YYYY-MM-DD.", err=True)
        sys.exit(1)

    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)

    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    for install in installs:
        click.echo(f"{install.label} ({install.package}) -- {install.media_path}")
        click.echo(f"Cutoff date: {cutoff_date.isoformat()}")
        click.echo()

        media_files = whatsapp_module.scan_media(client, serial, install)
        if not media_files:
            click.echo("  (no media found)")
            click.echo()
            continue

        summary = whatsapp_module.summarize_by_cutoff(media_files, cutoff_date)

        click.echo(f"  {'Folder Type':<28} {'Pre-cutoff':>20} {'Post-cutoff':>20} {'Unknown date':>20}")
        for group in summary:
            click.echo(
                f"  {group.folder_type:<28} "
                f"{group.pre_count:>6} files {format_bytes(group.pre_size):>10} "
                f"{group.post_count:>6} files {format_bytes(group.post_size):>10} "
                f"{group.unknown_count:>6} files {format_bytes(group.unknown_size):>10}"
            )

        total_pre_count = sum(group.pre_count for group in summary)
        total_pre_size = sum(group.pre_size for group in summary)
        total_post_count = sum(group.post_count for group in summary)
        total_post_size = sum(group.post_size for group in summary)
        total_unknown_count = sum(group.unknown_count for group in summary)
        total_unknown_size = sum(group.unknown_size for group in summary)
        click.echo(
            f"  {'TOTAL':<28} "
            f"{total_pre_count:>6} files {format_bytes(total_pre_size):>10} "
            f"{total_post_count:>6} files {format_bytes(total_post_size):>10} "
            f"{total_unknown_count:>6} files {format_bytes(total_unknown_size):>10}"
        )
        click.echo()
        click.echo(f"  Deletable (pre-cutoff): {total_pre_count} files, {format_bytes(total_pre_size)}")
        click.echo()
        report = whatsapp_reports.build_cutoff_comparison_report(media_files, cutoff_date)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _write_report(report, f"whatsapp-analyze_{_slug(install.label)}_{timestamp}")
        click.echo("Report saved to session_logs/reports/")
        click.echo()


@whatsapp_cmd.command("save-status")
@click.option(
    "--dest",
    required=True,
    type=click.Path(file_okay=False),
    help="Destination folder to save current status images/videos into.",
)
@_SERIAL_OPTION
@_APP_OPTION
@_CONFLICT_OPTION
@_NO_VERIFY_OPTION
def whatsapp_save_status(dest, serial, app, conflict, no_verify):
    """Save current WhatsApp / WhatsApp Business status images and videos to DEST."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)

    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    plan = whatsapp_module.plan_save_statuses(client, serial, installs, dest, conflict=conflict)

    _print_plan_summary(plan)

    if not plan.to_transfer:
        click.echo("Nothing to transfer.")
        return

    file_word = "file" if plan.total_files == 1 else "files"
    click.echo(f"Pulling {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

    def on_progress(progress):
        click.echo(_format_progress_line(progress), nl=False)

    with get_sleep_inhibitor("DroidBridge file transfer"):
        transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress)
    click.echo()

    if no_verify:
        return

    if not _report_verification(transfer_module.verify_pull(plan)):
        sys.exit(1)


@whatsapp_cmd.command("backup")
@click.option(
    "--dest",
    required=True,
    type=click.Path(file_okay=False),
    help="Destination folder for the backup.",
)
@_SERIAL_OPTION
@_APP_OPTION
@click.option(
    "--type",
    "types",
    default=None,
    help=(
        "Comma-separated media types to back up selectively "
        f"({', '.join(sorted(whatsapp_module.BACKUP_TYPES))}). Default: all."
    ),
)
@_CONFLICT_OPTION
@_NO_VERIFY_OPTION
def whatsapp_backup(dest, serial, app, types, conflict, no_verify):
    """Back up WhatsApp / WhatsApp Business media to DEST, mirroring the on-device folder layout."""
    type_set = None
    if types:
        type_set = set()
        for name in types.split(","):
            name = name.strip()
            if name not in whatsapp_module.BACKUP_TYPES:
                valid = ", ".join(sorted(whatsapp_module.BACKUP_TYPES))
                click.echo(f"Error: invalid --type {name!r}. Valid types: {valid}.", err=True)
                sys.exit(1)
            type_set.add(whatsapp_module.BACKUP_TYPES[name])

    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)

    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    plan = whatsapp_module.plan_backup(client, serial, installs, dest, types=type_set, conflict=conflict)

    _print_plan_summary(plan)

    if not plan.to_transfer:
        click.echo("Nothing to transfer.")
        return

    file_word = "file" if plan.total_files == 1 else "files"
    click.echo(f"Pulling {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

    def on_progress(progress):
        click.echo(_format_progress_line(progress), nl=False)

    with get_sleep_inhibitor("DroidBridge file transfer"):
        transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress)
    click.echo()

    if no_verify:
        return

    if not _report_verification(transfer_module.verify_pull(plan)):
        sys.exit(1)


@whatsapp_cmd.command("restore")
@click.option(
    "--src",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Backup folder created by `whatsapp backup` (containing <App>/Media/...).",
)
@_SERIAL_OPTION
@_APP_OPTION
@_CONFLICT_OPTION
@_NO_VERIFY_OPTION
def whatsapp_restore(src, serial, app, conflict, no_verify):
    """Restore media from a `whatsapp backup` folder back onto the device (media only, spec §4.9)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)

    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    any_failed = False
    for install in installs:
        plan = whatsapp_module.plan_restore(client, serial, install, src, conflict=conflict)

        if not plan.items:
            click.echo(f"{install.label}: no backup found at {os.path.join(src, install.label, 'Media')}")
            continue

        click.echo(f"{install.label} ({install.package}) -- {install.media_path}")
        _print_plan_summary(plan)

        if not plan.to_transfer:
            click.echo("Nothing to transfer.")
            click.echo()
            continue

        file_word = "file" if plan.total_files == 1 else "files"
        click.echo(f"Pushing {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

        def on_progress(progress):
            click.echo(_format_progress_line(progress), nl=False)

        with get_sleep_inhibitor("DroidBridge file transfer"):
            transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress)
        click.echo()

        if not no_verify:
            result = transfer_module.verify_push(client, serial, plan, install.media_path)
            if not _report_verification(result):
                any_failed = True

        click.echo()

    if any_failed:
        sys.exit(1)


@whatsapp_cmd.command("organize")
@click.option(
    "--src",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Backup media folder to organize (e.g. <backup>/WhatsApp/Media/WhatsApp Images).",
)
@click.option(
    "--type",
    "type_name",
    required=True,
    type=click.Choice(sorted(set(whatsapp_module.ORGANIZE_DATE_TYPES) | {"documents"})),
    help="Media type at --src; determines the organization structure to apply.",
)
def whatsapp_organize(src, type_name):
    """Reorganize a `whatsapp backup` media folder into a clean date/section structure (spec §4.4)."""
    renames = whatsapp_module.fix_filenames(src)
    if renames:
        word = "filename" if len(renames) == 1 else "filenames"
        click.echo(f"Fixed {len(renames)} {word} (double dots / missing extensions).")

    if type_name == "documents":
        plan = whatsapp_module.plan_organize_documents(src)
    else:
        sectioned = whatsapp_module.ORGANIZE_DATE_TYPES[type_name]
        plan = whatsapp_module.plan_organize_by_date(src, sectioned=sectioned)

    if not plan.items:
        click.echo("Nothing to organize.")
        return

    file_word = "file" if plan.total_files == 1 else "files"
    click.echo(f"Organizing {plan.total_files} {file_word}...")
    whatsapp_module.execute_organize_plan(plan)
    click.echo(f"Done. See {whatsapp_module._organized_dest_root(src)}")


@whatsapp_cmd.command("fix-extensions")
@click.option(
    "--path",
    "src_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Local backup folder to fix (collapse double dots, sniff missing extensions).",
)
def whatsapp_fix_extensions(src_dir):
    """Fix double-dot and missing-extension filenames in a backup folder (spec §4.5)."""
    renames = whatsapp_module.fix_filenames(src_dir)
    if not renames:
        click.echo("No filenames needed fixing.")
        return
    for old_path, new_path in renames:
        click.echo(f"{old_path} -> {new_path}")
    word = "filename" if len(renames) == 1 else "filenames"
    click.echo(f"Fixed {len(renames)} {word}.")


@whatsapp_cmd.command("delete")
@_SERIAL_OPTION
@_APP_OPTION
@click.option(
    "--before",
    required=True,
    help="Delete media dated before this date (YYYY-MM-DD).",
)
@click.option(
    "--keep",
    "keep_types",
    default=None,
    help=(
        "Comma-separated media types to keep regardless of date "
        f"({', '.join(sorted(whatsapp_module.BACKUP_TYPES))})."
    ),
)
@click.option(
    "--backup-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Backup folder created by `whatsapp backup` - deletion is blocked unless every file is verified here.",
)
def whatsapp_delete(serial, app, before, keep_types, backup_dir):
    """Delete WhatsApp media dated before --before, after verifying a backup exists (spec §4.6)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        before_date = datetime.strptime(before, "%Y-%m-%d").date()
    except ValueError:
        click.echo(f"Error: invalid --before date {before!r}, expected YYYY-MM-DD.", err=True)
        sys.exit(1)

    keep_set = None
    if keep_types:
        keep_set = set()
        for name in keep_types.split(","):
            name = name.strip()
            if name not in whatsapp_module.BACKUP_TYPES:
                valid = ", ".join(sorted(whatsapp_module.BACKUP_TYPES))
                click.echo(f"Error: invalid --keep {name!r}. Valid types: {valid}.", err=True)
                sys.exit(1)
            keep_set.add(whatsapp_module.BACKUP_TYPES[name])

    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)

    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    plans = []
    for install in installs:
        media_files = whatsapp_module.scan_media(client, serial, install)
        plan = whatsapp_module.plan_delete(media_files, before_date, keep_types=keep_set)
        plans.append((install, plan, media_files))

    total_files = sum(plan.total_files for _, plan, _ in plans)
    if total_files == 0:
        click.echo("Nothing to delete.")
        return

    before_storage = device_module.get_storage_breakdown(client, serial)

    for install, plan, _ in plans:
        if plan.total_files == 0:
            continue

        click.echo(f"{install.label} ({install.package}) -- {install.media_path}")
        for group in whatsapp_module.summarize_by_folder(plan.to_delete):
            click.echo(
                f"  {group.folder_type:<28} {group.section:<10} "
                f"{group.file_count:>6} files  {format_bytes(group.total_size):>10}"
            )
        for group in whatsapp_module.summarize_by_year_month(plan.to_delete):
            click.echo(
                f"  {group.year_month:<10} {group.file_count:>6} files  {format_bytes(group.total_size):>10}"
            )
        file_word = "file" if plan.total_files == 1 else "files"
        click.echo(f"  Total to delete: {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}")
        click.echo(f"  Keeping: {len(plan.kept)} file(s)")
        click.echo()

        preview_report = deletion_reports.build_deletion_preview_report(plan)
        _write_report(preview_report, f"whatsapp-deletion-preview_{_slug(install.label)}_{timestamp}")

    missing_backup = False
    for install, plan, _ in plans:
        if plan.total_files == 0:
            continue
        missing = whatsapp_module.verify_backup_exists(install, backup_dir, plan.to_delete)
        if missing:
            click.echo(
                f"Error: {len(missing)} file(s) for {install.label} are not backed up at {backup_dir}. "
                f"Run `whatsapp backup --dest {backup_dir}` first.",
                err=True,
            )
            missing_backup = True

    if missing_backup:
        sys.exit(1)

    total_bytes = sum(plan.total_bytes for _, plan, _ in plans)
    file_word = "file" if total_files == 1 else "files"
    click.echo(f"This will permanently delete {total_files} {file_word}, {format_bytes(total_bytes)}.")
    confirm = click.prompt("Type 'YES DELETE' to confirm", default="", show_default=False)
    if confirm != "YES DELETE":
        click.echo("Aborted.")
        return

    any_remaining = False
    for install, plan, media_files in plans:
        if plan.total_files == 0:
            continue
        whatsapp_module.execute_delete_plan(client, serial, plan)
        result = whatsapp_module.verify_delete(client, serial, install, plan)
        click.echo(f"{install.label}: deleted {result.deleted} file(s), {len(result.remaining)} remaining.")
        if result.remaining:
            any_remaining = True

        result_report = deletion_reports.build_deletion_result_report(plan, result)
        _write_report(result_report, f"whatsapp-deletion-result_{_slug(install.label)}_{timestamp}")

        cleanup_report = whatsapp_reports.build_cleanup_comparison_report(media_files, result.after_files)
        _write_report(cleanup_report, f"whatsapp-cleanup-comparison_{_slug(install.label)}_{timestamp}")

    after_storage = device_module.get_storage_breakdown(client, serial)
    storage_report = deletion_reports.build_storage_comparison_report(before_storage, after_storage)
    _write_report(storage_report, f"whatsapp-storage-comparison_{timestamp}")

    click.echo("Reports saved to session_logs/reports/")

    if any_remaining:
        sys.exit(1)


@whatsapp_cmd.command("backup-db")
@click.option(
    "--dest",
    required=True,
    type=click.Path(file_okay=False),
    help="Destination folder for the database backup.",
)
@_SERIAL_OPTION
@_APP_OPTION
@_CONFLICT_OPTION
@_NO_VERIFY_OPTION
def whatsapp_backup_db(dest, serial, app, conflict, no_verify):
    """Back up WhatsApp Databases/, Backups/, and accounts/ folders to DEST (spec §4.8).

    Database restore is intentionally out of scope for this tool - see the
    warning printed below.
    """
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)

    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    plan = whatsapp_module.plan_backup_db(client, serial, installs, dest, conflict=conflict)

    _print_plan_summary(plan)

    if not plan.to_transfer:
        click.echo("Nothing to transfer.")
        return

    encrypted = sum(1 for item in plan.to_transfer if whatsapp_module.is_encrypted_db_file(item.source))
    click.echo(f"{encrypted}/{plan.total_files} file(s) are encrypted (.crypt12/.crypt14/.crypt15).")
    click.echo(whatsapp_module.MSGSTORE_WARNING)

    file_word = "file" if plan.total_files == 1 else "files"
    click.echo(f"Pulling {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

    def on_progress(progress):
        click.echo(_format_progress_line(progress), nl=False)

    with get_sleep_inhibitor("DroidBridge file transfer"):
        transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress)
    click.echo()

    if no_verify:
        return

    if not _report_verification(transfer_module.verify_pull(plan)):
        sys.exit(1)


@cli.group("storage")
def storage_cmd():
    """Analyze storage usage: full breakdown, apps, media, large files, and cleanup suggestions."""


_STORAGE_CATEGORY_LABELS = (
    ("apps", "Apps"),
    ("app_data", "App Data"),
    ("app_cache", "App Cache"),
    ("photos", "Photos"),
    ("videos", "Videos"),
    ("audio", "Audio"),
    ("downloads", "Downloads"),
    ("system", "System"),
    ("other", "Other"),
)


@storage_cmd.command("analyze")
@_SERIAL_OPTION
def storage_analyze(serial):
    """Full storage breakdown: totals, usage bar, and category breakdown (spec §5.1)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    overview = storage_module.get_storage_overview(client, serial)

    click.echo(f"Total:  {format_size_kb(overview.total_kb)}")
    click.echo(f"Used:   {format_size_kb(overview.used_kb)}")
    click.echo(f"Free:   {format_size_kb(overview.free_kb)}")
    click.echo(format_bar(overview.used_kb, overview.total_kb))
    click.echo()
    click.echo("Breakdown:")
    for key, label in _STORAGE_CATEGORY_LABELS:
        if key in overview.categories:
            click.echo(f"  {label:<10} {format_bytes(overview.categories[key]):>10}")


@storage_cmd.command("apps")
@_SERIAL_OPTION
@click.option("--top", "top_n", type=int, default=20, show_default=True, help="Show the top N apps by total size.")
@click.option("--all", "show_all", is_flag=True, help="Show all apps, not just the top N.")
@click.option("--system", "filter_kind", flag_value="system", default=None, help="Show only system apps.")
@click.option("--user", "filter_kind", flag_value="user", help="Show only user-installed apps.")
def storage_apps(serial, top_n, show_all, filter_kind):
    """List installed apps by storage usage (APK + data + cache), descending (spec §5.2)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    apps = storage_module.get_app_storage(client, serial)

    if filter_kind == "system":
        apps = [a for a in apps if a.is_system]
    elif filter_kind == "user":
        apps = [a for a in apps if not a.is_system]

    apps = storage_module.top_space_consumers(apps, n=len(apps))
    if not show_all:
        apps = apps[:top_n]

    if not apps:
        click.echo("No apps found.")
        return

    for app in apps:
        kind = "system" if app.is_system else "user"
        click.echo(
            f"{app.package:<40} total={format_bytes(app.total_size):>10}  "
            f"apk={format_bytes(app.apk_size):>10}  data={format_bytes(app.data_size):>10}  "
            f"cache={format_bytes(app.cache_size):>10}  ({kind})"
        )


@storage_cmd.command("media")
@click.argument("path", default=None, required=False)
@_SERIAL_OPTION
@click.option(
    "--before",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only include files modified on or before this date (YYYY-MM-DD).",
)
def storage_media(path, serial, before):
    """Analyze media (photos/videos/audio/documents) under PATH (default: /sdcard) (spec §5.3)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    root = path or search_module.DEFAULT_ROOT
    breakdown = storage_module.analyze_media(client, serial, root, before=before)

    click.echo(f"Scanned {root}: {breakdown.total_count} file(s), {format_bytes(breakdown.total_size)}")
    click.echo()
    for media_type, (count, size) in breakdown.categories.items():
        click.echo(f"  {media_type:<12} {count:>6} files  {format_bytes(size):>10}")

    if breakdown.largest_files:
        click.echo()
        click.echo("Largest files:")
        for result in breakdown.largest_files:
            click.echo(f"  {format_bytes(result.size):>10}  {result.path}")

    if breakdown.duplicates:
        click.echo()
        click.echo(f"Duplicates: {len(breakdown.duplicates)} group(s)")
        groups = sorted(breakdown.duplicates, key=lambda g: g[0].size * (len(g) - 1), reverse=True)
        for group in groups[:10]:
            click.echo(f"  {group[0].name} ({format_bytes(group[0].size)}) x{len(group)}")
            for result in group:
                click.echo(f"    {result.path}")
        if len(groups) > 10:
            click.echo(f"  ... and {len(groups) - 10} more group(s)")


@storage_cmd.command("large-files")
@click.argument("path", default=None, required=False)
@_SERIAL_OPTION
@click.option("--min-size", default=None, help="Minimum file size, e.g. 50MB (default: 50MB).")
def storage_large_files(path, serial, min_size):
    """Find files at or above a size threshold under PATH (default: /sdcard, 50MB) (spec §5.4)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    root = path or search_module.DEFAULT_ROOT
    threshold = parse_size(min_size) if min_size else search_module.LARGE_FILE_THRESHOLD

    results = storage_module.find_large_files(client, serial, root, threshold=threshold)

    if not results:
        click.echo("No large files found.")
        return

    for result in results:
        click.echo(_format_result_line(result))


@storage_cmd.command("suggest-cleanup")
@_SERIAL_OPTION
def storage_suggest_cleanup(serial):
    """Suggest cleanup opportunities and their estimated recoverable space (spec §5.5)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    suggestions = storage_module.suggest_cleanup(client, serial)

    if not suggestions:
        click.echo("No cleanup suggestions found.")
        return

    total = 0
    for suggestion in suggestions:
        click.echo(f"{suggestion.title} - estimated {format_bytes(suggestion.estimated_bytes)} recoverable")
        click.echo(f"  {suggestion.description}")
        for item in suggestion.items[:10]:
            click.echo(f"  - {item}")
        if len(suggestion.items) > 10:
            click.echo(f"  ... and {len(suggestion.items) - 10} more")
        click.echo()
        total += suggestion.estimated_bytes

    click.echo(f"Total estimated recoverable: {format_bytes(total)}")


@cli.group("apps")
def apps_cmd():
    """Manage installed apps: list, cache, uninstall, APK extraction, bloatware (Module 8)."""


@apps_cmd.command("list")
@_SERIAL_OPTION
@click.option("--sort", "sort_by", type=click.Choice(apps_module.APP_SORT_KEYS), default="total", show_default=True, help="Sort key.")
@click.option("--reverse/--no-reverse", default=True, show_default=True, help="Sort order (largest/most-recent first by default).")
@click.option("--system", "filter_kind", flag_value="system", default=None, help="Show only system apps.")
@click.option("--user", "filter_kind", flag_value="user", help="Show only user-installed apps.")
@click.option("--top", "top_n", type=int, default=20, show_default=True, help="Show the top N apps.")
@click.option("--all", "show_all", is_flag=True, help="Show all apps, not just the top N.")
def apps_list(serial, sort_by, reverse, filter_kind, top_n, show_all):
    """List installed apps: version, install/update dates, and storage usage (spec §8.1)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    app_list = apps_module.get_apps(client, serial)
    app_list = apps_module.filter_apps(app_list, filter_kind or "all")
    app_list = apps_module.sort_apps(app_list, by=sort_by, reverse=reverse)
    if not show_all:
        app_list = app_list[:top_n]

    if not app_list:
        click.echo("No apps found.")
        return

    for app in app_list:
        kind = "system" if app.is_system else "user"
        disabled = " [disabled]" if app.is_disabled else ""
        installed = app.first_install_time.strftime("%Y-%m-%d") if app.first_install_time else "?"
        updated = app.last_update_time.strftime("%Y-%m-%d") if app.last_update_time else "?"
        click.echo(
            f"{app.package:<40} v{app.version_name or '?':<15} total={format_bytes(app.total_size):>10}  "
            f"installed={installed}  updated={updated}  ({kind}){disabled}"
        )


@apps_cmd.command("trim-cache")
@_SERIAL_OPTION
@click.option(
    "--target",
    default=None,
    help="Amount of cache to free, e.g. 100MB (default: total cache used by all apps).",
)
def apps_trim_cache(serial, target):
    """Trim app caches to free up space (pm trim-caches; safe, system-wide, spec §8.2)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    if target:
        desired_free_bytes = parse_size(target)
    else:
        app_list = apps_module.get_apps(client, serial)
        desired_free_bytes = apps_module.estimate_cache_clear(app_list)

    if desired_free_bytes <= 0:
        click.echo("No cache to trim.")
        return

    apps_module.trim_caches(client, serial, desired_free_bytes)
    click.echo(f"Requested up to {format_bytes(desired_free_bytes)} of cache to be trimmed.")


@apps_cmd.command("reset")
@click.argument("package")
@_SERIAL_OPTION
def apps_reset(package, serial):
    """Fully reset an app's data via `pm clear` (spec §8.2).

    This wipes ALL data for the app (including its cache, logins, and
    settings), the same as "Clear storage" in Android Settings. There is no
    non-root way to clear only the cache for a single app.
    """
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    app_list = apps_module.get_apps(client, serial)
    app = next((a for a in app_list if a.package == package), None)
    if app is None:
        click.echo(f"Error: package {package!r} not found.", err=True)
        sys.exit(1)

    if app.is_system:
        click.echo(f"Error: {package} is a system app; refusing to reset it.", err=True)
        sys.exit(1)

    click.echo(f"This will erase ALL data for {package} (including cache), as if freshly installed.")
    click.echo(f"  Data:  {format_bytes(app.data_size)}")
    click.echo(f"  Cache: {format_bytes(app.cache_size)}")
    confirm = click.prompt("Type 'YES DELETE' to confirm", default="", show_default=False)
    if confirm != "YES DELETE":
        click.echo("Aborted.")
        return

    apps_module.clear_app_data(client, serial, package)
    click.echo(f"Reset {package}.")


@apps_cmd.command("uninstall")
@click.argument("packages", nargs=-1, required=True)
@_SERIAL_OPTION
@click.option("--keep-data", is_flag=True, help="Keep the app's data and cache directories after uninstalling (-k).")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def apps_uninstall(packages, serial, keep_data, yes):
    """Uninstall one or more user apps via `pm uninstall` (spec §8.3). System apps are refused."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    app_list = apps_module.get_apps(client, serial)
    by_package = {a.package: a for a in app_list}

    targets = []
    for package in packages:
        app = by_package.get(package)
        if app is None:
            click.echo(f"Error: package {package!r} not found.", err=True)
            sys.exit(1)
        if app.is_system:
            click.echo(f"Error: {package} is a system app; refusing to uninstall it.", err=True)
            sys.exit(1)
        targets.append(app)

    for app in targets:
        click.echo(f"{app.package:<40} v{app.version_name or '?':<15} {format_bytes(app.total_size):>10}")

    if not yes:
        word = "app" if len(targets) == 1 else "apps"
        if not click.confirm(f"Uninstall {len(targets)} {word}?"):
            click.echo("Aborted.")
            return

    for app in targets:
        apps_module.uninstall_app(client, serial, app.package, keep_data=keep_data)
        click.echo(f"Uninstalled {app.package}.")


@apps_cmd.command("extract-apk")
@click.argument("package")
@click.option("--dest", required=True, type=click.Path(file_okay=False), help="Destination directory for the extracted APK(s).")
@_SERIAL_OPTION
def apps_extract_apk(package, dest, serial):
    """Extract a package's APK file(s) (base + splits) to DEST via `pm path` + pull (spec §8.4)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    apk_info = apps_module.get_apk_info(client, serial, package)
    if not apk_info:
        click.echo(f"Error: no APK found for package {package!r}.", err=True)
        sys.exit(1)

    total = sum(size for _, size in apk_info)
    click.echo(f"{package}: {len(apk_info)} APK file(s), {format_bytes(total)}")

    os.makedirs(dest, exist_ok=True)
    for path, size in apk_info:
        name = path.rsplit("/", 1)[-1]
        local_path = os.path.join(dest, name)
        client.pull(serial, path, local_path)
        click.echo(f"  {name}  {format_bytes(size)}")


@apps_cmd.command("disable")
@click.argument("package")
@_SERIAL_OPTION
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def apps_disable(package, serial, yes):
    """Disable an app via `pm disable-user` (spec §8.5). Reversible with `apps enable`."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    app_list = apps_module.get_apps(client, serial)
    app = next((a for a in app_list if a.package == package), None)
    if app is None:
        click.echo(f"Error: package {package!r} not found.", err=True)
        sys.exit(1)

    if app.is_disabled:
        click.echo(f"{package} is already disabled.")
        return

    kind = "system" if app.is_system else "user"
    click.echo(f"{package} ({kind} app)")
    click.echo("Disabling a system app can affect device functionality. This can be undone with `apps enable`.")
    if not yes and not click.confirm(f"Disable {package}?"):
        click.echo("Aborted.")
        return

    apps_module.disable_app(client, serial, package)
    click.echo(f"Disabled {package}.")


@apps_cmd.command("enable")
@click.argument("package")
@_SERIAL_OPTION
def apps_enable(package, serial):
    """Re-enable a previously disabled app via `pm enable` (spec §8.5)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    app_list = apps_module.get_apps(client, serial)
    app = next((a for a in app_list if a.package == package), None)
    if app is None:
        click.echo(f"Error: package {package!r} not found.", err=True)
        sys.exit(1)

    if not app.is_disabled:
        click.echo(f"{package} is already enabled.")
        return

    apps_module.enable_app(client, serial, package)
    click.echo(f"Enabled {package}.")


@cli.group("backup")
def backup_cmd():
    """Backup profiles, execution, history, and restore (Module 6)."""


@backup_cmd.group("profile")
def backup_profile_cmd():
    """Create, list, inspect, and remove backup profiles (spec §6.1)."""


@backup_profile_cmd.command("add")
@click.argument("name")
@click.option(
    "--source",
    "sources",
    multiple=True,
    required=True,
    help="A device folder/file to back up. Repeat for multiple sources.",
)
@click.option("--dest", required=True, type=click.Path(file_okay=False), help="Local backup destination folder.")
@_CONFLICT_OPTION
def backup_profile_add(name, sources, dest, conflict):
    """Create or update a backup profile."""
    profile = backup_module.BackupProfile(name=name, sources=list(sources), dest=dest, conflict=conflict)
    backup_module.save_profile(backup_module.DEFAULT_PROFILES_PATH, profile)
    click.echo(f"Saved profile {name!r}.")


@backup_profile_cmd.command("list")
def backup_profile_list():
    """List all saved backup profiles."""
    profiles = backup_module.load_profiles(backup_module.DEFAULT_PROFILES_PATH)
    if not profiles:
        click.echo("No backup profiles saved. Create one with `backup profile add`.")
        return

    for profile in profiles.values():
        click.echo(f"{profile.name:<20} {len(profile.sources)} source(s) -> {profile.dest}  (conflict={profile.conflict})")


@backup_profile_cmd.command("show")
@click.argument("name")
def backup_profile_show(name):
    """Show a backup profile's sources, destination, and conflict mode."""
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, name)
    if profile is None:
        click.echo(f"Error: profile {name!r} not found.", err=True)
        sys.exit(1)

    click.echo(f"Profile: {profile.name}")
    click.echo(f"Destination: {profile.dest}")
    click.echo(f"Conflict mode: {profile.conflict}")
    click.echo("Sources:")
    for source in profile.sources:
        click.echo(f"  {source}")


@backup_profile_cmd.command("remove")
@click.argument("name")
def backup_profile_remove(name):
    """Remove a saved backup profile."""
    if not backup_module.delete_profile(backup_module.DEFAULT_PROFILES_PATH, name):
        click.echo(f"Error: profile {name!r} not found.", err=True)
        sys.exit(1)
    click.echo(f"Removed profile {name!r}.")


@backup_cmd.command("run")
@click.option("--profile", "profile_name", required=True, help="Name of a saved backup profile.")
@_NO_VERIFY_OPTION
@_SERIAL_OPTION
def backup_run(profile_name, no_verify, serial):
    """Run a backup using a saved profile: pull new/changed files, verify, and log history (spec §6.2-6.4)."""
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, profile_name)
    if profile is None:
        click.echo(f"Error: profile {profile_name!r} not found.", err=True)
        sys.exit(1)

    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    plan = backup_module.plan_backup(client, serial, profile)
    _print_plan_summary(plan)

    relevant = [i for i in plan.items if i.action != transfer_module.ACTION_SKIP_CONFLICT]
    file_count = len(relevant)
    total_bytes = sum(i.size for i in relevant)

    duration = 0.0
    if plan.to_transfer:
        file_word = "file" if plan.total_files == 1 else "files"
        click.echo(f"Pulling {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

        def on_progress(progress):
            click.echo(_format_progress_line(progress), nl=False)

        start = time.monotonic()
        with get_sleep_inhibitor("DroidBridge backup"):
            transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress)
        click.echo()
        duration = time.monotonic() - start
    else:
        click.echo("Nothing new to back up.")

    verified = False
    if not no_verify:
        verified = _report_verification(transfer_module.verify_pull(plan))
        if not verified:
            for item in backup_module.find_failed_pull_items(plan)[:10]:
                click.echo(f"  FAILED: {item.source}", err=True)

    backup_module.append_history(
        backup_module.DEFAULT_HISTORY_PATH,
        backup_module.BackupRecord(
            profile=profile.name,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            file_count=file_count,
            total_bytes=total_bytes,
            duration_seconds=duration,
            destination=profile.dest,
            verified=verified,
        ),
    )

    if not no_verify and not verified:
        sys.exit(1)


@backup_cmd.command("restore")
@click.option("--profile", "profile_name", required=True, help="Name of a saved backup profile.")
@click.option(
    "--source",
    "sources",
    multiple=True,
    help="Restore only this profile source. Repeat for multiple. Default: all sources.",
)
@click.option(
    "--after",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only restore files last modified on or after this date (YYYY-MM-DD).",
)
@click.option(
    "--before",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only restore files last modified on or before this date (YYYY-MM-DD).",
)
@click.option(
    "--conflict",
    type=click.Choice(transfer_module.CONFLICT_MODES),
    default=None,
    help="How to handle files that already exist with different content (default: the profile's conflict mode).",
)
@_NO_VERIFY_OPTION
@_SERIAL_OPTION
def backup_restore(profile_name, sources, after, before, conflict, no_verify, serial):
    """Restore a profile's local backup copy back onto the device (spec §6.5)."""
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, profile_name)
    if profile is None:
        click.echo(f"Error: profile {profile_name!r} not found.", err=True)
        sys.exit(1)

    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    targets = backup_module.plan_restore(client, serial, profile, sources=list(sources) or None, conflict=conflict)

    any_failed = False
    for target in targets:
        plan = target.plan
        if after or before:
            plan = backup_module.filter_plan_by_date(
                plan, after=after.date() if after else None, before=before.date() if before else None
            )

        click.echo(f"{target.source} -> {target.remote_dir}")
        _print_plan_summary(plan)

        if not plan.to_transfer:
            click.echo("Nothing to transfer.")
            click.echo()
            continue

        file_word = "file" if plan.total_files == 1 else "files"
        click.echo(f"Pushing {plan.total_files} {file_word}, {format_bytes(plan.total_bytes)}...")

        def on_progress(progress):
            click.echo(_format_progress_line(progress), nl=False)

        with get_sleep_inhibitor("DroidBridge backup"):
            transfer_module.execute_plan(client, serial, plan, progress_callback=on_progress)
        click.echo()

        if not no_verify:
            result = transfer_module.verify_push(client, serial, plan, target.remote_dir)
            if not _report_verification(result):
                any_failed = True

        click.echo()

    if any_failed:
        sys.exit(1)


@backup_cmd.command("verify")
@click.option("--profile", "profile_name", required=True, help="Name of a saved backup profile.")
def backup_verify(profile_name):
    """Verify a backup's integrity against its last recorded run (spec §6.3)."""
    report, result = _build_backup_verification(profile_name)
    click.echo(to_txt(report))

    stem = f"backup-verification_{profile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _write_report(report, stem)
    click.echo(f"Report written to session_logs/reports/{stem}.txt")

    if not result.ok:
        sys.exit(1)


def _print_history_record(record):
    status = "verified" if record.verified else "unverified"
    file_word = "file" if record.file_count == 1 else "files"
    click.echo(
        f"{record.timestamp}  {record.profile:<20} {record.file_count} {file_word}, "
        f"{format_bytes(record.total_bytes)}, {format_duration(record.duration_seconds)} "
        f"-> {record.destination} ({status})"
    )


@backup_cmd.command("history")
@click.option("--profile", "profile_name", default=None, help="Show history for a single profile only.")
@click.option(
    "--max-age-days",
    default=7,
    show_default=True,
    help="Flag a profile's last backup as outdated after this many days.",
)
def backup_history(profile_name, max_age_days):
    """Show logged backup runs, outdated status, and change since the previous run (spec §6.4)."""
    history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)

    if profile_name is None:
        if not history:
            click.echo("No backup history yet.")
            return
        for record in history:
            _print_history_record(record)
        return

    matches = [r for r in history if r.profile == profile_name]
    if not matches:
        click.echo(f"No backups recorded for profile {profile_name!r}.")
        return

    for record in matches:
        _print_history_record(record)

    if backup_module.is_outdated(history, profile_name, max_age_days):
        click.echo(f"Outdated: last backup is older than {max_age_days} day(s).")
    else:
        click.echo(f"Up to date: last backup is within {max_age_days} day(s).")

    comparison = backup_module.compare_backups(history, profile_name)
    if comparison:
        click.echo(
            f"Change since previous backup: {comparison['file_count_delta']:+d} file(s), "
            f"{comparison['total_bytes_delta']:+d} byte(s)"
        )


@cli.group("report")
def report_cmd():
    """Generate TXT/HTML/CSV/JSON reports summarizing storage, backups, and WhatsApp media (spec §9)."""


_REPORT_TYPES = (
    "full",
    "storage",
    "top-apps",
    "large-files",
    "storage-trend",
    "whatsapp-inventory",
    "whatsapp-cutoff",
    "whatsapp-filetypes",
    "whatsapp-sections",
    "whatsapp-documents",
    "backup-history",
    "backup-summary",
    "backup-verification",
)

_REPORT_RENDERERS = {"txt": to_txt, "html": to_html, "csv": to_csv, "json": to_json}


def _build_whatsapp_media_files(client, serial, app):
    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)
    if not installs:
        click.echo("No WhatsApp or WhatsApp Business installation found on this device.", err=True)
        sys.exit(1)

    media_files = []
    for install in installs:
        media_files.extend(whatsapp_module.scan_media(client, serial, install))
    return media_files


def _build_full_report(client, serial, app, top_n):
    sections = []

    overview = storage_module.get_storage_overview(client, serial)
    storage_reports.record_storage_snapshot(overview, path=storage_reports.DEFAULT_TREND_PATH)
    sections.extend(storage_reports.build_storage_overview_report(overview).sections)

    apps = storage_module.get_app_storage(client, serial)
    sections.extend(storage_reports.build_top_apps_report(apps, top=top_n).sections)

    history = storage_reports.load_storage_history(storage_reports.DEFAULT_TREND_PATH)
    if len(history) >= 2:
        sections.extend(storage_reports.build_storage_trend_report(history).sections)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)
    if installs:
        media_files = []
        for install in installs:
            media_files.extend(whatsapp_module.scan_media(client, serial, install))
        sections.extend(whatsapp_reports.build_media_inventory_report(media_files).sections)

    backup_history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
    if backup_history:
        sections.extend(backup_reports.build_backup_history_report(backup_history).sections)

    return Report(title="DroidBridge Full Report", sections=sections)


@report_cmd.command("generate")
@_SERIAL_OPTION
@_APP_OPTION
@click.option(
    "--type",
    "report_type",
    type=click.Choice(_REPORT_TYPES),
    default="full",
    show_default=True,
    help="Report type to generate.",
)
@click.option(
    "--format",
    "report_format",
    type=click.Choice(("txt", "html", "csv", "json")),
    default="txt",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output file path (default: session_logs/reports/<type>_<timestamp>.<format>).",
)
@click.option("--top", "top_n", type=int, default=20, show_default=True, help="Number of apps for --type top-apps (or full).")
@click.option("--min-size", default=None, help="Minimum file size for --type large-files, e.g. 50MB (default: 50MB).")
@click.option("--cutoff", default=None, help="Cutoff date (YYYY-MM-DD), required for --type whatsapp-cutoff.")
@click.option("--profile", "profile_name", default=None, help="Backup profile name, required for --type backup-summary or backup-verification.")
def report_generate(serial, app, report_type, report_format, output_path, top_n, min_size, cutoff, profile_name):
    """Generate a report and write it to a file, e.g. `droidbridge report generate --format html` (spec §9)."""
    needs_device = report_type not in ("storage-trend", "backup-history", "backup-summary", "backup-verification")

    client = None
    if needs_device:
        try:
            client = _build_client()
        except AdbError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

        serial = _resolve_serial(client, serial)

    if report_type == "storage":
        overview = storage_module.get_storage_overview(client, serial)
        storage_reports.record_storage_snapshot(overview, path=storage_reports.DEFAULT_TREND_PATH)
        report = storage_reports.build_storage_overview_report(overview)
    elif report_type == "top-apps":
        apps = storage_module.get_app_storage(client, serial)
        report = storage_reports.build_top_apps_report(apps, top=top_n)
    elif report_type == "large-files":
        threshold = parse_size(min_size) if min_size else search_module.LARGE_FILE_THRESHOLD
        results = storage_module.find_large_files(client, serial, threshold=threshold)
        report = storage_reports.build_large_files_report(results)
    elif report_type == "storage-trend":
        history = storage_reports.load_storage_history(storage_reports.DEFAULT_TREND_PATH)
        if not history:
            click.echo("No storage history recorded yet. Run `report generate --type storage` first.", err=True)
            sys.exit(1)
        report = storage_reports.build_storage_trend_report(history)
    elif report_type == "backup-history":
        history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
        if profile_name:
            history = [r for r in history if r.profile == profile_name]
        report = backup_reports.build_backup_history_report(history)
    elif report_type == "backup-summary":
        if not profile_name:
            click.echo("Error: --profile is required for --type backup-summary.", err=True)
            sys.exit(1)
        history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
        record = backup_module.last_backup(history, profile_name)
        if record is None:
            click.echo(f"No backups recorded for profile {profile_name!r}.", err=True)
            sys.exit(1)
        report = backup_reports.build_backup_summary_report(record)
    elif report_type == "backup-verification":
        if not profile_name:
            click.echo("Error: --profile is required for --type backup-verification.", err=True)
            sys.exit(1)
        report, _result = _build_backup_verification(profile_name)
    elif report_type == "whatsapp-inventory":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_media_inventory_report(media_files)
    elif report_type == "whatsapp-cutoff":
        if not cutoff:
            click.echo("Error: --cutoff is required for --type whatsapp-cutoff.", err=True)
            sys.exit(1)
        try:
            cutoff_date = datetime.strptime(cutoff, "%Y-%m-%d").date()
        except ValueError:
            click.echo(f"Error: invalid --cutoff date {cutoff!r}, expected YYYY-MM-DD.", err=True)
            sys.exit(1)
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_cutoff_comparison_report(media_files, cutoff_date)
    elif report_type == "whatsapp-filetypes":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_file_type_breakdown_report(media_files)
    elif report_type == "whatsapp-sections":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_section_breakdown_report(media_files)
    elif report_type == "whatsapp-documents":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_documents_categorization_report(media_files)
    else:  # full
        report = _build_full_report(client, serial, app, top_n)

    content = _REPORT_RENDERERS[report_format](report)

    if output_path:
        out = Path(output_path)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path("session_logs") / "reports" / f"{report_type}_{timestamp}.{report_format}"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")

    if report_format == "txt":
        click.echo(content)
    click.echo(f"Report written to {out}")


@cli.command("gui")
def gui_cmd():
    """Launch the DroidBridge desktop GUI (requires the optional PyQt6 dependency)."""
    if importlib.util.find_spec("PyQt6") is None:
        click.echo(
            'Error: GUI dependencies not installed. Install with: pip install -e ".[gui]"',
            err=True,
        )
        sys.exit(1)

    from droidbridge.gui.app import main as gui_main

    sys.exit(gui_main(sys.argv[:1]))


if __name__ == "__main__":
    cli()

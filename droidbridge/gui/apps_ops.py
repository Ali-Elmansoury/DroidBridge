"""Plain-Python Apps GUI operations (sub-phase 6.5 part 2) - no Qt imports."""

import json
from datetime import datetime
from pathlib import Path

from droidbridge.modules import apps as apps_module
from droidbridge.utils import format as format_utils

_MANIFEST_NAME = "manifest.json"


def _format_date(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _format_app_row(app):
    return {
        "package": app.package,
        "version_name": app.version_name,
        "version_code": app.version_code,
        "installed_str": _format_date(app.first_install_time),
        "updated_str": _format_date(app.last_update_time),
        "apk_size": app.apk_size,
        "apk_size_str": format_utils.format_bytes(app.apk_size),
        "data_size": app.data_size,
        "data_size_str": format_utils.format_bytes(app.data_size),
        "cache_size": app.cache_size,
        "cache_size_str": format_utils.format_bytes(app.cache_size),
        "total_size_str": format_utils.format_bytes(app.total_size),
        "kind": "system" if app.is_system else "user",
        "is_system": app.is_system,
        "status": "Disabled" if app.is_disabled else "Enabled",
        "is_disabled": app.is_disabled,
    }


def get_apps(client, serial, filter_kind="all", sort_by="name", reverse=False):
    apps = apps_module.get_apps(client, serial)
    apps = apps_module.filter_apps(apps, kind=filter_kind)
    apps = apps_module.sort_apps(apps, by=sort_by, reverse=reverse)
    return [_format_app_row(a) for a in apps]


def get_app_info(client, serial, package):
    for app in apps_module.get_apps(client, serial):
        if app.package == package:
            return _format_app_row(app)
    return None


def estimate_cache_clear(rows):
    """Sum of cache sizes across already-fetched Listing `rows` - no device call."""
    total = sum(row["cache_size"] for row in rows)
    return {"estimate_bytes": total, "estimate_str": format_utils.format_bytes(total)}


def trim_caches(client, serial, estimate_bytes):
    apps_module.trim_caches(client, serial, estimate_bytes)


def reset_app_data(client, serial, package):
    app = next((a for a in apps_module.get_apps(client, serial) if a.package == package), None)
    if app is not None and app.is_system:
        raise ValueError(f"{package} is a system app; refusing to reset its data.")
    apps_module.clear_app_data(client, serial, package)


def uninstall_app(client, serial, package, keep_data=False):
    app = next((a for a in apps_module.get_apps(client, serial) if a.package == package), None)
    if app is not None and app.is_system:
        raise ValueError(f"{package} is a system app; refusing to uninstall it.")
    apps_module.uninstall_app(client, serial, package, keep_data=keep_data)
    return True


def disable_app(client, serial, package):
    apps_module.disable_app(client, serial, package)


def enable_app(client, serial, package):
    apps_module.enable_app(client, serial, package)


def get_apk_info(client, serial, package):
    info = apps_module.get_apk_info(client, serial, package)
    total = sum(size for _path, size in info)
    return {
        "files": [
            {"path": path, "size": size, "size_str": format_utils.format_bytes(size)}
            for path, size in info
        ],
        "total_size_str": format_utils.format_bytes(total),
    }


def extract_apk(client, serial, package, dest_dir, progress_callback=None):
    info = apps_module.get_apk_info(client, serial, package)
    pulled = []
    for path, _size in info:
        filename = Path(path).name
        local_path = str(Path(dest_dir) / filename)
        if progress_callback:
            progress_callback(f"Pulling {filename}...")
        client.pull(serial, path, local_path)
        pulled.append(local_path)
    return pulled


def backup_apk(client, serial, package, version_name, version_code, dest_dir, progress_callback=None):
    """Pull `package`'s APK file(s) into a versioned `<package>_<version_code>/`
    subfolder of `dest_dir`, alongside a manifest.json. Returns the bundle dir path."""
    info = apps_module.get_apk_info(client, serial, package)
    bundle_dir = Path(dest_dir) / f"{package}_{version_code}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    apk_files = []
    for path, size in info:
        filename = Path(path).name
        if progress_callback:
            progress_callback(f"Backing up {filename}...")
        client.pull(serial, path, str(bundle_dir / filename))
        apk_files.append({"filename": filename, "size": size})

    manifest = {
        "package": package,
        "version_name": version_name,
        "version_code": version_code,
        "apk_files": apk_files,
        "backed_up_at": datetime.now().isoformat(),
    }
    (bundle_dir / _MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))
    return str(bundle_dir)


def verify_apk_backup(bundle_dir):
    """Check every file recorded in `bundle_dir`'s manifest.json exists with the
    recorded size (same idea as `transfer_ops.verify_plans`)."""
    manifest = read_manifest(bundle_dir)
    for entry in manifest["apk_files"]:
        file_path = Path(bundle_dir) / entry["filename"]
        if not file_path.is_file() or file_path.stat().st_size != entry["size"]:
            return False
    return True


def read_manifest(bundle_dir):
    manifest_path = Path(bundle_dir) / _MANIFEST_NAME
    return json.loads(manifest_path.read_text())


def restore_apk(client, serial, bundle_dir, allow_downgrade=False):
    manifest = read_manifest(bundle_dir)
    apk_paths = [str(Path(bundle_dir) / f["filename"]) for f in manifest["apk_files"]]
    apps_module.install_apk(client, serial, apk_paths, allow_downgrade=allow_downgrade)
    return manifest

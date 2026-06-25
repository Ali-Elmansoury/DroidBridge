"""Plain-Python Apps GUI operations (sub-phase 6.5 part 2) - no Qt imports."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from droidbridge.modules import apps as apps_module
from droidbridge.utils import format as format_utils

_MANIFEST_NAME = "manifest.json"


def _format_date(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _format_app_row(app, label=None):
    return {
        "app_label": label if label is not None else app.package,
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
    labels = apps_module.get_launcher_labels(client, serial)
    apps = apps_module.filter_apps(apps, kind=filter_kind)
    apps = apps_module.sort_apps(apps, by=sort_by, reverse=reverse)
    return [_format_app_row(a, labels.get(a.package)) for a in apps]


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


# ── App display-name resolution (aapt2 + disk cache) ─────────────────────────

def _label_cache_path(serial):
    cache_dir = Path.home() / ".local" / "share" / "droidbridge" / "label_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{serial}.json"


def load_label_cache(serial):
    """Return cached {package: label} dict for the given serial, or {} on miss/error."""
    p = _label_cache_path(serial)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def _save_label_cache(serial, labels):
    try:
        _label_cache_path(serial).write_text(json.dumps(labels))
    except Exception:
        pass


def _parse_launcher_packages(output):
    """Parse `pm query-activities --brief` output → set of package names."""
    packages = set()
    for line in output.splitlines():
        line = line.strip()
        # Component lines look like "com.example/.Activity" — contain "/" but not "="
        if "/" in line and "=" not in line and "." in line and not line[0].isdigit():
            pkg = line.split("/")[0]
            if "." in pkg:
                packages.add(pkg)
    return packages


def _parse_apk_paths(output):
    """Parse `pm list packages -f` output → {package: base_apk_path}."""
    paths = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            rest = line[len("package:"):]
            if "=" in rest:
                apk_path, pkg = rest.rsplit("=", 1)
                # Only keep the first entry (base.apk) if package appears twice
                if pkg not in paths:
                    paths[pkg] = apk_path
    return paths


def resolve_app_labels(client, serial, packages, progress_callback=None):
    """Resolve display labels for launcher apps using host-side aapt2.

    Reads the disk cache first; pulls and aapt2-parses only uncached packages.
    Writes the cache after each resolved label for crash-safe progress.
    Calls progress_callback(done, total) from the calling thread if provided.
    Returns the updated {package: label} cache dict.
    """
    aapt2 = apps_module.find_aapt2()
    if aapt2 is None:
        return load_label_cache(serial)

    cache = load_label_cache(serial)

    # Packages with launcher icons only
    try:
        pm_out = client.shell(
            serial,
            ["pm", "query-activities", "--brief",
             "-a", "android.intent.action.MAIN",
             "-c", "android.intent.category.LAUNCHER"],
        )
        launcher_pkgs = _parse_launcher_packages(pm_out)
    except Exception:
        return cache

    # Resolve only what's not cached AND has a launcher icon
    package_set = set(packages)
    to_resolve = [p for p in packages if p in launcher_pkgs and p not in cache]
    if not to_resolve:
        return cache

    # Get APK paths for all packages in one call
    try:
        paths_out = client.shell(serial, ["pm", "list", "packages", "-f"])
        apk_paths = _parse_apk_paths(paths_out)
    except Exception:
        return cache

    total = len(to_resolve)
    done = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_apk = os.path.join(tmp_dir, "base.apk")
        for package in to_resolve:
            apk_path = apk_paths.get(package)
            if apk_path:
                try:
                    client.pull(serial, apk_path, local_apk)
                    label = apps_module.extract_label_from_apk(aapt2, local_apk)
                    if label:
                        cache[package] = label
                        _save_label_cache(serial, cache)
                except Exception:
                    pass
                finally:
                    try:
                        os.unlink(local_apk)
                    except OSError:
                        pass
            done += 1
            if progress_callback:
                progress_callback(done, total)

    return cache

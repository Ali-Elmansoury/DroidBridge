"""Module 8 - App Manager: app listing, cache management, uninstall, APK extraction, bloatware."""

import glob
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from shutil import which
from typing import Optional

from droidbridge.core.adb import AdbCommandError
from droidbridge.modules import storage as storage_module

_PACKAGE_HEADER_RE = re.compile(r"^\s*Package \[(\S+)\]")
_VERSION_CODE_RE = re.compile(r"^\s*versionCode=(\d+)")
_VERSION_NAME_RE = re.compile(r"^\s*versionName=(.*)$")
_FIRST_INSTALL_RE = re.compile(r"^\s*firstInstallTime=(.+)$")
_LAST_UPDATE_RE = re.compile(r"^\s*lastUpdateTime=(.+)$")

_LAUNCHER_PKG_RE = re.compile(r"^\s+packageName=(\S+)$")
_LAUNCHER_LABEL_RE = re.compile(r"^\s+nonLocalizedLabel=(.+)$")

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_package_dump(output):
    """Parse `dumpsys package packages` into {package: {version_code, version_name, first_install_time, last_update_time}}."""
    packages = {}
    current = None
    for line in output.splitlines():
        header = _PACKAGE_HEADER_RE.match(line)
        if header:
            current = {}
            packages[header.group(1)] = current
            continue
        if current is None:
            continue

        match = _VERSION_CODE_RE.match(line)
        if match:
            current["version_code"] = int(match.group(1))
            continue
        match = _VERSION_NAME_RE.match(line)
        if match:
            current["version_name"] = match.group(1).strip()
            continue
        match = _FIRST_INSTALL_RE.match(line)
        if match:
            current["first_install_time"] = datetime.strptime(match.group(1).strip(), _TIMESTAMP_FORMAT)
            continue
        match = _LAST_UPDATE_RE.match(line)
        if match:
            current["last_update_time"] = datetime.strptime(match.group(1).strip(), _TIMESTAMP_FORMAT)

    return packages


@dataclass
class AppInfo:
    """A single installed app: version/install metadata, storage usage, and system/disabled flags (spec §8.1)."""

    package: str
    version_name: str
    version_code: int
    first_install_time: Optional[datetime]
    last_update_time: Optional[datetime]
    apk_size: int
    data_size: int
    cache_size: int
    is_system: bool
    is_disabled: bool

    @property
    def name(self):
        """Friendly app label; falls back to the package ID.

        Resolving the real label requires parsing resources.arsc (aapt),
        which isn't available without extra non-root tooling.
        """
        return self.package

    @property
    def total_size(self):
        return self.apk_size + self.data_size + self.cache_size


def find_aapt2():
    """Return path to aapt2 binary on the host, or None if not found."""
    path = which("aapt2")
    if path:
        return path
    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(env_var)
        if root:
            candidates = glob.glob(os.path.join(root, "build-tools", "*", "aapt2"))
            if candidates:
                return sorted(candidates)[-1]
    home = os.path.expanduser("~")
    # Gradle transform cache: ~/.gradle/caches/*/transforms/*/transformed/aapt2-*/aapt2
    gradle_candidates = glob.glob(
        os.path.join(home, ".gradle", "caches", "*", "transforms", "*", "transformed", "aapt2-*", "aapt2")
    )
    if gradle_candidates:
        return sorted(gradle_candidates)[-1]
    return None


_AAPT2_BASE_LABEL_RE = re.compile(r"^application-label:'(.+)'$")


def extract_label_from_apk(aapt2_path, local_apk_path):
    """Run `aapt2 dump badging` on a local APK and return the app label, or None."""
    try:
        result = subprocess.run(
            [aapt2_path, "dump", "badging", local_apk_path],
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.splitlines():
            m = _AAPT2_BASE_LABEL_RE.match(line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def parse_launcher_labels(output):
    """Parse `cmd activity query-intents` output into {package: display_label}.

    Only packages with a resolved nonLocalizedLabel are included; callers fall
    back to the package name for the rest.
    """
    labels = {}
    current_pkg = None
    for line in output.splitlines():
        m = _LAUNCHER_PKG_RE.match(line)
        if m:
            current_pkg = m.group(1)
            continue
        m = _LAUNCHER_LABEL_RE.match(line)
        if m and current_pkg and current_pkg not in labels:
            label = m.group(1).strip()
            if label and label != "null":
                labels[current_pkg] = label
    return labels


def get_launcher_labels(client, serial):
    """Return {package: display_label} for apps that have a launcher icon.

    One ADB call; returns an empty dict on error or unsupported Android version.
    """
    try:
        output = client.shell(
            serial,
            ["cmd", "activity", "query-intents",
             "-a", "android.intent.action.MAIN",
             "-c", "android.intent.category.LAUNCHER"],
        )
        return parse_launcher_labels(output)
    except Exception:
        return {}


def get_apps(client, serial):
    """Return AppInfo for every installed package: sizes (diskstats), version/install
    metadata (dumpsys package packages), and system/disabled flags (pm list packages).

    Uses `pm list packages` as the authoritative package enumeration so that freshly
    installed apps (not yet in diskstats) always appear; sizes default to 0 when
    diskstats hasn't scanned the package yet.
    """
    diskstats_output = client.shell(serial, ["dumpsys", "diskstats"])
    package_dump = client.shell(serial, ["dumpsys", "package", "packages"], timeout=60)
    all_output = client.shell(serial, ["pm", "list", "packages"])
    system_output = client.shell(serial, ["pm", "list", "packages", "-s"])
    disabled_output = client.shell(serial, ["pm", "list", "packages", "-d"])

    metadata = parse_package_dump(package_dump)
    all_packages = storage_module.parse_package_list(all_output)
    system_packages = storage_module.parse_package_list(system_output)
    disabled_packages = storage_module.parse_package_list(disabled_output)
    sizes = {
        pkg: (apk, data, cache)
        for pkg, apk, data, cache in storage_module.parse_diskstats_apps(diskstats_output)
    }

    apps = []
    for package in all_packages:
        meta = metadata.get(package, {})
        apk_size, data_size, cache_size = sizes.get(package, (0, 0, 0))
        apps.append(
            AppInfo(
                package=package,
                version_name=meta.get("version_name", ""),
                version_code=meta.get("version_code", 0),
                first_install_time=meta.get("first_install_time"),
                last_update_time=meta.get("last_update_time"),
                apk_size=apk_size,
                data_size=data_size,
                cache_size=cache_size,
                is_system=package in system_packages,
                is_disabled=package in disabled_packages,
            )
        )
    return apps


APP_SORT_KEYS = ("name", "total", "size", "apk", "data", "cache", "install_date", "update_date")


def sort_apps(apps, by="name", reverse=False):
    """Sort AppInfo list by 'name', 'total'/'size', 'apk', 'data', 'cache', 'install_date', or 'update_date'."""
    if by == "name":
        key = lambda a: a.name.lower()
    elif by in ("total", "size"):
        key = lambda a: a.total_size
    elif by == "apk":
        key = lambda a: a.apk_size
    elif by == "data":
        key = lambda a: a.data_size
    elif by == "cache":
        key = lambda a: a.cache_size
    elif by == "install_date":
        key = lambda a: a.first_install_time or datetime.min
    elif by == "update_date":
        key = lambda a: a.last_update_time or datetime.min
    else:
        raise ValueError(f"Unknown sort key {by!r}; expected one of {APP_SORT_KEYS}")

    return sorted(apps, key=key, reverse=reverse)


APP_FILTER_KINDS = ("all", "system", "user")


def filter_apps(apps, kind="all"):
    """Filter AppInfo list to 'all', 'system', or 'user' apps."""
    if kind == "all":
        return list(apps)
    if kind == "system":
        return [a for a in apps if a.is_system]
    if kind == "user":
        return [a for a in apps if not a.is_system]

    raise ValueError(f"Unknown filter kind {kind!r}; expected one of {APP_FILTER_KINDS}")


# Cache management (spec §8.2)
#
# There is no non-root primitive to clear a SINGLE app's cache without
# touching its data:
#   - `pm trim-caches <bytes>` asks Android to evict cached files (system-wide,
#     LRU-based) until `bytes` are free. Safe/non-destructive - this is what
#     Android does automatically when storage is low - but not per-app.
#   - `pm clear <package>` fully resets a single app (data AND cache), the
#     same as "Clear storage" in Android Settings. Destructive.


def estimate_cache_clear(apps):
    """Sum of cache sizes across `apps` - the space `trim_caches` could free."""
    return sum(a.cache_size for a in apps)


def trim_caches(client, serial, desired_free_bytes):
    """Ask Android to evict cached files until `desired_free_bytes` are free (pm trim-caches)."""
    client.shell(serial, ["pm", "trim-caches", str(int(desired_free_bytes))])


def clear_app_data(client, serial, package):
    """Fully reset `package` via `pm clear` - wipes ALL app data, not just its cache."""
    client.shell(serial, ["pm", "clear", package])


# App uninstall (spec §8.3)


def uninstall_app(client, serial, package, keep_data=False):
    """Uninstall `package` via `pm uninstall`, optionally keeping its data/cache (-k)."""
    command = ["pm", "uninstall"]
    if keep_data:
        command.append("-k")
    command.append(package)
    client.shell(serial, command)


# APK extraction (spec §8.4)


def get_apk_paths(client, serial, package):
    """Return APK path(s) for `package` via `pm path` (base APK + any splits).

    Returns an empty list if `package` is not installed.
    """
    try:
        output = client.shell(serial, ["pm", "path", package])
    except AdbCommandError:
        return []
    return [line.split(":", 1)[1] for line in output.splitlines() if line.startswith("package:")]


def get_apk_info(client, serial, package):
    """Return [(path, size_bytes), ...] for `package`'s APK files (base + splits)."""
    info = []
    for path in get_apk_paths(client, serial, package):
        size = int(client.shell(serial, f"find -L {shlex.quote(path)} -maxdepth 0 -printf %s"))
        info.append((path, size))
    return info


# Bloatware manager (spec §8.5)


def disable_app(client, serial, package, user=0):
    """Disable `package` for `user` via `pm disable-user` (reversible with `enable_app`)."""
    client.shell(serial, ["pm", "disable-user", "--user", str(user), package])


def enable_app(client, serial, package, user=0):
    """Re-enable a previously disabled `package` for `user` via `pm enable`."""
    client.shell(serial, ["pm", "enable", "--user", str(user), package])


def install_apk(client, serial, apk_paths, allow_downgrade=False):
    """Install/replace an app from `apk_paths` (base + any splits) via `client.install`."""
    client.install(serial, apk_paths, allow_downgrade=allow_downgrade)

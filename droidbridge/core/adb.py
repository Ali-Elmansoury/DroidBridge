"""ADB wrapper: locate the adb binary and run devices/shell/pull/push commands."""

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"

_PLATFORM_DIRS = {
    "linux": "platform-tools-linux",
    "windows": "platform-tools-windows",
    "darwin": "platform-tools-darwin",
}


class AdbError(Exception):
    """Base exception for ADB wrapper errors."""


class AdbNotFoundError(AdbError):
    """Raised when no adb binary can be located (bundled or on PATH)."""


class AdbCommandError(AdbError):
    """Raised when an adb command exits with a non-zero status."""

    def __init__(self, command, returncode, stdout, stderr):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        message = stderr.strip() or stdout.strip() or f"exit code {returncode}"
        super().__init__(f"adb command failed ({' '.join(command)}): {message}")


class AdbTimeoutError(AdbError):
    """Raised when an adb command does not complete within its timeout."""

    def __init__(self, command, timeout):
        self.command = command
        self.timeout = timeout
        super().__init__(f"adb command timed out after {timeout}s: {' '.join(command)}")


@dataclass
class Device:
    """A device entry as reported by `adb devices -l`."""

    serial: str
    state: str
    product: str = ""
    model: str = ""
    device: str = ""
    transport_id: str = ""

    @property
    def is_ready(self):
        return self.state == "device"


def find_adb_binary(system=None, resources_dir=None):
    """Locate the adb binary, preferring the bundled platform-tools.

    Falls back to an `adb` binary on PATH if no bundled binary exists for
    the current platform. Raises AdbNotFoundError if neither is found.
    """
    system = (system or platform.system()).lower()
    resources_dir = Path(resources_dir) if resources_dir is not None else RESOURCES_DIR

    platform_dir = _PLATFORM_DIRS.get(system)
    if platform_dir:
        binary_name = "adb.exe" if system == "windows" else "adb"
        bundled = resources_dir / platform_dir / binary_name
        if bundled.is_file():
            return str(bundled)

    system_adb = shutil.which("adb")
    if system_adb:
        return system_adb

    raise AdbNotFoundError(
        "Could not locate an adb binary (bundled or on PATH). "
        "Install Android platform-tools or place adb in "
        f"{resources_dir}/{platform_dir or '<platform-tools-dir>'}/."
    )


_UNSET = object()


class AdbClient:
    """Thin wrapper around the adb command-line tool."""

    DEFAULT_TIMEOUT = 30

    def __init__(self, adb_path=None, default_timeout=DEFAULT_TIMEOUT):
        self.adb_path = adb_path or find_adb_binary()
        self.default_timeout = default_timeout

    def _run(self, args, serial=None, timeout=_UNSET, check=True):
        """Run `adb [-s <serial>] <args>` and return the CompletedProcess.

        `timeout` of _UNSET (the default) uses `self.default_timeout`.
        Pass `timeout=None` explicitly for no timeout (used for pull/push,
        which can run for a long time on large transfers).

        Raises AdbNotFoundError, AdbTimeoutError, or (if check=True)
        AdbCommandError on non-zero exit status.
        """
        cmd = [self.adb_path]
        if serial:
            cmd += ["-s", serial]
        cmd += list(args)

        run_timeout = self.default_timeout if timeout is _UNSET else timeout
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, errors="replace",
                timeout=run_timeout, stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise AdbNotFoundError(f"adb binary not found: {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbTimeoutError(cmd, exc.timeout) from exc

        if check and result.returncode != 0:
            raise AdbCommandError(cmd, result.returncode, result.stdout, result.stderr)
        return result

    def devices(self):
        """Return a list of Device objects for all devices known to adb."""
        result = self._run(["devices", "-l"])
        devices = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            serial, state = parts[0], parts[1]
            info = {}
            for token in parts[2:]:
                if ":" in token:
                    key, _, value = token.partition(":")
                    info[key] = value
            devices.append(
                Device(
                    serial=serial,
                    state=state,
                    product=info.get("product", ""),
                    model=info.get("model", ""),
                    device=info.get("device", ""),
                    transport_id=info.get("transport_id", ""),
                )
            )
        return devices

    def start_server(self):
        """Start the adb server (no-op if already running)."""
        self._run(["start-server"])

    def kill_server(self):
        """Stop the adb server."""
        self._run(["kill-server"])

    def restart_server(self):
        """Restart the adb server (kill then start)."""
        self.kill_server()
        self.start_server()

    def get_state(self, serial):
        """Return the connection state for a device, or 'not found'."""
        result = self._run(["get-state"], serial=serial, check=False)
        if result.returncode != 0:
            return "not found"
        return result.stdout.strip()

    def wait_for_device(self, serial=None, timeout=None):
        """Block until `adb` reports a device is connected (`adb wait-for-device`).

        Raises AdbTimeoutError if `timeout` (seconds) elapses first. The default
        `timeout=None` waits indefinitely.
        """
        self._run(["wait-for-device"], serial=serial, timeout=timeout)

    def shell(self, serial, command, timeout=_UNSET):
        """Run `adb -s <serial> shell <command>` and return stdout."""
        if isinstance(command, (list, tuple)):
            args = ["shell", *command]
        else:
            args = ["shell", command]
        result = self._run(args, serial=serial, timeout=timeout)
        return result.stdout

    def pull(self, serial, remote_path, local_path, timeout=None):
        """Run `adb -s <serial> pull <remote_path> <local_path>`.

        No timeout by default since transfers can take a long time.
        Returns the CompletedProcess (stdout/stderr/returncode).
        """
        return self._run(["pull", remote_path, local_path], serial=serial, timeout=timeout)

    def push(self, serial, local_path, remote_path, timeout=None):
        """Run `adb -s <serial> push <local_path> <remote_path>`.

        No timeout by default since transfers can take a long time.
        Returns the CompletedProcess (stdout/stderr/returncode).
        """
        return self._run(["push", local_path, remote_path], serial=serial, timeout=timeout)

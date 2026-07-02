# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Linux sleep inhibitor: prevents suspend/idle during long-running transfers."""

import shutil
import subprocess


class SleepInhibitor:
    """Context manager that holds a `systemd-inhibit` sleep/idle lock.

    If `systemd-inhibit` isn't available, this is a no-op (the transfer
    still runs, just without sleep prevention).
    """

    def __init__(self, reason="DroidBridge transfer in progress"):
        self.reason = reason
        self._process = None

    @staticmethod
    def is_available():
        return shutil.which("systemd-inhibit") is not None

    def __enter__(self):
        if self.is_available():
            self._process = subprocess.Popen(
                [
                    "systemd-inhibit",
                    "--what=sleep:idle",
                    "--who=DroidBridge",
                    f"--why={self.reason}",
                    "--mode=block",
                    "sleep",
                    "infinity",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._process is not None:
            self._process.terminate()
            self._process.wait()
            self._process = None
        return False

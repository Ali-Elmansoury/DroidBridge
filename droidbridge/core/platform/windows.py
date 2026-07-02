# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Windows sleep inhibitor: prevents suspend/idle during long-running transfers."""

import ctypes

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class SleepInhibitor:
    """Context manager that prevents Windows from sleeping via `SetThreadExecutionState`.

    If `ctypes.windll` isn't available (i.e. not running on Windows), this is
    a no-op (the transfer still runs, just without sleep prevention).
    """

    def __init__(self, reason="DroidBridge transfer in progress"):
        self.reason = reason

    @staticmethod
    def is_available():
        return hasattr(ctypes, "windll")

    def __enter__(self):
        if self.is_available():
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.is_available():
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        return False

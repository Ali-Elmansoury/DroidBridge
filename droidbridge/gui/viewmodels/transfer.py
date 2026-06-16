"""ViewModel for the Transfer module screen (Phase 6.2).

Owns Workers, plans/executes/verifies pull and push transfers via gui.transfer_ops,
reports live progress, and supports cooperative cancellation.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import transfer_ops
from droidbridge.gui.workers import Worker
from droidbridge.modules import transfer as transfer_module
from droidbridge.modules.transfer import CONFLICT_SKIP
from droidbridge.utils import format as format_utils


def _format_plan(plans):
    return {
        "total_files": sum(p.total_files for p in plans),
        "total_bytes": sum(p.total_bytes for p in plans),
        "already_present": sum(len(p.already_present) for p in plans),
        "conflicts_skipped": sum(len(p.conflicts_skipped) for p in plans),
    }


def _format_progress(progress):
    return {
        "done_files": progress.done_files,
        "total_files": progress.total_files,
        "done_bytes": progress.done_bytes,
        "total_bytes": progress.total_bytes,
        "done_bytes_str": format_utils.format_bytes(progress.done_bytes),
        "total_bytes_str": format_utils.format_bytes(progress.total_bytes),
        "speed_str": f"{format_utils.format_bytes(progress.speed_bps)}/s",
        "eta_str": format_utils.format_duration(progress.eta_seconds),
        "percent": progress.percent,
    }


def _format_verification(result):
    if result.ok:
        message = f"Verified: {result.actual_files} file(s), {format_utils.format_bytes(result.actual_bytes)}."
    else:
        message = (
            f"Verification FAILED: expected {result.expected_files} file(s) "
            f"({format_utils.format_bytes(result.expected_bytes)}), found {result.actual_files} file(s) "
            f"({format_utils.format_bytes(result.actual_bytes)})."
        )
    return {"ok": result.ok, "message": message}


def _format_history_entry(direction, result, verification, mirror_result=None):
    return {
        "direction": direction,
        "total_files": result.done_files,
        "total_bytes": result.done_bytes,
        "verification_ok": verification.ok if verification is not None else None,
        "failed": len(result.failed),
        "deleted_files": mirror_result.deleted_files if mirror_result is not None else 0,
    }


_BUSY_MESSAGE = "A transfer is already in progress."


class TransferViewModel(QObject):
    """Drives the Transfer page: plan/execute/verify pull and push transfers."""

    planChanged = pyqtSignal(dict)
    progressChanged = pyqtSignal(dict)
    verificationChanged = pyqtSignal(dict)
    historyEntryAdded = pyqtSignal(dict)
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)

    def __init__(self, context, worker_factory=Worker):
        super().__init__()
        self.context = context
        self._worker_factory = worker_factory
        self._workers = []
        self._cancel_requested = False

    def _reject_if_busy(self):
        """If a transfer is already running, emit a warning and return True."""
        if self._workers:
            self.statusChanged.emit(_BUSY_MESSAGE)
            self.logMessage.emit(_BUSY_MESSAGE, "WARNING")
            return True
        return False

    def start_pull(self, remote_path, local_dir, conflict, verify, retry_count=3):
        """Plan, execute, and (if `verify`) verify a pull of a single remote path."""
        if self._reject_if_busy():
            return
        self._cancel_requested = False
        client, serial = self.context.client, self.context.serial

        def do_transfer(progress_callback=None):
            plans = transfer_ops.plan_pull_many(client, serial, [remote_path], local_dir, conflict=conflict)
            self.planChanged.emit(_format_plan(plans))
            result = transfer_ops.execute_plans(
                client, serial, plans, progress_callback=progress_callback,
                should_cancel=lambda: self._cancel_requested,
                retry_count=retry_count,
            )
            verification = transfer_ops.verify_plans(client, serial, plans, direction="pull") if verify else None
            return "pull", result, verification

        self.logMessage.emit(f"Pulling {remote_path}...", "INFO")
        self._run(do_transfer, self._on_transfer_finished, report_progress=True, on_progress=self._on_progress)

    def start_push(self, local_path, remote_dir, conflict, verify, retry_count=3):
        """Plan, execute, and (if `verify`) verify a push of a single local path."""
        if self._reject_if_busy():
            return
        self._cancel_requested = False
        client, serial = self.context.client, self.context.serial

        def do_transfer(progress_callback=None):
            plans = transfer_ops.plan_push_many(client, serial, [local_path], remote_dir, conflict=conflict)
            self.planChanged.emit(_format_plan(plans))
            result = transfer_ops.execute_plans(
                client, serial, plans, progress_callback=progress_callback,
                should_cancel=lambda: self._cancel_requested,
                retry_count=retry_count,
            )
            verification = (
                transfer_ops.verify_plans(client, serial, plans, direction="push", remote_dir=remote_dir)
                if verify else None
            )
            return "push", result, verification

        self.logMessage.emit(f"Pushing {local_path}...", "INFO")
        self._run(do_transfer, self._on_transfer_finished, report_progress=True, on_progress=self._on_progress)

    def pull_selected(self, remote_paths, local_dir):
        """Pull multiple remote paths (Files/Search "Pull Selected"): always verified,
        conflicts always skipped (never overwrites an existing destination).
        """
        if self._reject_if_busy():
            return
        self._cancel_requested = False
        client, serial = self.context.client, self.context.serial

        def do_transfer(progress_callback=None):
            plans = transfer_ops.plan_pull_many(client, serial, remote_paths, local_dir, conflict=CONFLICT_SKIP)
            self.planChanged.emit(_format_plan(plans))
            result = transfer_ops.execute_plans(
                client, serial, plans, progress_callback=progress_callback,
                should_cancel=lambda: self._cancel_requested,
            )
            verification = transfer_ops.verify_plans(client, serial, plans, direction="pull")
            return "pull", result, verification

        self.logMessage.emit(f"Pulling {len(remote_paths)} item(s)...", "INFO")
        self._run(do_transfer, self._on_transfer_finished, report_progress=True, on_progress=self._on_progress)

    def cancel_transfer(self):
        """Request cancellation of the in-flight transfer (checked between/within plans)."""
        self._cancel_requested = True

    def _on_progress(self, progress):
        self.progressChanged.emit(_format_progress(progress))

    def _on_transfer_finished(self, payload):
        direction, result, verification = payload
        self.progressChanged.emit(_format_progress(result))
        if verification is not None:
            self.verificationChanged.emit(_format_verification(verification))
        self.historyEntryAdded.emit(_format_history_entry(direction, result, verification))
        self.logMessage.emit(
            f"{direction.capitalize()} complete: {result.done_files} file(s), "
            f"{format_utils.format_bytes(result.done_bytes)}.",
            "INFO",
        )

    def _run(self, fn, on_finished, report_progress=False, on_progress=None):
        self.busyChanged.emit(True)
        worker = self._worker_factory(fn, report_progress=report_progress)
        self._workers.append(worker)
        if on_progress is not None:
            worker.progress.connect(on_progress)
        worker.finished.connect(lambda result: self._finish(worker, on_finished, result))
        worker.error.connect(lambda exc: self._finish(worker, self._on_error, exc))
        worker.start()

    def _finish(self, worker, callback, payload):
        worker.wait()
        self._workers.remove(worker)
        callback(payload)
        if not self._workers:
            self.busyChanged.emit(False)

    def _on_error(self, exc):
        self.statusChanged.emit(str(exc))
        self.logMessage.emit(str(exc), "ERROR")

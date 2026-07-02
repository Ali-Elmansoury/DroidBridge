# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Shared rename/delete dialog flows for FilesPage and SearchPage (Phase 6.3).

Both pages need the same "scan -> confirm -> delete -> verify" and "rename"
flows; living here keeps that logic out of the page classes.
"""

from pathlib import PurePosixPath

from PyQt6.QtCore import QEventLoop, Qt
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QProgressDialog

from droidbridge.core.adb import AdbError
from droidbridge.gui import delete_ops, files_ops, transfer_ops
from droidbridge.gui.workers import Worker
from droidbridge.utils.format import format_bytes

_DELETE_CHOICE_BACKUP = "Back Up First..."
_DELETE_CHOICE_NO_BACKUP = "Delete Without Backup"


def _run_with_progress(parent, fn, *args, title="Working...", worker_factory=Worker, report_progress=False, **kwargs):
    """Run `fn(*args, **kwargs)` on a worker thread, showing a modal progress
    dialog until it finishes.

    Returns the result of `fn`, or None if `fn` raised (a warning dialog is
    shown with the exception's message in that case).
    """
    dialog = QProgressDialog(title, None, 0, 0, parent)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setCancelButton(None)
    dialog.setMinimumDuration(0)

    result = {}

    def on_finished(value):
        result["value"] = value
        loop.quit()

    def on_error(exc):
        result["error"] = exc
        loop.quit()

    def on_progress(value):
        dialog.setLabelText(str(value))

    if report_progress:
        kwargs = dict(kwargs)
        kwargs["report_progress"] = True

    worker = worker_factory(fn, *args, **kwargs)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    if report_progress:
        worker.progress.connect(on_progress)

    loop = QEventLoop()
    dialog.show()
    # `worker` was moved to its own QThread via moveToThread, so deferring
    # start() via QTimer.singleShot would queue the call onto that
    # not-yet-running thread's event loop and deadlock. Call it directly;
    # synchronous worker_factory implementations (e.g. tests' FakeWorker) may
    # already populate `result` and call loop.quit() here, before loop.exec()
    # has started - quit() on a not-yet-running loop is a no-op, so skip
    # exec() entirely in that case to avoid hanging forever.
    worker.start()
    if not result:
        loop.exec()

    dialog.close()
    worker.wait()

    if "error" in result:
        QMessageBox.warning(parent, title, str(result["error"]))
        return None

    return result.get("value")


def run_rename_flow(parent, client, serial, path):
    """Prompt for a new name and rename `path` on the device.

    Returns the new path, or None if the user cancelled, left the name
    unchanged, entered an invalid name, or the rename failed.
    """
    old_name = PurePosixPath(path).name
    new_name, ok = QInputDialog.getText(parent, "Rename", "New name:", text=old_name)
    new_name = new_name.strip()
    if not ok or not new_name or new_name == old_name:
        return None

    if "/" in new_name:
        QMessageBox.warning(parent, "Rename", "Name cannot contain '/'.")
        return None

    new_path = files_ops.join_path(files_ops.parent_path(path), new_name)

    try:
        delete_ops.rename_path(client, serial, path, new_path)
    except AdbError as exc:
        QMessageBox.warning(parent, "Rename", str(exc))
        return None

    return new_path


def run_delete_flow(parent, client, serial, paths, worker_factory=Worker):
    """Scan `paths`, confirm with the user (optionally backing up first),
    then delete and verify.

    Returns the set of paths that were actually deleted (may be empty if the
    user cancelled at any point, or partial if some paths could not be
    removed).
    """
    plan = _run_with_progress(
        parent, delete_ops.build_delete_plan, client, serial, paths,
        title="Scanning...", worker_factory=worker_factory,
    )
    if plan is None:
        return set()

    if plan.file_count == 0:
        QMessageBox.information(parent, "Delete", "Nothing to delete.")
        return set()

    file_word = "file" if plan.file_count == 1 else "files"
    message = (
        f"This will permanently delete {plan.file_count} {file_word} "
        f"({format_bytes(plan.total_size)}):\n\n" + "\n".join(plan.paths)
    )

    box = QMessageBox(parent)
    box.setWindowTitle("Delete")
    box.setText(message)
    backup_button = box.addButton(_DELETE_CHOICE_BACKUP, QMessageBox.ButtonRole.AcceptRole)
    delete_button = box.addButton(_DELETE_CHOICE_NO_BACKUP, QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    clicked = box.clickedButton()

    if clicked is backup_button:
        backup_dir = QFileDialog.getExistingDirectory(parent, "Select backup folder")
        if not backup_dir:
            return set()
        if not _run_backup(parent, client, serial, plan.paths, backup_dir, worker_factory):
            return set()
    elif clicked is not delete_button:
        return set()

    confirm, ok = QInputDialog.getText(parent, "Delete", "Type 'YES DELETE' to confirm:")
    if not ok or confirm != "YES DELETE":
        return set()

    _run_with_progress(
        parent, delete_ops.delete_paths, client, serial, plan.paths,
        title="Deleting...", worker_factory=worker_factory,
    )

    verification = _run_with_progress(
        parent, delete_ops.verify_deletion, client, serial, plan.paths,
        title="Verifying...", worker_factory=worker_factory,
    )
    if verification is None:
        return set()

    if verification.remaining:
        QMessageBox.warning(
            parent, "Delete",
            f"{len(verification.remaining)} item(s) could not be deleted:\n\n"
            + "\n".join(verification.remaining),
        )

    return set(verification.deleted)


def _run_backup(parent, client, serial, paths, backup_dir, worker_factory):
    """Pull `paths` to `backup_dir` and verify the copy.

    Returns True if the backup verified successfully, False otherwise (a
    warning dialog has already been shown in the False case).
    """
    def do_backup(progress_callback=None):
        plans = transfer_ops.plan_pull_many(client, serial, paths, backup_dir)
        transfer_ops.execute_plans(client, serial, plans, progress_callback=progress_callback)
        return transfer_ops.verify_plans(client, serial, plans, "pull", local_dir=backup_dir)

    verification = _run_with_progress(
        parent, do_backup, title="Backing up...", worker_factory=worker_factory, report_progress=True,
    )
    if verification is None:
        return False

    if not verification.ok:
        QMessageBox.warning(parent, "Delete", "Backup verification failed; deletion was not performed.")
        return False

    return True

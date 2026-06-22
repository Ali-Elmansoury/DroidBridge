"""Uninstall confirmation flow for the Apps Uninstall tab (sub-phase 6.5 part 2):
backup-the-APK-or-not, then a typed confirm, then uninstall. Mirrors
droidbridge/gui/widgets/delete_flow.py's run_delete_flow.
"""

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from droidbridge.gui import apps_ops
from droidbridge.gui.widgets.delete_flow import _run_with_progress
from droidbridge.gui.workers import Worker

_UNINSTALL_CHOICE_BACKUP = "Back Up APK First..."
_UNINSTALL_CHOICE_NO_BACKUP = "Uninstall Without Backup"


def run_uninstall_flow(parent, client, serial, app, keep_data=False, worker_factory=Worker):
    """Run the backup-or-not -> confirm -> uninstall flow for `app` (a row dict
    shaped like apps_ops.get_app_info's return value).

    Returns True if the app was uninstalled, False if the user cancelled at
    any step or backup verification failed (uninstall does not proceed in
    that case - never delete without a verified backup).
    """
    box = QMessageBox(parent)
    box.setWindowTitle("Uninstall")
    box.setText(f"Uninstall {app['package']} (v{app['version_name']}, {app['total_size_str']})?")
    backup_button = box.addButton(_UNINSTALL_CHOICE_BACKUP, QMessageBox.ButtonRole.AcceptRole)
    uninstall_button = box.addButton(_UNINSTALL_CHOICE_NO_BACKUP, QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    clicked = box.clickedButton()

    if clicked is backup_button:
        backup_dir = QFileDialog.getExistingDirectory(parent, "Select backup folder")
        if not backup_dir:
            return False
        if not _run_backup(parent, client, serial, app, backup_dir, worker_factory):
            return False
    elif clicked is not uninstall_button:
        return False

    confirm, ok = QInputDialog.getText(parent, "Uninstall", "Type 'YES DELETE' to confirm:")
    if not ok or confirm != "YES DELETE":
        return False

    _run_with_progress(
        parent, apps_ops.uninstall_app, client, serial, app["package"],
        title="Uninstalling...", worker_factory=worker_factory, keep_data=keep_data,
    )
    return True


def _run_backup(parent, client, serial, app, backup_dir, worker_factory):
    """Back up `app`'s APK into `backup_dir` and verify it.

    Returns True if the backup verified successfully, False otherwise (a
    warning dialog has already been shown in the False case).
    """
    def do_backup(progress_callback=None):
        bundle_dir = apps_ops.backup_apk(
            client, serial, app["package"], app["version_name"], app["version_code"],
            backup_dir, progress_callback=progress_callback,
        )
        return apps_ops.verify_apk_backup(bundle_dir)

    verified = _run_with_progress(
        parent, do_backup, title="Backing up APK...", worker_factory=worker_factory, report_progress=True,
    )
    if verified is None:
        return False

    if not verified:
        QMessageBox.warning(parent, "Uninstall", "Backup verification failed; uninstall was not performed.")
        return False

    return True

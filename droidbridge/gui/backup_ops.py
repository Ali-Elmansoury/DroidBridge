"""Plain-Python Backup Manager GUI operations (sub-phase 6.4) — no Qt imports."""

from droidbridge.modules import backup_manager as backup_module
from droidbridge.modules import transfer as transfer_module


def list_profiles():
    profiles = backup_module.load_profiles(backup_module.DEFAULT_PROFILES_PATH)
    return list(profiles.values())


def save_profile(name, sources, dest, conflict, excludes):
    profile = backup_module.BackupProfile(
        name=name, sources=list(sources), dest=dest, conflict=conflict, excludes=list(excludes),
    )
    backup_module.save_profile(backup_module.DEFAULT_PROFILES_PATH, profile)


def remove_profile(name):
    return backup_module.delete_profile(backup_module.DEFAULT_PROFILES_PATH, name)


def get_profile(name):
    return backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, name)

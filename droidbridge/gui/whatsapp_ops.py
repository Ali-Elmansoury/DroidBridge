"""Plain-Python WhatsApp GUI operations (sub-phase 6.3) — no Qt imports."""

import os
import tempfile

from droidbridge.modules import whatsapp as wa_module
from droidbridge.modules import transfer as transfer_module
from droidbridge.utils import format as format_utils


def _select_installs(installs, app):
    if app == "all":
        return installs
    package = "com.whatsapp" if app == "whatsapp" else "com.whatsapp.w4b"
    return [i for i in installs if i.package == package]


def run_scan(client, serial, app, breakdown):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    rows = []
    for install in selected:
        media = wa_module.scan_media(client, serial, install)
        if breakdown == "folder":
            for s in wa_module.summarize_by_folder(media):
                rows.append({"folder_type": s.folder_type, "section": s.section,
                             "file_count": s.file_count,
                             "total_size_str": format_utils.format_bytes(s.total_size)})
        elif breakdown == "year":
            for s in wa_module.summarize_by_year_month(media):
                rows.append({"year_month": s.year_month, "file_count": s.file_count,
                             "total_size_str": format_utils.format_bytes(s.total_size)})
        else:
            for s in wa_module.summarize_by_extension(media):
                rows.append({"extension": s.extension, "file_count": s.file_count,
                             "total_size_str": format_utils.format_bytes(s.total_size)})
    return rows


def run_analyze(client, serial, app, cutoff):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    rows = []
    for install in selected:
        media = wa_module.scan_media(client, serial, install)
        for s in wa_module.summarize_by_cutoff(media, cutoff):
            rows.append({"folder_type": s.folder_type,
                         "pre_count": s.pre_count,
                         "pre_size_str": format_utils.format_bytes(s.pre_size),
                         "post_count": s.post_count,
                         "post_size_str": format_utils.format_bytes(s.post_size),
                         "unknown_count": s.unknown_count,
                         "unknown_size_str": format_utils.format_bytes(s.unknown_size)})
    return rows


def run_backup(client, serial, app, dest, types, conflict, verify, progress_callback=None):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    total_done = total_files = total_failed = 0
    verified = None
    for install in selected:
        plan = wa_module.plan_backup(client, serial, [install], dest, types=types, conflict=conflict)
        total_files += plan.total_files
        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=progress_callback)
        total_done += progress.done_files
        total_failed += len(progress.failed)
        if verify:
            vr = transfer_module.verify_pull(plan)
            verified = vr.ok if verified is None else (verified and vr.ok)
    return {"done": total_done, "total": total_files, "failed": total_failed, "verified": verified}


def run_restore(client, serial, app, src, conflict, verify, progress_callback=None):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    total_done = total_files = total_failed = 0
    verified = None
    for install in selected:
        plan = wa_module.plan_restore(client, serial, install, src, conflict=conflict)
        total_files += plan.total_files
        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=progress_callback)
        total_done += progress.done_files
        total_failed += len(progress.failed)
        if verify:
            vr = transfer_module.verify_pull(plan)
            verified = vr.ok if verified is None else (verified and vr.ok)
    return {"done": total_done, "total": total_files, "failed": total_failed, "verified": verified}


def run_backup_db(client, serial, app, dest, conflict, verify, progress_callback=None):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    total_done = total_files = total_failed = 0
    verified = None
    for install in selected:
        plan = wa_module.plan_backup_db(client, serial, [install], dest, conflict=conflict)
        total_files += plan.total_files
        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=progress_callback)
        total_done += progress.done_files
        total_failed += len(progress.failed)
        if verify:
            vr = transfer_module.verify_pull(plan)
            verified = vr.ok if verified is None else (verified and vr.ok)
    return {"done": total_done, "total": total_files, "failed": total_failed, "verified": verified}


def pull_statuses_to_temp(client, serial, app, progress_callback=None):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    temp_dir = tempfile.mkdtemp(prefix="droidbridge_statuses_")
    items = []
    for install in selected:
        plan = wa_module.plan_save_statuses(client, serial, [install], temp_dir, conflict="overwrite")
        transfer_module.execute_plan(client, serial, plan, progress_callback=progress_callback)
        for item in plan.items:
            filename = os.path.basename(item.source)
            ext = os.path.splitext(filename)[1].lower().lstrip(".")
            items.append({"local_path": item.dest, "remote_path": item.source,
                          "extension": ext, "filename": filename})
    return temp_dir, items


def save_statuses(client, serial, app, dest, remote_paths, conflict, verify, progress_callback=None):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    remote_set = set(remote_paths)
    total_done = total_files = total_failed = 0
    verified = None
    for install in selected:
        full_plan = wa_module.plan_save_statuses(client, serial, [install], dest, conflict=conflict)
        filtered = [it for it in full_plan.items if it.source in remote_set]
        plan = transfer_module.TransferPlan(direction=full_plan.direction, items=filtered)
        total_files += plan.total_files
        progress = transfer_module.execute_plan(client, serial, plan, progress_callback=progress_callback)
        total_done += progress.done_files
        total_failed += len(progress.failed)
        if verify:
            vr = transfer_module.verify_pull(plan)
            verified = vr.ok if verified is None else (verified and vr.ok)
    return {"done": total_done, "total": total_files, "failed": total_failed, "verified": verified}


def build_delete_preview(client, serial, app, before, keep_types, backup_dir):
    installs = wa_module.detect_installs(client, serial)
    selected = _select_installs(installs, app)
    rows, plans = [], []
    for install in selected:
        media = wa_module.scan_media(client, serial, install)
        if backup_dir:
            missing = wa_module.verify_backup_exists(install, backup_dir, media)
            if missing:
                return {"plans": [], "rows": [], "error":
                        f"Backup verification failed: {len(missing)} files missing from {backup_dir}"}
        plan = wa_module.plan_delete(media, before, keep_types=keep_types)
        plans.append({"install": install, "plan": plan})
        for mf in plan.to_delete:
            rows.append({"path": mf.path, "folder_type": mf.folder_type,
                         "size_str": format_utils.format_bytes(mf.size)})
    return {"plans": plans, "rows": rows, "error": None}


def execute_delete(client, serial, plans):
    total_deleted = 0
    for entry in plans:
        wa_module.execute_delete_plan(client, serial, entry["plan"])
        total_deleted += entry["plan"].total_files
    return {"deleted": total_deleted}


def run_organize(src, type_name):
    fixed = wa_module.fix_filenames(src)
    if type_name == "documents":
        plan = wa_module.plan_organize_documents(src)
    else:
        sectioned = wa_module.ORGANIZE_DATE_TYPES.get(type_name, False)
        plan = wa_module.plan_organize_by_date(src, sectioned=sectioned)
    wa_module.execute_organize_plan(plan)
    dest = wa_module._organized_dest_root(src)
    return {"organized": plan.total_files, "fixed": len(fixed), "dest": dest}

# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Plain-Python GUI transfer operations (Phase 6.2) — no Qt imports.

Multi-path wrappers around droidbridge.modules.transfer: build one plan per path,
execute all plans while reporting one combined TransferProgress, and verify all
plans together.
"""

import time

from droidbridge.modules import transfer as transfer_module
from droidbridge.modules.transfer import CONFLICT_SKIP, TransferProgress


def plan_pull_many(client, serial, remote_paths, local_dir, conflict=CONFLICT_SKIP):
    """[plan_pull(client, serial, p, local_dir, conflict) for p in remote_paths]"""
    return [transfer_module.plan_pull(client, serial, p, local_dir, conflict=conflict) for p in remote_paths]


def plan_push_many(client, serial, local_paths, remote_dir, conflict=CONFLICT_SKIP):
    """[plan_push(client, serial, p, remote_dir, conflict) for p in local_paths]"""
    return [transfer_module.plan_push(client, serial, p, remote_dir, conflict=conflict) for p in local_paths]


def execute_plans(client, serial, plans, progress_callback=None, should_cancel=None,
                   retry_count=3, retry_delay=1.0, sleep_fn=time.sleep):
    """Execute each plan in `plans` via execute_plan(), reporting one overall
    TransferProgress across all plans.

    total_files/total_bytes are the sums of every plan's to_transfer, computed
    upfront. For each plan, execute_plan() is called with a wrapped
    progress_callback that adds the prior plans' completed done_files/done_bytes
    as an offset to that plan's TransferProgress before calling the outer
    progress_callback - so progress updates remain per-item (smooth) across the
    whole multi-plan operation. should_cancel() is passed through to each
    execute_plan() call (per-item cancellation) and is also checked between
    plans (skips remaining plans if True). retry_count, retry_delay, and
    sleep_fn are forwarded to each execute_plan() call. Returns the final overall
    TransferProgress with all failed items from all plans concatenated.
    """
    total_files = sum(len(p.to_transfer) for p in plans)
    total_bytes = sum(sum(i.size for i in p.to_transfer) for p in plans)

    start_time = time.monotonic()
    overall = TransferProgress(total_files=total_files, total_bytes=total_bytes, start_time=start_time)

    done_files_offset = 0
    done_bytes_offset = 0
    all_failed = []

    for plan in plans:
        if should_cancel is not None and should_cancel():
            break

        def on_plan_progress(item_progress):
            nonlocal overall
            overall = TransferProgress(
                total_files=total_files,
                total_bytes=total_bytes,
                done_files=done_files_offset + item_progress.done_files,
                done_bytes=done_bytes_offset + item_progress.done_bytes,
                start_time=start_time,
            )
            if progress_callback:
                progress_callback(overall)

        plan_result = transfer_module.execute_plan(
            client, serial, plan, progress_callback=on_plan_progress, should_cancel=should_cancel,
            retry_count=retry_count, retry_delay=retry_delay, sleep_fn=sleep_fn
        )

        done_files_offset += plan_result.done_files
        done_bytes_offset += plan_result.done_bytes
        all_failed.extend(plan_result.failed)
        overall = TransferProgress(
            total_files=total_files,
            total_bytes=total_bytes,
            done_files=done_files_offset,
            done_bytes=done_bytes_offset,
            start_time=start_time,
            failed=list(all_failed),
        )

    return overall


def verify_plans(client, serial, plans, direction, local_dir=None, remote_dir=None):
    """Run verify_pull(plan) (direction='pull') or verify_push(client, serial, plan,
    remote_dir) (direction='push') for each plan and sum into one VerificationResult.
    """
    expected_files = expected_bytes = actual_files = actual_bytes = 0

    for plan in plans:
        if direction == "pull":
            result = transfer_module.verify_pull(plan)
        else:
            result = transfer_module.verify_push(client, serial, plan, remote_dir)

        expected_files += result.expected_files
        expected_bytes += result.expected_bytes
        actual_files += result.actual_files
        actual_bytes += result.actual_bytes

    return transfer_module.VerificationResult(
        expected_files=expected_files,
        expected_bytes=expected_bytes,
        actual_files=actual_files,
        actual_bytes=actual_bytes,
    )

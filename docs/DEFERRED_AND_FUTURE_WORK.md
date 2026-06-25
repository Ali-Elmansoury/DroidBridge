# DroidBridge — Deferred Items, Blocked Features & Future Work

> Created 2026-06-25 after real-device validation of all GUI sub-phases.
> Covers every intentionally-deferred item, technically-blocked feature,
> out-of-scope decision, platform gap, and future enhancement idea found
> across the project document (§1–§17), PROGRESS.md, and spec/plan files.
>
> **Anything not listed here is implemented and validated.**

---

## 1. Deferred Items — Implementable, Not Yet Built

These are features the spec calls for (or that were scoped and acknowledged)
but were intentionally pushed to a later cycle. None are blocked by
technical constraints — they just need a spec → plan → implementation pass.

### 1.1 Storage Media — Full Duplicate-Group Listing

**Scope:** CLI `storage media` + GUI Storage → Media tab.

Both cap the duplicate-group display at the 10 largest groups
(`cli/main.py`'s `groups[:10]`, mirrored by `storage_ops.get_media`).
On the real test device (Realme RMX1931) this silently hides 2,254 groups.
There is no command or function anywhere that returns the full list.

**What's needed:** a new paginated/unfiltered duplicate-groups query in
`droidbridge/modules/storage.py` + a CLI option + a GUI "Show all" toggle
or scrollable view (matching the Apps tab's existing Top-N/"Show all" pattern
at `gui/pages/storage/apps.py`).

**Reference:** PROGRESS.md "Deferred follow-up for Storage GUI (6.5 part 1)
— full duplicate-group listing"; PROGRESS.md 2026-06-22 entry.

---

### 1.2 Storage GUI — Cancel Button for Long-Running Scans

**Scope:** Storage → Media, Large Files, and Cleanup tabs.

Full `/sdcard` scans can take 20+ seconds. The spec (§14 Key UI Requirements)
calls for "progress dialogs for all long-running operations with cancel button."
No existing GUI tab has cancellation today — it was explicitly deferred after
the 6.5 Storage real-device pass.

**What's needed:** thread a cancellation flag through `storage_ops.py`'s
background functions and the Worker pattern; surface it as a "Cancel" button
that becomes visible during a scan and hides on completion.

**Reference:** PROGRESS.md "Deferred follow-up for Storage GUI (6.5 part 1)".

---

### 1.3 Files GUI — Date/Size Range Filters Not Exposed

**Scope:** GUI Files page (Browse/Search).

`droidbridge/modules/search.py`'s `search_files` and `filter_results` fully
support `after`, `before`, `min_size`, and `max_size` parameters, and the CLI
exposes all four. The GUI Search page only exposes name, extension, and preset
filters — date and size range inputs were deferred from the GUI Files Polish
pass.

**What's needed:** four additional filter controls (date-from, date-to,
min-size, max-size) in the Search page's filter row; already wired to the
viewmodel's search call.

**Reference:** PROGRESS.md 2026-06-17 GUI Files Polish "Not in scope / deferred".

---

### 1.4 Files GUI — Tree View, Bookmarks, Audio Metadata

**Scope:** GUI Files page.

Three items deferred from the GUI Files Polish pass (2026-06-17):

- **Tree-view navigation**: side-panel directory tree instead of the
  breadcrumb+table navigation. Too invasive — would require a
  `QTableWidget` → `QTreeWidget` refactor of the entire Files page.
- **Bookmarks**: pin frequently visited device paths for quick access.
  No server-side state; would need a small config file.
- **Audio metadata preview**: show title/artist/duration in the preview
  panel for `.mp3`/`.opus`/`.aac` files (currently shows name/type/size/date
  only, same as all files).

**Reference:** PROGRESS.md 2026-06-17 GUI Files Polish "Not in scope / deferred".

---

### 1.5 Transfer Engine — Interactive Conflict Modes

**Scope:** CLI `transfer pull/push` + all GUI transfer operations.

Spec §3.4 calls for two additional conflict-resolution modes beyond the three
deterministic ones already implemented (skip/overwrite/rename):
- **"Ask each time"** — pause per-file and prompt the user.
- **"Remember choice for session"** — apply the first interactive choice to
  all remaining conflicts.

These were deferred because the GUI (Phase 6) provides the natural prompt UI
that an interactive mode needs. The engine's `plan_*` / `_classify*` functions
are already structured so an interactive mode could be added without changing
the engine's core logic.

**Reference:** PROGRESS.md Phase 2C "Deviations / Decisions"; spec §3.4.

---

### 1.6 Storage Trend / Compare-Across-Sessions Reports

**Scope:** CLI `report generate` + GUI Reports page.

Spec §9.2 lists "Storage trend: compare reports across sessions to see growth
over time." No implementation. Would need:
- Persisting past report snapshots (JSON) alongside session logs.
- A new report type (`--type storage-trend`) that reads historical data and
  shows growth deltas.

**Reference:** Project doc §9.2.

---

### 1.7 Transfer Engine — 500-File ADB Batching Not Implemented

**Scope:** `droidbridge/modules/transfer.py` `execute_plan` (pull/push).

Spec §6.2/§15 calls for "batch pull/push (500 files per ADB call)."
The current engine issues one `adb pull` / `adb push` call **per file** —
necessary because three design invariants are incompatible with batching:

1. **Per-file retry** — ADB returns one exit code for the whole batch with no
   signal on which individual file failed; `--retry N` logic can't know what
   to re-try.
2. **Per-file progress** — no in-batch progress event, so the progress bar
   would freeze for the full duration of each 500-file batch.
3. **Per-file cancel** — a cancel check can only fire at batch boundaries,
   not mid-batch.

The deletion engine **does** use 500-file batching (`rm -f <500 quoted paths>`
per shell call) because deletion produces no per-file feedback signal and
doesn't need retry or mid-operation progress updates.

**Possible future path:** an optional `--batch` flag on `transfer pull/push`
that sets `retry_count=0` and updates progress only at batch boundaries —
sacrificing per-file granularity for throughput when the user explicitly
opts in.

**Reference:** PROGRESS.md 2026-06-18 deferred-items pass "S1 — ADB
500-file batching"; `docs/superpowers/specs/2026-06-18-deferred-items-pass-design.md`
§ADB Batching.

---

### 1.8 "Detect If Backup Is Outdated" Alert

**Scope:** GUI Backup Manager + CLI `backup history`.

Spec §6.4 lists "Detect if backup is outdated (last backup > N days ago)."
The backup history is fully stored and browsable, but there is no alert or
flag that surfaces when a profile's last run exceeds a configured age threshold.

**What's needed:** a configurable threshold per profile (or global default);
a warning in the Backup Manager's History tab when a profile is stale.

**Reference:** Project doc §6.4.

---

### 1.9 Session Logs Auto-Sync to Backup Destination

**Scope:** `core/session.py` + `backup run`.

Spec §9.6 says "Logs automatically synced to backup destination." Session logs
are created and written correctly, but they are never automatically copied to
the backup profile's destination at the end of a run.

**What's needed:** a post-run copy step in `backup_manager.run_backup` (or
the CLI/GUI layer) that pushes the session's log file to `<dest>/session_logs/`.

**Reference:** Project doc §9.6.

---

### 1.10 `apps clear-cache` Target Accepts Raw Bytes Only

**Scope:** CLI `apps clear-cache --target`.

Minor UX inconsistency flagged after the post-audit pass: `apps clear-cache
--target` takes a raw integer (bytes), while `apps trim-cache --target` takes
human-readable sizes (`10MB`, `1.5GB`) via `parse_size()`. Both commands
ultimately call `pm trim-caches`; they should accept the same input format.

**Fix:** add `parse_size()` to `apps clear-cache --target`'s Click option
callback (one line).

**Reference:** PROGRESS.md 2026-06-17 "Known follow-up (deferred to post-#9 pass)".

---

### 1.11 Before/After Cleanup Comparison Report

**Scope:** CLI `report generate` + GUI Reports page.

Spec §9.4 describes a "phone storage before vs after comparison" report for
deletion operations. Pre-deletion preview (`build_delete_preview_report`) and
post-deletion summary (`build_post_deletion_report`) both exist individually,
but there is no combined side-by-side comparison report that takes both a
before-snapshot and the deletion result and shows the delta.

**Reference:** Project doc §9.4.

---

### 1.12 Mirror-Mode Real-Device Validation

**Scope:** CLI `transfer mirror-pull` / `transfer mirror-push`.

Mirror mode is implemented and unit-tested (PROGRESS.md 2026-06-16) but
real-device validation was deferred — it requires sufficient free space on the
test device to safely test a two-way sync without corrupting real data.
The note from the validation session: "Real-device validation pending (mirror
mode requires a device with sufficient storage to test)."

**Reference:** PROGRESS.md 2026-06-16 transfer retry/mirror entry.

---

## 2. Blocked Items — Technical Constraints

These features were investigated and found to be infeasible on a non-rooted
device via ADB. They are not bugs or gaps in the implementation — they are
fundamental Android security constraints.

### 2.1 Full App Data/Cache Backup & Restore

**What users expect:** extract an app's APK + its database/preferences/login
state, and restore all of it to the same or a new device.

**Why it's blocked:** An app's real internal data lives at
`/data/data/<package>/` (or `/data/user/0/<package>/`). This path is
inaccessible via `adb shell` without root for any normal app on Android 6+.
The only non-root mechanism, `adb backup`/`adb restore`, is effectively dead
since Android 12 (most apps disable it via `android:allowBackup="false"`;
requires an interactive on-device PIN; cannot be run headlessly).

The only external-storage folder accessible without root is
`/sdcard/Android/data/<package>/`, which for most apps is disposable cache
or asset storage — not the app state a user wants to back up.

**What IS implemented:** APK-only backup/restore — extract the APK file(s)
and a `manifest.json` bundle, reinstall with optional downgrade. This covers
the common use case of keeping an APK for offline sideloading.

**If revisited:** would require either (a) mandating root as a precondition
for this one feature (a project-wide scope change — DroidBridge is documented
as fully non-root), or (b) a companion on-device app that cooperates via ADB.

**Reference:** PROGRESS.md 2026-06-22 Apps GUI scoping; project doc §8 note.

---

### 2.2 WhatsApp Orphaned Media Detection

**What it would do:** identify files in WhatsApp's Media folder that have no
corresponding chat message in `msgstore.db` — safe to delete as truly orphaned.

**Why it's blocked:** `msgstore.db` is always encrypted as
`msgstore.db.crypt14` (or `.crypt12`/`.crypt15`). The decryption key lives at
`/data/data/com.whatsapp/files/key` — app-private storage, root-only on
Android 11+. There is no plain-SQLite `msgstore.db` accessible via ADB
without root, and there is no known method to decrypt `.crypt14` without the
key.

**Reference:** PROGRESS.md Phase 3.1 "Orphaned Media Detection — documented
out of scope (decision made 2026-06-12)"; project doc §4.1/§9.1.

---

### 2.3 WhatsApp Database Restore

**What it would do:** push a `msgstore.db.crypt14` backup back to the device
so WhatsApp picks it up and restores the chat history.

**Why it's blocked:** WhatsApp only processes a locally-restored database
during a fresh install + first-time login (not on an already-configured
device). Additionally, `Android/data/com.whatsapp/` is restricted on
Android 11+ — writing to it via ADB is blocked even for system files.

**What IS implemented:** database *backup* (`whatsapp backup-db`) — pulling
`Databases/`, `Backups/`, and `accounts/` to a local directory is fully
supported. The backup is useful for disaster recovery (re-install WhatsApp,
select the backup file during setup), but that restore flow is entirely
driven by the WhatsApp app itself.

**Reference:** Project doc §4.8/§4.9; PROGRESS.md Phase 3.5.

---

## 3. Out-of-Scope Decisions

These are features that were explicitly evaluated and decided against as
design decisions for the current project, not oversights.

### 3.1 WhatsApp Android-to-Android Full Chat Transfer

Investigated during Phase 3.5 wrap-up. The goal (clone chat history
from one Android to another) requires:
1. The decryption key from `/data/data/com.whatsapp/files/key` — root-only.
2. Re-encryption with the *destination* device's key — also root-only.

Without root on both devices simultaneously, it is not possible to move an
encrypted `msgstore.db.crypt14` from one device to another. WhatsApp's own
"Chat Transfer" feature (Wi-Fi Direct/QR, same network) already solves this
via its own device-to-device protocol — not something an external ADB tool
can drive.

**Decision:** Out of scope for DroidBridge. If ever pursued, it would be a
separate companion project that requires root on both devices.

**Reference:** Project doc §17.1; PROGRESS.md 2026-06-16 "Future idea".

---

### 3.2 WhatsApp Android-to-iOS Transfer

Moving WhatsApp chat history from Android to iOS is what paid tools
(MobileTrans, dr.fone, iCareFone) do. It requires:
1. Reading the decrypted Android `msgstore.db` (root-only, see §2.2 above).
2. Converting it to WhatsApp iOS's `ChatStorage.sqlite` (Core Data schema
   — changes with every WhatsApp iOS release).
3. Packaging the result as an iTunes/Finder-style backup.
4. Restoring it to an iPhone via `libimobiledevice` / `pymobiledevice3`
   (requires USB pairing trust with the iPhone).

This is a separate iOS-communication subsystem — not ADB, not Android.
The iOS schema maintenance is why these tools are paid/subscription products.
Building and distributing one carries real reverse-engineering/ToS exposure.

**Decision:** Out of scope for DroidBridge's ADB-only, fully-offline,
MIT-licensed, Android-focused design. Would be a separate companion project.

**Reference:** Project doc §17.1.

---

### 3.3 Large Files — Copy or Delete Found Files

Spec §5.4 mentions "Option to copy or delete found files." The Large Files
command and GUI tab are intentionally read-only (path/type/size only).

**Reasoning:**
- Copy → already covered by `transfer pull <path>`.
- Delete → would require the full backup-verification + `'YES DELETE'` safety
  machinery. Implementing it here would duplicate that machinery for arbitrary
  files; a future generic safe-delete command could cover this holistically.

**Reference:** PROGRESS.md Phase 4.1 "Deviations / Decisions".

---

### 3.4 System App Permanent Uninstall

The App Manager's uninstall command (and GUI) has a guard that refuses to
uninstall system apps (`is_system` check). Disabling system apps is supported
via the Bloatware Manager tab. Permanent removal of system apps (not just
disabling them) requires root and carries a high risk of breaking the device.

**Decision:** Safely blocked by design. Out of scope without root.

**Reference:** Project doc §8.3 "Cannot uninstall system apps (safely blocked)".

---

### 3.5 Contacts/Call Log Restore (Import)

The Backup Manager's Contacts & Call Log export is pull-only (backup only).
Restoring contacts or call log entries from a backup file back to the device
was considered and scoped out:
- Contacts import: `adb shell content insert` into the contacts provider is
  unreliable across Android versions; vCard import via the Contacts app is
  interactive and not automatable via ADB.
- Call log import: Android provides no ADB-accessible content provider for
  writing call log entries across all supported versions.

**Decision:** Export (backup) only. Restore is the user's responsibility via
the Contacts app (vCard import).

**Reference:** Project doc §6.6; PROGRESS.md 2026-06-19 Backup Manager entry.

---

## 4. Platform & Packaging Gaps

### 4.1 PyInstaller Packaging — Not Yet Done

**Status:** The final remaining Phase 6 deliverable.

**Scope:**
- Linux: `.AppImage` or directory bundle (primary target — development
  platform).
- Windows: `.exe` via PyInstaller + `--onefile` or `--onedir`.
- macOS: `.app` bundle via PyInstaller.

**Dependencies to resolve before bundling:**
- Swap the bundled Linux `adb` binary from the Debian package version
  (v28.0.2) to the official Google platform-tools release
  (CLAUDE.md note from Phase 1).
- Add the official Windows `adb.exe` and macOS `adb` binaries to
  `droidbridge/resources/platform-tools-windows/` and
  `droidbridge/resources/platform-tools-macos/` respectively.
  `core.adb.find_adb_binary`'s `_PLATFORM_DIRS` already has entries for both
  paths — drop-in, no code changes needed.
- Verify PyQt6 + all Python dependencies bundle cleanly under PyInstaller's
  `--collect-all` for Qt plugins.

**Reference:** Project doc §16 Phase 6; PROGRESS.md Phase 4.4.

---

### 4.2 Windows/macOS ADB Binaries Not Bundled

The official Google platform-tools archives for Windows and macOS were not
downloadable in the offline development environment. The `find_adb_binary`
function already falls back to the system PATH on those platforms, so the
CLI works if the user has ADB installed separately — but the packaging goal
is a zero-install single executable.

**To do:** download `platform-tools-latest-windows.zip` and
`platform-tools-latest-darwin.zip` from the official Android developer site
and extract `adb.exe` (Windows) / `adb` (macOS) into their respective
bundled resources folders.

---

### 4.3 Windows/macOS Real-Device Validation Deferred

The entire CLI and GUI have been validated only on Linux (Ubuntu with
Realme RMX1931). The cross-platform Python code (`os.path`/`pathlib`,
`PurePosixPath` for device paths, no Linux-specific shell syntax) is
designed to be portable, and Windows/macOS `SleepInhibitor` implementations
are unit-tested with mocks.

**To do:** run the full CLI and GUI test suites on real Windows and macOS
hardware once the ADB binaries and packaging are in place.

---

### 4.4 README and User Guide Not Finalized

Project doc §16 Phase 6 calls for "README, user guide, and CLI help text
finalized." CLI help text is in place (Click docstrings surfaced via `--help`).
The README (`README.md`) was created in Phase 1 as a project skeleton file
and has not been updated to reflect the full feature set.

**To do:** update `README.md` with installation, quick-start, feature
overview, and screenshots; consider a `docs/USER_GUIDE.md` with per-module
walkthroughs.

---

## 5. Future GUI Enhancement Ideas

These are improvements to the existing GUI that go beyond the original spec
but were noted during development or real-device validation passes. None are
bugs — the current GUI meets the spec.

### 5.1 Cancel / Interrupt for All Long-Running Operations

Only covers Storage GUI scans today (§1.2 above). The same need exists for:
- WhatsApp scan/analyze/backup (long ADB find + transfer).
- Storage media scan (full /sdcard find).
- App listing reload (dumpsys calls).
- App label resolution (the aapt2 pass takes ~5 minutes on first run).

A generalized cancellable-Worker pattern would let any background task be
interrupted cleanly.

---

### 5.2 App Label Cache Management

The aapt2 label cache lives at `~/.local/share/droidbridge/label_cache/<serial>.json`
and grows indefinitely. A user who reinstalls apps (new versions with new
labels) will see stale names until they manually delete the cache file.

**Enhancement ideas:**
- A "Clear label cache" button in the Apps Listing panel.
- Automatic cache invalidation when an app's `versionCode` changes.

---

### 5.3 Status Saver — Select All / Sort by Date

The thumbnail grid currently has no "Select All" checkbox and no sort control.
For users with 30+ status items, individual checkbox selection is tedious.

---

### 5.4 WhatsApp Delete — Live Preview of Space Freed

The Delete tab shows a preview table of files to be deleted. Adding a running
total ("Selecting X files will free Y GB") that updates as the user adjusts
the cutoff date would improve the decision workflow.

---

### 5.5 Backup Manager — Scheduled/Automatic Backups

The spec is silent on scheduling, but it's a natural follow-on: a
system-tray daemon that runs a named backup profile on a cron-like schedule
(daily/weekly) when the device is connected.

---

### 5.6 Multi-Device Support in GUI

The GUI currently assumes one connected device at a time (the single serial
shown in the top bar). The CLI already handles `--serial` selection. A
device-switcher dropdown in the top bar would let users work with multiple
simultaneously-connected devices.

---

## 6. Spec Audit Summary

Cross-check of every spec module against the current codebase.
**Legend:** ✅ Implemented & validated | 🔶 Partial (see note) | ❌ Not done

| Spec Section | Feature | Status |
|---|---|---|
| §1.1 Device detection | List/connect/auto-reconnect | ✅ |
| §1.2 USB info | Speed & mode detection | ✅ CLI only; not in GUI Device page |
| §1.3 Storage overview | Category breakdown, top apps, WhatsApp summary | ✅ |
| §1.4 ADB health | Auto-restart daemon, MTP detection | ✅ |
| §2.1 File browser | Browse, breadcrumb, quick-jump | ✅ |
| §2.2 Sorting & filtering | Name/size/date/type sort; ext/size/date/hidden filter | ✅ CLI; GUI missing date+size filters |
| §2.3 Preview | Text/image preview, path display | ✅ |
| §2.4 File operations | Pull, rename, delete, right-click menu, copy path | ✅ |
| §3.1 Transfer pull/push | Batch, progress, speed, ETA | ✅ |
| §3.2 Conflict resolution | skip/overwrite/rename | ✅; "ask each time" / "remember" deferred |
| §3/§15 Batch pull/push | 500 files per ADB call | ❌ Deferred (§1.7); deletion batching ✅ |
| §3.3 Resume | Skip already-present files on re-run | ✅ |
| §3.4 Mirror mode | plan_mirror_pull/push, execute_mirror | ✅ CLI; real-device validation pending |
| §3.5 Verification | Count + size post-transfer check | ✅ |
| §4.1 WhatsApp scan/analyze | Folder/year/month/ext/cutoff reports | ✅ |
| §4.1 Orphaned media | Detect files with no chat link | ❌ Blocked (root required, §2.2) |
| §4.2 Backup (media) | Full + selective, plan_backup | ✅ |
| §4.3 Organization | By date (voice/images/video), by category (docs) | ✅ |
| §4.5 Fix extensions | MIME sniff, double-dot fix | ✅ |
| §4.6 Cleanup/deletion | Preview, backup check, batch rm, rescan verify | ✅ |
| §4.8 Database backup | Databases/Backups/accounts pull | ✅ |
| §4.9 Database restore | Restore msgstore.db to device | ❌ Out of scope (§3.3) |
| §4.10 Status Saver | Pull .Statuses, thumbnail grid, checkbox select | ✅ |
| §5.1 Storage overview | df + diskstats categories | ✅ |
| §5.2 App storage | Per-package APK/data/cache sizes | ✅ |
| §5.3 Media analysis | Category breakdown, largest files, duplicates | ✅ |
| §5.3 Duplicate full list | All duplicate groups, not capped at 10 | ❌ Deferred (§1.1) |
| §5.4 Large files | List by size (read-only) | ✅; copy/delete out of scope (§3.3) |
| §5.5 Cleanup suggestions | APK installers, caches, logs | ✅ |
| §6.1 Backup profiles | Create/edit/delete/list named profiles | ✅ |
| §6.2 Backup execution | Run, incremental, sleep inhibitor | ✅; direct-to-external-drive untested |
| §6.3 Verification | Count + size check | ✅ |
| §6.4 Backup history | Log, browse, compare runs | ✅ |
| §6.4 Outdated detection | Alert when last backup > N days | ❌ Deferred (§1.8) |
| §6.5 Restore | Push backup back to device | ✅ |
| §6.6 Contacts & Call Log | Export vCard/CSV (backup only) | ✅; restore out of scope (§3.5) |
| §7.1 Search | Name/ext/size/date/MIME/regex/presets | ✅ CLI; GUI missing date+size (§1.3) |
| §7.2 Pull found files | --pull-to with transfer plan | ✅ |
| §8.1 App listing | All packages, versions, sizes, kind, status | ✅ |
| §8.2 Cache management | Estimate, trim-caches, clear per-app | ✅ |
| §8.3 Uninstall | User apps only; confirmation | ✅; batch uninstall GUI not implemented |
| §8.4 APK extraction | Pull APK(s) for any app | ✅ |
| §8.5 Bloatware manager | Disable/re-enable via pm | ✅ |
| §8 App data backup | Full data/cache backup/restore | ❌ Blocked (root required, §2.1) |
| §9.1 WhatsApp reports | Inventory, cutoff, file-type, section, documents | ✅ |
| §9.1 Orphaned media report | Files with no linked chat | ❌ Out of scope (§3.3) |
| §9.2 Storage reports | Overview, top apps, large files | ✅ |
| §9.2 Storage trend | Compare reports across sessions | ❌ Deferred (§1.6) |
| §9.3 Backup reports | Summary, verification, history | ✅ |
| §9.4 Deletion reports | Preview + post-deletion | ✅; before/after comparison deferred (§1.11) |
| §9.5 Report formats | TXT, HTML, CSV, JSON | ✅ |
| §9.6 Session logs | Create, write, summarize per operation | ✅ |
| §9.6 Log auto-sync | Copy session log to backup destination | ❌ Deferred (§1.9) |
| §14 GUI tooltips | All interactive widgets have tooltips | ✅ |
| §14 Keyboard shortcuts | Global + page-level shortcuts | ✅ |
| §14 Dark/light mode | Theme toggle | ✅ |
| §14 Cancel buttons | All long-running ops have Cancel | 🔶 Storage only (§1.2); others deferred (§5.1 future) |
| §14 Color-coded status | Error/warning/success in status bar | ✅ |
| §15 Windows/macOS support | Full validation on real hardware | ❌ Deferred (§4.3) |
| §15 Transfer speed | 3–5× faster than MTP | 🔶 Not formally benchmarked |
| §16 PyInstaller | Single executable per platform | ❌ Not yet done (§4.1) |
| §16 README/user guide | Finalized documentation | ❌ Not yet done (§4.4) |
| §17.1 WA cross-device | Android→Android/iOS chat transfer | ❌ Out of scope (§3.1/§3.2) |

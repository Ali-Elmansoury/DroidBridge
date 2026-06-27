# DroidBridge — User Guide

DroidBridge is an ADB-powered Android device management tool. It gives you fast
file transfers, a complete WhatsApp media toolkit, storage analysis, app
management, backups, and reporting — all from your computer, entirely
**offline**. No cloud account, no telemetry, no subscription. DroidBridge is
MIT licensed.

DroidBridge ships two interfaces that share the same underlying engine:

- A **PyQt6 desktop GUI** — point-and-click, with tooltips, keyboard shortcuts,
  and live progress for every operation.
- A **Click-based CLI** (`droidbridge`) — for scripting, automation, and
  terminal-only environments.

This guide covers both, end to end.

---

## Table of Contents

- [1. Getting Started](#1-getting-started)
  - [1.1 Enabling USB Debugging](#11-enabling-usb-debugging)
  - [1.2 Connecting Your Device](#12-connecting-your-device)
  - [1.3 Launching DroidBridge](#13-launching-droidbridge)
- [2. GUI Overview](#2-gui-overview)
  - [2.1 Layout](#21-layout)
  - [2.2 Top Bar (Device Status)](#22-top-bar-device-status)
  - [2.3 Sidebar Navigation](#23-sidebar-navigation)
  - [2.4 Status Bar and Log Panel](#24-status-bar-and-log-panel)
  - [2.5 Theme Toggle](#25-theme-toggle)
  - [2.6 Tooltips](#26-tooltips)
  - [2.7 The Export… Button](#27-the-export-button)
- [3. Module Pages](#3-module-pages)
  - [3.1 Device (Ctrl+1)](#31-device-ctrl1)
  - [3.2 Files (Ctrl+2)](#32-files-ctrl2)
  - [3.3 Transfer (Ctrl+3)](#33-transfer-ctrl3)
  - [3.4 Search (Ctrl+4)](#34-search-ctrl4)
  - [3.5 WhatsApp (Ctrl+5)](#35-whatsapp-ctrl5)
  - [3.6 Storage (Ctrl+6)](#36-storage-ctrl6)
  - [3.7 Backup (Ctrl+7)](#37-backup-ctrl7)
  - [3.8 Apps (Ctrl+8)](#38-apps-ctrl8)
  - [3.9 Reports (Ctrl+9)](#39-reports-ctrl9)
- [4. Keyboard Shortcuts Reference](#4-keyboard-shortcuts-reference)
- [5. Session Logs](#5-session-logs)
- [6. CLI Reference](#6-cli-reference)
  - [6.1 Global Conventions](#61-global-conventions)
  - [6.2 device](#62-device)
  - [6.3 files](#63-files)
  - [6.4 transfer](#64-transfer)
  - [6.5 whatsapp](#65-whatsapp)
  - [6.6 storage](#66-storage)
  - [6.7 backup](#67-backup)
  - [6.8 apps](#68-apps)
  - [6.9 report](#69-report)
  - [6.10 gui](#610-gui)
- [7. Tips and Best Practices](#7-tips-and-best-practices)
- [8. Troubleshooting](#8-troubleshooting)

---

## 1. Getting Started

### 1.1 Enabling USB Debugging

DroidBridge talks to your phone over ADB (Android Debug Bridge), the same
protocol Android Studio uses. Before connecting, enable Developer Options and
USB Debugging on the phone (Android 8 and newer):

1. Open **Settings → About phone**.
2. Tap **Build number** seven times in a row. You'll see a toast confirming
   "You are now a developer."
3. Go back to **Settings**, open the new **Developer options** menu.
4. Enable **USB debugging**.

### 1.2 Connecting Your Device

1. Plug your phone into the computer with a USB cable.
2. A dialog appears on the phone: **"Allow USB debugging?"** — tap **Allow**
   (optionally check "Always allow from this computer" to skip this in the
   future).
3. In DroidBridge, the device status dot in the top bar turns green and shows
   the device's serial number and model once it's recognized.

If nothing happens, see [Troubleshooting](#8-troubleshooting).

### 1.3 Launching DroidBridge

- **GUI:** run `droidbridge gui`, or use your platform's installed launcher
  (e.g. `droidbridge-gui` / the application menu entry / desktop icon).
- **CLI:** run any `droidbridge <command>` from a terminal — see
  [CLI Reference](#6-cli-reference).

---

## 2. GUI Overview

### 2.1 Layout

The main window is divided into four areas:

- **Left sidebar** — 9 module icons/labels, one per page.
- **Top bar** — device connection status and a Connect button.
- **Main content area** — the active module's page, switched via the sidebar
  or `Ctrl+1`–`Ctrl+9`.
- **Bottom status bar and log panel** — current operation status, with an
  expandable panel showing the live operation log.

### 2.2 Top Bar (Device Status)

- A colored **status dot**: green means a device is connected and ready,
  red means no device is detected.
- A **serial/model label** next to the dot, showing the connected device's
  serial number and model name once detected.
- A **Connect** button to manually trigger device detection/reconnection if
  the dot is red or if you've swapped devices.

### 2.3 Sidebar Navigation

The sidebar lists all 9 modules in order. Click any entry, or use its
shortcut, to switch pages:

| # | Module | Shortcut |
|---|--------|----------|
| 1 | Device | `Ctrl+1` |
| 2 | Files | `Ctrl+2` |
| 3 | Transfer | `Ctrl+3` |
| 4 | Search | `Ctrl+4` |
| 5 | WhatsApp | `Ctrl+5` |
| 6 | Storage | `Ctrl+6` |
| 7 | Backup | `Ctrl+7` |
| 8 | Apps | `Ctrl+8` |
| 9 | Reports | `Ctrl+9` |

These shortcuts work from anywhere in the main window, regardless of which
page or control currently has focus.

### 2.4 Status Bar and Log Panel

The bottom of the window has a status bar that summarizes the most recent
action ("Connected to device", "Transfer complete", "3 files deleted", etc.).
Next to it is a collapsible **log panel** — expand it to see a real-time,
timestamped log of every operation DroidBridge performs (ADB commands run,
files copied, errors hit). This is the best place to look when something
doesn't behave as expected, since it shows full detail that wouldn't fit in
the one-line status bar.

### 2.5 Theme Toggle

DroidBridge supports both dark and light themes. Use the theme toggle control
(in the top bar / settings area) to switch — your choice is saved as a
preference and restored automatically the next time you launch the app.

### 2.6 Tooltips

Every button, checkbox, dropdown, and field in the GUI has a tooltip. Hover
your mouse over any control for a second or two to see a short description of
what it does. If you're ever unsure what a button does, hovering over it is
the fastest way to find out before clicking.

### 2.7 The Export… Button

Most result tables across the app (Files, Search, Storage tabs, Apps tabs,
WhatsApp Scan/Analyze, etc.) have an **Export…** button. Clicking it opens a
file save dialog where you choose:

- **Format** — determined by the file extension you choose or type:
  - `.txt` — plain text, one entry per line, human-readable.
  - `.csv` — comma-separated values, for spreadsheets.
  - `.html` — a formatted HTML table, for sharing or printing.
  - `.json` — structured JSON, for scripts and other tools.
- **Path** — anywhere on your local filesystem.

The exported file always reflects exactly what's currently shown in the
table — including any filters, sorting, or search results applied — so you
can export a filtered subset rather than everything.

---

## 3. Module Pages

### 3.1 Device (Ctrl+1)

The landing page for the currently connected device. Shows:

- **Model** and **manufacturer**
- **Android version** and **build number**
- **Serial number**
- **Storage breakdown** — total, used, and free space
- **Battery percentage**
- **USB connection type** (e.g. USB 2.0 / USB 3.0)
- **Estimated transfer speed** based on the detected USB type

**Refresh:** click the Refresh button, or press `F5`, to re-query the device
and update all fields (useful after charging changes the battery level, or
after freeing up storage elsewhere in the app).

### 3.2 Files (Ctrl+2)

A full file browser for the device's filesystem, similar to a desktop file
manager.

**Navigation**

- **Address bar** — type a path and click **Go**, or press `Enter`/`Return`,
  to jump directly to that path.
- **Up button** — go to the parent directory. Also bound to `Backspace` when
  the file list has focus.
- **Double-click** a folder to open it; double-click a file to preview it
  (see Preview panel below).
- **Quick-jump dropdown** — jump straight to common locations such as
  `DCIM`, `Downloads`, or the WhatsApp media folder, without typing a path.

**Selection and editing**

- `Ctrl+A` — select all items in the current folder.
- `Escape` — deselect everything.
- `F2` — rename the selected item.
- `Delete` (with the file list focused) — delete the selected item(s).
- `Ctrl+Shift+C` — copy the full device path of the selected item to the
  clipboard.
- **Right-click** any item for a context menu: **Copy Path**, **Download**,
  **Rename**, **Delete**.

**Other controls**

- **F5** — refresh the current directory listing.
- **Download button** — pull the selected file(s) or folder(s) from the
  device to your computer (opens a destination picker).
- **New Folder button** — create a new subfolder inside the current device
  directory.
- **Toggle hidden files checkbox** — show or hide dotfiles and other hidden
  entries.
- **Sort** — click a column header (Name, Size, Date, Type) to sort by that
  column; click again to reverse the order.
- **File preview panel** (right side) — shows a thumbnail for images and
  general file info (size, date, type, permissions) for the selected item.
- **Export…** — export the current directory listing to TXT/CSV/HTML/JSON.

### 3.3 Transfer (Ctrl+3)

Dedicated bulk file-transfer page, for when you know exactly what you want to
move rather than browsing interactively.

1. **Mode** — choose **Pull** (device → computer) or **Push**
   (computer → device).
2. **Local path** — the computer-side folder or file. Use the **Browse**
   button to open a native file picker.
3. **Remote path** — the device-side folder or file. Use its **Browse**
   button to open the device file browser and pick a path visually.
4. **Conflict mode** — what to do if the destination already has a file with
   the same name:
   - **Skip** — leave the existing file untouched, don't transfer that item.
   - **Overwrite** — replace the existing file.
   - **Rename** — keep both, giving the incoming file a new unique name.
5. **Post-transfer verify checkbox** — after the transfer, re-check file sizes
   (and/or hashes) on both sides to confirm the copy was complete and
   uncorrupted.
6. Start the transfer with the **Start** button or `Ctrl+Return`.
7. Watch the **progress bar** for live status.
8. Use **Export…** afterward to save a record of what was transferred
   (including any skipped/failed items) to TXT/CSV/HTML/JSON.

### 3.4 Search (Ctrl+4)

Search the device's filesystem by name, type, date, and size — much faster
than browsing manually when looking for specific files.

**Filters**

- **Name field** with a **Glob/Regex toggle** — switch between simple
  wildcard matching (`*.jpg`, `IMG_*`) and full regular expressions for more
  precise patterns.
- **MIME type dropdown** — filter by general file category (e.g. image,
  video, audio, document) instead of typing a name pattern. The MIME dropdown
  and the name pattern are **mutually exclusive** — selecting one clears the
  other, since combining them doesn't make sense for how the search is
  built.
- **Date range** — **After**/**Before** date pickers to filter by last
  modified date.
- **Size range** — **Min**/**Max** fields with a unit dropdown (KB/MB/GB).
- **Scope** — search the **full device** or restrict to a **specific
  folder**.
- **Quick presets dropdown** — one-click common searches, such as "WhatsApp
  media," "large files," or "files with no extension," without manually
  configuring filters.

**Running and acting on results**

- `F5` — run the search with the current filters.
- `Ctrl+A` — select all results.
- `Escape` — clear the selection.
- `F2` — rename the selected result.
- `Delete` — delete the selected result(s).
- `Ctrl+Shift+C` — copy the device path of the selected result.
- **Export…** — export the result list to TXT/CSV/HTML/JSON.

### 3.5 WhatsApp (Ctrl+5)

A dedicated toolkit for managing WhatsApp's media and database files on the
device, organized as a tabbed page.

**App selector** — at the top of the page, choose which app to operate on:
**WhatsApp**, **WhatsApp Business**, or **Both**. This selection applies to
whichever tab is currently active.

#### Tab 1 — Scan

Scans the selected app's media folders and reports what's there. Results are
shown in a table broken down by folder (Images, Video, Voice Notes,
Documents, etc.) with file counts and total size per folder. Use
**Export…** to save the scan results.

#### Tab 2 — Analyze

Pick a **cutoff date** and DroidBridge produces a comparison table of media
**before** vs. **after** that date — file counts and total size for each
side. Useful for deciding how much you'd reclaim by clearing out old media.
Use **Export…** to save the comparison.

#### Tab 3 — Backup

Copies WhatsApp media off the device to a folder on your computer.

- **Destination folder** field + **Browse** button.
- **Type checkboxes** — choose exactly which media types to include:
  Images, Videos, Voice Notes, Documents, Stickers, Audio, GIFs, Profile
  Photos, Video Notes, WallPaper.
- **Conflict mode** — Skip / Overwrite / Rename, same semantics as Transfer.
- **Verify checkbox** — confirm files copied completely after the backup.
- **Progress bar** shows live status during the backup.

#### Tab 4 — Restore

Pushes a previously backed-up media folder back onto the device.

- **Source folder** — the backup folder on your computer.
- **Destination path** — auto-filled based on the selected app (WhatsApp vs.
  Business) so files land back in the correct media directories.
- **Conflict mode** and **Verify checkbox**, same as Backup.
- **Progress bar** during restore.

#### Tab 5 — Organize

Reorganizes media **in place on the device** (no copy to computer involved).

- **Source folder** — the WhatsApp media folder to organize.
- **Type selector** — `images`, `videos`, `voice_notes`, or `documents`.
- Running this sorts/cleans up that media type's folder structure on the
  device directly.

#### Tab 6 — Delete

Deletes old WhatsApp media by date, with a safety preview before anything is
removed.

1. Set a **cutoff date**.
2. Check **keep-types** for any media types you want to exclude from
   deletion regardless of age.
3. The **preview table** shows exactly what **will** be deleted — review it
   carefully before proceeding.
4. Click **Execute delete**. A confirmation dialog appears requiring you to
   type **`YES DELETE`** exactly — this is a deliberate friction point to
   prevent accidental data loss, since this operation is destructive and not
   easily reversible.
5. A **progress bar** shows deletion progress.

#### Tab 7 — Save Status

Lets you save WhatsApp/WhatsApp Business **Status** media (the
disappearing-after-24h photos/videos people post) before they expire.

1. Click **Load Statuses** to scan the current status cache and populate a
   **thumbnail grid** — images show a real preview, videos show a ▶ play
   icon, or an actual frame thumbnail if `ffmpeg` is available on your
   system `PATH`.
2. Check the items you want to keep (each item has its own checkbox).
3. Set the **Destination** folder (+ **Browse** button).
4. Click **Save Selected** to copy the chosen statuses to your computer.

#### Tab 8 — Backup DB

Backs up WhatsApp's database and account files — separate from the media
backed up in Tab 3.

- **Destination folder**.
- Backs up the `Databases/`, `Backups/`, and `accounts` data.
- **Verify checkbox** and **progress bar**, same conventions as the other
  transfer-style operations.

### 3.6 Storage (Ctrl+6)

Analyzes how the device's storage is being used, across five tabs.

#### Tab 1 — Overview

A visual breakdown (pie/bar chart) of **total/used/free** space, plus a
category breakdown: Apps, Images, Videos, Audio, Documents, Downloads,
System.

#### Tab 2 — Apps

A table of every installed app, sorted by **total size** (APK + app data +
cache combined). Shows the app's friendly **display name** rather than just
its package ID. Use **Export…** to save the listing.

#### Tab 3 — Media

Scans all media across the entire phone (not just WhatsApp) and breaks it
down by type (images, video, audio, etc.). Use **Export…** to save it.

#### Tab 4 — Large Files

Finds files above a size threshold you set with the **threshold spinner**
(defaults to **50 MB**). Results appear in a table. Use **Export…** to save
the list.

#### Tab 5 — Cleanup

Suggests safe things to clean up: cache files, leftover APK installers,
thumbnail caches, etc. Use **Export…** to save the suggestions list (note:
this tab only lists suggestions — it does not delete anything for you).

### 3.7 Backup (Ctrl+7)

Manage repeatable, named backup configurations across six tabs.

#### Tab 1 — Profiles

Create, edit, and delete named **backup profiles** — each profile bundles a
**name**, a list of **folders** to back up, and a **destination** path. This
lets you define a backup job once and re-run it without re-entering the
details every time.

#### Tab 2 — Run

Select a profile (and optionally override its destination), check
**Incremental** if you only want to copy files that changed since the last
run, and click **Run** to execute the backup. A **progress bar** tracks
status live.

#### Tab 3 — Verify

Select a backup's destination folder, and DroidBridge verifies it against
the original source — checking **file count** and **total size** match what
was expected.

#### Tab 4 — History

A table of every past backup run: timestamp, profile used, file count, total
size, and duration. Use this to audit what's been backed up and when.

#### Tab 5 — Restore

Push a previously created backup folder back onto the device. Choose the
**source backup folder**, **conflict mode** (Skip/Overwrite/Rename), and
watch the **progress bar** during the restore.

#### Tab 6 — Contacts/Call Log

Export your **Contacts** (as vCard, CSV, or JSON) or **Call Log** (as CSV or
JSON) directly from the device. This is a backup-only feature — it reads and
exports contacts/call log data but does not modify or restore them onto the
device. Click **Export…** to choose format and save location.

### 3.8 Apps (Ctrl+8)

App management across six tabs.

#### Tab 1 — Listing

A full table of installed apps: display name, package ID, APK size, data
size, cache size, and total. **Filter** by user / system / all apps, and
**sort** by any column. Use **Export…** to save the listing.

#### Tab 2 — Cache Management

Select one or more apps and click to **clear their cache**. DroidBridge shows
the **estimated space freed** after the operation completes.

#### Tab 3 — Uninstall

Select a **user-installed** app (system apps cannot be uninstalled this way)
and uninstall it. A **confirmation dialog** appears before anything is
removed, since uninstalling is irreversible without reinstalling the app.

#### Tab 4 — APK Extraction

Select an installed app and **extract its APK** file to a local folder on
your computer — useful for backing up an app you might need to reinstall
later, or for sharing an APK manually.

#### Tab 5 — Bloatware Manager

Identifies pre-installed manufacturer apps (the "bloatware" that comes
factory-installed on many Android phones) and lets you **disable** or
**re-enable** them. Disabling is non-destructive and reversible — it hides
the app and stops it from running without fully uninstalling system
components.

#### Tab 6 — Backup & Restore

Back up an app's **APK file** to a folder, or **restore** (reinstall) an APK
from a previously saved file.

### 3.9 Reports (Ctrl+9)

Generates formatted reports summarizing device, WhatsApp, storage, or backup
data.

1. Choose a **report type** from the dropdown. Thirteen types are available:
   - Full Report
   - Storage Breakdown
   - Top Apps by Size
   - Large Files
   - Storage Trend
   - WhatsApp Media Inventory
   - WhatsApp Pre/Post Cutoff Comparison
   - WhatsApp File Type Breakdown
   - WhatsApp Sent/Received/Private Breakdown
   - WhatsApp Documents Categorization
   - Backup History
   - Backup Summary
   - Backup Verification
2. Fill in any **contextual parameters** that appear for the chosen report
   type — only the relevant ones are shown:
   - **Top N** spinner (e.g. for "Top Apps by Size")
   - **Min size** (e.g. for "Large Files")
   - **Cutoff date** (for WhatsApp comparison reports)
   - **WhatsApp app** selector (WhatsApp / Business / Both)
   - **Backup profile** selector (for Backup-related reports)
3. Choose an output **Format**: TXT, CSV, HTML, or JSON.
4. Click **Generate** — the report renders in a **live preview** text area so
   you can review it before saving.
5. Click **Save As…** to write the report to disk in your chosen format.

---

## 4. Keyboard Shortcuts Reference

### Global (work anywhere in the main window)

| Shortcut | Action |
|---|---|
| `Ctrl+1` | Switch to Device page |
| `Ctrl+2` | Switch to Files page |
| `Ctrl+3` | Switch to Transfer page |
| `Ctrl+4` | Switch to Search page |
| `Ctrl+5` | Switch to WhatsApp page |
| `Ctrl+6` | Switch to Storage page |
| `Ctrl+7` | Switch to Backup page |
| `Ctrl+8` | Switch to Apps page |
| `Ctrl+9` | Switch to Reports page |

### Device page

| Shortcut | Action |
|---|---|
| `F5` | Refresh device info, battery, and storage |

### Files page

| Shortcut | Scope | Action |
|---|---|---|
| `Enter` / `Return` | Address bar | Navigate to the typed path |
| `Backspace` | File list focused | Navigate to parent directory |
| `F5` | Page | Refresh current directory |
| `Ctrl+A` | Page | Select all items |
| `Escape` | Page | Deselect all |
| `F2` | File list focused | Rename selected item |
| `Delete` | File list focused | Delete selected item(s) |
| `Ctrl+Shift+C` | Page | Copy selected item's path to clipboard |

### Transfer page

| Shortcut | Action |
|---|---|
| `Ctrl+Return` | Start the pull or push transfer |

### Search page

| Shortcut | Scope | Action |
|---|---|---|
| `F5` | Page | Run search with current filters |
| `Ctrl+A` | Page | Select all results |
| `Escape` | Page | Clear selection |
| `F2` | Results table focused | Rename selected result |
| `Delete` | Results table focused | Delete selected result(s) |
| `Ctrl+Shift+C` | Page | Copy selected result's path to clipboard |

### WhatsApp, Storage, Backup, Apps, Reports pages

These are multi-tab pages where each tab has its own dedicated buttons
(Scan, Run, Generate, Delete, Uninstall, etc.) rather than a single page-wide
action — use the on-screen buttons within each tab. The only shortcuts that
apply are the global `Ctrl+5`–`Ctrl+9` page-switch shortcuts above.

---

## 5. Session Logs

Every time DroidBridge runs (GUI or CLI), it writes a **session log** to a
`session_logs/` folder created in the current working directory. Each run
gets its **own subfolder**, so logs from different sessions never overwrite
each other.

Each session log records:

- **Timestamps** for every operation performed
- **Counts** of files/items processed
- **Sizes** transferred or affected
- **Errors** encountered, with enough detail to diagnose what went wrong

Use session logs to audit exactly what an operation did after the fact, or to
get the precise error text when something fails — the in-app log panel shows
the same information live, but the session log file persists after you close
the app.

---

## 6. CLI Reference

The CLI is invoked as `droidbridge <group> <command> [options]`. Every
command that targets a connected device supports `-s SERIAL` /
`--serial SERIAL` to target a specific device when multiple are connected;
omit it if only one device is attached.

### 6.1 Global Conventions

- Dates are given as `YYYY-MM-DD`.
- Sizes accept a number with a unit suffix (e.g. `50MB`, `1.5GB`).
- `--conflict` accepts `skip`, `overwrite`, or `rename`.
- `--verify` is a flag (no value) that enables post-transfer verification.
- Run `droidbridge --help` or `droidbridge <group> --help` at any time to see
  built-in usage help.

### 6.2 device

```bash
droidbridge device info [-s SERIAL]
droidbridge device connect [-s SERIAL]
```

- `info` — print model, manufacturer, Android version, build number, serial,
  storage breakdown, and battery percentage.
- `connect` — check that ADB can see and communicate with the device.

### 6.3 files

```bash
droidbridge files browse <path> [-s SERIAL]
droidbridge files search [--name] [--regex] [--mime] [--after] [--before]
                         [--min-size] [--max-size] [--path] [-s SERIAL]
droidbridge files rename <old_path> <new_path> [-s SERIAL]
droidbridge files delete <path> [<path>...] [-s SERIAL]
```

- `browse` — list the contents of `<path>` on the device (default: `/sdcard`).
- `search` — search the device filesystem:
  - `--name` — filename pattern (glob by default, or literal string).
  - `--regex` — treat `--name` as a regular expression instead of a glob.
  - `--mime` — filter by MIME type (e.g. `image/jpeg`); mutually exclusive with `--name`.
  - `--after` / `--before` — date range (`YYYY-MM-DD`).
  - `--min-size` / `--max-size` — size range (e.g. `10MB`, `500KB`).
  - `--path` — restrict search to a specific folder instead of the whole device.
- `rename` — rename or move a file/folder on the device from `old_path` to `new_path`.
- `delete` — permanently delete one or more files/folders from the device (use with caution).

### 6.4 transfer

```bash
droidbridge transfer pull <remote_path> <local_path> [--conflict skip|overwrite|rename] [--verify] [-s SERIAL]
droidbridge transfer push <local_path> <remote_path> [--conflict skip|overwrite|rename] [--verify] [-s SERIAL]
```

- `pull` — copy `<remote_path>` from the device to `<local_path>` on your
  computer.
- `push` — copy `<local_path>` from your computer to `<remote_path>` on the
  device.
- `--conflict` — how to handle existing files at the destination.
- `--verify` — verify the copy completed correctly after transfer.

### 6.5 whatsapp

```bash
droidbridge whatsapp scan [--app whatsapp|business|all] [--breakdown folder|year|ext] [-s SERIAL]
droidbridge whatsapp analyze --cutoff YYYY-MM-DD [--app] [-s SERIAL]
droidbridge whatsapp backup --dest PATH [--app] [--type TYPES] [--conflict] [--verify] [-s SERIAL]
droidbridge whatsapp restore --src PATH [--app] [--conflict] [--verify] [-s SERIAL]
droidbridge whatsapp organize --src PATH --type images|videos|voice_notes|documents [-s SERIAL]
droidbridge whatsapp delete --before YYYY-MM-DD [--app] [--keep TYPES] [-s SERIAL]
droidbridge whatsapp save-status --dest PATH [--app] [-s SERIAL]
droidbridge whatsapp backup-db --dest PATH [--app] [--verify] [-s SERIAL]
droidbridge whatsapp fix-extensions --path PATH
```

- `scan` — inventory WhatsApp media. `--breakdown` controls how results are
  grouped: by `folder`, by `year`, or by file `ext`(ension).
- `analyze` — compare media before/after `--cutoff` date.
- `backup` — copy media to `--dest`. `--type` accepts a comma-separated list
  of media types (e.g. `images,videos,documents`).
- `restore` — push a previously backed-up folder (`--src`) back to the
  device.
- `organize` — reorganize one media `--type` in place on the device.
- `delete` — delete media older than `--before`. `--keep` accepts a
  comma-separated list of types to exclude from deletion. **This is
  destructive** — review what would be deleted (e.g. with `scan`/`analyze`
  first) before running it.
- `save-status` — copy current WhatsApp Status media to `--dest` before it
  expires.
- `backup-db` — back up WhatsApp's `Databases/`, `Backups/`, and account
  files to `--dest`.
- `fix-extensions` — scan a local backup directory and rename any files that
  have a missing or double-dot extension using MIME-type fingerprinting (e.g.
  `DOC-20220310-WA0001.` → `.pdf`).

For all `whatsapp` commands, `--app` accepts `whatsapp`, `business`, or `all`
to target WhatsApp, WhatsApp Business, or both.

### 6.6 storage

```bash
droidbridge storage analyze [-s SERIAL]
droidbridge storage apps [--top N] [-s SERIAL]
droidbridge storage large-files [--min-size SIZE] [-s SERIAL]
droidbridge storage cleanup [-s SERIAL]
```

- `analyze` — overall storage breakdown (total/used/free + category
  breakdown).
- `apps` — list apps by total size; `--top N` limits to the N largest.
- `large-files` — find files above `--min-size` (default 50MB-equivalent
  threshold used by the GUI; specify explicitly on the CLI).
- `cleanup` — list cleanup suggestions (cache, leftover installers,
  thumbnails).

### 6.7 backup

```bash
droidbridge backup run --profile NAME [--dest PATH] [-s SERIAL]
droidbridge backup verify --dest PATH [-s SERIAL]
droidbridge backup history
droidbridge backup restore --src PATH [--conflict] [-s SERIAL]
```

- `run` — execute a backup using profile `NAME` (profiles are configured via
  the GUI's Backup → Profiles tab); `--dest` overrides the profile's saved
  destination if provided.
- `verify` — check a completed backup at `--dest` against its source (file
  count and size).
- `history` — print the table of past backup runs (no device required).
- `restore` — push a backup folder (`--src`) back onto the device.

### 6.8 apps

```bash
droidbridge apps list [--filter user|system|all] [--sort size|name] [-s SERIAL]
droidbridge apps clear-cache [--all] [--package PACKAGE] [-s SERIAL]
droidbridge apps uninstall --package PACKAGE [-s SERIAL]
droidbridge apps extract-apk --package PACKAGE --dest PATH [-s SERIAL]
```

- `list` — list installed apps; `--filter` restricts to user/system/all
  apps, `--sort` orders by size or name.
- `clear-cache` — clear cache for `--package PACKAGE`, or for every app with
  `--all`.
- `uninstall` — uninstall the given `--package` (user apps only).
- `extract-apk` — extract the APK for `--package` to `--dest`.

### 6.9 report

```bash
droidbridge report generate --type TYPE [--format txt|csv|html|json] [--output PATH] [-s SERIAL]
```

- `generate` — produce a report of `--type` (matching the 13 report types
  available in the GUI's Reports page — e.g. `full`, `storage-breakdown`,
  `top-apps`, `large-files`, `whatsapp-inventory`, `backup-history`, etc.),
  in the chosen `--format`, written to `--output` (prints to stdout if
  `--output` is omitted).

### 6.10 gui

```bash
droidbridge gui
```

Launches the PyQt6 desktop GUI described in the rest of this guide.

---

## 7. Tips and Best Practices

- **Hover before you click.** Every control has a tooltip — if a button's
  purpose isn't obvious, hover over it first.
- **Use Export… liberally.** Since it exports exactly what's currently shown
  in a table, you can filter or search first, then export just the subset
  you care about, rather than the full unfiltered data.
- **Always verify destructive operations in preview first.** WhatsApp Delete
  shows a preview table of what *will* be deleted before you confirm — read
  it carefully. The `YES DELETE` confirmation phrase is intentional friction,
  not a bug.
- **Use Search presets** for common tasks (like "WhatsApp media" or "large
  files") instead of manually configuring filters every time.
- **Run Storage → Large Files and Storage → Cleanup periodically** to spot
  reclaimable space before you run out of storage on the device.
- **Set up Backup Profiles** for any folder structure you back up
  regularly — it turns a multi-field form into a one-click **Run**.
- **Check the log panel** when something seems to silently fail — it almost
  always has more detail than the one-line status bar message, and the same
  detail is preserved afterward in the session log.
- **For video thumbnails in WhatsApp → Save Status**, install `ffmpeg` and
  make sure it's on your system `PATH` — without it, videos show only a
  generic ▶ icon instead of an actual frame preview.
- **Scripting repetitive workflows?** Every GUI action has a CLI equivalent;
  use the CLI in shell scripts or cron jobs for unattended backups and
  reports.

---

## 8. Troubleshooting

**Device not detected (status dot stays red / `device connect` fails)**

- Confirm USB debugging is enabled (see
  [1.1 Enabling USB Debugging](#11-enabling-usb-debugging)).
- Check the phone screen for an **"Allow USB debugging?"** dialog and tap
  **Allow** — it can appear after a delay or be hidden behind other apps.
- Try a different USB cable or port; some cables are charge-only and don't
  carry data.
- From a terminal, run `adb kill-server` and then reconnect — this resets
  ADB's internal device list and often clears stale connection state.
- Click the **Connect** button in the top bar to force DroidBridge to
  re-scan for devices.

**ADB errors mid-operation ("device offline", "device not found", etc.)**

- The device may have gone to sleep, locked, or been physically unplugged
  mid-transfer. Wake/unlock the phone, reconnect the cable, and retry the
  operation.
- Large or slow operations (full-device scans, big transfers) can be
  interrupted if the phone's screen times out and USB enters a low-power
  state on some devices — keep the screen on during long operations if you
  see this repeatedly.

**WhatsApp media not found (Scan/Analyze show nothing)**

- WhatsApp (or WhatsApp Business) must have been **run at least once** on
  the device — if it's freshly installed and never opened, its media
  folders don't exist yet.
- DroidBridge automatically tries both the modern (Android 10+) and legacy
  WhatsApp media paths, so this is rarely a path issue — it usually means
  there's genuinely no media yet, or you scanned the wrong app (check the
  **App selector**: WhatsApp vs. WhatsApp Business vs. Both).

**Video thumbnails missing in Save Status**

- Thumbnail generation for videos requires `ffmpeg` to be installed and
  available on your system `PATH`. Without it, DroidBridge falls back to a
  generic ▶ icon — this is expected behavior, not an error.

**Export or report file won't open in another program**

- Double-check the format matches the file extension you chose in the save
  dialog (e.g. a `.csv` opened as plain text will look comma-separated
  rather than tabular — open it with a spreadsheet program instead).

**Where to look for more detail**

- Expand the **log panel** at the bottom of the GUI for the live, detailed
  operation log.
- Check the relevant subfolder under `session_logs/` (created in the
  directory you launched DroidBridge from) for a persisted record of
  timestamps, counts, sizes, and error text from that session.

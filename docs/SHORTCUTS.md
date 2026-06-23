# DroidBridge Keyboard Shortcuts

All shortcuts are active within their listed scope. **Page shortcuts** require the
respective page to be open in the main window. **Table-focused shortcuts** only
fire when the file/results table has keyboard focus (click the table first).

## Global (anywhere in the window)

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

## Device page

| Shortcut | Action |
|---|---|
| `F5` | Refresh device info, battery, and storage |

## Files page

| Shortcut | Scope | Action |
|---|---|---|
| `F5` | Page | Refresh current directory listing |
| `Escape` | Page | Clear the file selection |
| `Ctrl+Shift+C` | Page | Copy device path of selected entry to clipboard |
| `Ctrl+A` | Page | Select all entries (Qt built-in) |
| `Backspace` | Table focused | Navigate to parent directory |
| `Return` | Table focused | Navigate into selected directory |
| `F2` | Table focused | Rename selected entry |
| `Delete` | Table focused | Delete selected entries |
| `Ctrl+Click` | Table focused | Toggle one entry in/out of the selection (Qt built-in) |
| `Shift+Click` | Table focused | Select a range from the last-clicked entry (Qt built-in) |

## Transfer page

| Shortcut | Action |
|---|---|
| `Ctrl+Return` | Start the pull or push transfer |

## Search page

| Shortcut | Scope | Action |
|---|---|---|
| `F5` | Page | Run search with current filters |
| `Escape` | Page | Clear the result selection |
| `Ctrl+Shift+C` | Page | Copy device path of selected result to clipboard |
| `Ctrl+A` | Page | Select all results (Qt built-in) |
| `F2` | Table focused | Rename selected result |
| `Delete` | Table focused | Delete selected results |
| `Ctrl+Click` | Table focused | Toggle one result in/out of the selection (Qt built-in) |
| `Shift+Click` | Table focused | Select a range from the last-clicked result (Qt built-in) |

## WhatsApp, Storage, Backup, Apps, Reports pages

No page-internal shortcuts. Each is a multi-tab page where every tab has its own
buttons (Refresh, Delete, Uninstall, etc.) with no single unambiguous page-wide
action to bind F5/Escape/Delete to. Use the global `Ctrl+5`..`Ctrl+9` shortcuts
above to switch to these pages, then click the relevant tab's buttons directly.

The WhatsApp page's **Backup** and **Delete** tabs have a multi-select list
(file types to back up / keep) that supports the same `Ctrl+Click` (toggle one)
and `Shift+Click` (select a range) gestures as the Files/Search tables above —
also Qt built-in, no custom wiring.

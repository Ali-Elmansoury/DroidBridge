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

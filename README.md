# DroidBridge

**ADB-powered Android device management — 3–5× faster than MTP, complete WhatsApp toolkit, storage analysis, app manager, and rich reports. 100% offline. No cloud. MIT licensed.**

> Version 1.0.0 | Linux · Windows · macOS

---

## Features

| Module | What it does |
|--------|-------------|
| **Device Manager** | Auto-detect devices, show model/Android version/storage/battery |
| **File Browser** | Browse, preview, rename, delete, and download device files |
| **Transfer Engine** | Batch ADB pull/push with conflict resolution, resume, and verification |
| **Search & Discovery** | Search by name (glob/regex), MIME type, date range, size range |
| **WhatsApp Toolkit** | Scan, backup, restore, organize, delete, save statuses, backup databases |
| **Storage Analyzer** | Full breakdown by category, top apps, large files, cleanup suggestions |
| **Backup Manager** | Named profiles, incremental backup, history, restore, contacts/call log export |
| **App Manager** | List all apps, clear cache, uninstall, extract APKs, manage bloatware |
| **Reports** | 13 structured report types in TXT / CSV / HTML / JSON |

Every results table has an **Export…** button — save what you see in any format.

---

## Screenshots

> _Screenshots will be added for the v1.0.0 release._

---

## Install

### Linux — .deb (Ubuntu 20.04+, amd64)

```bash
sudo dpkg -i droidbridge_1.0.0_amd64.deb
droidbridge-gui          # GUI
droidbridge --help       # CLI
```

### Linux — tarball (any distro, glibc 2.35+)

```bash
sudo tar -xzf droidbridge-linux-x86_64.tar.gz -C /opt/droidbridge --strip-components=1
sudo ln -s /opt/droidbridge/droidbridge-gui /usr/local/bin/droidbridge-gui
sudo ln -s /opt/droidbridge/droidbridge     /usr/local/bin/droidbridge
```

### Windows 10/11 (x64)

Extract `droidbridge-windows-x64.zip` anywhere and run `droidbridge-gui.exe`.
Add the folder to `PATH` for CLI access.

### macOS 12+ (Intel / Apple Silicon)

```bash
unzip droidbridge-macos-universal.zip -d /Applications/DroidBridge
/Applications/DroidBridge/droidbridge-gui
```

First launch: **System Settings → Privacy & Security → Open Anyway**, or:
```bash
xattr -dr com.apple.quarantine /Applications/DroidBridge/
```

See **[docs/INSTALL.md](docs/INSTALL.md)** for full install instructions, driver notes, and build-from-source guide.

---

## Quick Start

### Enable USB Debugging on your phone

1. **Settings → About phone** → tap **Build number** 7 times
2. **Developer options → USB debugging** → enable it
3. Plug in via USB → tap **Allow** on the phone

### GUI

```bash
droidbridge-gui
```

The device status dot in the top-left turns **green** when your phone is detected.
Use **Ctrl+1–9** to switch between modules. Hover any control for a tooltip.

### CLI

```bash
droidbridge device info                                    # device info
droidbridge whatsapp scan                                  # WhatsApp media scan
droidbridge whatsapp backup --dest /media/drive/backup/   # full WhatsApp backup
droidbridge transfer pull /sdcard/DCIM ~/Pictures/        # pull photos
droidbridge report generate --type full --format html     # HTML report
```

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/INSTALL.md](docs/INSTALL.md) | Full install guide for all platforms |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Per-module walkthroughs, CLI reference, shortcuts |
| [docs/DroidBridge_Project_Document.md](docs/DroidBridge_Project_Document.md) | Full spec and architecture |
| [docs/DEFERRED_AND_FUTURE_WORK.md](docs/DEFERRED_AND_FUTURE_WORK.md) | Known gaps, blocked items, future ideas |

---

## Build from Source

```bash
git clone https://github.com/your-org/droidbridge.git
cd droidbridge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gui]"
pip install pyinstaller

# Run from source
droidbridge --help
droidbridge-gui

# Run tests (1647 tests)
pytest

# Build Linux bundle + .deb
bash scripts/package-linux.sh
```

---

## Tech Stack

- **Python 3.10+** — core logic, CLI, GUI
- **PyQt6** — cross-platform desktop GUI
- **Click** — CLI argument parsing
- **ADB** — bundled Google platform-tools v37 (no Android SDK needed)
- **PyInstaller** — self-contained directory bundle per platform

---

## License

MIT — see [LICENSE](LICENSE).

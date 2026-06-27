# DroidBridge

### The Android device manager your phone deserves.

**3–5× faster than MTP. Complete WhatsApp toolkit. Storage analyzer. App manager. Rich reports. 100% offline — no cloud, no account, no subscription.**

> Works on Linux · Windows · macOS — GUI and CLI included.

---

## The problem DroidBridge solves

If you've ever tried to manage files on an Android phone from a computer, you know the pain:

- **MTP is painfully slow** — copying a few GB of photos takes forever, and it randomly disconnects mid-transfer
- **WhatsApp media piles up with no good way to manage it** — years of images, videos, and voice notes with no tools to analyze, organize, or clean them up
- **Android file management on Linux is almost broken** — MTP support is unreliable, and the few tools that exist are clunky
- **ADB is powerful but intimidating** — it's a command-line tool with no documentation for everyday users

DroidBridge wraps ADB in a clean desktop interface that makes all of this fast, safe, and accessible — without requiring any Android SDK or cloud services.

---

## What DroidBridge can do

### Files & Transfer
- Browse the device filesystem like a regular file manager
- Batch transfer files at **3–5× the speed of MTP** using ADB's pull/push engine
- Resume interrupted transfers — pick up where you left off
- Post-transfer verification — confirm every file copied correctly
- Search by name (glob/regex), MIME type, date range, or size

### WhatsApp Toolkit
The most complete WhatsApp media management tool available outside of WhatsApp itself:
- **Scan** — instant inventory of every media folder (Images, Video, Voice Notes, Documents, Stickers, and more) with counts and sizes
- **Analyze** — compare media before vs. after a cutoff date — see exactly how much space you'd reclaim
- **Backup** — selective backup by media type, with verification
- **Restore** — push a backup back to the device
- **Organize** — sort media by date or category, fix broken file extensions
- **Delete** — preview exactly what will be deleted, then confirm with a mandatory phrase before anything is removed
- **Save Statuses** — capture WhatsApp/Business Status media before it expires (24h)
- **Backup Databases** — back up the WhatsApp message database and account files

### Storage Analyzer
- Full storage breakdown by category (Apps, Images, Video, Audio, Documents, Downloads, System)
- App storage table sorted by total size — find what's eating your space
- Large file finder with a configurable size threshold
- Cleanup suggestions — cache, leftover APK installers, thumbnail caches

### Backup Manager
- Named backup profiles — define a backup job once, re-run it in one click
- Incremental backups — only transfer what changed
- Backup history — see every run with timestamps, file counts, and sizes
- Backup verification — confirm a backup is complete before deleting originals
- **Contacts & Call Log export** — export as vCard, CSV, or JSON

### App Manager
- Full app listing with display names, package IDs, APK/data/cache sizes
- Clear app cache (individual or all apps)
- Uninstall user apps
- Extract APKs — back up an app before uninstalling
- Bloatware manager — disable pre-installed manufacturer apps without rooting

### Reports
13 structured report types in TXT / CSV / HTML / JSON:
Full Report, Storage Breakdown, Top Apps by Size, Large Files, Storage Trend, WhatsApp Media Inventory, WhatsApp Pre/Post Cutoff, WhatsApp File Types, WhatsApp Sections, WhatsApp Documents, Backup History, Backup Summary, Backup Verification.

---

## No Android SDK required

DroidBridge bundles ADB (Google platform-tools v37) for all three platforms. You don't need to install the Android SDK, Android Studio, or anything from Google. Just plug in your phone.

---

## Screenshots

> Screenshots and demo video coming with the v1.0.0 launch.

---

## Install

Download the latest release for your platform from the [Releases](../../releases) page.

### Linux — .deb (Ubuntu 20.04+, amd64) — recommended

```bash
sudo dpkg -i droidbridge_1.0.0_amd64.deb
droidbridge-gui          # launch the GUI
droidbridge --help       # use the CLI
```

### Linux — tarball (any distro, glibc 2.35+)

```bash
tar -xzf droidbridge-linux-x86_64.tar.gz
./droidbridge-linux/droidbridge-gui
```

### Windows 10/11 (x64)

Extract `droidbridge-windows-x64.zip` and run `droidbridge-gui.exe`.
Add the folder to `PATH` for CLI access from any terminal.

### macOS (Apple Silicon / Intel)

```bash
unzip droidbridge-macos-universal.zip
./droidbridge-macos/droidbridge-gui
```

> First launch: macOS may block the app. Go to **System Settings → Privacy & Security → Open Anyway**, or run:
> ```bash
> xattr -dr com.apple.quarantine ./droidbridge-macos/
> ```

---

## Quick start

**1. Enable USB Debugging on your Android phone**

Settings → About phone → tap **Build number** 7 times → back → **Developer options** → enable **USB debugging**.

**2. Plug in your phone and launch DroidBridge**

```bash
droidbridge-gui
```

The status dot in the top bar turns **green** when your phone is detected. Tap **Allow** on the phone if a USB debugging dialog appears.

**3. Use `Ctrl+1` through `Ctrl+9`** to switch between modules. Hover any button for a tooltip.

---

## CLI examples

```bash
droidbridge device info
droidbridge whatsapp scan
droidbridge whatsapp analyze --cutoff 2024-01-01
droidbridge whatsapp backup --dest /media/drive/WA_backup/
droidbridge transfer pull /sdcard/DCIM ~/Pictures/
droidbridge storage large-files --min-size 100MB
droidbridge report generate --type full --format html --output ~/report.html
```

Full CLI reference: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)

---

## Documentation

| Document | Contents |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Full GUI and CLI reference, all modules, keyboard shortcuts |
| [docs/USER_GUIDE.pdf](docs/USER_GUIDE.pdf) | Same guide as a formatted PDF |
| [docs/DroidBridge_Project_Document.pdf](docs/DroidBridge_Project_Document.pdf) | Architecture, design decisions, implementation notes |

---

## Tech stack

Python 3.10 · PyQt6 · Click · ADB platform-tools v37 · PyInstaller · SQLite

---

## License

DroidBridge is **free for personal, non-commercial use**.

Commercial use (business deployment, resale, integration into paid products) requires a commercial license. See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) for tiers and pricing.

Source code is publicly available for transparency and review. See [LICENSE](LICENSE) for the full terms.

---

## Contact & commercial licensing

**Ali Elmansoury** — Junior Embedded Software / Android Automotive Engineer

- Email: ali.elmansoury21@gmail.com
- GitHub: [@Ali-Elmansoury](https://github.com/Ali-Elmansoury)
- LinkedIn: [ali-elmansoury](https://www.linkedin.com/in/ali-elmansoury/)

For commercial licensing inquiries, bug reports, or feature requests, open a [GitHub Issue](../../issues) or email directly.

# DroidBridge — Installation Guide

DroidBridge is distributed as a self-contained bundle — **no Python or ADB installation required**. The official Google ADB binary is bundled inside the package for every platform.

---

## Table of Contents

- [Linux](#linux)
  - [Option A: .deb package (recommended on Ubuntu/Debian)](#option-a-deb-package-recommended-on-ubuntudebian)
  - [Option B: Tarball (works on any Linux distro)](#option-b-tarball-works-on-any-linux-distro)
- [Windows](#windows)
- [macOS](#macos)
- [Building from Source](#building-from-source)
  - [Linux](#linux-build)
  - [Windows](#windows-build)
  - [macOS](#macos-build)
- [Uninstalling](#uninstalling)

---

## Linux

### Option A: .deb package (recommended on Ubuntu/Debian)

**Requires:** Ubuntu 20.04+ or any Debian-based distro, amd64.

```bash
# Download (replace X.Y.Z with the version number)
wget https://github.com/your-org/droidbridge/releases/download/vX.Y.Z/droidbridge_X.Y.Z_amd64.deb

# Install
sudo dpkg -i droidbridge_X.Y.Z_amd64.deb

# If dpkg reports missing dependencies, run:
sudo apt-get install -f
```

What gets installed:
| Path | Contents |
|------|----------|
| `/opt/droidbridge/` | Application bundle (executables + Qt runtime) |
| `/usr/bin/droidbridge` | CLI launcher (shell wrapper) |
| `/usr/bin/droidbridge-gui` | GUI launcher (shell wrapper) |
| `/usr/share/applications/droidbridge.desktop` | Application menu entry |

**Launch the GUI:**

```bash
droidbridge-gui
# or from your application menu: search "DroidBridge"
```

**Use the CLI:**

```bash
droidbridge --help
droidbridge device info
droidbridge whatsapp scan
```

**Connect your device:**

1. Enable USB Debugging on your Android phone:
   `Settings → About phone → tap Build number 7× → Developer options → USB debugging`
2. Plug in via USB
3. Tap "Allow" on the phone when prompted
4. The GUI device bar turns green; `droidbridge device info` prints device details

---

### Option B: Tarball (works on any Linux distro)

**Requires:** Linux x86_64, glibc 2.35+ (Ubuntu 22.04 / Fedora 36 or newer).

```bash
# Download
wget https://github.com/your-org/droidbridge/releases/download/vX.Y.Z/droidbridge-linux-x86_64.tar.gz

# Extract to /opt/droidbridge (or any directory you prefer)
sudo mkdir -p /opt/droidbridge
sudo tar -xzf droidbridge-linux-x86_64.tar.gz -C /opt/droidbridge --strip-components=1

# Optional: add launchers to PATH
sudo ln -s /opt/droidbridge/droidbridge-gui /usr/local/bin/droidbridge-gui
sudo ln -s /opt/droidbridge/droidbridge     /usr/local/bin/droidbridge
```

**Run directly** (without PATH symlinks):

```bash
/opt/droidbridge/droidbridge-gui       # GUI
/opt/droidbridge/droidbridge --help    # CLI
```

**glibc version check:** if the app fails to start with a `GLIBC_X.Y not found` error,
your distro is too old. Use a newer distro or build from source (see below).

---

## Windows

**Requires:** Windows 10 or 11, x64.

1. Download `droidbridge-windows-x64.zip` from the releases page.
2. Extract the zip — right-click → "Extract All" → choose a location such as
   `C:\Program Files\DroidBridge\`.
3. **Run the GUI:** double-click `droidbridge-gui.exe` inside the extracted folder.

**Optional: add to PATH for CLI use**

1. Open `Settings → System → About → Advanced system settings → Environment Variables`
2. Under "System variables", select `Path` → Edit → New
3. Add the path to the extracted folder (e.g., `C:\Program Files\DroidBridge`)
4. Open a new Command Prompt and run `droidbridge --help`

**ADB driver note:** Windows requires a USB driver to communicate with Android devices.
- Many devices work with the Google USB Driver (included in Android SDK Platform Tools).
- If your device isn't recognized: download the OEM USB driver from your phone
  manufacturer's website (Samsung, Xiaomi, etc.).
- After installing the driver, enable USB Debugging on your device (same steps as Linux
  above) and plug in the USB cable.

**Windows Defender / SmartScreen:** because the executable is not code-signed yet,
Windows may show "Windows protected your PC" on first run. Click "More info" →
"Run anyway".

---

## macOS

**Requires:** macOS 12 (Monterey) or newer, Intel or Apple Silicon (ARM64).

1. Download `droidbridge-macos-universal.zip` from the releases page.
2. Unzip: double-click the `.zip` in Finder, or:
   ```bash
   unzip droidbridge-macos-universal.zip -d /Applications/DroidBridge
   ```
3. **Run the GUI:**
   ```bash
   /Applications/DroidBridge/droidbridge-gui
   ```
   Or double-click `droidbridge-gui` in Finder.

**Gatekeeper (first run):**

macOS blocks unsigned binaries by default. On first run:

- A dialog appears: "droidbridge-gui cannot be opened because it is from an unidentified
  developer."
- Go to `System Settings → Privacy & Security` → scroll down → click **"Open Anyway"**
  next to the DroidBridge entry.
- Click "Open" in the confirmation dialog.

Alternatively, remove the quarantine attribute from Terminal:

```bash
xattr -dr com.apple.quarantine /Applications/DroidBridge/
```

**Optional: add CLI to PATH:**

```bash
sudo ln -s /Applications/DroidBridge/droidbridge /usr/local/bin/droidbridge
```

---

## Building from Source

Building requires Python 3.10+, PyInstaller, and PyQt6.
The build must run **on the target operating system** — PyInstaller does not cross-compile.

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-org/droidbridge.git
cd droidbridge
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,gui]"
pip install pyinstaller
```

### Linux build

```bash
bash scripts/package-linux.sh
```

Produces:
- `releases/droidbridge-linux-x86_64.tar.gz`
- `releases/droidbridge_1.0.0_amd64.deb`

Requires `dpkg-deb` and `fakeroot` (already present on Ubuntu):
```bash
sudo apt install dpkg-dev fakeroot
```

### Windows build

Run from a Windows machine in Command Prompt or PowerShell (Python and PyInstaller must
be on PATH):

```bat
scripts\package-windows.bat
```

Produces:
- `releases\droidbridge-windows-x64.zip`

### macOS build

```bash
bash scripts/package-macos.sh
```

Produces:
- `releases/droidbridge-macos-universal.zip`

---

## Uninstalling

**Linux (.deb install):**

```bash
sudo dpkg -r droidbridge
```

**Linux (tarball install):**

```bash
sudo rm -rf /opt/droidbridge
sudo rm -f /usr/local/bin/droidbridge /usr/local/bin/droidbridge-gui
```

**Windows:** delete the extracted folder (`C:\Program Files\DroidBridge\`).
Remove the PATH entry if you added one.

**macOS:** delete the extracted folder (`/Applications/DroidBridge/`).
Remove the symlink if you created one:
```bash
sudo rm /usr/local/bin/droidbridge
```

---

## User data

DroidBridge stores its configuration and label cache in:

| Platform | Path |
|----------|------|
| Linux | `~/.local/share/droidbridge/` |
| Windows | `%APPDATA%\droidbridge\` |
| macOS | `~/Library/Application Support/droidbridge/` |

Session logs are written to `session_logs/` in the **current working directory**
when the CLI or GUI is launched.

Uninstalling the application does **not** delete these directories. Remove them
manually if you want a clean uninstall.

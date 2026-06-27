# PyInstaller spec for DroidBridge — all platforms (Linux, Windows, macOS)
#
# Produces two executables sharing one _internal/ directory:
#   droidbridge-gui   — GUI, no console window
#   droidbridge       — CLI, console
#
# Build (run on the target OS):
#   pyinstaller droidbridge-gui.spec --distpath dist --workpath build/pyinstaller
#
# Output directory per platform:
#   dist/droidbridge-linux/    (Linux x86_64)
#   dist/droidbridge-windows/  (Windows x64)
#   dist/droidbridge-macos/    (macOS arm64/x86_64)
#
# The bundled adb binary is placed at:
#   _internal/droidbridge/resources/platform-tools-<os>/adb[.exe]
# find_adb_binary() in core/adb.py resolves it via __file__-relative RESOURCES_DIR,
# which PyInstaller preserves under _MEIPASS/droidbridge/core/adb.py.

import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ── Platform detection ────────────────────────────────────────────────────────

if sys.platform.startswith("linux"):
    _os_tag = "linux"
    _adb_src = "droidbridge/resources/platform-tools-linux/adb"
    _adb_dst = "droidbridge/resources/platform-tools-linux"
    _dist_name = "droidbridge-linux"
    _console_gui = False
elif sys.platform == "darwin":
    _os_tag = "macos"
    _adb_src = "droidbridge/resources/platform-tools-darwin/adb"
    _adb_dst = "droidbridge/resources/platform-tools-darwin"
    _dist_name = "droidbridge-macos"
    _console_gui = False
else:  # Windows
    _os_tag = "windows"
    _adb_src = "droidbridge/resources/platform-tools-windows/adb.exe"
    _adb_dst = "droidbridge/resources/platform-tools-windows"
    _dist_name = "droidbridge-windows"
    _console_gui = False

# ── Collect all PyQt6 data/binaries/hiddenimports ────────────────────────────
# Ensures Qt platform plugins (xcb, wayland, egl, cocoa, windows) and
# image format plugins (jpeg, png, svg) are all included.

pyqt6_datas, pyqt6_binaries, pyqt6_hiddenimports = collect_all("PyQt6")

# ── Shared binary list ────────────────────────────────────────────────────────

_adb_binary = [(_adb_src, _adb_dst)]
_all_binaries = _adb_binary + pyqt6_binaries

# ── GUI Analysis ──────────────────────────────────────────────────────────────

gui_a = Analysis(
    ["droidbridge/gui/app.py"],
    pathex=["."],
    binaries=_all_binaries,
    datas=pyqt6_datas,
    hiddenimports=[*pyqt6_hiddenimports, "PyQt6.sip"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

gui_pyz = PYZ(gui_a.pure, gui_a.zipped_data, cipher=block_cipher)

gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    [],
    exclude_binaries=True,
    name="droidbridge-gui",
    debug=False,
    strip=False,
    upx=True,
    console=_console_gui,
)

# ── CLI Analysis ──────────────────────────────────────────────────────────────

cli_a = Analysis(
    ["droidbridge/cli/main.py"],
    pathex=["."],
    binaries=_all_binaries,
    datas=pyqt6_datas,
    hiddenimports=[*pyqt6_hiddenimports, "PyQt6.sip"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

cli_pyz = PYZ(cli_a.pure, cli_a.zipped_data, cipher=block_cipher)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name="droidbridge",
    debug=False,
    strip=False,
    upx=True,
    console=True,
)

# ── Shared COLLECT (deduplicates Qt libraries between the two EXEs) ───────────

MERGE(
    (gui_a, "droidbridge-gui", "droidbridge-gui"),
    (cli_a, "droidbridge", "droidbridge"),
)

coll = COLLECT(
    gui_exe,
    gui_a.binaries,
    gui_a.zipfiles,
    gui_a.datas,
    cli_exe,
    cli_a.binaries,
    cli_a.zipfiles,
    cli_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=_dist_name,
)

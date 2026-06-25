# PyInstaller spec for DroidBridge — Linux x86_64 (primary build target)
#
# Produces two executables sharing one _MEIPASS directory:
#   dist/droidbridge-linux/droidbridge-gui   (GUI, no terminal window)
#   dist/droidbridge-linux/droidbridge        (CLI, terminal)
#
# Usage:
#   pyinstaller droidbridge-gui.spec
#
# Output:
#   dist/droidbridge-linux/
#
# The bundled adb binary at droidbridge/resources/platform-tools-linux/adb
# is picked up automatically by core.adb.find_adb_binary() because PyInstaller
# preserves the droidbridge/ package tree under _MEIPASS and __file__ in
# droidbridge/core/adb.py resolves to _MEIPASS/droidbridge/core/adb.py.

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Pull in all PyQt6 data/binaries/hiddenimports in one call.
# This ensures Qt platform plugins (xcb, wayland, egl) and image format
# plugins (jpeg, png, svg) are all included.
pyqt6_datas, pyqt6_binaries, pyqt6_hiddenimports = collect_all("PyQt6")

# ── GUI Analysis ──────────────────────────────────────────────────────────────

gui_a = Analysis(
    ["droidbridge/gui/app.py"],
    pathex=["."],
    binaries=[
        # Official Google ADB binary (v37+); path inside bundle mirrors source tree.
        (
            "droidbridge/resources/platform-tools-linux/adb",
            "droidbridge/resources/platform-tools-linux",
        ),
        *pyqt6_binaries,
    ],
    datas=[
        *pyqt6_datas,
    ],
    hiddenimports=[
        *pyqt6_hiddenimports,
        "PyQt6.sip",
    ],
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
    console=False,
)

# ── CLI Analysis ──────────────────────────────────────────────────────────────

cli_a = Analysis(
    ["droidbridge/cli/main.py"],
    pathex=["."],
    binaries=[
        (
            "droidbridge/resources/platform-tools-linux/adb",
            "droidbridge/resources/platform-tools-linux",
        ),
        *pyqt6_binaries,
    ],
    datas=[
        *pyqt6_datas,
    ],
    hiddenimports=[
        *pyqt6_hiddenimports,
        "PyQt6.sip",
    ],
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

# ── Shared collect (deduplicates Qt libraries between the two EXEs) ───────────

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
    name="droidbridge-linux",
)

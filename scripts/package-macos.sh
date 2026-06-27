#!/usr/bin/env bash
# Build DroidBridge macOS distribution: directory bundle + .zip
# Run from the project root on a macOS machine.
#
# Prerequisites:
#   pip install pyinstaller PyQt6
#   (Python 3.10+ from python.org or Homebrew)
#
# Output:
#   dist/droidbridge-macos/
#   releases/droidbridge-macos-universal.zip

set -euo pipefail

VERSION="${VERSION:-1.0.0}"
DIST_DIR="dist/droidbridge-macos"
RELEASE_DIR="releases"
ZIPNAME="droidbridge-macos-universal.zip"

echo "=== DroidBridge macOS Packaging (v${VERSION}) ==="

echo "[1/2] Building with PyInstaller..."
pyinstaller droidbridge-gui.spec \
    --distpath dist \
    --workpath build/pyinstaller \
    --noconfirm
echo "      Bundle: ${DIST_DIR}/ ($(du -sh "${DIST_DIR}" | cut -f1))"

echo "[2/2] Creating zip archive..."
mkdir -p "${RELEASE_DIR}"
cd dist && zip -r -q "../${RELEASE_DIR}/${ZIPNAME}" droidbridge-macos && cd ..
echo "      → ${RELEASE_DIR}/${ZIPNAME} ($(du -sh "${RELEASE_DIR}/${ZIPNAME}" | cut -f1))"

echo ""
echo "=== Done ==="
echo "  Archive: ${RELEASE_DIR}/${ZIPNAME}"
echo ""
echo "To install:"
echo "  1. Unzip ${ZIPNAME} to /Applications/DroidBridge/ (or anywhere)"
echo "  2. Run ./droidbridge-gui for the GUI"
echo "  3. Optionally: sudo ln -s /Applications/DroidBridge/droidbridge /usr/local/bin/droidbridge"
echo ""
echo "First-run Gatekeeper note:"
echo "  macOS may block the binary because it is not notarized."
echo "  To allow: System Settings → Privacy & Security → Open Anyway"
echo "  Or from Terminal: xattr -dr com.apple.quarantine /Applications/DroidBridge/"

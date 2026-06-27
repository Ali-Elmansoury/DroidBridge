#!/usr/bin/env bash
# Build DroidBridge Linux distribution: .tar.gz + .deb
# Run from the project root: bash scripts/package-linux.sh
#
# Prerequisites:
#   pip install pyinstaller
#   sudo apt install dpkg-dev fakeroot   (already present on Ubuntu)
#
# Outputs (in releases/):
#   releases/droidbridge-linux-x86_64.tar.gz
#   releases/droidbridge_1.0.0_amd64.deb

set -euo pipefail

VERSION="${VERSION:-1.0.0}"
ARCH="x86_64"
DIST_DIR="dist/droidbridge-linux"
RELEASE_DIR="releases"
TARBALL="droidbridge-linux-${ARCH}.tar.gz"
DEB_NAME="droidbridge_${VERSION}_amd64"

echo "=== DroidBridge Linux Packaging (v${VERSION}) ==="

# ── Step 1: PyInstaller build ─────────────────────────────────────────────────
echo "[1/4] Building with PyInstaller..."
pyinstaller droidbridge-gui.spec \
    --distpath dist \
    --workpath build/pyinstaller \
    --noconfirm
echo "      Bundle: ${DIST_DIR}/ ($(du -sh "${DIST_DIR}" | cut -f1))"

# ── Step 2: tar.gz ────────────────────────────────────────────────────────────
echo "[2/4] Creating tarball..."
mkdir -p "${RELEASE_DIR}"
tar -czf "${RELEASE_DIR}/${TARBALL}" -C dist droidbridge-linux
echo "      → ${RELEASE_DIR}/${TARBALL} ($(du -sh "${RELEASE_DIR}/${TARBALL}" | cut -f1))"

# ── Step 3: .deb package ─────────────────────────────────────────────────────
echo "[3/4] Building .deb package..."

DEB_ROOT="${RELEASE_DIR}/${DEB_NAME}"
rm -rf "${DEB_ROOT}"

# Debian control structure
mkdir -p "${DEB_ROOT}/DEBIAN"
mkdir -p "${DEB_ROOT}/opt/droidbridge"
mkdir -p "${DEB_ROOT}/usr/bin"
mkdir -p "${DEB_ROOT}/usr/share/applications"

# Copy bundle contents
cp -r "${DIST_DIR}/." "${DEB_ROOT}/opt/droidbridge/"

# Launcher wrappers in /usr/bin so they're on PATH
cat > "${DEB_ROOT}/usr/bin/droidbridge" <<'LAUNCHER'
#!/bin/bash
exec /opt/droidbridge/droidbridge "$@"
LAUNCHER
chmod 755 "${DEB_ROOT}/usr/bin/droidbridge"

cat > "${DEB_ROOT}/usr/bin/droidbridge-gui" <<'LAUNCHER'
#!/bin/bash
exec /opt/droidbridge/droidbridge-gui "$@"
LAUNCHER
chmod 755 "${DEB_ROOT}/usr/bin/droidbridge-gui"

# .desktop entry for application launcher
cat > "${DEB_ROOT}/usr/share/applications/droidbridge.desktop" <<DESKTOP
[Desktop Entry]
Name=DroidBridge
Comment=ADB-powered Android device management
Exec=/opt/droidbridge/droidbridge-gui
Terminal=false
Type=Application
Categories=Utility;System;
DESKTOP

# DEBIAN/control
INSTALLED_SIZE=$(du -sk "${DEB_ROOT}/opt/droidbridge" | cut -f1)
cat > "${DEB_ROOT}/DEBIAN/control" <<CONTROL
Package: droidbridge
Version: ${VERSION}
Architecture: amd64
Maintainer: DroidBridge Project
Installed-Size: ${INSTALLED_SIZE}
Description: ADB-powered Android device management tool
 DroidBridge is a cross-platform desktop app and CLI for managing Android
 devices via ADB. Includes WhatsApp toolkit, file manager, storage analyzer,
 backup manager, app manager, and reports — no Android SDK required.
CONTROL

# DEBIAN/postinst: fix permissions on bundled adb
cat > "${DEB_ROOT}/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
chmod +x /opt/droidbridge/_internal/droidbridge/resources/platform-tools-linux/adb 2>/dev/null || true
exit 0
POSTINST
chmod 755 "${DEB_ROOT}/DEBIAN/postinst"

fakeroot dpkg-deb --build "${DEB_ROOT}" "${RELEASE_DIR}/${DEB_NAME}.deb"
echo "      → ${RELEASE_DIR}/${DEB_NAME}.deb ($(du -sh "${RELEASE_DIR}/${DEB_NAME}.deb" | cut -f1))"

# ── Step 4: Cleanup staging dir ──────────────────────────────────────────────
echo "[4/4] Cleaning up staging directory..."
rm -rf "${DEB_ROOT}"

echo ""
echo "=== Done ==="
echo "  Tarball : ${RELEASE_DIR}/${TARBALL}"
echo "  Deb     : ${RELEASE_DIR}/${DEB_NAME}.deb"
echo ""
echo "Install .deb:  sudo dpkg -i ${RELEASE_DIR}/${DEB_NAME}.deb"
echo "Run GUI:       droidbridge-gui"
echo "Run CLI:       droidbridge --help"

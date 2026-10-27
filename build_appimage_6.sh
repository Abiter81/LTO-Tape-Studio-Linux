#!/usr/bin/env bash
# Build a portable AppImage for LTO Tape Studio.
# Usage: ./build_appimage_6.sh
#
# Programmer / Author: Jörg Althaus
set -euo pipefail

APP_NAME="LTO_Tape_Studio"
APP_ID="lto_tape_studio"
VERSION="${VERSION:-1.0.0}"
AUTHOR="Jörg Althaus"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${ROOT_DIR}/build_appimage"
APPDIR="${BUILD_DIR}/AppDir"
DIST_DIR="${ROOT_DIR}/dist"

echo "==> LTO Tape Studio ${VERSION} - programmed by ${AUTHOR}"

echo "==> Cleaning previous builds"
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}"

echo "==> Creating virtual environment"
python3 -m venv "${BUILD_DIR}/venv" --system-site-packages || python3 -m venv "${BUILD_DIR}/venv"
# shellcheck disable=SC1091
source "${BUILD_DIR}/venv/bin/activate"

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r "${ROOT_DIR}/requirements.txt"
pip install pyinstaller

echo "==> Building with PyInstaller"
cd "${ROOT_DIR}"
pyinstaller --noconfirm --clean --name "${APP_ID}" \
  --windowed \
  --add-data "resources:resources" \
  --hidden-import "PySide6" \
  --hidden-import "PySide6.QtCore" \
  --hidden-import "PySide6.QtGui" \
  --hidden-import "PySide6.QtWidgets" \
  --hidden-import "pyudev" \
  --hidden-import "psutil" \
  --hidden-import "zstandard" \
  --hidden-import "pyzstd" \
  --hidden-import "cryptography" \
  --hidden-import "cryptography.fernet" \
  main.py

echo "==> Assembling AppDir"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/lib" "${APPDIR}/usr/share/applications" \
  "${APPDIR}/usr/share/icons/hicolor/256x256/apps" "${APPDIR}/usr/share/metainfo"
cp -r "${DIST_DIR}/${APP_ID}/." "${APPDIR}/usr/bin/"
cp "${ROOT_DIR}/resources/lto_tape_studio.desktop" "${APPDIR}/usr/share/applications/${APP_ID}.desktop"
cp "${ROOT_DIR}/resources/lto_tape_studio.desktop" "${APPDIR}/${APP_ID}.desktop"
if [ -f "${ROOT_DIR}/resources/icon.png" ]; then
  cp "${ROOT_DIR}/resources/icon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png"
  cp "${ROOT_DIR}/resources/icon.png" "${APPDIR}/${APP_ID}.png"
fi

# --------------------------------------------------------------------------- #
# Bundle external system binaries (mt, sg3-utils) for a self-contained AppImage
# --------------------------------------------------------------------------- #
echo "==> Bundling external binaries"
EXTERNAL_BINS="mt sg_inq sg_logs sg_modes"
for bin in ${EXTERNAL_BINS}; do
  src="$(command -v ${bin} 2>/dev/null || true)"
  if [ -z "${src}" ]; then
    echo "WARNING: ${bin} not found on host; skipping"
    continue
  fi
  # Resolve symlink (mt -> mt-st)
  real="$(readlink -f "${src}")"
  cp "${real}" "${APPDIR}/usr/bin/$(basename ${bin})"
  chmod +x "${APPDIR}/usr/bin/$(basename ${bin})"
  echo "   bundled ${bin} -> ${APPDIR}/usr/bin/$(basename ${bin})"
  # Copy shared libraries reported by ldd
  if command -v ldd >/dev/null 2>&1; then
    ldd "${real}" 2>/dev/null | grep -oE '/[^ ]+' | while read -r lib; do
      if [ -f "${lib}" ]; then
        cp -n "${lib}" "${APPDIR}/usr/lib/" 2>/dev/null || true
      fi
    done
  fi
done
# Also bundle mt-st itself (target of mt symlink) if present
if [ -f /usr/bin/mt-st ]; then
  cp /usr/bin/mt-st "${APPDIR}/usr/bin/mt-st"
  chmod +x "${APPDIR}/usr/bin/mt-st"
fi

# Embed author credit into AppImage metadata (skipped to avoid appstreamcli validation issues)
# Author credit is preserved in main.py (__author__) and the .desktop file (X-Developer).
rm -rf "${APPDIR}/usr/share/metainfo"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
# Self-contained: prefer bundled binaries and libraries
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
# Ensure mt finds mt-st
if [ -x "${HERE}/usr/bin/mt-st" ] && [ ! -x "${HERE}/usr/bin/mt" ]; then
  ln -sf mt-st "${HERE}/usr/bin/mt" 2>/dev/null || true
fi
exec "${HERE}/usr/bin/lto_tape_studio" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

echo "==> Obtaining appimagetool"
TOOL="${BUILD_DIR}/appimagetool"
if ! command -v appimagetool >/dev/null 2>&1; then
  if [ ! -f "${TOOL}" ]; then
    ARCH="$(uname -m)"
    URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    echo "Downloading ${URL}"
    if command -v wget >/dev/null 2>&1; then
      wget -O "${TOOL}" "${URL}"
    elif command -v curl >/dev/null 2>&1; then
      curl -L -o "${TOOL}" "${URL}"
    else
      echo "Neither wget nor curl available" >&2
      exit 1
    fi
    chmod +x "${TOOL}"
  fi
else
  TOOL="$(command -v appimagetool)"
fi

echo "==> Producing AppImage"
OUTPUT="${ROOT_DIR}/${APP_NAME}-${VERSION}-x86_64.AppImage"
ARCH=x86_64 "${TOOL}" "${APPDIR}" "${OUTPUT}"
chmod +x "${OUTPUT}"

echo "==> Done: ${OUTPUT}"
echo "==> Programmed by ${AUTHOR}"
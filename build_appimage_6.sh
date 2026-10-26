#!/usr/bin/env bash
# Build a portable AppImage for LTO Tape Studio.
# Usage: ./build_appimage_6.sh
set -euo pipefail

APP_NAME="LTO_Tape_Studio"
APP_ID="lto_tape_studio"
VERSION="${VERSION:-1.0.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${ROOT_DIR}/build_appimage"
APPDIR="${BUILD_DIR}/AppDir"
DIST_DIR="${ROOT_DIR}/dist"

echo "==> Cleaning previous builds"
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}"

echo "==> Creating virtual environment"
python3 -m venv "${BUILD_DIR}/venv" --system-site-packages || python3 -m venv "${BUILD_DIR}/venv"
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
  --hidden-import "pyudev" \
  --hidden-import "psutil" \
  --hidden-import "zstandard" \
  main.py

echo "==> Assembling AppDir"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
cp -r "${DIST_DIR}/${APP_ID}/." "${APPDIR}/usr/bin/"
cp "${ROOT_DIR}/resources/lto_tape_studio.desktop" "${APPDIR}/usr/share/applications/${APP_ID}.desktop"
cp "${ROOT_DIR}/resources/lto_tape_studio.desktop" "${APPDIR}/${APP_ID}.desktop"
cp "${ROOT_DIR}/resources/icon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png"
cp "${ROOT_DIR}/resources/icon.png" "${APPDIR}/${APP_ID}.png"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/lto_tape_studio" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

echo "==> Obtaining appimagetool"
TOOL="${BUILD_DIR}/appimagetool"
if ! command -v appimagetool >/dev/null 2>&1; then
  if [ ! -f "${TOOL}" ]; then
    ARCH="$(uname -m)"
    wget -O "${TOOL}" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
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
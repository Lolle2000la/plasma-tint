#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Build a self-contained plasma-tint AppImage.
#
#   packaging/build-appimage.sh
#
# Environment:
#   VERSION   Version embedded in the output filename (default: pyproject.toml)
#   ARCH      AppImage architecture (default: uname -m)
#   PYTHON    Interpreter used to create the build venv (default: python3)
#   OUTDIR    Directory for the finished .AppImage (default: <repo>/dist)
#
# The bundle contains Python, PySide6/Qt and plasma-tint. It still uses the
# system libraries a KDE Plasma desktop always has (glibc, libGL, fontconfig,
# xcb/Wayland client libraries) plus the external `kscreen-doctor` tool.

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

VERSION=${VERSION:-$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n 1)}
ARCH=${ARCH:-$(uname -m)}
PYTHON=${PYTHON:-python3}
OUTDIR=${OUTDIR:-$ROOT/dist}

BUILD_DIR=$ROOT/build/appimage
VENV=$BUILD_DIR/venv
PYINSTALLER_DIST=$BUILD_DIR/pyinstaller
APPDIR=$BUILD_DIR/AppDir
TOOLS_DIR=$ROOT/build/tools
APPIMAGETOOL=$TOOLS_DIR/appimagetool-$ARCH.AppImage
OUTPUT=$OUTDIR/plasma-tint-$VERSION-$ARCH.AppImage

case "$ARCH" in
    x86_64 | aarch64) ;;
    *)
        echo "error: unsupported architecture '$ARCH' (expected x86_64 or aarch64)" >&2
        exit 1
        ;;
esac

if [ -z "$VERSION" ]; then
    echo "error: could not determine the version; set VERSION=..." >&2
    exit 1
fi

pip_install() {
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$VENV/bin/python" "$@"
    else
        "$VENV/bin/python" -m pip install "$@"
    fi
}

echo "==> Building plasma-tint $VERSION ($ARCH)"

rm -rf "$APPDIR" "$PYINSTALLER_DIST"
install -d "$BUILD_DIR" "$OUTDIR"

# A disposable venv keeps host site-packages (and any system PySide6) out of
# the bundle. When PYTHON points at a relocatable/standalone interpreter (what
# CI uses) PyInstaller bundles that interpreter's libpython as well.
if [ ! -x "$VENV/bin/python" ]; then
    echo "==> Creating build venv with $PYTHON"
    "$PYTHON" -m venv "$VENV"
fi

echo "==> Installing build dependencies"
pip_install --upgrade pip >/dev/null 2>&1 || true
# PySide6-Essentials is enough for QtCore/QtGui/QtWidgets and avoids pulling
# QtWebEngine, QtQuick, Qt3D and the rest of PySide6-Addons into the bundle.
pip_install "pyinstaller>=6.10" "PySide6-Essentials>=6.6"
# --no-deps: the project's dependency is satisfied by PySide6-Essentials above.
pip_install --no-deps --reinstall "$ROOT"

echo "==> Running PyInstaller"
"$VENV/bin/python" -m PyInstaller \
    --noconfirm \
    --clean \
    --log-level WARN \
    --distpath "$PYINSTALLER_DIST" \
    --workpath "$BUILD_DIR/work" \
    "$ROOT/packaging/plasma-tint.spec"

echo "==> Assembling AppDir"
install -d \
    "$APPDIR/usr/bin" \
    "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp -a "$PYINSTALLER_DIST/plasma-tint/." "$APPDIR/usr/bin/"
install -m 0755 "$ROOT/packaging/AppRun" "$APPDIR/AppRun"
install -m 0644 "$ROOT/packaging/plasma-tint.desktop" "$APPDIR/plasma-tint.desktop"
install -m 0644 "$ROOT/packaging/plasma-tint.desktop" \
    "$APPDIR/usr/share/applications/plasma-tint.desktop"
install -m 0644 "$ROOT/packaging/plasma-tint.svg" "$APPDIR/plasma-tint.svg"
install -m 0644 "$ROOT/packaging/plasma-tint.svg" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps/plasma-tint.svg"
ln -sfn plasma-tint.svg "$APPDIR/.DirIcon"

echo "==> Fetching appimagetool"
if [ ! -x "$APPIMAGETOOL" ]; then
    install -d "$TOOLS_DIR"
    url="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    curl -fsSL --retry 3 -o "$APPIMAGETOOL.part" "$url"
    chmod +x "$APPIMAGETOOL.part"
    mv "$APPIMAGETOOL.part" "$APPIMAGETOOL"
fi

echo "==> Packaging AppImage"
# --appimage-extract-and-run avoids depending on FUSE being available
# (containers and CI runners usually do not have it).
ARCH="$ARCH" VERSION="$VERSION" "$APPIMAGETOOL" \
    --appimage-extract-and-run \
    --no-appstream \
    "$APPDIR" "$OUTPUT"

echo "==> Built $OUTPUT ($(du -h "$OUTPUT" | cut -f 1))"

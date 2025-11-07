#!/bin/bash
set -e

# Usage: ./build-deb.sh <version>
if [ -z "$1" ]; then
  echo "ERROR: Version argument missing!"
  echo "Usage: ./build-deb.sh <version>"
  exit 1
fi

VERSION="$1"
PACKAGE_NAME="fim-daemon"
ARCHITECTURE="amd64"

echo "Building $PACKAGE_NAME v$VERSION ($ARCHITECTURE)..."

# Create build directory
BUILD_DIR="build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Create package directory structure
PKG_DIR="$BUILD_DIR/${PACKAGE_NAME}-v${VERSION}_${ARCHITECTURE}"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/local/bin"
mkdir -p "$PKG_DIR/etc/systemd/system"
mkdir -p "$PKG_DIR/var/lib/fim-daemon"
mkdir -p "$PKG_DIR/var/log/fim-daemon"

# Debug info
echo "Current directory: $(pwd)"
echo "Files in current directory:"
ls -la

# Copy main script
if [ -f "fim_daemon_linux.py" ]; then
    cp "fim_daemon_linux.py" "$PKG_DIR/usr/local/bin/fim-daemon"
    chmod +x "$PKG_DIR/usr/local/bin/fim-daemon"
    echo "Main script copied"
else
    echo "ERROR: fim_daemon_linux.py not found!"
    exit 1
fi

# Copy core modules
if [ -d "../core" ]; then
    mkdir -p "$PKG_DIR/usr/local/bin/core"
    cp ../core/*.py "$PKG_DIR/usr/local/bin/core/"
    echo "Core modules copied"
else
    echo "ERROR: ../core directory not found!"
    exit 1
fi

# Copy control and service files
echo "Copying packaging files..."
cp packaging/DEBIAN/* "$PKG_DIR/DEBIAN/"
cp packaging/etc/systemd/system/fim-daemon.service "$PKG_DIR/etc/systemd/system/_

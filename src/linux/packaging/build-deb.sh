#!/bin/bash
set -e

echo "Building FIM Daemon DEB package..."

# Configuration
PACKAGE_NAME="fim-daemon"
VERSION="1.0.0"
ARCHITECTURE="amd64"

# Create build directory
BUILD_DIR="../build"
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR

# Create package directory structure
PKG_DIR="$BUILD_DIR/${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}"
mkdir -p $PKG_DIR/DEBIAN
mkdir -p $PKG_DIR/usr/local/bin
mkdir -p $PKG_DIR/etc/systemd/system
mkdir -p $PKG_DIR/var/lib/fim-daemon
mkdir -p $PKG_DIR/var/log/fim-daemon

# Copy files
echo "Copying application files..."
cp ../fim_daemon_linux.py $PKG_DIR/usr/local/bin/fim-daemon
cp ../../core/*.py $PKG_DIR/usr/local/bin/
chmod +x $PKG_DIR/usr/local/bin/fim-daemon

# Copy packaging files
echo "Copying packaging files..."
cp DEBIAN/* $PKG_DIR/DEBIAN/
cp etc/systemd/system/fim-daemon.service $PKG_DIR/etc/systemd/system/

# Build the package
echo "Building DEB package..."
dpkg-deb --build $PKG_DIR

echo "Package built: $PKG_DIR.deb"
ls -la $BUILD_DIR/*.deb
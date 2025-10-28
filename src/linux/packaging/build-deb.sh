#!/bin/bash
set -e

echo "Building FIM Daemon DEB package..."

# Configuration
PACKAGE_NAME="fim-daemon"
VERSION="1.0.0"
ARCHITECTURE="amd64"

# Create build directory
BUILD_DIR="build"
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR

# Create package directory structure
PKG_DIR="$BUILD_DIR/${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}"
mkdir -p $PKG_DIR/DEBIAN
mkdir -p $PKG_DIR/usr/local/bin
mkdir -p $PKG_DIR/etc/systemd/system
mkdir -p $PKG_DIR/var/lib/fim-daemon
mkdir -p $PKG_DIR/var/log/fim-daemon

# Debug: Show current directory and files
echo "Current directory: $(pwd)"
echo "Files in current directory:"
ls -la

# Copy the main script
echo "Copying main script..."
if [ -f "fim_daemon_linux.py" ]; then
    cp "fim_daemon_linux.py" "$PKG_DIR/usr/local/bin/fim-daemon"
    chmod +x "$PKG_DIR/usr/local/bin/fim-daemon"
    echo "Main script copied successfully"
else
    echo "ERROR: fim_daemon_linux.py not found in current directory!"
    exit 1
fi

# Copy core modules
echo "Copying core modules..."
if [ -d "../core" ]; then
    mkdir -p "$PKG_DIR/usr/local/bin/core"
    cp "../core/"*.py "$PKG_DIR/usr/local/bin/core/"
    echo "✅ Core modules copied successfully"
else
    echo "❌ ERROR: ../core directory not found!"
    exit 1
fi

# Copy packaging files
echo "Copying packaging files..."
cp "packaging/DEBIAN/"* "$PKG_DIR/DEBIAN/"
cp "packaging/etc/systemd/system/fim-daemon.service" "$PKG_DIR/etc/systemd/system/"

# Set permissions
chmod 755 "$PKG_DIR/DEBIAN/postinst"
chmod 755 "$PKG_DIR/DEBIAN/prerm"
chmod 644 "$PKG_DIR/etc/systemd/system/fim-daemon.service"

# Build the package
echo "Building DEB package..."
dpkg-deb --build $PKG_DIR

echo "Package built: $PKG_DIR.deb"
ls -la $BUILD_DIR/*.deb
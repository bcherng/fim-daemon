#!/bin/bash
set -e

echo "🔧 Building FIM Daemon DEB package..."

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

# Copy the main script and make it executable
cp ../fim_daemon_linux.py $PKG_DIR/usr/local/bin/fim-daemon
chmod +x $PKG_DIR/usr/local/bin/fim-daemon

# Copy core modules
mkdir -p $PKG_DIR/usr/local/bin/core
cp ../../core/*.py $PKG_DIR/usr/local/bin/core/

# Create control file
cat > $PKG_DIR/DEBIAN/control << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCHITECTURE
Depends: python3, python3-pip
Maintainer: FIM Team <fim@example.com>
Description: File Integrity Monitor Daemon
 Real-time file integrity monitoring using Merkle trees
 and cryptographic verification.
EOF

# Create postinst script
cat > $PKG_DIR/DEBIAN/postinst << 'EOF'
#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip3 install watchdog python-daemon

echo "Creating directories and service user..."
mkdir -p /var/lib/fim-daemon/watch-folder
chmod 755 /var/lib/fim-daemon /var/lib/fim-daemon/watch-folder

# Create service user if needed
if ! id "fim-daemon" &>/dev/null; then
    useradd -r -s /bin/false -d /var/lib/fim-daemon fim-daemon
fi

chown -R fim-daemon:fim-daemon /var/lib/fim-daemon /var/log/fim-daemon

echo "Setting up systemd service..."
systemctl daemon-reload
systemctl enable fim-daemon

echo "FIM Daemon installed successfully!"
echo "Start with: systemctl start fim-daemon"
exit 0
EOF

# Create prerm script
cat > $PKG_DIR/DEBIAN/prerm << 'EOF'
#!/bin/bash
set -e

echo "Stopping FIM Daemon service..."
systemctl stop fim-daemon || true
systemctl disable fim-daemon || true
exit 0
EOF

# Create systemd service file
cat > $PKG_DIR/etc/systemd/system/fim-daemon.service << EOF
[Unit]
Description=File Integrity Monitor Daemon
After=network.target

[Service]
Type=simple
User=fim-daemon
Group=fim-daemon
ExecStart=/usr/bin/python3 /usr/local/bin/fim-daemon
WorkingDirectory=/var/lib/fim-daemon
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
chmod 755 $PKG_DIR/DEBIAN/postinst
chmod 755 $PKG_DIR/DEBIAN/prerm
chmod 644 $PKG_DIR/etc/systemd/system/fim-daemon.service

# Build the package
echo "Building DEB package..."
dpkg-deb --build $PKG_DIR

echo "Package built: $PKG_DIR.deb"
ls -la $BUILD_DIR/*.deb
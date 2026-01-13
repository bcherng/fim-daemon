#!/bin/bash
# build/build_local.sh - Local Linux build script

set -e

echo "==================================="
echo "FIM Client - Linux Build Script"
echo "==================================="

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $PYTHON_VERSION"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt
pip3 install pyinstaller

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf dist/ build/linux/fim-client_* build/linux/output/

# Build with PyInstaller
echo ""
echo "Building executable with PyInstaller..."
cd build/linux
pyinstaller --clean --noconfirm fim_client.spec
cd ../..

# Get version
if [ -f "../../VERSION" ]; then
    VERSION=$(cat ../../VERSION)
elif [ -n "$1" ]; then
    VERSION="$1"
else
    VERSION="dev-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
fi

echo ""
echo "Building version: $VERSION"

# Create Debian package structure
PKG_DIR="build/linux/fim-client_${VERSION}"

echo ""
echo "Creating Debian package structure..."
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/opt/fim-client"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/etc/systemd/system"

# Copy files
echo "Copying files..."
cp -r build/linux/dist/fim_client/* "${PKG_DIR}/opt/fim-client/"
cp build/linux/fim-client.desktop "${PKG_DIR}/usr/share/applications/"

# Copy icon if exists
if [ -f "assets/icon.png" ]; then
    cp assets/icon.png "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps/fim-client.png"
else
    echo "Warning: Icon not found at assets/icon.png"
    # Create a placeholder icon
    touch "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps/fim-client.png"
fi

# Create symlink script
cat > "${PKG_DIR}/usr/bin/fim-client" << 'EOF'
#!/bin/bash
cd /opt/fim-client && ./fim_client "$@"
EOF
chmod +x "${PKG_DIR}/usr/bin/fim-client"

# Copy systemd service
cp build/linux/fim-client.service "${PKG_DIR}/etc/systemd/system/"

# Create control file
cat > "${PKG_DIR}/DEBIAN/control" << EOF
Package: fim-client
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: bcherng <bcherng@github.com>
Description: Cross-platform File Integrity Monitoring (FIM) Client
 FIM Client monitors file changes and reports them to a central server.
 It provides real-time monitoring with cryptographic verification.
Depends: python3, python3-tk
EOF

# Create postinst script
cat > "${PKG_DIR}/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

# Reload systemd daemon
systemctl daemon-reload || true

# Update desktop database
update-desktop-database || true

# Update icon cache
gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true

echo ""
echo "======================================"
echo "FIM Client installed successfully!"
echo "======================================"
echo ""
echo "Run 'fim-client' to start the application."
echo ""

exit 0
EOF
chmod +x "${PKG_DIR}/DEBIAN/postinst"

# Create prerm script
cat > "${PKG_DIR}/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e

# Stop service if running
systemctl stop fim-client.service 2>/dev/null || true
systemctl disable fim-client.service 2>/dev/null || true

exit 0
EOF
chmod +x "${PKG_DIR}/DEBIAN/prerm"

# Build package
echo ""
echo "Building Debian package..."
dpkg-deb --build "${PKG_DIR}"

# Move to output
mkdir -p build/linux/output
mv "build/linux/fim-client_${VERSION}.deb" "build/linux/output/"

echo ""
echo "======================================"
echo "Build completed successfully!"
echo "======================================"
echo ""
echo "Package: build/linux/output/fim-client_${VERSION}.deb"
echo ""
echo "To install:"
echo "  sudo dpkg -i build/linux/output/fim-client_${VERSION}.deb"
echo "  sudo apt-get install -f"
echo ""

#!/bin/bash
set -e

echo "Installing File Integrity Monitor (Linux)..."

TARGET_DIR="/opt/fim-daemon"

# Ensure root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./install.sh)"
  exit 1
fi

# Install Python + pip if missing
if ! command -v python3 &> /dev/null; then
  echo "Installing Python..."
  apt-get update -y && apt-get install -y python3 python3-pip
fi

# Create daemon directory
mkdir -p "$TARGET_DIR"

# Copy files
cp fim_daemon_linux.py "$TARGET_DIR/"
cp requirements.txt "$TARGET_DIR/"
cp fim-daemon.service /etc/systemd/system/fim-daemon.service

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r "$TARGET_DIR/requirements.txt"

# Enable + start daemon
echo "Enabling systemd service..."
systemctl daemon-reload
systemctl enable fim-daemon
systemctl restart fim-daemon

echo "Installation complete."
systemctl status fim-daemon --no-pager

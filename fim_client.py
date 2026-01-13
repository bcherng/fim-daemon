#!/usr/bin/env python3
"""
FIM Client - Main entry point
"""
import os
import sys
from pathlib import Path


__version__ = "0.2.22"

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from core.state import FIMState
from core.connection import ConnectionManager
from core.admin import AdminVerifier
from gui.client_gui import FIMClientGUI


def get_state_directory():
    """Get platform-specific state directory"""
    if sys.platform == 'win32':
        return os.path.expandvars(r'%APPDATA%\FIMClient')
    else:
        return os.path.expanduser("~/.fim-client")


def get_config():
    """Get platform-specific configuration"""
    if sys.platform == 'win32':
        from platform_specific.windows_config import WindowsFIMConfig
        return WindowsFIMConfig()
    else:
        from platform_specific.linux_config import LinuxFIMConfig
        return LinuxFIMConfig()


def main():
    """Main entry point"""
    # Initialize configuration
    config = get_config()
    
    # Initialize state
    state_dir = get_state_directory()
    state_file = os.path.join(state_dir, "state.json")
    state = FIMState(state_file)
    
    # Initialize connection manager
    conn_mgr = ConnectionManager(config, state)
    
    # Initialize admin verifier
    admin_verifier = AdminVerifier(config, state)
    
    # Create and run GUI
    gui = FIMClientGUI(config, state, conn_mgr, admin_verifier)
    gui.run()


if __name__ == '__main__':
    main()
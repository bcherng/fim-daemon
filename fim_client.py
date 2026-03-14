#!/usr/bin/env python3
"""
FIM Client - Main entry point
"""
import os
import sys
from pathlib import Path


__version__ = "1.1.0"

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.state import FIMState
from core.registration_client import RegistrationClient
from core.token_client import TokenClient
from gui.client_gui import FIMClientGUI
import daemon.background # Force PyInstaller to include this module


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


def try_acquire_client_lock():
    """Attempt to acquire a single-instance OS lock"""
    if sys.platform == 'win32':
        import ctypes
        mutex_name = "Global\\FIM_Client_Singleton_Mutex"
        # 0x001F0001 is MUTEX_ALL_ACCESS, but we just need to try creating it
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
            return False, mutex
        return True, mutex
    else:
        import fcntl
        lock_file_path = os.path.join(get_state_directory(), "client.lock")
        os.makedirs(os.path.dirname(lock_file_path), exist_ok=True)
        try:
            lock_file = open(lock_file_path, 'w')
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True, lock_file
        except (IOError, OSError):
            return False, None

def main():
    """Main entry point"""
    # Enforce exactly-one client process
    acquired, lock_obj = try_acquire_client_lock()
    if not acquired:
        print("FIM Client is already running. Exiting.")
        sys.exit(0)
        
    # Ensure admin daemon is running (relies on its own lock to avoid duplicates)
    import subprocess
    daemon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'daemon', 'admin_daemon.py')
    if sys.platform == 'win32':
        subprocess.Popen([sys.executable, daemon_path, "run"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([sys.executable, daemon_path, "run"])
        
        
    # Initialize configuration
    config = get_config()
    
    # Initialize state
    state_dir = get_state_directory()
    state_file = os.path.join(state_dir, "state.json")
    state = FIMState(state_file)
    
    # Initialize connection manager
    conn_mgr = RegistrationClient(config, state)
    
    # Initialize admin verifier
    admin_verifier = TokenClient(config, state)
    
    # Create and run GUI
    gui = FIMClientGUI(config, state, conn_mgr, admin_verifier)
    gui.run()


if __name__ == '__main__':
    main()
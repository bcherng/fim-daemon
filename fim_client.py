#!/usr/bin/env python3
"""
FIM Client - Main entry point (GUI only)
State management, monitoring, and server reporting are owned by the FIMAdmin service.
"""
import os
import sys
from pathlib import Path


__version__ = "1.2.0"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gui.client_gui import FIMClientGUI


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
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False, mutex
        return True, mutex
    else:
        import fcntl
        state_dir = os.path.expanduser("~/.fim-client")
        os.makedirs(state_dir, exist_ok=True)
        lock_file_path = os.path.join(state_dir, "client.lock")
        try:
            lock_file = open(lock_file_path, 'w')
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True, lock_file
        except (IOError, OSError):
            return False, None


def main():
    """Main entry point — GUI only; all monitoring runs in the FIMAdmin service."""
    acquired, lock_obj = try_acquire_client_lock()
    if not acquired:
        print("FIM Client is already running. Exiting.")
        sys.exit(0)

    # Ensure admin service is running (it owns monitoring + state)
    import subprocess
    daemon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'daemon', 'admin_daemon.py')

    _service_started = False
    if sys.platform == 'win32':
        try:
            import win32serviceutil
            import win32service
            status = win32serviceutil.QueryServiceStatus('FIMAdmin')
            if status[1] == win32service.SERVICE_RUNNING:
                _service_started = True
            else:
                try:
                    win32serviceutil.StartService('FIMAdmin')
                    # Give it a second to start
                    import time
                    time.sleep(1)
                    status = win32serviceutil.QueryServiceStatus('FIMAdmin')
                    if status[1] == win32service.SERVICE_RUNNING:
                        _service_started = True
                except:
                    _service_started = False
        except Exception:
            _service_started = False

    if not _service_started:
        print("Service 'FIMAdmin' not running or not found. Starting standalone Admin Daemon...")
        if sys.platform == 'win32':
            subprocess.Popen([sys.executable, daemon_path, "run"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([sys.executable, daemon_path, "run"])

    # Initialize configuration
    config = get_config()

    # Create and run GUI — pure log subscriber, no local monitoring thread
    gui = FIMClientGUI(config)
    gui.run()


if __name__ == '__main__':
    main()
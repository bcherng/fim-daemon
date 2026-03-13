#!/usr/bin/env python3
"""
Admin Daemon for FIM Client
Runs with elevated privileges to execute critical actions verified by short-lived server tokens.
"""
import os
import sys
import json
import socket
import logging
import threading
import requests
import time
from multiprocessing.connection import Listener

# Windows Service Imports
if sys.platform == 'win32':
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager
        import win32pipe
        import win32file
        import win32security
        import winreg
    except ImportError:
        pass

import subprocess

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

if sys.platform == 'win32':
    from platform_specific.windows_config import WindowsFIMConfig
else:
    from platform_specific.linux_config import LinuxFIMConfig

def get_config(skip_logging=True):
    """Get platform-specific configuration"""
    if sys.platform == 'win32':
        return WindowsFIMConfig(skip_logging=skip_logging)
    else:
        return LinuxFIMConfig()

def get_system_config_path():
    """Get the path to the system-wide configuration file"""
    if sys.platform == 'win32':
        base_dir = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
        config_dir = os.path.join(base_dir, 'FIMClient')
    else:
        config_dir = '/etc/fim-client'
    
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'system_config.json')

# Windows Pipe Listener helper
if sys.platform == 'win32':
    class WindowsPipeListener:
        def __init__(self, address):
            self.address = address
            self._lock = threading.Lock()
            self._next_pipe()
            
        def _next_pipe(self):
            
            sd = win32security.SECURITY_DESCRIPTOR()
            sd.Initialize()
            sd.SetSecurityDescriptorDacl(1, None, 0) # NULL DACL = Everyone
            
            sa = win32security.SECURITY_ATTRIBUTES()
            sa.SECURITY_DESCRIPTOR = sd
            sa.bInheritHandle = 1
            
            self._pipe_handle = win32pipe.CreateNamedPipe(
                self.address,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                65536, 65536,
                0,
                sa
            )

        def accept(self):
            
            # This blocks until a client connects
            win32pipe.ConnectNamedPipe(self._pipe_handle, None)
            
            with self._lock:
                # Detach the handle so it's not closed when we reassign self._pipe_handle
                # We return the raw handle (int) to avoid multiprocessing.Connection issues
                handle = self._pipe_handle.Detach()
                
                # Prepare for the next client connection
                self._next_pipe()
                
                return int(handle)

class FIMAdminDaemon:
    
    def __init__(self):
        self.config = get_config(skip_logging=True)
        self.setup_logging()
        self.sys_config_path = get_system_config_path()
        self.running = True

    def setup_logging(self):
        if sys.platform == 'win32':
            log_dir = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'FIMClient', 'logs')
        else:
            log_dir = '/var/log/fim-client'
            
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'admin_daemon.log')
            
            handlers = [logging.FileHandler(log_file)]
            if sys.stdout is not None:
                handlers.append(logging.StreamHandler(sys.stdout))
                
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - AdminDaemon - %(levelname)s - %(message)s',
                handlers=handlers,
                force=True
            )
            self.logger = logging.getLogger(__name__)
            self.logger.info("Admin logging initialized successfully")
        except Exception as e:
            print(f"CRITICAL: Failed to setup logging: {e}")
            self.logger = logging.getLogger(__name__)

    def verify_action_token(self, token, action):
        """Verify the short-lived action token with the FIM Server"""
        try:
            self.logger.info(f"Verifying token for action: {action}")
            response = requests.post(
                f"{self.config.server_url}/api/auth/verify-action-token",
                json={
                    "token": token,
                    "client_id": self.config.host_id,
                    "action": action
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return True, response.json()
            else:
                error = response.json().get('error', 'Token verification failed')
                self.logger.warning(f"Token verification rejected: {error}")
                return False, error
                
        except Exception as e:
            self.logger.error(f"Error communicating with server for token verification: {e}")
            return False, str(e)

    def handle_change_directory(self, payload):
        """Handle the change directory critical action"""
        new_path = payload.get('path')
        if not new_path:
            return {"success": False, "error": "No path provided"}
            
        sys_config = {}
        if os.path.exists(self.sys_config_path):
            try:
                with open(self.sys_config_path, 'r') as f:
                    sys_config = json.load(f)
            except Exception as e:
                self.logger.error(f"Error reading system config: {e}")
                
        sys_config['watch_directory'] = new_path
        
        try:
            with open(self.sys_config_path, 'w') as f:
                json.dump(sys_config, f, indent=2)
            self.logger.info(f"Successfully updated system watch directory to: {new_path}")
            return {"success": True, "message": f"Directory changed to {new_path}"}
        except Exception as e:
            self.logger.error(f"Failed to write system config: {e}")
            return {"success": False, "error": f"Failed to save configuration: {str(e)}"}

    def handle_uninstall(self, payload):
        """Handle self-uninstallation"""
        self.logger.warning("Uninstallation triggered via Admin Daemon")
        
        if sys.platform == 'win32':
            try:
                uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{FIM-CLIENT-99E7-4562-AB89-1234567890AB}_is1"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key) as key:
                    uninstall_string = winreg.QueryValueEx(key, "QuietUninstallString")[0]
                    if uninstall_string:
                        subprocess.Popen(uninstall_string, shell=True)
                        return {"success": True, "message": "Uninstallation started"}
            except Exception as e:
                self.logger.error(f"Failed to find or launch Windows uninstaller: {e}")
                return {"success": False, "error": f"Failed to find uninstaller: {str(e)}"}
        else:
            try:
                subprocess.Popen("apt-get remove -y fim-client || dpkg -r fim-client", shell=True)
                return {"success": True, "message": "Uninstallation started"}
            except Exception as e:
                self.logger.error(f"Failed to launch Linux uninstaller: {e}")
                return {"success": False, "error": f"Uninstallation failed: {str(e)}"}
                
        return {"success": False, "error": "Uninstallation not fully supported on this platform"}

    def handle_client(self, conn, addr=None):
        try:
            # On Windows, conn is a raw handle (int)
            if sys.platform == 'win32' and isinstance(conn, int):
                # Use raw byte read/write to avoid multiprocessing.connection socket errors
                self.logger.info("Handling Windows raw pipe client")
                # hr, data = win32file.ReadFile(conn, 65536)
                # ReadFile can be tricky with chunks, but for our JSON small payloads it's fine once
                # Alternatively we can use a loop or just trust the 64KB buffer
                _, data = win32file.ReadFile(conn, 65536)
                if not data:
                    return
                request = json.loads(data.decode('utf-8'))
            elif hasattr(conn, 'recv'):
                # multiprocessing.connection or raw socket (Linux)
                if type(conn).__name__ == 'Connection':
                    request = conn.recv()
                else:
                    data = conn.recv(8192)
                    if not data:
                        return
                    request = json.loads(data.decode('utf-8'))
                self.logger.info(f"Received IPC request from {addr if addr else 'client'}")
            else:
                self.logger.error(f"Unknown connection type: {type(conn)}")
                return
                
            action = request.get('action')
            token = request.get('token')
            payload = request.get('payload', {})
            
            if not action or not token:
                response = {"success": False, "error": "Missing action or token"}
            else:
                is_valid, validation_data = self.verify_action_token(token, action)
                if not is_valid:
                    response = {"success": False, "error": f"Token rejected: {validation_data}"}
                else:
                    if action == 'change_directory':
                        response = self.handle_change_directory(payload)
                    elif action == 'uninstall':
                        response = self.handle_uninstall(payload)
                    else:
                        response = {"success": False, "error": f"Unknown action: {action}"}
                        
            # Provide response back
            if sys.platform == 'win32' and isinstance(conn, int):
                win32file.WriteFile(conn, json.dumps(response).encode('utf-8'))
                win32pipe.DisconnectNamedPipe(conn)
                win32file.CloseHandle(conn)
            elif hasattr(conn, 'send'):
                if type(conn).__name__ == 'Connection':
                    conn.send(response)
                else:
                    conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                conn.close()
                
        except Exception as e:
            self.logger.error(f"Error handling IPC client: {e}")
            try:
                err_resp = {"success": False, "error": "Internal daemon error"}
                if sys.platform == 'win32' and isinstance(conn, int):
                    win32file.WriteFile(conn, json.dumps(err_resp).encode('utf-8'))
                    win32pipe.DisconnectNamedPipe(conn)
                    win32file.CloseHandle(conn)
                elif hasattr(conn, 'send'):
                    if type(conn).__name__ == 'Connection':
                        conn.send(err_resp)
                    else:
                        conn.sendall((json.dumps(err_resp) + '\n').encode('utf-8'))
                    conn.close()
            except:
                pass

    def stop(self):
        self.running = False

    def run(self):
        self.logger.info(f"Starting FIM Admin Daemon on {self.config.platform_type}")
        
        if sys.platform == 'win32':
            address = r'\\.\pipe\fim_admin_ipc'
            try:
                listener = WindowsPipeListener(address)
                self.logger.info(f"Listening on Named Pipe with permissive DACL: {address}")
                
                while self.running:
                    try:
                        conn = listener.accept()
                        client_thread = threading.Thread(target=self.handle_client, args=(conn,))
                        client_thread.daemon = True
                        client_thread.start()
                    except Exception as e:
                        if self.running:
                            self.logger.error(f"Listener error: {e}")
                            time.sleep(1)
            except Exception as e:
                self.logger.critical(f"Failed to start listener: {e}")
        else:
            # Unix socket
            address = '/var/run/fim_admin.sock'
            if os.path.exists(address):
                os.remove(address)
                
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(address)
            os.chmod(address, 0o666)  # Allow all local users to connect
            sock.listen(5)
            self.logger.info(f"Listening on Unix Socket: {address}")
            
            while self.running:
                try:
                    conn, addr = sock.accept()
                    client_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    client_thread.daemon = True
                    client_thread.start()
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Listener error: {e}")
                        time.sleep(1)

# Windows Service Class
if sys.platform == 'win32':
    class FIMAdminService(win32serviceutil.ServiceFramework):
        _svc_name_ = "FIMAdmin"
        _svc_display_name_ = "FIM Admin Service"
        _svc_description_ = "Elevated background worker for FIM Client critical actions"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.daemon = FIMAdminDaemon()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.daemon.stop()
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            self.daemon.run()

if __name__ == '__main__':
    if sys.platform == 'win32':
        if len(sys.argv) > 1 and sys.argv[1] in ['install', 'update', 'remove', 'start', 'stop', 'restart', 'status']:
            win32serviceutil.HandleCommandLine(FIMAdminService)
        else:
            try:
                servicemanager.Initialize()
                servicemanager.PrepareToHostSingle(FIMAdminService)
                servicemanager.StartServiceCtrlDispatcher()
            except:
                daemon = FIMAdminDaemon()
                daemon.run()
    else:
        daemon = FIMAdminDaemon()
        daemon.run()

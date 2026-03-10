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

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

def get_config():
    """Get platform-specific configuration"""
    if sys.platform == 'win32':
        from platform_specific.windows_config import WindowsFIMConfig
        return WindowsFIMConfig()
    else:
        from platform_specific.linux_config import LinuxFIMConfig
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

class FIMAdminDaemon:
    
    def __init__(self):
        self.config = get_config()
        self.setup_logging()
        self.sys_config_path = get_system_config_path()
        self.running = True

    def setup_logging(self):
        log_dir = os.path.dirname(self.config.pid_file) if self.config.pid_file else '/tmp'
        if sys.platform == 'win32':
            log_dir = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'FIMClient', 'logs')
        else:
            log_dir = '/var/log/fim-client'
            
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'admin_daemon.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - AdminDaemon - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
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
            
        # Read current system config
        sys_config = {}
        if os.path.exists(self.sys_config_path):
            try:
                with open(self.sys_config_path, 'r') as f:
                    sys_config = json.load(f)
            except Exception as e:
                self.logger.error(f"Error reading system config: {e}")
                
        # Update watch directory
        sys_config['watch_directory'] = new_path
        
        # Save back to system config
        try:
            with open(self.sys_config_path, 'w') as f:
                json.dump(sys_config, f, indent=2)
            self.logger.info(f"Successfully updated system watch directory to: {new_path}")
            return {"success": True, "message": f"Directory changed to {new_path}"}
        except Exception as e:
            self.logger.error(f"Failed to write system config: {e}")
            return {"success": False, "error": f"Failed to save configuration: {str(e)}"}

    def handle_uninstall(self, payload):
        """Handle self-uninstallation. The script will try to remove the service/files."""
        self.logger.warning("Uninstallation triggered via Admin Daemon")
        
        if sys.platform == 'win32':
            # Try to run the InnoSetup uninstaller silently
            import winreg
            try:
                uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{FIM-CLIENT-99E7-4562-AB89-1234567890AB}_is1"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key) as key:
                    uninstall_string = winreg.QueryValueEx(key, "QuietUninstallString")[0]
                    if uninstall_string:
                        import subprocess
                        # Run uninstaller detached
                        subprocess.Popen(uninstall_string, shell=True)
                        return {"success": True, "message": "Uninstallation started"}
            except Exception as e:
                self.logger.error(f"Failed to find or launch Windows uninstaller: {e}")
                return {"success": False, "error": f"Failed to find uninstaller: {str(e)}"}
        else:
            # Linux uninstallation (dpkg purge or manual rm)
            import subprocess
            try:
                # Run apt-get remove detached or remove service files
                subprocess.Popen("apt-get remove -y fim-client || dpkg -r fim-client", shell=True)
                return {"success": True, "message": "Uninstallation started"}
            except Exception as e:
                self.logger.error(f"Failed to launch Linux uninstaller: {e}")
                return {"success": False, "error": f"Uninstallation failed: {str(e)}"}
                
        return {"success": False, "error": "Uninstallation not fully supported on this platform"}

    def handle_client(self, conn, addr=None):
        try:
            # Depending on if it's multiprocessing.connection or raw socket
            if hasattr(conn, 'recv'):
                # multiprocessing.connection
                request = conn.recv()
                self.logger.info(f"Received IPC request from {addr if addr else 'client'}")
            else:
                # Raw socket
                data = conn.recv(8192)
                if not data:
                    return
                request = json.loads(data.decode('utf-8'))
                self.logger.info(f"Received IPC socket request from {addr}")
                
            action = request.get('action')
            token = request.get('token')
            payload = request.get('payload', {})
            
            if not action or not token:
                response = {"success": False, "error": "Missing action or token"}
            else:
                # Verify token physically with server
                is_valid, validation_data = self.verify_action_token(token, action)
                
                if not is_valid:
                    response = {"success": False, "error": f"Token rejected: {validation_data}"}
                else:
                    # Token is valid, route to handler
                    if action == 'change_directory':
                        response = self.handle_change_directory(payload)
                    elif action == 'uninstall':
                        response = self.handle_uninstall(payload)
                    else:
                        response = {"success": False, "error": f"Unknown action: {action}"}
                        
            # Send response back
            if hasattr(conn, 'send'):
                conn.send(response)
            else:
                conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                
        except Exception as e:
            self.logger.error(f"Error handling IPC client: {e}")
            try:
                err_resp = {"success": False, "error": "Internal daemon error"}
                if hasattr(conn, 'send'):
                    conn.send(err_resp)
                else:
                    conn.sendall((json.dumps(err_resp) + '\n').encode('utf-8'))
            except:
                pass
        finally:
            conn.close()

    def run(self):
        self.logger.info(f"Starting FIM Admin Daemon on {self.config.platform_type}")
        
        if sys.platform == 'win32':
            address = r'\\.\pipe\fim_admin_ipc'
            listener = Listener(address)
            self.logger.info(f"Listening on Named Pipe: {address}")
            
            while self.running:
                try:
                    conn = listener.accept()
                    client_thread = threading.Thread(target=self.handle_client, args=(conn,))
                    client_thread.daemon = True
                    client_thread.start()
                except Exception as e:
                    self.logger.error(f"Listener error: {e}")
                    time.sleep(1)
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
                    self.logger.error(f"Listener error: {e}")
                    time.sleep(1)

if __name__ == '__main__':
    daemon = FIMAdminDaemon()
    daemon.run()

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
    RING_BUFFER_SIZE = 500   # log entries replayed to a freshly connecting GUI

    def __init__(self):
        self.config = get_config(skip_logging=True)
        self.setup_logging()
        self.sys_config_path = get_system_config_path()
        self.running = True

        # --- Monitoring ownership ---
        self.state = None               # FIMState instance (loaded in _start_monitoring)
        self.conn_mgr = None            # RegistrationClient instance
        self._subscribers = []          # list of (pipe_handle, lock) for live GUI connections
        self._subscribers_lock = threading.Lock()
        self._log_ring = []             # ring buffer of last RING_BUFFER_SIZE log msgs
        self._ring_lock = threading.Lock()
        self._monitor_stop = threading.Event()
        self._monitor_thread = None

    def _make_log_callback(self):
        """Return a log_callback that broadcasts to all subscribers and stores in ring buffer."""
        def _callback(msg):
            # Store in ring buffer
            with self._ring_lock:
                self._log_ring.append(msg)
                if len(self._log_ring) > self.RING_BUFFER_SIZE:
                    self._log_ring.pop(0)
            # Broadcast to all connected GUI pipes
            self._broadcast(msg)

        return _callback

    def _broadcast(self, msg):
        """Write msg as newline-delimited JSON to all connected subscriber handles."""
        encoded = (json.dumps(msg) + '\n').encode('utf-8')
        dead = []
        with self._subscribers_lock:
            for entry in self._subscribers:
                handle, lock = entry
                try:
                    with lock:
                        if sys.platform == 'win32':
                            win32file.WriteFile(handle, encoded)
                        else:
                            handle.sendall(encoded)
                except Exception:
                    dead.append(entry)
            for d in dead:
                self._subscribers.remove(d)

    def _start_monitoring(self):
        """Resolve state/conn objects and launch run_daemon_background in a thread."""
        try:
            # Build the same objects fim_client.py used to build
            if sys.platform == 'win32':
                base_dir = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
                state_dir = os.path.join(base_dir, 'FIMClient')
            else:
                state_dir = os.path.expanduser('~/.fim-client')
            os.makedirs(state_dir, exist_ok=True)
            state_file = os.path.join(state_dir, 'state.json')

            from core.state import FIMState
            from core.registration_client import RegistrationClient

            self.state = FIMState(state_file)
            cb = self._make_log_callback()
            self.conn_mgr = RegistrationClient(self.config, self.state, log_callback=cb)

            watch_dir = self.state.get_watch_directory()
            if not watch_dir:
                self.logger.warning('No watch directory configured; monitoring deferred until GUI sets one.')
                # Re-check periodically until a directory is set
                def _wait_for_dir():
                    while self.running and not self._monitor_stop.is_set():
                        import time
                        time.sleep(5)
                        wd = self.state.get_watch_directory()
                        if wd:
                            self._launch_monitor_thread(self.state, self.conn_mgr, wd)
                            return
                threading.Thread(target=_wait_for_dir, daemon=True).start()
                return

            self._launch_monitor_thread(self.state, self.conn_mgr, watch_dir)
        except Exception as e:
            self.logger.error(f'Failed to start monitoring: {e}')

    def _launch_monitor_thread(self, state, conn_mgr, watch_dir):
        from daemon.background import run_daemon_background
        
        # Guard against duplicate threads in the same process
        if self._monitor_thread and self._monitor_thread.is_alive():
            self.logger.warning(f"Monitoring thread already alive for {watch_dir}; signaling stop before restart.")
            self._monitor_stop.set()
            # Wait briefly for it to exit
            self._monitor_thread.join(timeout=3)
            
        cb = self._make_log_callback()
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(
            target=run_daemon_background,
            args=(self.config, state, conn_mgr, cb, watch_dir, self._monitor_stop),
            daemon=True,
            name='FIMMonitor'
        )
        self._monitor_thread.start()
        self.logger.info(f'Monitoring thread started for {watch_dir}')

    def _handle_subscribe(self, conn):
        """Long-lived connection: replay ring buffer then stream live logs to the GUI."""
        lock = threading.Lock()
        # Replay history
        with self._ring_lock:
            history = list(self._log_ring)
        
        # Send initial sync message to give GUI context immediately
        if self.state:
            sync_msg = {
                'type': 'sync',
                'directory': self.state.get_watch_directory(),
                'connected': self.conn_mgr.connected if self.conn_mgr else False,
                'pending': self.state.get_queue_size(),
                'deregistered': self.state.is_deregistered()
            }
            history.insert(0, sync_msg)

        for msg in history:
            try:
                encoded = (json.dumps(msg) + '\n').encode('utf-8')
                if sys.platform == 'win32' and isinstance(conn, int):
                    win32file.WriteFile(conn, encoded)
                else:
                    conn.sendall(encoded)
            except Exception:
                return
        # Register as live subscriber
        entry = (conn, lock)
        with self._subscribers_lock:
            self._subscribers.append(entry)
        # Block until the connection dies (client will close it on exit)
        try:
            while True:
                import time
                time.sleep(1)
                # Probe: try a zero-byte write
                if sys.platform == 'win32' and isinstance(conn, int):
                    try:
                        win32file.WriteFile(conn, b'')
                    except Exception:
                        break
                elif hasattr(conn, 'fileno'):
                    import select
                    r, _, _ = select.select([conn], [], [], 0)
                    if r:
                        data = conn.recv(1, socket.MSG_PEEK)
                        if not data:
                            break
        except Exception:
            pass
        finally:
            with self._subscribers_lock:
                if entry in self._subscribers:
                    self._subscribers.remove(entry)

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

    def broadcast_status(self):
        """Broadcast current connection and pending stats to all subscribers."""
        if self.state and self.conn_mgr:
            msg = {
                'type': 'sync', # reused by GUI to update multiple labels
                'directory': self.state.get_watch_directory(),
                'connected': self.conn_mgr.connected,
                'pending': self.state.get_queue_size(),
                'deregistered': self.state.is_deregistered()
            }
            self._broadcast(msg)

    def handle_reregister(self, payload):
        """Handle manual reregistration request from GUI"""
        username = payload.get('username')
        password = payload.get('password')
        if not username or not password:
            return {"success": False, "error": "Missing credentials"}
            
        try:
            import requests
            response = requests.post(
                f"{self.config.server_url}/api/clients/reregister",
                json={
                    'client_id': self.config.host_id,
                    'username': username,
                    'password': password
                },
                timeout=15
            )
            
            if response.status_code == 200:
                if self.state:
                    self.state.set_deregistered(False)
                self.logger.info("Reregistration successful")
                self.broadcast_status()
                # If monitoring wasn't running, start it
                if not self._monitor_thread or not self._monitor_thread.is_alive():
                    self._start_monitoring()
                return {"success": True, "message": "Reregistered successfully"}
            else:
                error = response.json().get('error', 'Server rejected request')
                return {"success": False, "error": error}
        except Exception as e:
            self.logger.error(f"Reregistration failed: {e}")
            return {"success": False, "error": str(e)}

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
        
        # Remove old signature if present to ensure the hash is calculated purely on the config values
        sys_config.pop('_signature', None)
        
        try:
            # Generate a signature for the config to prevent manual tampering
            config_str = json.dumps(sys_config, sort_keys=True)
            self.logger.info(f"Hashing Config string: {repr(config_str)}")
            signature = self._generate_config_signature(config_str)
            self.logger.info(f"Generated Signature: {signature}")
            sys_config['_signature'] = signature
            
            with open(self.sys_config_path, 'w') as f:
                json.dump(sys_config, f, indent=2)
            self.logger.info(f"Successfully updated system watch directory to: {new_path}")
            
            # Restart monitoring thread to pick up the new directory and trigger scan
            if self.running:
                self.logger.info("Restarting monitoring for new directory...")
                self._monitor_stop.set()
                if self._monitor_thread:
                    self._monitor_thread.join(timeout=2)
                self._start_monitoring()

            return {"success": True, "message": f"Directory changed to {new_path}"}
        except Exception as e:
            self.logger.error(f"Failed to write system config: {e}")
            return {"success": False, "error": f"Failed to save configuration: {str(e)}"}
            
    def _generate_config_signature(self, data_str):
        """Generate a signature for the configuration string"""
        import hashlib
        import base64
        
        # We need a stable key for HMAC.
        # It's better to use the same logic as FIMState._get_machine_id_key
        # but since we are in AdminDaemon, we can just hash a known machine attribute.
        machine_key = self._get_machine_key()
        self.logger.info(f"Using Machine Key: {machine_key.hex()}")
        
        hasher = hashlib.sha256()
        hasher.update(machine_key)
        hasher.update(data_str.encode('utf-8'))
        return base64.b64encode(hasher.digest()).decode('utf-8')
        
    def _get_machine_key(self):
        """Get a stable machine key for signing the local config"""
        import hashlib
        if sys.platform == 'win32':
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                    machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                    return hashlib.sha256(machine_guid.encode()).digest()
            except Exception:
                pass
        
        # Linux fallback or Windows failure
        machine_id_paths = ['/etc/machine-id', '/var/lib/dbus/machine-id']
        machine_id = None
        for path in machine_id_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        machine_id = f.read().strip()
                    break
                except:
                    continue
        
        if not machine_id:
            import socket
            machine_id = socket.gethostname()
            
        return hashlib.sha256(machine_id.encode()).digest()

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
                
            if not action:
                response = {"success": False, "error": "Missing action"}
            else:
                if action == 'change_directory':
                    response = self.handle_change_directory(payload)
                elif action == 'uninstall':
                    response = self.handle_uninstall(payload)
                elif action == 'reregister':
                    response = self.handle_reregister(payload)
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
        self.logger.info("Stopping Admin Daemon...")
        self.running = False
        self._monitor_stop.set()
        
        # Unblock the listener.accept() call by connecting to the pipe/socket
        try:
            if sys.platform == 'win32':
                import win32file
                # A simple connection to the pipe is enough to wake up ConnectNamedPipe
                handle = win32file.CreateFile(
                    r'\\.\pipe\fim_admin_ipc',
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0, None,
                    win32file.OPEN_EXISTING,
                    0, None
                )
                win32file.CloseHandle(handle)
            else:
                address = '/var/run/fim_admin.sock'
                if os.path.exists(address):
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(address)
                    sock.close()
        except Exception as e:
            self.logger.debug(f"Self-connection to unblock listener failed (intended): {e}")

    def run(self):
        # Enforce single-instance lock globally (Service or Manual)
        acquired, lock_obj = try_acquire_admin_lock()
        if not acquired:
            self.logger.critical("FIM Admin Daemon is already running (Mutex held). Exiting. [SPLIT_BRAIN_V8]")
            return
            
        self.logger.info(f'Starting FIM Admin Daemon on {self.config.platform_type}')
        # Store lock to keep it alive
        self._mutex_lock = lock_obj
        
        # Start monitoring in background
        self._start_monitoring()
        
        if sys.platform == 'win32':
            address = r'\\.\pipe\fim_admin_ipc'
            try:
                listener = WindowsPipeListener(address)
                self.logger.info(f"Listening on Named Pipe with permissive DACL: {address}")
                
                while self.running:
                    try:
                        conn = listener.accept()
                        if not self.running:
                             # We were woken up just to exit
                             if isinstance(conn, int):
                                 import win32pipe, win32file
                                 try:
                                     win32pipe.DisconnectNamedPipe(conn)
                                     win32file.CloseHandle(conn)
                                 except: pass
                             break
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

def try_acquire_admin_lock():
    """Attempt to acquire a single-instance OS lock for the Admin Daemon"""
    import sys
    if sys.platform == 'win32':
        import win32event
        import win32api
        import winerror
        mutex_name = "Global\\FIM_Admin_Daemon_Mutex"
        mutex = win32event.CreateMutex(None, False, mutex_name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            return False, mutex
        return True, mutex
    else:
        import os
        import fcntl
        lock_file_path = "/var/run/fim_admin.pid"
        try:
            lock_file = open(lock_file_path, 'w')
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(str(os.getpid()))
            lock_file.flush()
            return True, lock_file
        except (IOError, OSError):
            return False, None

def run_daemon():
    """Helper to run daemon"""
    daemon = FIMAdminDaemon()
    daemon.run()

if __name__ == '__main__':
    if sys.platform == 'win32':
        if len(sys.argv) > 1 and sys.argv[1] in ['install', 'update', 'remove', 'start', 'stop', 'restart', 'status']:
            win32serviceutil.HandleCommandLine(FIMAdminService)
        else:
            try:
                servicemanager.Initialize()
                servicemanager.PrepareToHostSingle(FIMAdminService)
                # The service manager has its own single-instance guarantees,
                # but our SvcDoRun will also acquire the mutex just in case.
                servicemanager.StartServiceCtrlDispatcher()
            except:
                run_daemon()
    else:
        run_daemon()

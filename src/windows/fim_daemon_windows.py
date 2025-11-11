#!/usr/bin/env python3
import sys
import os
import time
import hashlib
import logging
import platform
import subprocess
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add core module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

from merkle import build_merkle_tree, get_merkle_path
from utils import sha256_file, ensure_directory

SERVER_URL = "https://fim-distribution.vercel.app"

class HardwareClientIdentifier:
    def __init__(self):
        self.client_id = self.get_hardware_id()
        self.client_info = self.get_hardware_info()
    
    def get_hardware_id(self):
        """Generate client ID from hardware characteristics"""
        hardware_data = []
        
        # Windows hardware identifiers
        board_serial = self._get_windows_wmi("Win32_BaseBoard", "SerialNumber")
        if board_serial:
            hardware_data.append(f"board:{board_serial}")
        
        bios_serial = self._get_windows_wmi("Win32_BIOS", "SerialNumber")
        if bios_serial:
            hardware_data.append(f"bios:{bios_serial}")
        
        cpu_id = self._get_windows_wmi("Win32_Processor", "ProcessorId")
        if cpu_id:
            hardware_data.append(f"cpu:{cpu_id}")
        
        if hardware_data:
            # Sort for consistency and create hash
            hardware_data.sort()
            hardware_hash = hashlib.sha256('|'.join(hardware_data).encode()).hexdigest()[:16]
            return f"windows-{hardware_hash}"
        else:
            # Fallback if no hardware info available
            hostname = platform.node()
            return f"windows-{hostname}"
    
    def _get_windows_wmi(self, class_name, property_name):
        """Get WMI property using PowerShell"""
        try:
            cmd = f"Get-WmiObject -Class {class_name} | Select-Object -ExpandProperty {property_name}"
            result = subprocess.run([
                "powershell", "-Command", cmd
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        return None
    
    def get_hardware_info(self):
        """Collect hardware information for reporting"""
        return {
            'hostname': platform.node(),
            'platform': 'windows',
            'board_serial': self._get_windows_wmi("Win32_BaseBoard", "SerialNumber"),
            'bios_serial': self._get_windows_wmi("Win32_BIOS", "SerialNumber"),
            'cpu_id': self._get_windows_wmi("Win32_Processor", "ProcessorId")
        }

class FIMConfig:
    def __init__(self):
        self.hardware_id = HardwareClientIdentifier()
        self.watch_dir = r"C:\ProgramData\FIM-Daemon\watch-folder"
        self.host_id = self.hardware_id.client_id
        self.baseline_id = 1
        self.server_url = SERVER_URL
        self.setup_logging()
        self.register_with_server()
        
    def setup_logging(self):
        log_dir = ensure_directory(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))
        log_file = os.path.join(log_dir, 'fim-daemon.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - {self.host_id} - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"FIM Windows client initialized with hardware ID: {self.host_id}")
    
    def register_with_server(self):
        """Register this client with the central server"""
        try:
            response = requests.post(
                f"{self.server_url}/api/clients/register",
                json={
                    'client_id': self.host_id,
                    'hardware_info': self.hardware_id.client_info,
                    'baseline_id': self.baseline_id,
                    'platform': 'windows'
                },
                timeout=10
            )
            if response.status_code == 200:
                self.logger.info("Successfully registered with central server")
            else:
                self.logger.warning(f"Failed to register with server: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Error registering with server: {e}")
    
    def send_heartbeat(self, file_count, current_root_hash):
        """Send heartbeat to server"""
        try:
            response = requests.post(
                f"{self.server_url}/api/clients/heartbeat",
                json={
                    'client_id': self.host_id,
                    'file_count': file_count,
                    'current_root_hash': current_root_hash
                },
                timeout=5
            )
            if response.status_code == 200:
                self.logger.debug("Heartbeat sent successfully")
        except Exception as e:
            self.logger.debug(f"Heartbeat failed: {e}")
    
    def report_event(self, event_data):
        """Report file event to server"""
        try:
            response = requests.post(
                f"{self.server_url}/api/events/report",
                json=event_data,
                timeout=10
            )
            if response.status_code == 200:
                self.logger.debug(f"Event reported successfully: {event_data['event_type']}")
            else:
                self.logger.warning(f"Failed to report event: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Error reporting event: {e}")

class FIMEventHandler(FileSystemEventHandler):
    def __init__(self, tree, files, config):
        self.tree = tree
        self.files = files
        self.config = config
        self.ignore_events = False
        self.last_heartbeat = 0

    def update_merkle_tree(self, changed_index, new_hash):
        """Update Merkle tree after file modification"""
        level_idx = len(self.tree) - 1
        self.tree[level_idx][changed_index] = new_hash
        idx = changed_index

        while level_idx > 0:
            parent_idx = idx // 2
            left_idx = parent_idx * 2
            right_idx = left_idx + 1

            level = self.tree[level_idx]
            left_hash = level[left_idx]
            right_hash = level[right_idx] if right_idx < len(level) else left_hash

            parent_hash = hashlib.sha256(left_hash + right_hash).digest()
            self.tree[level_idx-1][parent_idx] = parent_hash

            idx = parent_idx
            level_idx -= 1

    def send_heartbeat_if_needed(self):
        """Send heartbeat every 5 minutes"""
        current_time = time.time()
        if current_time - self.last_heartbeat > 300:  # 5 minutes
            root_hash = self.tree[0][0].hex() if self.tree else None
            self.config.send_heartbeat(len(self.files), root_hash)
            self.last_heartbeat = current_time

    def on_created(self, event):
        if self.ignore_events or event.is_directory:
            return
        self._process_created(event)

    def on_modified(self, event):
        if self.ignore_events or event.is_directory:
            return
        self._process_modified(event)

    def on_deleted(self, event):
        if self.ignore_events or event.is_directory:
            return
        self._process_deleted(event)

    def _process_created(self, event):
        self.ignore_events = True
        time.sleep(0.05)  # debounce for file write completion

        h = sha256_file(event.src_path)
        if not h:
            self.config.logger.error(f"FAILED to track new file: {event.src_path}")
            self.ignore_events = False
            return

        self.files.append((event.src_path, h))
        self.files.sort(key=lambda x: x[0])
        self.tree, self.files = build_merkle_tree(self.files)

        path_info = get_merkle_path(self.tree, self.files, event.src_path)
        if path_info:
            event_data = {
                'client_id': self.config.host_id,
                'event_type': 'created',
                'file_path': event.src_path,
                'new_hash': h.hex(),
                'root_hash': path_info['root_hash'].hex(),
                'merkle_proof': {
                    'path': [p.hex() for p in path_info['path']],
                    'index': path_info['index']
                }
            }
            self.config.report_event(event_data)
            
            self.config.logger.info(f"New file tracked: {event.src_path}")
            self.config.logger.info(f"Root: {path_info['root_hash'].hex()[:16]}...")

        self.send_heartbeat_if_needed()
        self.ignore_events = False

    def _process_modified(self, event):
        self.ignore_events = True
        time.sleep(0.05)  # debounce

        h = sha256_file(event.src_path)
        if not h:
            self.config.logger.error(f"FAILED to verify modification: {event.src_path}")
            self.ignore_events = False
            return

        for i, (path, old_hash) in enumerate(self.files):
            if path == event.src_path:
                if old_hash == h:
                    self.ignore_events = False
                    return

                self.files[i] = (path, h)
                self.update_merkle_tree(i, h)

                path_info = get_merkle_path(self.tree, self.files, event.src_path)
                
                event_data = {
                    'client_id': self.config.host_id,
                    'event_type': 'modified',
                    'file_path': event.src_path,
                    'old_hash': old_hash.hex(),
                    'new_hash': h.hex(),
                    'root_hash': path_info['root_hash'].hex() if path_info else None,
                    'merkle_proof': {
                        'path': [p.hex() for p in path_info['path']] if path_info else [],
                        'index': path_info['index'] if path_info else 0
                    } if path_info else None
                }
                self.config.report_event(event_data)
                
                self.config.logger.info(f"Change detected: {event.src_path}")
                if path_info:
                    self.config.logger.info(f"New root: {path_info['root_hash'].hex()[:16]}...")
                self.ignore_events = False
                return

        # If file not found, treat as new
        self._process_created(event)
        self.ignore_events = False

    def _process_deleted(self, event):
        self.ignore_events = True
        
        # Find the file before removing it to get its hash
        old_hash = None
        for path, h in self.files:
            if path == event.src_path:
                old_hash = h
                break

        self.files = [(path, h) for path, h in self.files if path != event.src_path]

        if self.files:
            self.tree, self.files = build_merkle_tree(self.files)
            root_hash = self.tree[0][0].hex() if self.tree else None
            
            event_data = {
                'client_id': self.config.host_id,
                'event_type': 'deleted',
                'file_path': event.src_path,
                'old_hash': old_hash.hex() if old_hash else None,
                'root_hash': root_hash,
                'merkle_proof': None
            }
            self.config.report_event(event_data)
            
            self.config.logger.info(f"File deleted: {event.src_path}")
            if self.tree:
                self.config.logger.info(f"New root: {self.tree[0][0].hex()[:16]}...")
        else:
            self.tree = None
            
            event_data = {
                'client_id': self.config.host_id,
                'event_type': 'deleted',
                'file_path': event.src_path,
                'old_hash': old_hash.hex() if old_hash else None,
                'root_hash': None,
                'merkle_proof': None
            }
            self.config.report_event(event_data)
            self.config.logger.info(f"File deleted: {event.src_path} - No files remaining")

        self.send_heartbeat_if_needed()
        self.ignore_events = False

class FIMDaemon:
    def __init__(self):
        self.config = FIMConfig()
        self.observer = None
        
    def build_initial_tree(self, directory):
        """Build initial Merkle tree from directory contents"""
        files = []
        inaccessible_files = []
        
        for root, _, filenames in os.walk(directory):
            for fname in filenames:
                path = os.path.join(root, fname)
                h = sha256_file(path)
                if h:
                    files.append((path, h))
                else:
                    inaccessible_files.append(path)
        
        if inaccessible_files:
            self.config.logger.warning(f"{len(inaccessible_files)} files inaccessible")
            for f in inaccessible_files[:5]:
                self.config.logger.warning(f"  - {f}")
        
        return build_merkle_tree(files)

    def run(self):
        self.config.logger.info("FIM Windows Daemon starting...")

        ensure_directory(self.config.watch_dir)
        self.config.logger.info(f"Watching: {self.config.watch_dir}")

        tree, files = self.build_initial_tree(self.config.watch_dir)

        if tree:
            self.config.logger.info(f"Initial root: {tree[0][0].hex()}")
            self.config.logger.info(f"Tracking {len(files)} files")
            
            # Send initial baseline to server
            try:
                response = requests.post(
                    f"{self.config.server_url}/api/baselines/save",
                    json={
                        'client_id': self.config.host_id,
                        'root_hash': tree[0][0].hex(),
                        'file_count': len(files)
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    self.config.logger.info("Initial baseline saved to server")
                else:
                    self.config.logger.warning(f"Failed to save initial baseline: {response.status_code}")
            except Exception as e:
                self.config.logger.error(f"Failed to save initial baseline: {e}")
        else:
            self.config.logger.info("No files to monitor at startup")

        event_handler = FIMEventHandler(tree, files, self.config)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.config.watch_dir, recursive=True)
        self.observer.start()

        self.config.logger.info("FIM Windows Daemon started - Press Ctrl+C to stop")

        try:
            while True:
                time.sleep(1)
                # Send periodic heartbeat
                if tree:
                    event_handler.send_heartbeat_if_needed()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.config.logger.info("FIM Windows Daemon stopped")

if __name__ == "__main__":
    daemon = FIMDaemon()
    daemon.run()
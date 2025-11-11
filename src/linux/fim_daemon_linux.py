#!/usr/bin/env python3
import sys
import os
import time
import hashlib
import logging
import signal
import requests
import json
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
        
        # Linux hardware identifiers
        machine_id = self._read_file('/etc/machine-id') or self._read_file('/var/lib/dbus/machine-id')
        if machine_id:
            hardware_data.append(f"machine:{machine_id}")
        
        cpu_info = self._get_cpu_info()
        if cpu_info:
            hardware_data.append(f"cpu:{cpu_info}")
        
        serial = self._get_system_serial()
        if serial:
            hardware_data.append(f"serial:{serial}")
        
        if hardware_data:
            # Sort for consistency and create hash
            hardware_data.sort()
            hardware_hash = hashlib.sha256('|'.join(hardware_data).encode()).hexdigest()[:16]
            return f"linux-{hardware_hash}"
        else:
            # Fallback if no hardware info available
            return "linux-unknown"
    
    def _read_file(self, path):
        """Read file content if it exists"""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    content = f.read().strip()
                    return content if content else None
        except:
            pass
        return None
    
    def _get_cpu_info(self):
        """Extract CPU identifier"""
        try:
            cpuinfo = self._read_file('/proc/cpuinfo')
            if cpuinfo:
                for line in cpuinfo.split('\n'):
                    if line.startswith('vendor_id') or line.startswith('model name'):
                        key, value = line.split(':', 1)
                        return hashlib.sha256(value.strip().encode()).hexdigest()[:8]
        except:
            pass
        return None
    
    def _get_system_serial(self):
        """Get system serial number"""
        serial_sources = [
            '/sys/class/dmi/id/product_uuid',
            '/sys/class/dmi/id/product_serial', 
            '/sys/class/dmi/id/board_serial'
        ]
        
        for source in serial_sources:
            serial = self._read_file(source)
            if serial and serial != 'None' and len(serial) > 4:
                return serial
        return None
    
    def get_hardware_info(self):
        """Collect hardware information for reporting"""
        return {
            'machine_id': self._read_file('/etc/machine-id'),
            'product_uuid': self._read_file('/sys/class/dmi/id/product_uuid'),
            'platform': 'linux'
        }

class FIMConfig:
    def __init__(self):
        self.hardware_id = HardwareClientIdentifier()
        self.watch_dir = "/var/lib/fim-daemon/watch-folder"
        self.host_id = self.hardware_id.client_id
        self.baseline_id = 1
        self.pid_file = "/var/run/fim-daemon.pid"
        self.server_url = SERVER_URL
        self.setup_logging()
        self.register_with_server()
        
    def setup_logging(self):
        ensure_directory("/var/log/fim-daemon")
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - {self.host_id} - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/fim-daemon/fim-daemon.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def register_with_server(self):
        """Register this client with the central server"""
        try:
            response = requests.post(
                f"{self.server_url}/api/clients/register",
                json={
                    'client_id': self.host_id,
                    'hardware_info': self.hardware_id.client_info,
                    'baseline_id': self.baseline_id,
                    'platform': 'linux'
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
            requests.post(
                f"{self.server_url}/api/clients/heartbeat",
                json={
                    'client_id': self.host_id,
                    'file_count': file_count,
                    'current_root_hash': current_root_hash
                },
                timeout=5
            )
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
            if response.status_code != 200:
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
        time.sleep(0.05)

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

        self.send_heartbeat_if_needed()
        self.ignore_events = False

    def _process_modified(self, event):
        self.ignore_events = True
        time.sleep(0.05)

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
        self.running = False
        
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

    def signal_handler(self, signum, frame):
        self.config.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run(self):
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.config.logger.info("FIM Daemon starting...")
        
        ensure_directory(self.config.watch_dir)
        self.config.logger.info(f"Watching: {self.config.watch_dir}")
        
        # Write PID file
        with open(self.config.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        tree, files = self.build_initial_tree(self.config.watch_dir)
        
        event_handler = FIMEventHandler(tree, files, self.config)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.config.watch_dir, recursive=True)
        self.observer.start()

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
            except Exception as e:
                self.config.logger.error(f"Failed to save initial baseline: {e}")
        
        self.config.logger.info("FIM Daemon started")
        self.running = True

        try:
            while self.running:
                time.sleep(1)
                # Send periodic heartbeat
                if tree:
                    event_handler.send_heartbeat_if_needed()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        # Remove PID file
        if os.path.exists(self.config.pid_file):
            os.remove(self.config.pid_file)
            
        self.config.logger.info("FIM Daemon stopped")

if __name__ == "__main__":
    daemon = FIMDaemon()
    daemon.run()
#!/usr/bin/env python3
import os
import time
import logging
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from merkle import build_merkle_tree, update_merkle_tree, get_merkle_path
from utils import sha256_file, ensure_directory

SERVER_URL = "https://fim-distribution.vercel.app"

class FIMConfig:
    def __init__(self, platform_type, watch_dir=None, pid_file=None):
        self.platform_type = platform_type
        self.host_id = None  # To be set by platform-specific code
        self.baseline_id = 1
        self.server_url = SERVER_URL
        self.watch_dir = watch_dir
        self.pid_file = pid_file
        self.daemon_token = None
        self.token_expires = 0
        
    def setup_logging(self, log_file):
        """Setup logging with provided log file path"""
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - {self.host_id} - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"FIM {self.platform_type} client initialized with hardware ID: {self.host_id}")
    
    def register_with_server(self, client_id, hardware_info):
        """Register this client with the central server and get JWT"""
        try:
            response = requests.post(
                f"{self.server_url}/api/clients/register",
                json={
                    'client_id': client_id,
                    'hardware_info': hardware_info,
                    'baseline_id': self.baseline_id,
                    'platform': self.platform_type
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.daemon_token = data['token']  # Store JWT
                self.token_expires = time.time() + data['expires_in']
                self.logger.info("Successfully registered with central server")
            else:
                self.logger.warning(f"Failed to register with server: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Error registering with server: {e}")

    def send_heartbeat(self, file_count, current_root_hash):
        """Send heartbeat to server using JWT"""
        try:
            response = requests.post(
                f"{self.server_url}/api/clients/heartbeat",
                headers={
                    'Authorization': f'Bearer {self.daemon_token}'
                },
                json={
                    'file_count': file_count,
                    'current_root_hash': current_root_hash
                },
                timeout=5
            )
            if response.status_code == 401:
                # Token might be expired, try to re-register
                return False
        except Exception as e:
            self.logger.debug(f"Heartbeat failed: {e}")
        return True

    def report_event(self, event_data):
        """Report file event to server using JWT"""
        try:
            response = requests.post(
                f"{self.server_url}/api/events/report",
                headers={
                    'Authorization': f'Bearer {self.daemon_token}'
                },
                json=event_data,
                timeout=10
            )
            if response.status_code == 200:
                self.logger.debug(f"Event reported successfully: {event_data['event_type']}")
            elif response.status_code == 401:
                # Token might be expired
                return False
            else:
                self.logger.warning(f"Failed to report event: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Error reporting event: {e}")
        return True

    def save_baseline(self, root_hash, file_count):
        """Save initial baseline to server"""
        try:
            response = requests.post(
                f"{self.server_url}/api/baselines/save",
                headers={
                    'Authorization': f'Bearer {self.daemon_token}'
                },
                json={
                    'client_id': self.host_id,
                    'root_hash': root_hash,
                    'file_count': file_count
                },
                timeout=10
            )
            if response.status_code == 200:
                self.logger.info("Initial baseline saved to server")
                return True
            else:
                self.logger.warning(f"Failed to save baseline: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to save baseline: {e}")
            return False

class FIMEventHandler(FileSystemEventHandler):
    def __init__(self, tree, files, config):
        self.tree = tree
        self.files = files
        self.config = config
        self.ignore_events = False
        self.last_heartbeat = 0

    def send_heartbeat_if_needed(self):
        """Send heartbeat every 5 minutes"""
        current_time = time.time()
        if current_time - self.last_heartbeat > 300:  # 5 minutes
            root_hash = self.tree[0][0].hex() if self.tree else None
            if self.config.send_heartbeat(len(self.files), root_hash):
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
            if self.config.report_event(event_data):
                self.config.logger.info(f"New file tracked: {event.src_path}")

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
                self.tree = update_merkle_tree(self.tree, i, h)

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
                if self.config.report_event(event_data):
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
            if self.config.report_event(event_data):
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
            if self.config.report_event(event_data):
                self.config.logger.info(f"File deleted: {event.src_path} - No files remaining")

        self.send_heartbeat_if_needed()
        self.ignore_events = False

class FIMDaemon:
    def __init__(self, config):
        self.config = config
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

    def run_daemon(self):
        """Main daemon loop - handles observer setup for both platforms"""
        self.config.logger.info(f"FIM {self.config.platform_type} Daemon starting...")

        ensure_directory(self.config.watch_dir)
        self.config.logger.info(f"Watching: {self.config.watch_dir}")

        tree, files = self.build_initial_tree(self.config.watch_dir)

        event_handler = FIMEventHandler(tree, files, self.config)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.config.watch_dir, recursive=True)
        self.observer.start()

        if tree:
            self.config.logger.info(f"Initial root: {tree[0][0].hex()}")
            self.config.logger.info(f"Tracking {len(files)} files")
            
            # Send initial baseline to server
            self.config.save_baseline(tree[0][0].hex(), len(files))
        else:
            self.config.logger.info("No files to monitor at startup")

        self.config.logger.info(f"FIM {self.config.platform_type} Daemon started")
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
            self.stop_daemon()

    def stop_daemon(self):
        """Stop the daemon - platform-specific cleanup"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.config.logger.info(f"FIM {self.config.platform_type} Daemon stopped")
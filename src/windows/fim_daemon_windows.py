#!/usr/bin/env python3
import sys
import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add core module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

from merkle import build_merkle_tree, get_merkle_path
from utils import sha256_file, ensure_directory

class FIMConfig:
    def __init__(self):
        self.watch_dir = r"C:\ProgramData\FIM-Daemon\watch-folder"
        self.host_id = "win01"
        self.baseline_id = 1
        self.setup_logging()
        
    def setup_logging(self):
        log_dir = ensure_directory(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))
        log_file = os.path.join(log_dir, 'fim-daemon.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

class FIMEventHandler(FileSystemEventHandler):
    def __init__(self, tree, files, config):
        self.tree = tree
        self.files = files
        self.config = config

    def update_merkle_tree(self, changed_index, new_hash):
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

    def on_created(self, event):
        if event.is_directory:
            return
        
        time.sleep(0.05)  # Allow file to be fully written
        
        h = sha256_file(event.src_path)
        if not h:
            self.config.logger.error(f"FAILED to track new file: {event.src_path}")
            return
        
        self.files.append((event.src_path, h))
        self.files.sort(key=lambda x: x[0])
        
        self.tree, self.files = build_merkle_tree(self.files)
        
        path_info = get_merkle_path(self.tree, self.files, event.src_path)
        if path_info:
            self.config.logger.info(f"New file tracked: {event.src_path}")
            self.config.logger.info(f"Root: {path_info['root_hash'][:16]}...")

    def on_modified(self, event):
        if event.is_directory:
            return
        
        h = sha256_file(event.src_path)
        if not h:
            self.config.logger.error(f"FAILED to verify modification: {event.src_path}")
            return
        
        for i, (path, old_hash) in enumerate(self.files):
            if path == event.src_path:
                if old_hash == h:
                    return
                    
                self.files[i] = (path, h)
                self.update_merkle_tree(i, h)
                
                path_info = get_merkle_path(self.tree, self.files, event.src_path)
                self.config.logger.info(f"Change detected: {event.src_path}")
                if path_info:
                    self.config.logger.info(f"New root: {path_info['root_hash'][:16]}...")
                return
        
        self.on_created(event)

    def on_deleted(self, event):
        if event.is_directory:
            return
        
        self.files = [(path, h) for path, h in self.files if path != event.src_path]
        if self.files:
            self.tree, self.files = build_merkle_tree(self.files)
            self.config.logger.info(f"File deleted: {event.src_path}")
            if self.tree:
                self.config.logger.info(f"New root: {self.tree[0][0].hex()[:16]}...")
        else:
            self.tree = None
            self.config.logger.info(f"File deleted: {event.src_path} - No files remaining")

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
        self.config.logger.info("FIM Daemon starting...")
        
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
        else:
            self.config.logger.info("No files to monitor")

        self.config.logger.info("FIM Daemon started - Press Ctrl+C to stop")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.config.logger.info("FIM Daemon stopped")

if __name__ == "__main__":
    daemon = FIMDaemon()
    daemon.run()
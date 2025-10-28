#!/usr/bin/env python3
import sys
import os
import time
import logging
import signal
import daemon
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add core module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

from merkle import build_merkle_tree, get_merkle_path
from utils import sha256_file, ensure_directory

class FIMConfig:
    def __init__(self):
        self.watch_dir = "/var/lib/fim-daemon/watch-folder"
        self.host_id = "linux01"
        self.baseline_id = 1
        self.pid_file = "/var/run/fim-daemon.pid"
        self.setup_logging()
        
    def setup_logging(self):
        ensure_directory("/var/log/fim-daemon")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/fim-daemon/fim-daemon.log'),
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
        
        time.sleep(0.05)
        
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
                return
        
        self.on_created(event)

    def on_deleted(self, event):
        if event.is_directory:
            return
        
        self.files = [(path, h) for path, h in self.files if path != event.src_path]
        if self.files:
            self.tree, self.files = build_merkle_tree(self.files)
            self.config.logger.info(f"File deleted: {event.src_path}")
        else:
            self.tree = None
            self.config.logger.info(f"File deleted: {event.src_path} - No files remaining")

class FIMDaemon:
    def __init__(self):
        self.config = FIMConfig()
        self.observer = None
        self.running = False
        
    def build_initial_tree(self, directory):
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
        
        self.config.logger.info("FIM Daemon started")
        self.running = True

        try:
            while self.running:
                time.sleep(1)
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

def main():
    daemon = FIMDaemon()
    
    # Run as daemon in production
    if len(sys.argv) > 1 and sys.argv[1] == "--foreground":
        daemon.run()
    else:
        with daemon.DaemonContext():
            daemon.run()

if __name__ == "__main__":
    main()
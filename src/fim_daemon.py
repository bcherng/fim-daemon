import hashlib
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR = r"C:\Users\brian\Documents\fim-daemon\New folder"
HOST_ID = "win01"
BASELINE_ID = 1

def sha256_file(path):
    h = hashlib.sha256()
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    h.update(chunk)
            return h.digest()
        except PermissionError as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            print(f"PERMISSION DENIED after {max_retries} attempts: {path}")
            return None
        except Exception as e:
            print(f"Unexpected error hashing {path}: {e}")
            return None
    
    return None

def build_merkle_tree(directory):
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
    
    # Log inaccessible files for investigation
    if inaccessible_files:
        print(f"WARNING: {len(inaccessible_files)} files could not be accessed:")
        for f in inaccessible_files[:5]:  # Show first 5
            print(f"  - {f}")
        if len(inaccessible_files) > 5:
            print(f"  ... and {len(inaccessible_files) - 5} more")
    
    if not files:
        return None, []

    files.sort(key=lambda x: x[0])
    level = [h for _, h in files]
    tree = [level]

    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i+1] if i+1 < len(level) else left
            h = hashlib.sha256(left + right).digest()
            next_level.append(h)
        tree.insert(0, next_level)
        level = next_level

    return tree, files

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, tree, files):
        self.tree = tree
        self.files = files

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
            print(f"FAILED to track new file (access issue): {event.src_path}")
            return
        
        self.files.append((event.src_path, h))
        self.files.sort(key=lambda x: x[0])
        
        self.tree, self.files = build_merkle_tree(WATCH_DIR)
        
        path_info = get_merkle_path(self.tree, self.files, event.src_path)
        if path_info:
            print(f"New file tracked: {event.src_path}")
            print(f"  Merkle path length: {len(path_info['merkle_path'])}")
            print(f"  New root: {path_info['root_hash'][:16]}...")

    def on_modified(self, event):
        if event.is_directory:
            return
        
        h = sha256_file(event.src_path)
        if not h:
            print(f"FAILED to verify modification (access issue): {event.src_path}")
            return
        
        for i, (path, old_hash) in enumerate(self.files):
            if path == event.src_path:
                if old_hash == h:
                    return
                    
                self.files[i] = (path, h)
                self.update_merkle_tree(i, h)
                
                path_info = get_merkle_path(self.tree, self.files, event.src_path)
                print(f"Change detected: {event.src_path}")
                if path_info:
                    print(f"  Merkle path length: {len(path_info['merkle_path'])}")
                    print(f"  New root: {path_info['root_hash'][:16]}...")
                return
        
        self.on_created(event)

    def on_deleted(self, event):
        if event.is_directory:
            return
        
        self.files = [(path, h) for path, h in self.files if path != event.src_path]
        if self.files:
            self.tree, self.files = build_merkle_tree(WATCH_DIR)
            print(f"File deleted: {event.src_path}")
            if self.tree:
                print(f"  New root: {self.tree[0][0].hex()[:16]}...")
        else:
            self.tree = None
            print(f"File deleted: {event.src_path} - No files remaining")

def get_merkle_path(tree, files, changed_path):
    try:
        leaf_idx = next(i for i, (path, _) in enumerate(files) if path == changed_path)
    except StopIteration:
        return None

    path_hashes = []
    level_idx = len(tree) - 1
    idx = leaf_idx

    while level_idx > 0:
        sibling_idx = idx - 1 if idx % 2 else idx + 1
        sibling_level = tree[level_idx]
        if sibling_idx >= len(sibling_level):
            sibling_idx = idx
        path_hashes.append(sibling_level[sibling_idx].hex())
        idx = idx // 2
        level_idx -= 1

    root_hash = tree[0][0].hex()
    return {"root_hash": root_hash, "merkle_path": path_hashes, "leaf_index": leaf_idx}


def main():
    print("File Integrity Monitor starting...")
    print(f"Watching directory: {WATCH_DIR}")
    
    tree, files = build_merkle_tree(WATCH_DIR)
    
    event_handler = ChangeHandler(tree, files)
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=True)
    observer.start()

    if tree:
        print(f"Initial root hash: {tree[0][0].hex()}")
        print(f"Tracking {len(files)} files")
        print("Monitoring started - Press Ctrl+C to stop")
    else:
        print("No files to monitor. Waiting for new files...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nMonitoring stopped.")
    observer.join()

    
if __name__ == "__main__":
    main()
import hashlib
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR = r"C:\Users\brian\Documents\fim-daemon"  # small test folder
HOST_ID = "win01"
BASELINE_ID = 1

def sha256_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.digest()
    except Exception as e:
        print(f"Error hashing {path}: {e}")
        return None

# Build full tree to get leaf indices (used at startup)
def build_merkle_tree(directory):
    files = []
    for root, _, filenames in os.walk(directory):
        for fname in filenames:
            path = os.path.join(root, fname)
            h = sha256_file(path)
            if h:
                files.append((path, h))
    if not files:
        return None, [], []

    files.sort(key=lambda x: x[0])
    level = [h for _, h in files]
    tree = [level]  # leaves at bottom

    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i+1] if i+1 < len(level) else left
            h = hashlib.sha256(left + right).digest()
            next_level.append(h)
        tree.insert(0, next_level)  # prepend for root at index 0
        level = next_level

    return tree, files  # return tree and file list

# Compute Merkle path for a single file
def get_merkle_path(tree, files, changed_path):
    try:
        leaf_idx = next(i for i, (path, _) in enumerate(files) if path == changed_path)
    except StopIteration:
        return None

    path_hashes = []
    level_idx = len(tree) - 1  # leaves
    idx = leaf_idx

    while level_idx > 0:
        sibling_idx = idx - 1 if idx % 2 else idx + 1
        sibling_level = tree[level_idx]
        if sibling_idx >= len(sibling_level):
            sibling_idx = idx  # duplicate if out of bounds
        path_hashes.append(sibling_level[sibling_idx].hex())

        idx = idx // 2
        level_idx -= 1

    root_hash = tree[0][0].hex()
    return {"root_hash": root_hash, "merkle_path": path_hashes, "leaf_index": leaf_idx}

# Watcher
class ChangeHandler(FileSystemEventHandler):
    def __init__(self, tree, files):
        self.tree = tree
        self.files = files

    def on_modified(self, event):
        if event.is_directory:
            return
        h = sha256_file(event.src_path)
        if not h:
            return
        # update leaf
        for i, (path, _) in enumerate(self.files):
            if path == event.src_path:
                self.files[i] = (path, h)
                self.tree[-1][i] = h
                break
        path_info = get_merkle_path(self.tree, self.files, event.src_path)
        print(f"Change detected: {event.src_path}")
        print(f"Merkle path: {path_info['merkle_path']}")
        print(f"New root: {path_info['root_hash']}")

if __name__ == "__main__":
    tree, files = build_merkle_tree(WATCH_DIR)
    if not files:
        print("No files to monitor.")
        exit(1)
    print(f"Initial root hash: {tree[0][0].hex()}")

    event_handler = ChangeHandler(tree, files)
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=True)
    observer.start()

    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

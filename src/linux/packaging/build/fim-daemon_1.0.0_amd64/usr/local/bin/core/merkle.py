import hashlib
import os

def build_merkle_tree(files):
    """
    Build a Merkle tree from a list of (file_path, file_hash) tuples
    """
    if not files:
        return None, []

    # Sort files for consistent ordering
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

def get_merkle_path(tree, files, changed_path):
    """
    Generate Merkle path for a given file
    """
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
#!/usr/bin/env python3
import hashlib

def build_merkle_tree(files):
    """
    Build a Merkle tree from a list of (file_path, hash) tuples.
    Returns (tree, files) where tree is a list of levels.
    """
    if not files:
        return None, files
    
    # Sort files by path for consistency
    files.sort(key=lambda x: x[0])
    
    # Leaf level: hashes of files
    leaves = [h for _, h in files]
    
    if not leaves:
        return None, files
    
    tree = [leaves]
    current_level = leaves
    
    while len(current_level) > 1:
        next_level = []
        
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            parent = hashlib.sha256(left + right).digest()
            next_level.append(parent)
        
        tree.insert(0, next_level)
        current_level = next_level
    
    return tree, files

def update_merkle_tree(tree, changed_index, new_hash):
    """
    Update Merkle tree after file modification.
    Modifies the tree in-place and returns the updated tree.
    """
    if not tree or changed_index >= len(tree[-1]):
        return tree
    
    # Update the leaf node
    level_idx = len(tree) - 1
    tree[level_idx][changed_index] = new_hash
    idx = changed_index

    # Recalculate parent hashes up to root
    while level_idx > 0:
        parent_idx = idx // 2
        left_idx = parent_idx * 2
        right_idx = left_idx + 1

        level = tree[level_idx]
        left_hash = level[left_idx]
        right_hash = level[right_idx] if right_idx < len(level) else left_hash

        parent_hash = hashlib.sha256(left_hash + right_hash).digest()
        tree[level_idx-1][parent_idx] = parent_hash

        idx = parent_idx
        level_idx -= 1
    
    return tree

def get_merkle_path(tree, files, file_path):
    """
    Get the Merkle path for a specific file.
    Returns dict with 'path', 'index', and 'root_hash'
    """
    if not tree or not files:
        return None
    
    # Find the file index
    file_index = -1
    for i, (path, _) in enumerate(files):
        if path == file_path:
            file_index = i
            break
    
    if file_index == -1:
        return None
    
    merkle_path = []
    current_index = file_index
    
    # Start from the bottom level (leaves)
    for level_idx in range(len(tree) - 1, 0, -1):
        level = tree[level_idx]
        
        # Determine if current node is left or right
        is_left = current_index % 2 == 0
        sibling_index = current_index + 1 if is_left else current_index - 1
        
        # Add sibling hash to path
        if sibling_index < len(level):
            merkle_path.append(level[sibling_index])
        else:
            # If no sibling, duplicate current node
            merkle_path.append(level[current_index])
        
        # Move to parent level
        current_index = current_index // 2
    
    return {
        'path': merkle_path,
        'index': file_index,
        'root_hash': tree[0][0]
    }
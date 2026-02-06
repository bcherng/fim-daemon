#!/usr/bin/env python3
"""
Merkle tree builder for initial directory scanning
"""
import os
from core.merkle import build_merkle_tree
from core.utils import sha256_file


def build_initial_tree(directory, logger=None):
    """
    Build initial Merkle tree from directory contents
    
    Args:
        directory: Path to directory to scan
        logger: Optional logger for warnings
        
    Returns:
        tuple: (tree, files) where tree is the merkle tree and files is list of (path, hash) tuples
    """
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
    
    if inaccessible_files and logger:
        logger.warning(f"{len(inaccessible_files)} files inaccessible")
        for f in inaccessible_files[:5]:
            logger.warning(f"  - {f}")
    
    return build_merkle_tree(files)

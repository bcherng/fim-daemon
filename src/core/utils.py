import hashlib
import time
import os

def sha256_file(path, max_retries=3, retry_delay=0.1):
    """
    Compute SHA-256 hash of a file with retry logic for locked files
    """
    h = hashlib.sha256()
    
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

def ensure_directory(directory):
    """Ensure directory exists"""
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return directory
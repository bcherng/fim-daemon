#!/usr/bin/env python3
"""
File monitor for creating Merkle trees and detecting changes
"""
import time
from datetime import datetime

from core.merkle import build_merkle_tree, get_merkle_path
from core.utils import sha256_file

class FileMonitor:
    def __init__(self, tree, files, config, state, gui_queue, event_queue_mgr, lock):
        self.tree = tree
        self.files = files
        self.config = config
        self.state = state
        self.gui_queue = gui_queue
        self.event_queue_mgr = event_queue_mgr
        self.lock = lock
        self.event_counter = 0
        self.deregistered = False

    def log_to_gui(self, message, status="info"):
        self.gui_queue.put({
            'type': 'log',
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'status': status
        })

    def detect_change(self, file_path, is_new=False, is_deleted=False):
        if self.deregistered:
            return
            
        time.sleep(0.1) 
        
        with self.lock:
            h = None
            if not is_deleted:
                h = sha256_file(file_path)
                if not h:
                    self.config.logger.warning(f"Could not hash {file_path} - skipping")
                    return
            
            file_index = -1
            old_hash = None
            for i, (path, file_hash) in enumerate(self.files):
                if path == file_path:
                    file_index = i
                    old_hash = file_hash
                    break
            
            if is_deleted:
                if file_index < 0:
                    return
                self.files.pop(file_index)
            elif file_index >= 0:
                if old_hash == h:
                    return
                self.files[file_index] = (file_path, h)
            else:
                self.files.append((file_path, h))
            
            self.tree, self.files = build_merkle_tree(self.files)
            path_info = get_merkle_path(self.tree, self.files, file_path)
            
            event_data = {
                'id': f"{self.config.host_id}-{self.event_counter}-{int(time.time()*1000)}",
                'client_id': self.config.host_id,
                'event_type': 'deleted' if is_deleted else ('modified' if file_index >= 0 else 'created'),
                'file_path': file_path,
                'old_hash': old_hash.hex() if old_hash else None,
                'new_hash': h.hex() if h else None,
                'root_hash': path_info['root_hash'].hex() if path_info else None,
                'merkle_proof': {
                    'path': [p.hex() for p in path_info['path']] if path_info else [],
                    'index': path_info['index'] if path_info else 0
                } if path_info else None,
                'last_valid_hash': self.state.get_last_valid_hash(),
                'timestamp': datetime.now().isoformat()
            }
            
            self.event_counter += 1
            
            self.state.enqueue_event(event_data)
            self.log_to_gui(f"Queued: {event_data['event_type']} - {file_path}", "info")
            self.gui_queue.put({'type': 'pending', 'count': self.state.get_queue_size()})
            
            self.event_queue_mgr.start_processing()

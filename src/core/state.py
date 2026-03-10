#!/usr/bin/env python3
"""
Persistent state management for FIM client
"""
import os
import json
import threading
import uuid
from pathlib import Path


class FIMState:
    """Thread-safe persistent state manager"""
    
    def __init__(self, state_file):
        self.state_file = state_file
        self.lock = threading.RLock()
        self.state = self._load_state()
        self.boot_id = uuid.uuid4().hex # Unique ID for this process run
        
        from core.crypto import DeviceSigner
        state_dir = os.path.dirname(state_file)
        self.device_signer = DeviceSigner(state_dir)
    
    def _load_state(self):
        """Load state from disk or create default"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load state: {e}")
        
        return {
            'watch_directory': None,
            'last_valid_hash': None,
            'last_server_validation': None,
            'event_queue': [],
            'is_deregistered': False
        }
    
    def save(self):
        """Save state to disk"""
        try:
            with self.lock:
                os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
                with open(self.state_file, 'w') as f:
                    json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Failed to save state: {e}")
    
    def _get_system_config_path(self):
        import sys
        if sys.platform == 'win32':
            base_dir = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
            return os.path.join(base_dir, 'FIMClient', 'system_config.json')
        else:
            return '/etc/fim-client/system_config.json'

    # Directory management
    def set_watch_directory(self, directory):
        """No-op for User Daemon. Admin Daemon changes this via IPC."""
        pass
        
    def get_watch_directory(self):
        """Get the monitoring directory from system config"""
        sys_config_path = self._get_system_config_path()
        if os.path.exists(sys_config_path):
            try:
                with open(sys_config_path, 'r') as f:
                    config = json.load(f)
                    return config.get('watch_directory')
            except Exception:
                return None
        return None
    
    # Hash management
    def update_last_valid_hash(self, hash_value, validation):
        """Update the last validated hash from server"""
        with self.lock:
            self.state['last_valid_hash'] = hash_value
            self.state['last_server_validation'] = validation
            self.save()
    
    def get_last_valid_hash(self):
        """Get the last validated hash"""
        return self.state.get('last_valid_hash')
    
    # Event queue operations
    def enqueue_event(self, event):
        """Add event to end of queue"""
        from datetime import datetime
        with self.lock:
            event['queued_at'] = datetime.now().isoformat()
            
            # Ensure last_valid_hash is present if not provided
            if event.get('last_valid_hash') is None:
                event['last_valid_hash'] = self.get_last_valid_hash()

            # Determine prev_event_hash for the chain
            prev_event_hash = None
            if self.state['event_queue']:
                prev_event_hash = self.state['event_queue'][-1].get('event_hash')
            else:
                prev_event_hash = self.get_last_valid_hash()
                
            event['prev_event_hash'] = prev_event_hash
            
            # Calculate new event_hash
            import hashlib
            hasher = hashlib.sha256()
            hasher.update(str(event.get('id', '')).encode())
            hasher.update(str(event.get('prev_event_hash') or '').encode())
            hasher.update(str(event.get('last_valid_hash') or '').encode())
            hasher.update(str(event.get('new_hash') or '').encode())
            event['event_hash'] = hasher.hexdigest()
            
            # Sign event if possible
            if hasattr(self, 'device_signer') and self.device_signer:
                # Sign the deterministically stringified base chain elements
                payload_str = f"{event.get('id')}{event.get('prev_event_hash')}{event.get('last_valid_hash')}{event.get('new_hash')}"
                event['signature'] = self.device_signer.sign_payload(payload_str)
            
            self.state['event_queue'].append(event)
            self.save()
    
    def peek_event(self):
        """Get first event without removing"""
        with self.lock:
            if self.state['event_queue']:
                return self.state['event_queue'][0]
            return None
    
    def dequeue_event(self):
        """Remove first event from queue"""
        with self.lock:
            if self.state['event_queue']:
                event = self.state['event_queue'].pop(0)
                self.save()
                return event
            return None
    
    def get_queue_size(self):
        """Get current queue size"""
        with self.lock:
            return len(self.state['event_queue'])

    def set_deregistered(self, status):
        """Set the deregistered flag"""
        with self.lock:
            self.state['is_deregistered'] = status
            self.save()

    def is_deregistered(self):
        """Check if this machine is deregistered"""
        return self.state.get('is_deregistered', False)
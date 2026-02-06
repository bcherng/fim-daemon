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
            'jwt_token': None,
            'token_expires': 0,
            'admin_credentials': None,
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
    
    # Directory management
    def set_watch_directory(self, directory):
        """Set the monitoring directory"""
        with self.lock:
            self.state['watch_directory'] = directory
            self.save()
    
    def get_watch_directory(self):
        """Get the monitoring directory"""
        return self.state.get('watch_directory')
    
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
    
    def update_queued_events_base(self, new_hash):
        """Update last_valid_hash for queued events to maintain chain"""
        with self.lock:
            first = True
            for event in self.state['event_queue']:
                if not first and event.get('event_type') == 'directory_selected':
                    # Stop updating as this event starts a new chain
                    break
                event['last_valid_hash'] = new_hash
                first = False
            self.save()
    
    def get_queue_size(self):
        """Get current queue size"""
        with self.lock:
            return len(self.state['event_queue'])
    
    # JWT management
    def set_jwt(self, token, expires_in=2592000):
        """Set JWT token and expiration"""
        import time
        with self.lock:
            self.state['jwt_token'] = token
            self.state['token_expires'] = time.time() + expires_in
            self.save()
    
    def get_jwt(self):
        """Get JWT token if not expired"""
        import time
        if self.state['jwt_token'] and time.time() < self.state['token_expires']:
            return self.state['jwt_token']
        return None
    
    def clear_jwt(self):
        """Clear JWT token"""
        with self.lock:
            self.state['jwt_token'] = None
            self.state['token_expires'] = 0
            self.save()
    
    # Admin credentials
    def set_admin_credentials(self, username, password_hash):
        """Cache admin credentials"""
        with self.lock:
            self.state['admin_credentials'] = {
                'username': username,
                'password_hash': password_hash
            }
            self.save()
    
    def verify_admin_credentials(self, username, password):
        """Verify admin credentials against cached hash"""
        creds = self.state.get('admin_credentials')
        if not creds or creds['username'] != username:
            return False
        
        try:
            import bcrypt
            return bcrypt.checkpw(password.encode(), creds['password_hash'].encode())
        except:
            return False
    
    def clear_admin_credentials(self):
        """Clear cached admin credentials"""
        with self.lock:
            self.state['admin_credentials'] = None
            self.save()

    def set_deregistered(self, status):
        """Set the deregistered flag"""
        with self.lock:
            self.state['is_deregistered'] = status
            if status:
                self.state['jwt_token'] = None
            self.save()

    def is_deregistered(self):
        """Check if this machine is deregistered"""
        return self.state.get('is_deregistered', False)
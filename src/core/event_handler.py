#!/usr/bin/env python3
"""
Event handler with queue management and handshake protocol
"""
import time
import threading
from datetime import datetime
import requests

from core.merkle import build_merkle_tree, get_merkle_path
from core.utils import sha256_file


class FIMEventHandler:
    """Event handler with proper queue and handshake protocol"""
    
    def __init__(self, tree, files, config, state, connection_mgr, gui_queue):
        self.tree = tree
        self.files = files
        self.config = config
        self.state = state
        self.connection_mgr = connection_mgr
        self.gui_queue = gui_queue
        self.ignore_events = False
        self.last_heartbeat = 0
        self.event_counter = 0
        self.processing_queue = False
        self.lock = threading.Lock()
    
    def log_to_gui(self, message, status="info"):
        """Send log message to GUI"""
        self.gui_queue.put({
            'type': 'log',
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'status': status
        })
    
    def process_event_queue(self):
        """Process events from queue with handshake protocol"""
        if self.processing_queue or not self.connection_mgr.connected:
            return
        
        self.processing_queue = True
        
        try:
            while self.connection_mgr.connected:
                # Peek at first event
                event = self.state.peek_event()
                if not event:
                    break
                
                # Try to send to server
                result = self.send_event_to_server(event)
                
                if result['success']:
                    # Server verified, send acknowledgement
                    ack_result = self.send_acknowledgement(
                        result['event_id'], 
                        result['validation']
                    )
                    
                    if ack_result:
                        # Update local state
                        self.state.update_last_valid_hash(
                            event['root_hash'],
                            result['validation']
                        )
                        
                        # Fix Hash Chain: Update remaining events in queue to use this new valid hash
                        self.state.update_queued_events_base(event['root_hash'])
                        
                        # Dequeue event
                        self.state.dequeue_event()
                        self.log_to_gui(
                            f"✓ Synced: {event['event_type']} - {event.get('file_path', 'N/A')}", 
                            "success"
                        )
                        self.gui_queue.put({
                            'type': 'pending', 
                            'count': self.state.get_queue_size()
                        })
                    else:
                        # Acknowledgement failed, will retry
                        self.log_to_gui("⚠ Acknowledgement failed, will retry", "warning")
                        self.connection_mgr.mark_disconnected()
                        break
                else:
                    # Server rejected or connection failed
                    if result.get('rejected'):
                        self.log_to_gui(
                            f"Event rejected: {result.get('reason')}", 
                            "error"
                        )
                        # Remove invalid event
                        self.state.dequeue_event()
                    else:
                        self.log_to_gui("⚠ Connection lost, will retry", "warning")
                        self.connection_mgr.mark_disconnected()
                        break
        finally:
            self.processing_queue = False
    
    def send_event_to_server(self, event_data):
        """Send event to server and get verification/rejection"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/events/report",
                headers={'Authorization': f'Bearer {self.config.daemon_token}'},
                json=event_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'event_id': data['event_id'],
                    'validation': data['validation']
                }
            elif response.status_code == 400:
                # Server rejected
                data = response.json()
                return {
                    'success': False,
                    'rejected': True,
                    'reason': data.get('error', 'Unknown error')
                }
            elif response.status_code == 401:
                data = response.json()
                if "not registered" in data.get('error', '').lower():
                    self.gui_queue.put({'type': 'removal_detected'})
                    return {'success': False, 'rejected': True, 'reason': 'Machine removed from server'}
                # Token expired
                self.state.clear_jwt()
                return {'success': False, 'rejected': False}
            else:
                try:
                    error_msg = response.json().get('error', response.text)
                except:
                    error_msg = response.text
                self.config.logger.error(f"Server error {response.status_code}: {error_msg}")
                return {'success': False, 'rejected': False}
        except Exception as e:
            self.config.logger.error(f"Failed to send event: {e}")
            return {'success': False, 'rejected': False}
    
    def send_acknowledgement(self, event_id, validation):
        """Send acknowledgement that we received the validation"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/events/acknowledge",
                headers={'Authorization': f'Bearer {self.config.daemon_token}'},
                json={
                    'event_id': event_id,
                    'validation_received': validation
                },
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def detect_file_change(self, file_path, is_new=False, is_deleted=False):
        """Detect and queue file change with thread safety and deduplication"""
        # System-level debounce to allow Windows file operations to settle
        time.sleep(0.1) 
        
        with self.lock:
            h = None
            if not is_deleted:
                h = sha256_file(file_path)
                if not h:
                    # File might have been moved or deleted between event and hash attempt
                    self.config.logger.warning(f"Could not hash {file_path} - skipping")
                    return
            
            # Find current file state in memory
            file_index = -1
            old_hash = None
            for i, (path, file_hash) in enumerate(self.files):
                if path == file_path:
                    file_index = i
                    old_hash = file_hash
                    break
            
            # DEDUPLICATION CHECK
            if is_deleted:
                if file_index < 0:
                    return # Already removed or never tracked
                self.files.pop(file_index)
            elif file_index >= 0:
                # Modification check: Has it actually changed from what we already have?
                if old_hash == h:
                    return # Duplicate event (hash matches current memory state)
                self.files[file_index] = (file_path, h)
            else:
                # Creation
                self.files.append((file_path, h))
            
            # Rebuild tree logic
            self.tree, self.files = build_merkle_tree(self.files)
            path_info = get_merkle_path(self.tree, self.files, file_path)
            
            # Create event data
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
            
            # Queue the event
            self.state.enqueue_event(event_data)
            self.log_to_gui(
                f"Queued: {event_data['event_type']} - {file_path}", 
                "info"
            )
            self.gui_queue.put({
                'type': 'pending', 
                'count': self.state.get_queue_size()
            })
            
            # Try to process queue in background
            threading.Thread(target=self.process_event_queue, daemon=True).start()
    
    def send_heartbeat(self):
        """Send heartbeat to server"""
        if not self.connection_mgr.connected:
            return False
        
        try:
            # IMPORTANT: Send the LAST VALID hash the server and client both agreed on.
            # Sending the current local tree root hash (which may be unvalidated)
            # would update the server's record prematurely and break attestation 
            # for any pending events in the queue.
            root_hash = self.state.get_last_valid_hash()
            
            response = requests.post(
                f"{self.config.server_url}/api/clients/heartbeat",
                headers={'Authorization': f'Bearer {self.config.daemon_token}'},
                json={
                    'file_count': len(self.files),
                    'current_root_hash': root_hash
                },
                timeout=5
            )
            
            if response.status_code == 200:
                self.log_to_gui(
                    f"✓ Heartbeat (files: {len(self.files)}, pending: {self.state.get_queue_size()})", 
                    "success"
                )
                return True
            elif response.status_code == 401:
                data = response.json()
                if "not registered" in data.get('error', '').lower():
                    self.gui_queue.put({'type': 'removal_detected'})
                self.state.clear_jwt()
                self.connection_mgr.mark_disconnected()
        except Exception as e:
            self.log_to_gui(f"⚠ Heartbeat failed: {str(e)}", "warning")
            self.connection_mgr.mark_disconnected()
        
        return False
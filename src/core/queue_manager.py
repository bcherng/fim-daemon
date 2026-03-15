#!/usr/bin/env python3
"""
Event Queue processing manager
"""
import threading
from datetime import datetime

class EventQueueManager:
    def __init__(self, state, network_client, connection_mgr, log_callback):
        self.state = state
        self.network_client = network_client
        self.connection_mgr = connection_mgr
        self.log_callback = log_callback
        self.processing_queue = False
        self.deregistered = False
        self._last_security_error = 0

    def log_to_gui(self, message, status="info"):
        self.log_callback({
            'type': 'log',
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'status': status
        })

    def start_processing(self):
        threading.Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        if self.processing_queue or not self.connection_mgr.connected or self.deregistered:
            return
            
        import time
        if time.time() - self._last_security_error < 5:
            return
        
        # Prevent race conditions with a simple lock
        if not hasattr(self, '_process_lock'):
            self._process_lock = threading.Lock()
            
        if not self._process_lock.acquire(blocking=False):
            return
            
        self.processing_queue = True
        
        try:
            while self.connection_mgr.connected and not self.deregistered:
                event = self.state.peek_event()
                if not event:
                    break
                
                # Verify local signature (Witness Mode: Log warning but don't skip)
                if not self._verify_local_signature(event):
                    self.log_to_gui(f"⚠ SECURITY ALERT: Local signature verification failed for event {event.get('id')}. Reporting as WITNESS.", "warning")

                result = self.network_client.send_event_to_server(event)
                
                if result['success']:
                    # Update local state if the server actually accepted the integrity
                    if result.get('accepted', True):
                        ack_result = self.network_client.send_acknowledgement(
                            result['event_id'], 
                            result['validation']
                        )
                        if ack_result:
                            self.state.update_last_valid_hash(
                                event['root_hash'],
                                result['validation']
                            )
                        else:
                            self.log_to_gui("⚠ Acknowledgement failed, will retry", "warning")
                            self._last_security_error = time.time() # Backoff on ack failure too
                            self.connection_mgr.mark_disconnected()
                            break
                    else:
                        self.log_to_gui(f"⚠ Integrity Conflict recorded by server: {event.get('file_path', 'N/A')}", "warning")

                    # If it was recorded (even if integrity was rejected), we pop and continue
                    if result.get('recorded', True):
                        self.state.dequeue_event()
                        self.log_callback({'type': 'pending', 'count': self.state.get_queue_size()})
                        # Continue the loop to process the next event
                        continue
                else:
                    if self.network_client.deregistered:
                        self.deregistered = True
                        break
                    
                    if result.get('rejected'):
                        self.log_to_gui(f"Event rejected: {result.get('reason')}", "error")
                        
                        if "Security Error" in result.get('reason', ''):
                            self._last_security_error = time.time()
                            # Do NOT dequeue on security error - we want to retry but with backoff
                            # This prevents spamming when server keys rotate or are mismatched
                            break

                        # Dequeue and continue to allow subsequent events (audit trail)
                        self.state.dequeue_event()
                        self.log_callback({'type': 'pending', 'count': self.state.get_queue_size()})
                        continue
                    else:
                        self.log_to_gui("⚠ Connection lost, will retry", "warning")
                        self.connection_mgr.mark_disconnected()
                        break
        finally:
            self.processing_queue = False
            if hasattr(self, '_process_lock'):
                self._process_lock.release()
            # Race condition check: if a new event was queued while we were exiting, 
            # re-trigger processing to ensure it doesn't stay stuck.
            if self.state.get_queue_size() > 0 and self.connection_mgr.connected and not self.deregistered:
                threading.Thread(target=self.process_queue, daemon=True).start()

    def _verify_local_signature(self, event):
        """Verify the RSA signature of an event using the device's public key"""
        try:
            if not hasattr(self.state, 'device_signer') or not self.state.device_signer:
                return True # Can't verify if no signer
                
            signature = event.get('signature')
            if not signature:
                return False
                
            payload_str = f"{event.get('id')}{event.get('prev_event_hash') or ''}{event.get('last_valid_hash') or ''}{event.get('new_hash') or ''}"
            
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives import hashes
            
            sig_bytes = bytes.fromhex(signature)
            self.state.device_signer.public_key.verify(
                sig_bytes,
                payload_str.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=32
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

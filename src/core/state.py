#!/usr/bin/env python3
"""
Persistent state management for FIM client
"""
import os
import json
import threading
import uuid
import sys
import hashlib
import base64
from datetime import datetime
from pathlib import Path
import logging

try:
    import win32crypt
except ImportError:
    win32crypt = None

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

from core.crypto import DeviceSigner, ServerVerifier


class FIMState:
    """Thread-safe persistent state manager"""
    
    def __init__(self, state_file, logger=None):
        """Initialize state manager and load persistent state from disk"""
        self.logger = logger or logging.getLogger(__name__)
        self.state_file = state_file
        self.lock = threading.RLock()
        self._last_disk_hash = None
        self.state = self._load_state()
        self.boot_id = uuid.uuid4().hex
        state_dir = os.path.dirname(state_file)
        self.device_signer = DeviceSigner(state_dir)
        self.server_verifier = ServerVerifier()
        
        if self.state.get('server_public_key'):
            self.server_verifier.load_public_key(self.state['server_public_key'])
            
        # Perform initial integrity check on existing queue
        self.queue_integrity_valid = self.validate_queue_integrity()
        if not self.queue_integrity_valid:
            self.logger.error("SECURITY ALERT: Local event queue integrity check failed! Queue may be tampered.")
    
    def _load_state(self):
        """Load state from disk or create default"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'rb') as f:
                    data = f.read()
                
                self._last_disk_hash = hashlib.sha256(data).hexdigest()
                
                if data and data[0:1] != b'{':
                    data = self._decrypt(data)
                
                return json.loads(data)
            except Exception as e:
                print(f"Failed to load state: {e}")
        
        return {
            'watch_directory': None,
            'last_valid_hash': None,
            'last_server_validation': None,
            'last_event_id': 0,
            'event_queue': [],
            'is_deregistered': False,
            'server_public_key': None
        }
    
    def save(self):
        """Save state to disk (encrypted)"""
        try:
            with self.lock:
                os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
                json_data = json.dumps(self.state, indent=2).encode('utf-8')
                
                encrypted_data = self._encrypt(json_data)
                
                with open(self.state_file, 'wb') as f:
                    f.write(encrypted_data)
                
                self._last_disk_hash = hashlib.sha256(encrypted_data).hexdigest()
                
                if sys.platform != 'win32':
                    os.chmod(self.state_file, 0o600)
        except Exception as e:
            print(f"Failed to save state: {e}")

    def check_disk_tampering(self):
        """Check if state.json was modified externally"""
        if not self.state_file or not os.path.exists(self.state_file):
            return False
            
        with self.lock:
            try:
                with open(self.state_file, 'rb') as f:
                    raw_data = f.read()
                current_hash = hashlib.sha256(raw_data).hexdigest()
                if self._last_disk_hash and current_hash != self._last_disk_hash:
                    return True
            except:
                pass
        return False

    def _encrypt(self, data):
        """Encrypt data using Windows DPAPI or Linux Fernet"""
        if sys.platform == 'win32' and win32crypt:
            try:
                # Use CRYPTPROTECT_LOCAL_MACHINE (4) so the state can be accessed 
                # by both the LocalSystem service and Admin-level tools.
                return win32crypt.CryptProtectData(data, "FIM State", None, None, None, 4)
            except Exception as e:
                print(f"DPAPI Encryption failed: {e}")
        elif sys.platform != 'win32' and Fernet:
            try:
                f = Fernet(self._get_machine_id_key())
                return f.encrypt(data)
            except Exception as e:
                print(f"Linux Encryption failed: {e}")
        return data

    def _decrypt(self, data):
        """Decrypt data using Windows DPAPI or Linux Fernet"""
        if sys.platform == 'win32' and win32crypt:
            try:
                # CryptUnprotectData(data, entropy, reserved, prompt_struct, flags)
                # We try both local machine and current user contexts to handle transition
                try:
                    # Try with machine context (flag 4) first if it was saved it that way
                    _, decrypted_data = win32crypt.CryptUnprotectData(data, None, None, None, 4)
                except:
                    # Fallback to user context (flag 0) if it was an old save
                    _, decrypted_data = win32crypt.CryptUnprotectData(data, None, None, None, 0)
                return decrypted_data
            except Exception as e:
                print(f"DPAPI Decryption failed: {e}")
        elif sys.platform != 'win32' and Fernet:
            try:
                f = Fernet(self._get_machine_id_key())
                return f.decrypt(data)
            except Exception as e:
                print(f"Linux Decryption failed: {e}")
        return data

    def _get_machine_id_key(self):
        """Derive a unique machine-bound key for Linux"""
        machine_id_paths = ['/etc/machine-id', '/var/lib/dbus/machine-id']
        machine_id = None
        for path in machine_id_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        machine_id = f.read().strip()
                    break
                except:
                    continue
        
        if not machine_id:
            import socket
            machine_id = socket.gethostname()
            
        key_hash = hashlib.sha256(machine_id.encode()).digest()
        return base64.urlsafe_b64encode(key_hash)
    
    def _get_system_config_path(self):
        """Determine path to core system configuration file"""
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
        """Get the monitoring directory from system config with tamper protection"""
        sys_config_path = self._get_system_config_path()
        if os.path.exists(sys_config_path):
            try:
                with open(sys_config_path, 'r') as f:
                    config = json.load(f)
                    
                # Verify tamper protection signature
                provided_signature = config.pop('_signature', None)
                if provided_signature:
                    # Recompute signature
                    config_str = json.dumps(config, sort_keys=True)
                    expected_signature = self._generate_config_signature(config_str)
                    
                    if provided_signature == expected_signature:
                        return config.get('watch_directory')
                    else:
                        print("SECURITY ALERT: system_config.json signature mismatch! Tampering detected.")
                        # Log it to the queue to send to server or display in GUI
                        return None
                else:
                    # Legacy config without signature, or stripped signature
                    print("SECURITY ALERT: system_config.json missing signature! Tampering detected.")
                    return None
                    
            except Exception as e:
                print(f"Error reading system config: {e}")
                return None
        return None

    def _generate_config_signature(self, data_str):
        """Generate a signature for the configuration string using the same logic as AdminDaemon"""
        import hashlib
        import base64
        import sys
        
        # Must match AdminDaemon._get_machine_key() exactly
        def get_machine_key():
            if sys.platform == 'win32':
                import winreg
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                        machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                        return hashlib.sha256(machine_guid.encode()).digest()
                except Exception:
                    pass
            
            machine_id_paths = ['/etc/machine-id', '/var/lib/dbus/machine-id']
            machine_id = None
            for path in machine_id_paths:
                if os.path.exists(path):
                    try:
                        with open(path, 'r') as f:
                            machine_id = f.read().strip()
                        break
                    except:
                        continue
            
            if not machine_id:
                import socket
                machine_id = socket.gethostname()
                
            return hashlib.sha256(machine_id.encode()).digest()

        machine_key = get_machine_key()
        hasher = hashlib.sha256()
        hasher.update(machine_key)
        hasher.update(data_str.encode('utf-8'))
        return base64.b64encode(hasher.digest()).decode('utf-8')
    
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
        with self.lock:
            event['queued_at'] = datetime.now().isoformat()
            
            if event.get('last_valid_hash') is None:
                event['last_valid_hash'] = self.get_last_valid_hash()
 
            # Assign and increment monotonic event ID
            if 'last_event_id' not in self.state:
                self.state['last_event_id'] = 0
                
            if 'id' not in event:
                self.state['last_event_id'] += 1
                event['id'] = self.state['last_event_id']
            elif isinstance(event['id'], str) and '-' in event['id']:
                # If it's a legacy string ID, we still want to track it but maybe convert eventually
                # For now, if no ID is passed, we use the counter.
                pass
 
            # Determine prev_event_hash for the chain
            prev_event_hash = None
            if self.state['event_queue']:
                prev_event_hash = self.state['event_queue'][-1].get('event_hash')
            else:
                prev_event_hash = self.get_last_valid_hash()
                
            event['prev_event_hash'] = prev_event_hash
            
            # Calculate new event_hash
            hasher = hashlib.sha256()
            hasher.update(str(event.get('id', '')).encode())
            hasher.update(str(event.get('prev_event_hash') or '').encode())
            hasher.update(str(event.get('last_valid_hash') or '').encode())
            hasher.update(str(event.get('new_hash') or '').encode())
            event['event_hash'] = hasher.hexdigest()
            
            if hasattr(self, 'device_signer') and self.device_signer:
                payload_str = f"{event.get('id')}{event.get('prev_event_hash') or ''}{event.get('last_valid_hash') or ''}{event.get('new_hash') or ''}"
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

    def validate_queue_integrity(self):
        """Iterate through the event queue and verify signatures and hash chain"""
        with self.lock:
            queue = self.state.get('event_queue', [])
            if not queue:
                return True
                
            prev_hash = self.get_last_valid_hash()
            
            for event in queue:
                # 1. Verify Hash Chain
                if event.get('prev_event_hash') != prev_hash:
                    self.logger.error(f"Queue Error: Hash chain break at event {event.get('id')}")
                    return False
                
                # 2. Recompute and verify event_hash
                hasher = hashlib.sha256()
                hasher.update(str(event.get('id', '')).encode())
                hasher.update(str(event.get('prev_event_hash') or '').encode())
                hasher.update(str(event.get('last_valid_hash') or '').encode())
                hasher.update(str(event.get('new_hash') or '').encode())
                recomputed_hash = hasher.hexdigest()
                
                if recomputed_hash != event.get('event_hash'):
                    self.logger.error(f"Queue Error: Event hash mismatch at event {event.get('id')}")
                    return False
                
                # 3. Verify RSA Signature (if signer available)
                if hasattr(self, 'device_signer') and self.device_signer:
                    payload_str = f"{event.get('id')}{event.get('prev_event_hash') or ''}{event.get('last_valid_hash') or ''}{event.get('new_hash') or ''}"
                    signature = event.get('signature')
                    
                    if not signature:
                        self.logger.error(f"Queue Error: Missing signature at event {event.get('id')}")
                        return False
                        
                    try:
                        from cryptography.hazmat.primitives.asymmetric import padding
                        from cryptography.hazmat.primitives import hashes
                        
                        sig_bytes = bytes.fromhex(signature)
                        self.device_signer.public_key.verify(
                            sig_bytes,
                            payload_str.encode('utf-8'),
                            padding.PSS(
                                mgf=padding.MGF1(hashes.SHA256()),
                                salt_length=32
                            ),
                            hashes.SHA256()
                        )
                    except Exception as e:
                        self.logger.error(f"Queue Error: Signature verification failed at event {event.get('id')}: {e}")
                        return False
                
                prev_hash = event.get('event_hash')
                
            return True
 
    def set_deregistered(self, status):
        """Set the deregistered flag"""
        with self.lock:
            self.state['is_deregistered'] = status
            self.save()
 
    def is_deregistered(self):
        """Check if this machine is deregistered"""
        return self.state.get('is_deregistered', False)

    def set_server_public_key(self, public_key_pem):
        """Update the server's public key and re-initialize verifier"""
        with self.lock:
            self.state['server_public_key'] = public_key_pem
            self.server_verifier.load_public_key(public_key_pem)
            self.save()
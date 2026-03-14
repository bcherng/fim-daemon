#!/usr/bin/env python3
"""
Server connection management with exponential backoff
"""
import time
import requests
import json
from datetime import datetime


class RegistrationClient:
    """Manages server connection with exponential backoff"""
    
    def __init__(self, config, state, log_callback=None, max_backoff=600):
        self.config = config
        self.state = state
        self.log_callback = log_callback
        self.max_backoff = max_backoff
        self.current_backoff = 1
        self.connected = False
        self.last_attempt = 0
        import logging
        self.logger = logging.getLogger(__name__)
    
    def _log(self, msg, status="info"):
        if self.log_callback:
            self.log_callback({
                'type': 'log',
                'timestamp': datetime.now().isoformat(),
                'message': msg,
                'status': status
            })
        print(msg) # Still print for console mode
    
    def get_auth_headers(self):
        """Get authentication headers using device signature"""
        headers = {
            'X-Client-ID': self.config.host_id,
            'X-Timestamp': str(int(time.time()))
        }
        
        if hasattr(self.state, 'device_signer') and self.state.device_signer:
            signature = self.state.device_signer.sign_payload(f"{headers['X-Timestamp']}.{self.config.host_id}")
            if signature:
                headers['X-Signature'] = signature
                
        return headers

    def attempt_connection(self):
        """Attempt to connect to server with exponential backoff"""
        current_time = time.time()
        
        if current_time - self.last_attempt < self.current_backoff:
            return False
        
        self.last_attempt = current_time
        
        if self.verify_registration():
            self.connected = True
            self.current_backoff = 1
            return True
            
        if self.register_client():
            self.connected = True
            self.current_backoff = 1
            return True
        
        self.current_backoff = min(self.current_backoff * 2, self.max_backoff)
        return False
    
    def verify_registration(self):
        """Verify client registration and synchronize server public key"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/clients/verify",
                headers=self.get_auth_headers(),
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                # Verify server signature before trusting content
                if hasattr(self.state, 'server_verifier') and self.state.server_verifier:
                    if not self.state.server_verifier.verify_signature(
                        {k: v for k, v in data.items() if k != 'signature'}, 
                        data.get('signature')
                    ):
                        # If verification fails, it might be due to an outdated key.
                        # We don't update yet, but we log the warning.
                        print("Warning: Received invalid server signature during verification.")
                    
                # Synchronize public key if provided
                if 'server_public_key' in data:
                    self.state.set_server_public_key(data['server_public_key'])
                
                return True
            return False
        except Exception as e:
            self._log(f"Verification failed: {str(e)}", "error")
            return False
    
    def register_client(self):
        """Register with server and get JWT"""
        try:
            public_key = None
            if hasattr(self.state, 'device_signer') and self.state.device_signer:
                public_key = self.state.device_signer.get_public_key_pem()
                
            response = requests.post(
                f"{self.config.server_url}/api/clients/register",
                json={
                    'client_id': self.config.host_id,
                    'hardware_info': getattr(self.config, 'hardware_info', {}),
                    'baseline_id': self.config.baseline_id,
                    'platform': self.config.platform_type,
                    'public_key': public_key
                },
                headers=self.get_auth_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'server_public_key' in data:
                    self.state.set_server_public_key(data['server_public_key'])
                return True
            else:
                try:
                    resp_json = response.json()
                    msg = f"Registration rejected by server ({response.status_code}): {json.dumps(resp_json)}"
                    self._log(msg, "error")
                    self.logger.error(msg)
                except:
                    msg = f"Registration rejected by server ({response.status_code}): {response.text}"
                    self._log(msg, "error")
                    self.logger.error(msg)
        except Exception as e:
            self._log(f"Registration failed: {str(e)}", "error")
            self.logger.error(f"Registration failed: {str(e)}")
        
        return False
    
    def mark_disconnected(self):
        """Mark connection as lost and increase backoff"""
        self.connected = False
        self.current_backoff = min(self.current_backoff * 2, self.max_backoff)
    
    def reset(self):
        """Reset connection state"""
        self.connected = False
        self.current_backoff = 1
        self.last_attempt = 0
#!/usr/bin/env python3
"""
Server connection management with exponential backoff
"""
import time
import requests


class RegistrationClient:
    """Manages server connection with exponential backoff"""
    
    def __init__(self, config, state, max_backoff=600):
        self.config = config
        self.state = state
        self.max_backoff = max_backoff
        self.current_backoff = 1
        self.connected = False
        self.last_attempt = 0
    
    def get_auth_headers(self):
        """Get authentication headers using device signature"""
        headers = {
            'X-Client-ID': self.config.host_id,
            'X-Timestamp': str(int(time.time() * 1000))
        }
        
        if hasattr(self.state, 'device_signer') and self.state.device_signer:
            signature = self.state.device_signer.sign_payload(f"{headers['X-Timestamp']}.{self.config.host_id}")
            if signature:
                headers['X-Signature'] = signature
                
        return headers

    def attempt_connection(self):
        """Attempt to connect to server with exponential backoff"""
        current_time = time.time()
        
        # Check if we should attempt based on backoff
        if current_time - self.last_attempt < self.current_backoff:
            return False
        
        self.last_attempt = current_time
        
        # Try to verify registration with server
        if self.verify_registration():
            self.connected = True
            self.current_backoff = 1
            return True
            
        # Need to register
        if self.register_client():
            self.connected = True
            self.current_backoff = 1
            return True
        
        # Increase backoff on failure
        self.current_backoff = min(self.current_backoff * 2, self.max_backoff)
        return False
        
        # Increase backoff on failure
        self.current_backoff = min(self.current_backoff * 2, self.max_backoff)
        return False
    
    def verify_registration(self):
        """Verify client is registered using device signature"""
        try:
            response = requests.get(
                f"{self.config.server_url}/api/health",
                headers=self.get_auth_headers(),
                timeout=5
            )
            
            # Health is unauthenticated, but we can hit verify or just rely on heartbeat later.
            # Wait, let's actually hit a daemon-authenticated endpoint to prove registration
            response = requests.post(
                f"{self.config.server_url}/api/clients/verify",
                headers=self.get_auth_headers(),
                timeout=5
            )
            return response.status_code == 200
        except:
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
                print("Registration successful with public key.")
                return True
        except Exception as e:
            print(f"Registration failed: {e}")
        
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
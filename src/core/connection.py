#!/usr/bin/env python3
"""
Server connection management with exponential backoff
"""
import time
import requests


class ConnectionManager:
    """Manages server connection with exponential backoff"""
    
    def __init__(self, config, state, max_backoff=600):
        self.config = config
        self.state = state
        self.max_backoff = max_backoff
        self.current_backoff = 1
        self.connected = False
        self.last_attempt = 0
    
    def attempt_connection(self):
        """Attempt to connect to server with exponential backoff"""
        current_time = time.time()
        
        # Check if we should attempt based on backoff
        if current_time - self.last_attempt < self.current_backoff:
            return False
        
        self.last_attempt = current_time
        
        # Try to get JWT from state or register
        token = self.state.get_jwt()
        if token:
            self.config.daemon_token = token
            if self.verify_token():
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
    
    def verify_token(self):
        """Quick token verification"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/clients/verify",
                headers={'Authorization': f'Bearer {self.config.daemon_token}'},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def register_client(self):
        """Register with server and get JWT"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/clients/register",
                json={
                    'client_id': self.config.host_id,
                    'hardware_info': getattr(self.config, 'hardware_info', {}),
                    'baseline_id': self.config.baseline_id,
                    'platform': self.config.platform_type
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.state.set_jwt(data['token'], data['expires_in'])
                self.config.daemon_token = data['token']
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
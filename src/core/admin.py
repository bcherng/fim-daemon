#!/usr/bin/env python3
"""
Admin credential verification and management
"""
import requests
import bcrypt


class AdminVerifier:
    """Handles admin credential verification"""
    
    def __init__(self, config, state):
        self.config = config
        self.state = state
    
    def verify_credentials(self, username, password):
        """Verify admin credentials (local cache or server)"""
        # Try local cache first
        if self.state.verify_admin_credentials(username, password):
            return True
        
        # Fall back to server verification
        return self.verify_with_server(username, password)
    
    def verify_with_server(self, username, password):
        """Verify credentials with server and cache on success"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/auth/verify-admin",
                json={
                    'username': username,
                    'password': password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                # Cache credentials locally
                password_hash = bcrypt.hashpw(
                    password.encode(), 
                    bcrypt.gensalt()
                ).decode()
                self.state.set_admin_credentials(username, password_hash)
                return True
        except Exception as e:
            print(f"Server verification failed: {e}")
        
        return False
    
    def clear_cached_credentials(self):
        """Clear cached admin credentials"""
        self.state.clear_admin_credentials()
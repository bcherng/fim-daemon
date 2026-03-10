#!/usr/bin/env python3
"""
Admin credential verification and management
"""
import requests
import bcrypt


class TokenClient:
    """Handles admin credential verification"""
    
    def __init__(self, config, state):
        self.config = config
        self.state = state
    
    def get_action_token(self, username, password, action):
        """Get a short-lived action token from the server"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/auth/action-token",
                json={
                    'username': username,
                    'password': password,
                    'action': action,
                    'client_id': self.config.host_id
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('token')
            else:
                print(f"Server rejected token request: {response.text}")
                return None
        except Exception as e:
            print(f"Failed to get action token: {e}")
            return None
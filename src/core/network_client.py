#!/usr/bin/env python3
"""
Network Client for communicating with the FIM Server
"""
import requests
from datetime import datetime

class NetworkClient:
    def __init__(self, config, connection_mgr, gui_queue, state):
        """Initialize the network client with configuration and shared state"""
        self.config = config
        self.connection_mgr = connection_mgr
        self.gui_queue = gui_queue
        self.state = state
        self.deregistered = False

    def send_event_to_server(self, event_data):
        """Send event to server and get verification/rejection"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/events/report",
                headers=self.connection_mgr.get_auth_headers(),
                json=event_data,
                timeout=10,
                verify=self.config.server_cert if self.config.server_cert else True
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if not self._verify_server_response(data):
                    return {'success': False, 'rejected': True, 'reason': 'Security Error: Invalid Server Signature'}

                self.connection_mgr.connected = True
                self.connection_mgr.current_backoff = 1
                self.gui_queue.put({'type': 'status', 'connected': True})
                return {
                    'success': True,
                    'event_id': data['event_id'],
                    'validation': data['validation']
                }
            elif response.status_code == 400:
                data = response.json()
                
                if not self._verify_server_response(data):
                     return {'success': False, 'rejected': True, 'reason': 'Security Error: Invalid Server Signature'}

                return {
                    'success': False,
                    'rejected': True,
                    'reason': data.get('error', 'Unknown error')
                }
            elif response.status_code == 403:
                data = response.json()
                if not self._verify_server_response(data):
                    return {'success': False, 'rejected': True, 'reason': 'Security Error: Invalid Server Signature'}
                    
                if data.get('status') == 'deregistered':
                    self.deregistered = True
                    self.gui_queue.put({
                        'type': 'deregistered',
                        'message': data.get('message', 'This machine has been deregistered by the administrator.')
                    })
                    return {'success': False, 'rejected': True, 'reason': 'Client deregistered'}
                
                return {'success': False, 'rejected': True, 'reason': 'Forbidden'}
            elif response.status_code == 401:
                data = response.json()
                if not self._verify_server_response(data):
                     return {'success': False, 'rejected': True, 'reason': 'Security Error: Invalid Server Signature'}

                if "not registered" in data.get('error', '').lower():
                    self.gui_queue.put({'type': 'removal_detected'})
                    return {'success': False, 'rejected': True, 'reason': 'Machine removed from server'}
                return {'success': False, 'rejected': False}
            else:
                try:
                    data = response.json()
                    self._verify_server_response(data)
                    error_msg = data.get('error', response.text)
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
                headers=self.connection_mgr.get_auth_headers(),
                json={
                    'event_id': event_id,
                    'validation_received': validation
                },
                timeout=5,
                verify=self.config.server_cert if self.config.server_cert else True
            )
            if response.status_code == 200:
                data = response.json()
                if not self._verify_server_response(data):
                    return False
                self.connection_mgr.connected = True
                self.connection_mgr.current_backoff = 1
                self.gui_queue.put({'type': 'status', 'connected': True})
                return True
            return False
        except:
            return False

    def send_heartbeat(self, root_hash, file_count, boot_id):
        """Send heartbeat to server"""
        if not self.connection_mgr.connected or self.deregistered:
            return False
        
        try:
            response = requests.post(
                f"{self.config.server_url}/api/clients/heartbeat",
                headers=self.connection_mgr.get_auth_headers(),
                json={
                    'tracked_file_count': file_count,
                    'current_root_hash': root_hash,
                    'boot_id': boot_id,
                    'timestamp': datetime.now().isoformat(),
                    'expected_interval': 900
                },
                timeout=5,
                verify=self.config.server_cert if self.config.server_cert else True
            )
            
            if response.status_code == 200:
                data = response.json()
                if not self._verify_server_response(data):
                    return False
                self.connection_mgr.connected = True
                self.connection_mgr.current_backoff = 1
                self.gui_queue.put({'type': 'status', 'connected': True})
                return True
            elif response.status_code == 403:
                data = response.json()
                self._verify_server_response(data)
                if data.get('status') == 'deregistered':
                    self.deregistered = True
                    self.gui_queue.put({
                        'type': 'deregistered',
                        'message': data.get('message', 'This machine has been deregistered.')
                    })
                    self.connection_mgr.mark_disconnected()
                    return False
            else:
                try:
                    data = response.json()
                    self._verify_server_response(data)
                    error_msg = data.get('error', response.text)
                except:
                    error_msg = response.text
                self.config.logger.error(f"Heartbeat failed with {response.status_code}: {error_msg}")
        except Exception as e:
            self.config.logger.error(f"Heartbeat exception: {e}")
            self.connection_mgr.mark_disconnected()
        
        return False

    def _verify_server_response(self, data):
        """Verify the RSA-PSS signature in a server response"""
        if not self.state or not hasattr(self.state, 'server_verifier'):
            return True
            
        signature = data.get('signature')
        if not signature:
            self.config.logger.warning("Server response missing signature")
            if self.state.state.get('server_public_key'):
                return False
            return True
            
        payload = data.copy()
        payload.pop('signature', None)
        
        if self.state.server_verifier.verify_signature(payload, signature):
            return True
            
        self.config.logger.error("MODIFIED SERVER RESPONSE DETECTED! Signature verification failed.")
        self.gui_queue.put({
            'type': 'status_message', 
            'message': 'SECURITY ALERT: Received invalid server signature!',
            'level': 'error'
        })
        return False

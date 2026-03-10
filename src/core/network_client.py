#!/usr/bin/env python3
"""
Network Client for communicating with the FIM Server
"""
import requests
from datetime import datetime

class NetworkClient:
    def __init__(self, config, connection_mgr, gui_queue):
        self.config = config
        self.connection_mgr = connection_mgr
        self.gui_queue = gui_queue
        self.deregistered = False

    def send_event_to_server(self, event_data):
        """Send event to server and get verification/rejection"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/events/report",
                headers=self.connection_mgr.get_auth_headers(),
                json=event_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.gui_queue.put({'type': 'status', 'connected': True})
                return {
                    'success': True,
                    'event_id': data['event_id'],
                    'validation': data['validation']
                }
            elif response.status_code == 403:
                # Check for deregistration
                data = response.json()
                if data.get('status') == 'deregistered':
                    self.deregistered = True
                    self.gui_queue.put({
                        'type': 'deregistered',
                        'message': data.get('message', 'This machine has been deregistered by the administrator.')
                    })
                    return {'success': False, 'rejected': True, 'reason': 'Client deregistered'}
                
                return {'success': False, 'rejected': True, 'reason': 'Forbidden'}
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
                headers=self.connection_mgr.get_auth_headers(),
                json={
                    'event_id': event_id,
                    'validation_received': validation
                },
                timeout=5
            )
            if response.status_code == 200:
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
                    'file_count': file_count,
                    'current_root_hash': root_hash,
                    'boot_id': boot_id,
                    'timestamp': datetime.now().isoformat(),
                    'expected_interval': 900
                },
                timeout=5
            )
            
            if response.status_code == 200:
                self.gui_queue.put({'type': 'status', 'connected': True})
                return True
            elif response.status_code == 403:
                data = response.json()
                if data.get('status') == 'deregistered':
                    self.deregistered = True
                    self.gui_queue.put({
                        'type': 'deregistered',
                        'message': data.get('message', 'This machine has been deregistered.')
                    })
                    self.connection_mgr.mark_disconnected()
                    return False
            elif response.status_code == 401:
                data = response.json()
                if "not registered" in data.get('error', '').lower():
                    self.gui_queue.put({'type': 'removal_detected'})
                self.connection_mgr.mark_disconnected()
        except Exception as e:
            self.connection_mgr.mark_disconnected()
            raise e
        
        return False

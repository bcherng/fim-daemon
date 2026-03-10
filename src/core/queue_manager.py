#!/usr/bin/env python3
"""
Event Queue processing manager
"""
import threading
from datetime import datetime

class EventQueueManager:
    def __init__(self, state, network_client, connection_mgr, gui_queue):
        self.state = state
        self.network_client = network_client
        self.connection_mgr = connection_mgr
        self.gui_queue = gui_queue
        self.processing_queue = False
        self.deregistered = False

    def log_to_gui(self, message, status="info"):
        self.gui_queue.put({
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
        
        self.processing_queue = True
        
        try:
            while self.connection_mgr.connected and not self.deregistered:
                event = self.state.peek_event()
                if not event:
                    break
                
                result = self.network_client.send_event_to_server(event)
                
                if result['success']:
                    ack_result = self.network_client.send_acknowledgement(
                        result['event_id'], 
                        result['validation']
                    )
                    
                    if ack_result:
                        self.state.update_last_valid_hash(
                            event['root_hash'],
                            result['validation']
                        )
                        self.state.dequeue_event()
                        self.log_to_gui(
                            f"✓ Synced: {event['event_type']} - {event.get('file_path', 'N/A')}", 
                            "success"
                        )
                        self.gui_queue.put({'type': 'pending', 'count': self.state.get_queue_size()})
                    else:
                        self.log_to_gui("⚠ Acknowledgement failed, will retry", "warning")
                        self.connection_mgr.mark_disconnected()
                        break
                else:
                    if self.network_client.deregistered:
                        self.deregistered = True
                        break
                    
                    if result.get('rejected'):
                        self.log_to_gui(f"Event rejected: {result.get('reason')}", "error")
                        # We stop processing the queue because subsequent events will likely fail 
                        # due to hash chaining dependencies.
                        self.state.dequeue_event()
                        break
                    else:
                        self.log_to_gui("⚠ Connection lost, will retry", "warning")
                        self.connection_mgr.mark_disconnected()
                        break
        finally:
            self.processing_queue = False

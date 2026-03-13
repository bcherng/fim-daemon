#!/usr/bin/env python3
"""
Event handler Facade combining Network, Monitor, and Queue Manager
"""
import threading
from core.network_client import NetworkClient
from core.queue_manager import EventQueueManager
from core.file_monitor import FileMonitor


class FIMEventHandler:
    """Facade for the previously monolithic Event Handler"""
    def __init__(self, tree, files, config, state, connection_mgr, gui_queue):
        """Initialize the event handler facade and its sub-components"""
        self.lock = threading.Lock()
        
        self.network_client = NetworkClient(config, connection_mgr, gui_queue, state)
        self.event_queue_mgr = EventQueueManager(state, self.network_client, connection_mgr, gui_queue)
        self.file_monitor = FileMonitor(tree, files, config, state, gui_queue, self.event_queue_mgr, self.lock)

    @property
    def files(self):
        """Expose current files dictionary from file_monitor"""
        return self.file_monitor.files
    
    @property
    def deregistered(self):
        """Aggregate deregistered status across all components"""
        return self.network_client.deregistered or self.event_queue_mgr.deregistered or self.file_monitor.deregistered
        
    @deregistered.setter
    def deregistered(self, value):
        """Propagate deregistered status to all sub-components"""
        self.network_client.deregistered = value
        self.event_queue_mgr.deregistered = value
        self.file_monitor.deregistered = value

    def log_to_gui(self, message, status="info"):
        """Relay status messages to the GUI queue"""
        self.file_monitor.log_to_gui(message, status)

    def process_event_queue(self):
        """Triggers the queue manager to process pending events"""
        self.event_queue_mgr.process_queue()

    def send_event_to_server(self, event_data):
        """Delegate event reporting to the network client"""
        return self.network_client.send_event_to_server(event_data)

    def send_acknowledgement(self, event_id, validation):
        """Delegate server acknowledgement to the network client"""
        return self.network_client.send_acknowledgement(event_id, validation)

    def detect_file_change(self, file_path, is_new=False, is_deleted=False):
        """Trigger the file monitor to process a specific path change"""
        self.file_monitor.detect_change(file_path, is_new, is_deleted)

    def send_heartbeat(self):
        """Retrieve current state and dispatch a server heartbeat"""
        try:
            root_hash = self.file_monitor.state.get_last_valid_hash()
            success = self.network_client.send_heartbeat(
                root_hash, 
                len(self.files), 
                self.file_monitor.state.boot_id
            )
            if success:
                self.log_to_gui(
                    f"✓ Heartbeat (files: {len(self.files)}, pending: {self.file_monitor.state.get_queue_size()})", 
                    "success"
                )
            return success
        except Exception as e:
            self.log_to_gui(f"⚠ Heartbeat failed: {str(e)}", "warning")
            return False
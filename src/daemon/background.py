#!/usr/bin/env python3
"""
Background daemon for file monitoring
"""
import time
import threading
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from core.tree_builder import build_initial_tree
from core.event_handler import FIMEventHandler
from core.utils import ensure_directory


class WatchdogFileHandler(FileSystemEventHandler):
    """Watchdog event handler that delegates to FIMEventHandler"""
    
    def __init__(self, fim_handler):
        self.fim_handler = fim_handler
    
    def on_created(self, event):
        if not event.is_directory:
            self.fim_handler.detect_file_change(event.src_path, is_new=True)
    
    def on_modified(self, event):
        if not event.is_directory:
            self.fim_handler.detect_file_change(event.src_path, is_new=False)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.fim_handler.detect_file_change(event.src_path, is_deleted=True)


def run_daemon_background(config, state, conn_mgr, gui_queue, watch_dir, stop_event=None):
    """Run FIM daemon in background thread"""
    gui_queue.put({
        'type': 'log',
        'timestamp': datetime.now().isoformat(),
        'message': 'FIM daemon starting...',
        'status': 'info'
    })
    
    # Attempt initial connection
    max_attempts = 10
    for attempt in range(max_attempts):
        if conn_mgr.attempt_connection():
            gui_queue.put({'type': 'status', 'connected': True})
            gui_queue.put({
                'type': 'log',
                'timestamp': datetime.now().isoformat(),
                'message': '✓ Connected to server',
                'status': 'success'
            })
            break
        else:
            wait_time = min(conn_mgr.current_backoff, 60)
            gui_queue.put({
                'type': 'log',
                'timestamp': datetime.now().isoformat(),
                'message': f'Connection failed, retrying in {wait_time}s...',
                'status': 'warning'
            })
            time.sleep(wait_time)
    
    
    # Build initial tree
    ensure_directory(watch_dir)
    tree, files = build_initial_tree(watch_dir)
    
    # Create event handler
    event_handler = FIMEventHandler(tree, files, config, state, conn_mgr, gui_queue)
    
    # Create watchdog handler
    watchdog_handler = WatchdogFileHandler(event_handler)
    
    # Start file watching
    observer = Observer()
    observer.schedule(watchdog_handler, watch_dir, recursive=True)
    observer.start()
    
    gui_queue.put({
        'type': 'log',
        'timestamp': datetime.now().isoformat(),
        'message': f'Watching {len(files)} files in {watch_dir}',
        'status': 'success'
    })
    
    # Check for pending events on startup
    pending_count = state.get_queue_size()
    gui_queue.put({'type': 'pending', 'count': pending_count})
    
    if pending_count > 0 and conn_mgr.connected:
        gui_queue.put({
            'type': 'log',
            'timestamp': datetime.now().isoformat(),
            'message': f'Processing {pending_count} pending events...',
            'status': 'info'
        })
        threading.Thread(
            target=event_handler.process_event_queue,
            daemon=True
        ).start()
    
    # Main loop
    heartbeat_interval = 360  # 6 minutes
    last_heartbeat = 0
    
    try:
        while True:
            if stop_event and stop_event.is_set():
                gui_queue.put({
                    'type': 'log',
                    'timestamp': datetime.now().isoformat(),
                    'message': 'Stopping daemon...',
                    'status': 'info'
                })
                break
                
            current_time = time.time()
            
            # Check for deregistration
            if event_handler.deregistered:
                gui_queue.put({
                    'type': 'log',
                    'timestamp': datetime.now().isoformat(),
                    'message': '⚠ Client deregistered by server. Stopping monitoring.',
                    'status': 'error'
                })
                break

            # Reconnection logic
            if not conn_mgr.connected:
                if conn_mgr.attempt_connection():
                    gui_queue.put({'type': 'status', 'connected': True})
                    # Process pending events
                    threading.Thread(
                        target=event_handler.process_event_queue,
                        daemon=True
                    ).start()
            
            # Heartbeat
            if conn_mgr.connected and current_time - last_heartbeat >= heartbeat_interval:
                if event_handler.send_heartbeat():
                    last_heartbeat = current_time
                else:
                    gui_queue.put({'type': 'status', 'connected': False})
            
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
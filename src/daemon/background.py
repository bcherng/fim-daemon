#!/usr/bin/env python3
"""
Background daemon loop for file integrity monitoring.
Accepts a log_callback(msg: dict) instead of a gui_queue so it can run
inside the admin service without depending on tkinter or a thread-safe queue.
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
    """Watchdog event handler that delegates to FIMEventHandler."""

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


def _log(callback, message, status="info", timestamp=None):
    """Helper: invoke log_callback with a standard message dict."""
    callback({
        'type': 'log',
        'timestamp': (timestamp or datetime.now()).isoformat(),
        'message': message,
        'status': status
    })


def run_daemon_background(config, state, conn_mgr, log_callback, watch_dir, stop_event=None):
    """
    Run the FIM monitoring loop.

    Args:
        config       -- platform config object
        state        -- FIMState instance
        conn_mgr     -- RegistrationClient / ConnectionManager
        log_callback -- callable(msg: dict) for all status/log output
        watch_dir    -- directory to monitor
        stop_event   -- threading.Event; set it to request a clean shutdown
    """
    _log(log_callback, 'FIM daemon starting...')

    # Initial connection with exponential backoff
    for attempt in range(10):
        if conn_mgr.attempt_connection():
            log_callback({'type': 'status', 'connected': True})
            _log(log_callback, '✓ Connected to server', 'success')
            break
        else:
            wait_time = min(conn_mgr.current_backoff, 60)
            _log(log_callback, f'Connection failed, retrying in {wait_time}s...', 'warning')
            time.sleep(wait_time)

    # Build initial Merkle tree
    ensure_directory(watch_dir)
    tree, files = build_initial_tree(watch_dir)

    # Set up event handling
    event_handler = FIMEventHandler(tree, files, config, state, conn_mgr, log_callback)
    watchdog_handler = WatchdogFileHandler(event_handler)

    observer = Observer()
    observer.schedule(watchdog_handler, watch_dir, recursive=True)
    observer.start()

    _log(log_callback, f'Watching {len(files)} files in {watch_dir}', 'success')
    log_callback({'type': 'directory', 'directory': watch_dir})

    # Drain any events queued from a previous session
    pending_count = state.get_queue_size()
    log_callback({'type': 'pending', 'count': pending_count})
    if pending_count > 0 and conn_mgr.connected:
        _log(log_callback, f'Processing {pending_count} pending events...', 'info')
        threading.Thread(target=event_handler.process_event_queue, daemon=True).start()

    heartbeat_interval = 360
    pulse_interval = 30
    last_heartbeat = 0
    last_pulse = 0
    tamper_reported = False

    try:
        while True:
            if stop_event and stop_event.is_set():
                _log(log_callback, 'Stopping daemon...', 'info')
                break

            now = time.time()
            
            # ... [skip deregistration and reconnection checks] ...
            
            # Queue Pulse: if events are stuck, re-trigger processing periodically
            if conn_mgr.connected and now - last_pulse >= pulse_interval:
                if state.get_queue_size() > 0:
                    event_handler.process_event_queue()
                last_pulse = now

            # Deregistration check
            if event_handler.deregistered:
                _log(log_callback, '⚠ Client deregistered by server. Stopping monitoring.', 'error')
                log_callback({'type': 'deregistered', 'message': 'Deregistered by server'})
                break

            # Reconnection & queue flush
            if not conn_mgr.connected:
                if conn_mgr.attempt_connection():
                    log_callback({'type': 'status', 'connected': True})
                    threading.Thread(target=event_handler.process_event_queue, daemon=True).start()
                else:
                    log_callback({'type': 'status', 'connected': False})

            # Heartbeat
            if conn_mgr.connected and now - last_heartbeat >= heartbeat_interval:
                event_handler.send_heartbeat()
                last_heartbeat = now

            # Config tamper detection via watch_directory becoming None
            if state.get_watch_directory() is None:
                if not tamper_reported:
                    _log(log_callback,
                         'SECURITY ALERT: system_config.json compromised. '
                         'Maintaining current valid state and syncing with server.',
                         'error')
                    current_hash = state.get_last_valid_hash()
                    state.enqueue_event({
                        'client_id': config.host_id,
                        'event_type': 'config_tampered',
                        'file_path': 'C:/ProgramData/FIMClient/system_config.json',
                        'old_hash': current_hash,
                        'new_hash': current_hash,
                        'root_hash': current_hash,
                        'last_valid_hash': current_hash,
                        'merkle_proof': None,
                        'timestamp': datetime.now().isoformat()
                    })
                    tamper_reported = True
                    if conn_mgr.connected:
                        threading.Thread(target=event_handler.process_event_queue, daemon=True).start()
            else:
                tamper_reported = False

            # Granular sleep (20 × 0.5 s = 10 s) for responsiveness to stop_event
            for _ in range(20):
                if stop_event and stop_event.is_set():
                    break
                time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
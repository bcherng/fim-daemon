#!/usr/bin/env python3
"""
Tamper Demo: Forging events in the encrypted queue.
This script demonstrates how the FIM system detects unauthorized modification of its 
offline event queue, even before it talks to the server.
"""
import os
import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from core.state import FIMState

def main():
    print("--- FIM Security Demo: Queue Tampering ---")
    
    # Locate state file
    base_dir = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
    state_file = os.path.join(base_dir, 'FIMClient', 'state.json')
    
    if not os.path.exists(state_file):
        print(f"ERROR: State file not found at {state_file}")
        print("Please ensure the FIM service has been started at least once.")
        return

    print(f"[*] Loading state from: {state_file}")
    state_mgr = FIMState(state_file)
    
    # 1. Forge an event
    # We bypass state_mgr.enqueue_event() because it would sign the event correctly.
    # Instead, we modify the dictionary directly.
    fake_event = {
        "client_id": state_mgr.state.get('client_id') or "demo-client",
        "id": 9999,
        "event_type": "modified",
        "file_path": "C:/Windows/System32/drivers/etc/hosts",
        "old_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "new_hash": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "timestamp": "2026-03-14T12:00:00Z",
        "prev_event_hash": state_mgr.get_last_valid_hash(), # Keep chain look valid
        "event_hash": "forged_hash_that_wont_match_signature",
        "signature": "FAKED_SIGNATURE_DATA" # This will fail local verification
    }
    
    print("[!] Injecting FORGED event into queue...")
    state_mgr.state['event_queue'].append(fake_event)
    
    # 2. Save the tampered state
    print("[*] Saving tampered state (re-encrypting with DPAPI)...")
    state_mgr.save()
    print("[√] Done. The state.json is now poisoned.")
    
    print("\n--- NEXT STEPS ---")
    print("1. Restart the FIM Admin Service.")
    print("2. Check the logs at C:\\ProgramData\\FIMClient\\logs\\admin_daemon.log")
    print("3. You should see: 'SECURITY ALERT: Local event queue integrity check failed!'")
    print("   Or if the service was already running, the QueueManager will log:")
    print("   '⚠ SECURITY ALERT: Local signature verification failed for event 9999'")

if __name__ == "__main__":
    main()

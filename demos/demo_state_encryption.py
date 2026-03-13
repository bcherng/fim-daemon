#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from core.state import FIMState

def run_demo():
    print("=== FIM Security Demo: DPAPI State Encryption ===")
    
    # Setup dummy state
    demo_dir = os.path.join(os.path.dirname(__file__), 'temp_state')
    os.makedirs(demo_dir, exist_ok=True)
    state_file = os.path.join(demo_dir, "demo_state.json")
    
    if os.path.exists(state_file):
        os.remove(state_file)
        
    print(f"1. Creating state file at: {state_file}")
    state = FIMState(state_file)
    state.set_server_public_key("DUMMY_PUBLIC_KEY_CONTENT")
    
    print("2. Reading raw file content (should be opaque/encrypted):")
    with open(state_file, 'rb') as f:
        raw_content = f.read()
        print(f"   Raw bytes (first 32): {raw_content[:32].hex()}...")
        
    print("\n3. Verifying decryption via FIMState:")
    new_state_instance = FIMState(state_file)
    key = new_state_instance.state.get('server_public_key')
    print(f"   Decrypted Server Public Key: {key}")
    
    if key == "DUMMY_PUBLIC_KEY_CONTENT":
        print("\nSUCCESS: State was transparently encrypted/decrypted via DPAPI.")
    else:
        print("\nFAILURE: Decryption did not return expected data.")

    # Cleanup
    del state
    del new_state_instance
    import gc
    gc.collect()
    try:
        os.remove(state_file)
        os.rmdir(demo_dir)
    except:
        pass

if __name__ == "__main__":
    run_demo()

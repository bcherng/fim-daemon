#!/usr/bin/env python3
import os
import sys
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from core.crypto import DeviceSigner, ServerVerifier

def run_demo():
    print("=== FIM Security Demo: Asymmetric Signature Verification ===")
    
    # 1. Setup Signer
    keys_dir = os.path.join(os.path.dirname(__file__), 'temp_keys')
    os.makedirs(keys_dir, exist_ok=True)
    
    print("1. Initializing DeviceSigner (generating keys if needed)...")
    signer = DeviceSigner(keys_dir)
    
    # 2. Sign a payload
    payload = {
        "event": "file_modified",
        "path": "C:/test.txt",
        "hash": "abcdef123456"
    }
    # Standardize serialization for signing
    payload_string = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    print(f"2. Signing payload: {payload_string}")
    signature = signer.sign_payload(payload_string)
    print(f"   Signature: {signature[:32]}...")
    
    # 3. Verify with ServerVerifier
    print("\n3. Initializing ServerVerifier with Device Public Key...")
    public_key_pem = signer.get_public_key_pem()
    verifier = ServerVerifier()
    # Manually load the public key for this demo
    from cryptography.hazmat.primitives import serialization
    verifier.public_key = serialization.load_pem_public_key(public_key_pem.encode())
    
    print("4. Verifying signature...")
    is_valid = verifier.verify_signature(payload, signature)
    
    if is_valid:
        print("   ✓ SUCCESS: Signature verified successfully.")
    else:
        print("   ✗ FAILURE: Signature verification failed.")
        
    # 4. Tamper Test
    print("\n5. Tamper Test: Modifying payload...")
    payload['event'] = "file_deleted"
    is_valid_tampered = verifier.verify_signature(payload, signature)
    
    if not is_valid_tampered:
        print("   ✓ SUCCESS: Tampered payload correctly rejected.")
    else:
        print("   ✗ FAILURE: Tampered payload was accepted!")

    # Cleanup
    for f in os.listdir(keys_dir):
        os.remove(os.path.join(keys_dir, f))
    os.rmdir(keys_dir)

if __name__ == "__main__":
    run_demo()

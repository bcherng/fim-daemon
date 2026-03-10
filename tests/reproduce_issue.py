import requests
import time
import json
import uuid

SERVER_URL = "http://localhost:3000"
CLIENT_ID = f"repro-client-{uuid.uuid4().hex[:8]}"

def repro():
    print(f"Reproduction for {CLIENT_ID}")
    
    # 1. Register
    print("\n1. Registering...")
    res = requests.post(f"{SERVER_URL}/api/clients/register", json={
        'client_id': CLIENT_ID,
        'hardware_info': {'hostname': 'repro-machine'}
    })
    token = res.json()['token']
    headers = {'Authorization': f'Bearer {token}'}
    
    # 2. Select Directory A (Initial Baseline)
    print("\n2. Selecting Directory A...")
    hash_a_v1 = "hash-a-v1"
    res = requests.post(f"{SERVER_URL}/api/events/report", headers=headers, json={
        'id': 'evt1',
        'event_type': 'directory_selected',
        'file_path': 'C:\\dir_a',
        'root_hash': hash_a_v1,
        'new_hash': hash_a_v1,
        'file_count': 5,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
    })
    event_id = res.json()['event_id']
    requests.post(f"{SERVER_URL}/api/events/acknowledge", headers=headers, json={'event_id': event_id, 'validation_received': True})
    
    # 3. Switch to Directory B
    print("\n3. Switching to Directory B...")
    hash_b = "hash-b"
    # Unselect A
    res = requests.post(f"{SERVER_URL}/api/events/report", headers=headers, json={
        'id': 'evt2',
        'event_type': 'directory_unselected',
        'file_path': 'C:\\dir_a',
        'last_valid_hash': hash_a_v1,
        'root_hash': hash_a_v1,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
    })
    # Select B
    res = requests.post(f"{SERVER_URL}/api/events/report", headers=headers, json={
        'id': 'evt3',
        'event_type': 'directory_selected',
        'file_path': 'C:\\dir_b',
        'root_hash': hash_b,
        'new_hash': hash_b,
        'file_count': 3,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
    })
    event_id = res.json()['event_id']
    requests.post(f"{SERVER_URL}/api/events/acknowledge", headers=headers, json={'event_id': event_id, 'validation_received': True})

    # 4. Switch BACK to Directory A (but it has changed!)
    print("\n4. Switching BACK to Directory A (modified)...")
    hash_a_v2 = "hash-a-v2-modified"
    # Unselect B
    res = requests.post(f"{SERVER_URL}/api/events/report", headers=headers, json={
        'id': 'evt4',
        'event_type': 'directory_unselected',
        'file_path': 'C:\\dir_b',
        'last_valid_hash': hash_b,
        'root_hash': hash_b,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
    })
    
    # Select A (v2)
    # The user says "server correctly identifies an attestation error"
    # Let's see if this call fails
    res = requests.post(f"{SERVER_URL}/api/events/report", headers=headers, json={
        'id': 'evt5',
        'event_type': 'directory_selected',
        'file_path': 'C:\\dir_a',
        'root_hash': hash_a_v2,
        'new_hash': hash_a_v2,
        'last_valid_hash': hash_b, # Daemon sends what it thinks is the global last valid hash
        'file_count': 5,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
    })
    
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}")

    # 5. Check Dashboard Logic (Events table)
    print("\n5. Checking events for attestation_failed...")
    # Login as admin to check events
    admin_res = requests.post(f"{SERVER_URL}/api/auth/login", json={'username': 'admin', 'password': 'password123'})
    admin_headers = {'Authorization': f"Bearer {admin_res.json()['token']}"}
    
    events_res = requests.get(f"{SERVER_URL}/api/events/client/{CLIENT_ID}", headers=admin_headers)
    events = events_res.json()['events']
    
    attestation_events = [e for e in events if e['event_type'] == 'attestation_failed']
    print(f"Found {len(attestation_events)} attestation_failed events.")
    for e in attestation_events:
        print(f" - {e['file_path']}: {e['old_hash']} -> {e['new_hash']}")

if __name__ == "__main__":
    repro()

import requests
import time
import json
import uuid

SERVER_URL = "http://localhost:3000"
CLIENT_ID = f"test-client-{uuid.uuid4().hex[:8]}"

def test_interaction():
    print(f"Testing interaction with {SERVER_URL} for client {CLIENT_ID}")
    
    # 1. Register Client
    print("\n1. Registering client...")
    reg_data = {
        'client_id': CLIENT_ID,
        'hardware_info': {'hostname': 'test-machine', 'machine_id': 'test-uuid'},
        'baseline_id': 1,
        'platform': 'windows'
    }
    res = requests.post(f"{SERVER_URL}/api/clients/register", json=reg_data)
    if res.status_code != 200:
        print(f"FAILED: Registration returned {res.status_code}")
        print(res.text)
        return
    
    data = res.json()
    token = data['token']
    print(f"SUCCESS: Registered. Token: {token[:20]}...")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    # 2. Verify Token
    print("\n2. Verifying token...")
    res = requests.post(f"{SERVER_URL}/api/clients/verify", headers=headers)
    if res.status_code == 200:
        print("SUCCESS: Token verified.")
    else:
        print(f"FAILED: Token verification returned {res.status_code}")
    
    # 3. Heartbeat
    print("\n3. Sending heartbeat...")
    heartbeat_data = {
        'file_count': 10,
        'current_root_hash': 'initial-root-hash'
    }
    res = requests.post(f"{SERVER_URL}/api/clients/heartbeat", headers=headers, json=heartbeat_data)
    if res.status_code == 200:
        print("SUCCESS: Heartbeat accepted.")
    else:
        print(f"FAILED: Heartbeat returned {res.status_code}")
        
    # 4. Save Baseline
    print("\n4. Saving baseline...")
    baseline_data = {
        'root_hash': 'initial-root-hash',
        'file_count': 10
    }
    res = requests.post(f"{SERVER_URL}/api/clients/baseline", headers=headers, json=baseline_data)
    if res.status_code == 200:
        print("SUCCESS: Baseline saved.")
    else:
        print(f"FAILED: Baseline returned {res.status_code}")

    # 5. Report Event (Handshake)
    print("\n5. Reporting event (Handshake protocol)...")
    event_data = {
        'event_type': 'modified',
        'file_path': 'C:\\test\\file.txt',
        'old_hash': 'old-hash',
        'new_hash': 'new-hash',
        'root_hash': 'new-root-hash',
        'last_valid_hash': 'initial-root-hash',
        'merkle_proof': {'path': [], 'index': 0},
        'timestamp': '2026-01-16T12:00:00Z'
    }
    res = requests.post(f"{SERVER_URL}/api/events/report", headers=headers, json=event_data)
    if res.status_code == 200:
        data = res.json()
        event_id = data.get('event_id')
        print(f"SUCCESS: Event verified. Event ID: {event_id}")
        
        # Acknowledge
        print("   Acknowledging event...")
        ack_data = {'event_id': event_id, 'validation_received': True}
        res = requests.post(f"{SERVER_URL}/api/events/acknowledge", headers=headers, json=ack_data)
        if res.status_code == 200:
            print("   SUCCESS: Handshake complete.")
        else:
            print(f"   FAILED: Acknowledgement returned {res.status_code}")
    else:
        # If it returns 400 because of root hash mismatch in mock DB, that's "fine" for endpoint test
        print(f"FAILED or REJECTED: Report returned {res.status_code}")
        print(res.text)

    # 6. Admin Login and Status Verification
    print("\n6. Admin login and status verification...")
    admin_data = {
        'username': 'admin',
        'password': 'password123'
    }
    res = requests.post(f"{SERVER_URL}/api/auth/login", json=admin_data)
    if res.status_code == 200:
        admin_session = res.json()['token']
        admin_headers = {'Authorization': f'Bearer {admin_session}'}
        print("SUCCESS: Admin logged in.")
        
        # Check Client Status
        print("   Checking client status indicators...")
        res = requests.get(f"{SERVER_URL}/api/clients", headers=admin_headers)
        if res.status_code == 200:
            data = res.json()
            clients = data.get('clients', [])
            print(f"   Total clients on server: {len(clients)}")
            client = next((c for c in clients if c['client_id'] == CLIENT_ID), None)
            if client:
                print(f"   Indicators: Integrity={client.get('integrity_change_count')}, Attestation={'Valid' if client.get('attestation_valid') else 'Invalid'}, Missed Heartbeats={client.get('missed_heartbeat_count')}")
            else:
                print("   FAILED: Client not found in list.")
        else:
            print(f"   FAILED: Client list returned {res.status_code}")
            print(res.text)
        
        # 7. Review Client
        print("\n7. Reviewing client...")
        res = requests.post(f"{SERVER_URL}/api/clients/{CLIENT_ID}/review", headers=admin_headers)
        if res.status_code == 200:
            print("   SUCCESS: Client reviewed.")
            # Verify reset
            res = requests.get(f"{SERVER_URL}/api/clients", headers=admin_headers)
            if res.status_code == 200:
                client = next((c for c in res.json().get('clients', []) if c['client_id'] == CLIENT_ID), None)
                if client:
                    print(f"   Post-review Indicators: Integrity={client.get('integrity_change_count')}, Attestation={'Valid' if client.get('attestation_valid') else 'Invalid'}, Missed Heartbeats={client.get('missed_heartbeat_count')}")
                else:
                    print("   FAILED: Client not found after review.")
            else:
                print(f"   FAILED: Post-review list returned {res.status_code}")
        else:
            print(f"   FAILED: Review returned {res.status_code}")
            print(res.text)
    else:
        print(f"FAILED: Admin login returned {res.status_code}")

if __name__ == "__main__":
    test_interaction()

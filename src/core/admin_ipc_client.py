#!/usr/bin/env python3
"""
IPC Client for communicating with the Admin Daemon
"""
import sys
import json
import socket
from multiprocessing.connection import Client

def get_ipc_address():
    if sys.platform == 'win32':
        return r'\\.\pipe\fim_admin_ipc'
    else:
        return '/var/run/fim_admin.sock'

def send_admin_request(action, token, payload=None, timeout=5.0):
    """
    Send an action request to the admin daemon and wait for the response.
    Returns: {"success": bool, "error": str, ...}
    """
    address = get_ipc_address()
    
    try:
        # Use sockets directly to allow robust timeout handling
        if sys.platform == 'win32':
            # multiprocessing.connection on Windows uses named pipes
            conn = Client(address)
        else:
            # Unix socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(address)
            conn = sock

        request_data = {
            "action": action,
            "token": token,
            "payload": payload or {}
        }
        
        if sys.platform == 'win32':
            conn.send(request_data)
            if conn.poll(timeout):
                response = conn.recv()
            else:
                response = {"success": False, "error": "IPC timeout"}
            conn.close()
        else:
            sock.sendall((json.dumps(request_data) + '\n').encode('utf-8'))
            response_bytes = sock.recv(4096)
            sock.close()
            if not response_bytes:
                response = {"success": False, "error": "Empty response"}
            else:
                response = json.loads(response_bytes.decode('utf-8'))
                
        return response
        
    except FileNotFoundError:
        return {"success": False, "error": "Admin daemon is not running (IPC pipe not found). [BUILD_REF_V3]"}
    except ConnectionRefusedError:
        return {"success": False, "error": "Admin daemon connection refused."}
    except Exception as e:
        import traceback
        return {"success": False, "error": f"IPC connection error: {str(e)}", "traceback": traceback.format_exc()}


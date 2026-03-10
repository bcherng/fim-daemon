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
        request_data = {
            "action": action,
            "token": token,
            "payload": payload or {}
        }

        if sys.platform == 'win32':
            # On Windows we use win32pipe.CallNamedPipe for a clean request-response
            # This avoids multiprocessing.connection's socket-related errors on Windows
            import win32pipe
            import win32file
            
            try:
                # CallNamedPipe connects, writes, reads, and closes in one go
                response_bytes = win32pipe.CallNamedPipe(
                    address,
                    json.dumps(request_data).encode('utf-8'),
                    65536,
                    int(timeout * 1000)
                )
                
                if not response_bytes:
                    return {"success": False, "error": "Empty response from admin daemon"}
                
                return json.loads(response_bytes.decode('utf-8'))
            except Exception as pipe_err:
                # Check for common pipe errors
                error_str = str(pipe_err)
                if "2" in error_str:
                    return {"success": False, "error": "Admin daemon is not running (pipe not found). [BUILD_REF_V7]"}
                elif "5" in error_str:
                    return {"success": False, "error": "Access denied to admin pipe. [BUILD_REF_V7]"}
                raise
        else:
            # Unix socket (Linux)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(address)
            
            sock.sendall((json.dumps(request_data) + '\n').encode('utf-8'))
            response_bytes = sock.recv(4096)
            sock.close()
            
            if not response_bytes:
                return {"success": False, "error": "Empty response from admin daemon"}
            
            return json.loads(response_bytes.decode('utf-8'))
        
    except FileNotFoundError:
        return {"success": False, "error": "Admin daemon is not running (IPC pipe not found). [BUILD_REF_V7]"}
    except ConnectionRefusedError:
        return {"success": False, "error": "Admin daemon connection refused."}
    except Exception as e:
        import traceback
        return {"success": False, "error": f"IPC connection error: {str(e)}", "traceback": traceback.format_exc()}

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


def subscribe_to_logs(callback, stop_event=None):
    """
    Open a persistent connection to the admin daemon log broadcast channel.

    Reads newline-delimited JSON messages in a background thread and calls
    callback(msg: dict) for each one.  Automatically reconnects on disconnect
    (up to once per 3 seconds) until stop_event is set.

    Args:
        callback   -- callable(msg: dict) — usually queues into the GUI's queue
        stop_event -- threading.Event; set it to stop the subscriber thread
    """
    import threading
    import time

    address = get_ipc_address()
    subscribe_request = json.dumps({"action": "subscribe", "token": None, "payload": {}}).encode('utf-8')

    def _reader():
        while stop_event is None or not stop_event.is_set():
            try:
                if sys.platform == 'win32':
                    import win32pipe, win32file
                    # Open a fresh pipe instance for the long-lived subscribe connection
                    handle = win32file.CreateFile(
                        address,
                        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                        0, None,
                        win32file.OPEN_EXISTING,
                        0, None
                    )
                    # Switch to message-read mode
                    win32pipe.SetNamedPipeHandleState(
                        handle,
                        win32pipe.PIPE_READMODE_MESSAGE,
                        None, None
                    )
                    win32file.WriteFile(handle, subscribe_request)
                    # Read loop
                    buf = b''
                    while stop_event is None or not stop_event.is_set():
                        try:
                            _, data = win32file.ReadFile(handle, 65536)
                            buf += data
                            while b'\n' in buf:
                                line, buf = buf.split(b'\n', 1)
                                line = line.strip()
                                if line:
                                    try:
                                        callback(json.loads(line))
                                    except Exception:
                                        pass
                        except Exception:
                            break
                    try:
                        win32file.CloseHandle(handle)
                    except Exception:
                        pass
                else:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(address)
                    sock.sendall(subscribe_request + b'\n')
                    buf = b''
                    while stop_event is None or not stop_event.is_set():
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                        while b'\n' in buf:
                            line, buf = buf.split(b'\n', 1)
                            line = line.strip()
                            if line:
                                try:
                                    callback(json.loads(line))
                                except Exception:
                                    pass
                    sock.close()
            except Exception:
                pass
            # Reconnect pause
            time.sleep(3)

    t = threading.Thread(target=_reader, daemon=True, name='FIMLogSubscriber')
    t.start()
    return t

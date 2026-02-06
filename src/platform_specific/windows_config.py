#!/usr/bin/env python3
"""
Windows-specific configuration and hardware identification
"""
import os
import sys
import subprocess
import hashlib
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from core.config import FIMConfig
from core.utils import ensure_directory


class WindowsHardwareIdentifier:
    """Windows hardware identification"""
    
    def __init__(self):
        self.client_id = self.get_hardware_id()
        self.client_info = self.get_hardware_info()
    
    def get_hardware_id(self):
        """Generate client ID from hardware characteristics"""
        hardware_data = []
        
        # Try to get MachineGuid from registry
        try:
            result = subprocess.run(
                ['reg', 'query', 
                 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography',
                 '/v', 'MachineGuid'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if 'MachineGuid' in line:
                        guid = line.split()[-1]
                        hardware_data.append(f"guid:{guid}")
        except:
            pass
        
        # Get MAC address as fallback
        mac = hex(uuid.getnode())[2:]
        hardware_data.append(f"mac:{mac}")
        
        # Get system UUID
        try:
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'uuid'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    system_uuid = lines[1].strip()
                    if system_uuid and system_uuid != 'UUID':
                        hardware_data.append(f"uuid:{system_uuid}")
        except:
            pass
        
        if hardware_data:
            hardware_data.sort()
            hardware_hash = hashlib.sha256('|'.join(hardware_data).encode()).hexdigest()[:16]
            return f"windows-{hardware_hash}"
        else:
            return "windows-unknown"
    
    def get_hardware_info(self):
        """Collect hardware information for reporting"""
        import platform
        
        info = {
            'platform': 'windows',
            'hostname': platform.node(),
            'processor': platform.processor(),
            'machine': platform.machine()
        }
        
        # Try to get UUID
        try:
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'uuid'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    info['uuid'] = lines[1].strip()
        except:
            pass
        
        return info


class WindowsFIMConfig(FIMConfig):
    """Windows-specific FIM configuration"""
    
    def __init__(self):
        super().__init__(
            platform_type="windows",
            watch_dir=None,  # Set by user
            pid_file=os.path.expandvars(r'%TEMP%\fim-client.pid')
        )
        
        self.hardware_id = WindowsHardwareIdentifier()
        self.host_id = self.hardware_id.client_id
        self.hardware_info = self.hardware_id.client_info
        
        # Setup logging
        log_dir = os.path.expandvars(r'%APPDATA%\FIMClient\logs')
        ensure_directory(log_dir)
        log_file = os.path.join(log_dir, 'fim-client.log')
        self.setup_logging(log_file)
        
        # Register with server (will be called by connection manager)
        # self.register_with_server(self.host_id, self.hardware_info)
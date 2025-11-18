#!/usr/bin/env python3
import sys
import os
import platform
import subprocess

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

from fim import FIMConfig, FIMDaemon
from utils import ensure_directory

class WindowsHardwareIdentifier:
    def __init__(self):
        self.client_id = self.get_hardware_id()
        self.client_info = self.get_hardware_info()
    
    def _get_windows_wmi(self, class_name, property_name):
        """Get WMI property using PowerShell"""
        try:
            cmd = f"Get-WmiObject -Class {class_name} | Select-Object -ExpandProperty {property_name}"
            result = subprocess.run([
                "powershell", "-Command", cmd
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        return None
    
    def get_hardware_id(self):
        """Generate client ID from hardware characteristics"""
        import hashlib
        hardware_data = []
        
        board_serial = self._get_windows_wmi("Win32_BaseBoard", "SerialNumber")
        if board_serial:
            hardware_data.append(f"board:{board_serial}")
        
        bios_serial = self._get_windows_wmi("Win32_BIOS", "SerialNumber")
        if bios_serial:
            hardware_data.append(f"bios:{bios_serial}")
        
        cpu_id = self._get_windows_wmi("Win32_Processor", "ProcessorId")
        if cpu_id:
            hardware_data.append(f"cpu:{cpu_id}")
        
        if hardware_data:
            hardware_data.sort()
            hardware_hash = hashlib.sha256('|'.join(hardware_data).encode()).hexdigest()[:16]
            return f"windows-{hardware_hash}"
        else:
            hostname = platform.node()
            return f"windows-{hostname}"
    
    def get_hardware_info(self):
        """Collect hardware information for reporting"""
        return {
            'hostname': platform.node(),
            'platform': 'windows',
            'board_serial': self._get_windows_wmi("Win32_BaseBoard", "SerialNumber"),
            'bios_serial': self._get_windows_wmi("Win32_BIOS", "SerialNumber"),
            'cpu_id': self._get_windows_wmi("Win32_Processor", "ProcessorId")
        }

class WindowsFIMConfig(FIMConfig):
    def __init__(self):
        super().__init__(
            platform_type="windows", 
            watch_dir=r"C:\ProgramData\FIM-Daemon\watch-folder"
        )
        
        self.hardware_id = WindowsHardwareIdentifier()
        self.host_id = self.hardware_id.client_id
        
        # Setup Windows-specific logging
        log_dir = ensure_directory(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))
        log_file = os.path.join(log_dir, 'fim-daemon.log')
        self.setup_logging(log_file)
        
        # Register with server
        self.register_with_server(self.host_id, self.hardware_id.client_info)

class WindowsFIMDaemon(FIMDaemon):
    def __init__(self):
        config = WindowsFIMConfig()
        super().__init__(config)

    def run(self):
        # Use the common daemon logic from base class
        super().run_daemon()

if __name__ == "__main__":
    daemon = WindowsFIMDaemon()
    daemon.run()
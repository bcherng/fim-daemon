#!/usr/bin/env python3
import sys
import os
import signal

# Add the core module to path
sys.path.insert(0, '/usr/share/fim-daemon/core')

from fim import FIMConfig, FIMDaemon
from utils import ensure_directory

class LinuxHardwareIdentifier:
    def __init__(self):
        self.client_id = self.get_hardware_id()
        self.client_info = self.get_hardware_info()
    
    def _read_file(self, path):
        """Read file content if it exists"""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    content = f.read().strip()
                    return content if content else None
        except:
            pass
        return None
    
    def get_hardware_id(self):
        """Generate client ID from hardware characteristics"""
        import hashlib
        hardware_data = []
        
        machine_id = self._read_file('/etc/machine-id') or self._read_file('/var/lib/dbus/machine-id')
        if machine_id:
            hardware_data.append(f"machine:{machine_id}")
        
        cpu_info = self._get_cpu_info()
        if cpu_info:
            hardware_data.append(f"cpu:{cpu_info}")
        
        serial = self._get_system_serial()
        if serial:
            hardware_data.append(f"serial:{serial}")
        
        if hardware_data:
            hardware_data.sort()
            hardware_hash = hashlib.sha256('|'.join(hardware_data).encode()).hexdigest()[:16]
            return f"linux-{hardware_hash}"
        else:
            return "linux-unknown"
    
    def _get_cpu_info(self):
        """Extract CPU identifier"""
        import hashlib
        try:
            cpuinfo = self._read_file('/proc/cpuinfo')
            if cpuinfo:
                for line in cpuinfo.split('\n'):
                    if line.startswith('vendor_id') or line.startswith('model name'):
                        key, value = line.split(':', 1)
                        return hashlib.sha256(value.strip().encode()).hexdigest()[:8]
        except:
            pass
        return None
    
    def _get_system_serial(self):
        """Get system serial number"""
        serial_sources = [
            '/sys/class/dmi/id/product_uuid',
            '/sys/class/dmi/id/product_serial', 
            '/sys/class/dmi/id/board_serial'
        ]
        
        for source in serial_sources:
            serial = self._read_file(source)
            if serial and serial != 'None' and len(serial) > 4:
                return serial
        return None
    
    def get_hardware_info(self):
        """Collect hardware information for reporting"""
        return {
            'machine_id': self._read_file('/etc/machine-id'),
            'product_uuid': self._read_file('/sys/class/dmi/id/product_uuid'),
            'platform': 'linux'
        }


class LinuxFIMConfig(FIMConfig):
    def __init__(self):
        super().__init__(
            platform_type="linux", 
            watch_dir="/var/lib/fim-daemon/watch-folder",
            pid_file="/var/run/fim-daemon/fim-daemon.pid"
        )
        
        self.hardware_id = LinuxHardwareIdentifier()
        self.host_id = self.hardware_id.client_id
        
        # Setup Linux-specific logging
        ensure_directory("/var/log/fim-daemon")
        log_file = '/var/log/fim-daemon/fim-daemon.log'
        self.setup_logging(log_file)
        
        # Register with server
        self.register_with_server(self.host_id, self.hardware_id.client_info)

class LinuxFIMDaemon(FIMDaemon):
    def __init__(self):
        config = LinuxFIMConfig()
        super().__init__(config)
        self.running = False

    def signal_handler(self, signum, frame):
        self.config.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run(self):
        # Setup Linux signal handling
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Write PID file
        ensure_directory(os.path.dirname(self.config.pid_file))
        with open(self.config.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # Use the common daemon logic from base class
        super().run_daemon()
        
        # Remove PID file on exit
        if os.path.exists(self.config.pid_file):
            os.remove(self.config.pid_file)

if __name__ == "__main__":
    daemon = LinuxFIMDaemon()
    daemon.run()
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
#!/usr/bin/env python3
import sys
import os
import signal

# Add the core module to path
sys.path.insert(0, '/usr/share/fim-daemon/core')

from fim import FIMConfig, FIMDaemon
from utils import ensure_directory

class LinuxHardwareIdentifier:
    # ... your existing Linux hardware identification code ...
    pass

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
#!/usr/bin/env python3
"""
Base configuration class for FIM daemon
"""
import logging
import sys

SERVER_URL = "https://fim-distribution.vercel.app"


class FIMConfig:
    """Base configuration for FIM daemon"""
    
    def __init__(self, platform_type, watch_dir=None, pid_file=None):
        self.platform_type = platform_type
        self.host_id = None  # To be set by platform-specific code
        self.baseline_id = 1
        self.server_url = SERVER_URL
        self.watch_dir = watch_dir
        self.pid_file = pid_file
        self.daemon_token = None
        self.token_expires = 0
        
    def setup_logging(self, log_file):
        """Setup logging with provided log file path"""
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - {self.host_id} - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"FIM {self.platform_type} client initialized with hardware ID: {self.host_id}")

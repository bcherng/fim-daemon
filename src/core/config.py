#!/usr/bin/env python3
"""
Base configuration class for FIM daemon
"""

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

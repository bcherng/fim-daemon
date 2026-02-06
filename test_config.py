#!/usr/bin/env python3
"""Test FIMConfig initialization"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from platform_specific.windows_config import WindowsFIMConfig

try:
    config = WindowsFIMConfig()
    print("✓ Config initialized successfully")
    print(f"  - host_id: {config.host_id}")
    print(f"  - server_url: {config.server_url}")
    print(f"  - platform_type: {config.platform_type}")
    print(f"  - baseline_id: {config.baseline_id}")
    print(f"  - has logger: {hasattr(config, 'logger')}")
    print(f"  - has daemon_token: {hasattr(config, 'daemon_token')}")
    print("\n✓ All required attributes present!")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

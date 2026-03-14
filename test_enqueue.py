import os
import sys
from datetime import datetime


print("Sys path:", sys.path)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from core.state import FIMState
from platform_specific.windows_config import WindowsFIMConfig

config = WindowsFIMConfig()
state = FIMState('./test_state.json')

directory = 'C:/Users/brian/OneDrive/Documents/7402/a1'
new_root_hash = 'test_hash'
file_count = 5
old_hash = None

print("Calling enqueue_event")
try:
    state.enqueue_event({
        'client_id': config.host_id,
        'event_type': 'directory_selected',
        'file_path': directory,
        'old_hash': new_root_hash,
        'new_hash': new_root_hash,
        'root_hash': new_root_hash,
        'last_valid_hash': old_hash,
        'merkle_proof': None,
        'tracked_file_count': file_count,
        'timestamp': datetime.now().isoformat()
    })
    print("Success")
except Exception as e:
    import traceback
    print("Error:", traceback.format_exc())

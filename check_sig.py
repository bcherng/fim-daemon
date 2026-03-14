import os, sys, json, base64

def get_machine_key():
    import hashlib
    if sys.platform == 'win32':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                return hashlib.sha256(machine_guid.encode()).digest()
        except:
            pass
    import socket
    machine_id = socket.gethostname()
    return hashlib.sha256(machine_id.encode()).digest()

sys_config_path = r'C:\ProgramData\FIMClient\system_config.json'
with open(sys_config_path, 'r') as f:
    config = json.load(f)

provided_signature = config.pop('_signature', None)
config_str = json.dumps(config, sort_keys=True)
import hashlib
machine_key = get_machine_key()
hasher = hashlib.sha256()
hasher.update(machine_key)
hasher.update(config_str.encode('utf-8'))
expected_signature = base64.b64encode(hasher.digest()).decode('utf-8')

print("Config String:", repr(config_str))
print("Provided Sig :", provided_signature)
print("Expected Sig :", expected_signature)
print("Keys Match   :", provided_signature == expected_signature)
print("Machine Key  :", machine_key.hex())


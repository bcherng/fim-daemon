import sys, winreg, hashlib, socket

def get_machine_key():
    if sys.platform == 'win32':
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                print("Got MachineGuid from registry:", machine_guid)
                return hashlib.sha256(machine_guid.encode()).digest()
        except Exception as e:
            print("Failed to get MachineGuid:", type(e).__name__, str(e))
            pass
    
    machine_id = socket.gethostname()
    print("Fell back to hostname:", machine_id)
    return hashlib.sha256(machine_id.encode()).digest()

get_machine_key()

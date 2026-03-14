#!/usr/bin/env python3
"""
Live Attack Simulator for FIM GUI Demo
Usage: python live_attack_sim.py <monitoring_directory>
"""

import sys
import os
import time
import json
import hashlib
import subprocess
import shutil

# Add src directories to path so we can import FIM modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from core.state import FIMState

DAEMON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'daemon', 'admin_daemon.py')
CLIENT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fim_client.py')

FIM_SCRIPTS = ('fim_client.py', 'admin_daemon.py')


# ──────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────

def print_step(title, desc):
    print(f"\n[{time.strftime('%H:%M:%S')}] 🔴 ATTACK: {title}")
    print(f"   -> {desc}")


def fim_processes_running():
    """Return True if the FIMAdmin service OR the fim_client GUI is currently running."""
    if sys.platform == 'win32':
        # Check 1: FIMAdmin Windows Service (production mode)
        try:
            result = subprocess.run(
                ['sc', 'query', 'FIMAdmin'],
                capture_output=True, text=True, timeout=5
            )
            if 'RUNNING' in result.stdout:
                return True
        except Exception:
            pass

        # Check 2: fim_client.py or admin_daemon.py as plain Python processes (dev mode)
        try:
            ps_cmd = (
                "Get-WmiObject Win32_Process "
                "| Where-Object { $_.Name -eq 'python.exe' -and ("
                "$_.CommandLine -like '*fim_client.py*' "
                "-or $_.CommandLine -like '*admin_daemon.py*') } "
                "| Measure-Object | Select-Object -ExpandProperty Count"
            )
            result = subprocess.run(
                ['powershell', '-NonInteractive', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            count_str = result.stdout.strip()
            if count_str.isdigit() and int(count_str) > 0:
                return True
        except Exception:
            pass

        return False
    else:
        try:
            result = subprocess.run(['pgrep', '-f', '|'.join(FIM_SCRIPTS)], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False


def wait_for_fim_live(timeout=60):
    """Block until at least one FIM process is detected, or timeout."""
    print("   ⏳ Waiting for FIM processes to come online...", end='', flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fim_processes_running():
            print(" ✓ Live!")
            return True
        print('.', end='', flush=True)
        time.sleep(1)
    print(" ✗ Timed out.")
    return False


def wait_for_fim_dead(timeout=30):
    """Block until all FIM processes have exited, or timeout."""
    print("   ⏳ Waiting for FIM processes to fully exit...", end='', flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not fim_processes_running():
            print(" ✓ Offline!")
            return True
        print('.', end='', flush=True)
        time.sleep(1)
    print(" ✗ Timed out.")
    return False


def kill_fim():
    """Stop the FIMAdmin service (if running) and terminate any plain Python FIM processes."""
    if sys.platform == 'win32':
        # Stop SCM service if installed
        subprocess.run(['sc', 'stop', 'FIMAdmin'], capture_output=True)

        # Also kill any plain Python fim processes (dev mode fallback)
        try:
            result = subprocess.run(
                ['wmic', 'process', 'where', "name='python.exe'", 'get', 'ProcessId,CommandLine'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if any(s in line for s in FIM_SCRIPTS):
                    parts = line.strip().rsplit(None, 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        subprocess.run(['taskkill', '/F', '/PID', parts[1]], capture_output=True)
        except Exception:
            pass
        subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq FIM Client*"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "fim_client.py"], capture_output=True)
        subprocess.run(["pkill", "-f", "admin_daemon.py"], capture_output=True)


def launch_fim():
    """Launch admin daemon and GUI client in new console windows."""
    if sys.platform == 'win32':
        subprocess.Popen([sys.executable, DAEMON_PATH, "run"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        subprocess.Popen([sys.executable, CLIENT_PATH], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([sys.executable, DAEMON_PATH, "run"])
        subprocess.Popen([sys.executable, CLIENT_PATH])


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python live_attack_sim.py <monitoring_directory>")
        print("Example: python live_attack_sim.py C:/Users/Admin/Documents/SecureDocs")
        sys.exit(1)

    watch_dir = sys.argv[1]
    if not os.path.exists(watch_dir):
        print(f"Error: Directory '{watch_dir}' does not exist.")
        sys.exit(1)

    state_file = (os.path.expandvars(r'%APPDATA%\FIMClient\state.json')
                  if sys.platform == 'win32'
                  else os.path.expanduser("~/.fim-client/state.json"))
    sys_config_path = r'C:\ProgramData\FIMClient\system_config.json'

    print("══════════════════════════════════════════════════")
    print("      FIM LIVE DEMO — ATTACK SIMULATION           ")
    print("══════════════════════════════════════════════════")
    print(f"  Target : {watch_dir}")
    print()

    # ─── PART 1 SETUP ────────────────────────────────────
    print("▶ PART 1: Launching FIM stack and waiting for server connection...")
    print("   (single-instance locks prevent duplicate processes if already running)")
    launch_fim()
    wait_for_fim_live(timeout=90)

    print("\n  Focus the FIM Client GUI window now to capture Part 1 on screen.")
    input("  Press ENTER when ready to begin the attack sequence...")

    # ─── ATTACK 1: Malware Drop ───────────────────────────
    rogue_file = os.path.join(watch_dir, "svchost_backdoor.exe")
    print_step(
        "Malware Dropper [1/7]",
        f"Writing rogue executable to monitored directory → FIM detects file creation in real-time."
    )
    with open(rogue_file, "wb") as f:
        f.write(b"MZ\x90\x00[SIMULATED PE PAYLOAD]")

    # ─── ATTACK 2: File Modification ─────────────────────
    print_step(
        "Payload Mutation [2/7]",
        "Appending a secondary stage to the dropped binary → FIM detects the content change."
    )
    with open(rogue_file, "a") as f:
        f.write("\n[STAGE 2 SHELLCODE APPENDED — evading static hash checks]")

    # ─── ATTACK 3: Covering Tracks ────────────────────────
    print_step(
        "Evidence Destruction [3/7]",
        "Deleting the payload to erase physical traces → FIM still logs the deletion event."
    )
    if os.path.exists(rogue_file):
        os.remove(rogue_file)

    # ─── ATTACK 4: Config Tampering ──────────────────────
    print_step(
        "Config Hijacking [4/7]",
        "Directly overwriting system_config.json to redirect FIM monitoring away from the target directory.\n"
        "   -> The Admin Daemon signature check will catch this immediately without a restart."
    )
    if os.path.exists(sys_config_path):
        try:
            with open(sys_config_path, 'r') as f:
                config_raw = f.read()
                config = json.loads(config_raw)
            # Back up the valid config before poisoning it
            with open(sys_config_path + '.bak', 'w') as f:
                f.write(config_raw)
            config['watch_directory'] = 'C:/Windows/Temp'
            with open(sys_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print("   -> Config rewritten: watch_directory → C:/Windows/Temp")
            print("   -> FIM GUI will flag a config_tampered event within seconds!")
        except PermissionError:
            print("   -> ✗ Permission denied — run this script as Administrator to demonstrate config tampering.")
        except Exception as e:
            print(f"   -> ✗ Failed: {e}")
    else:
        print(f"   -> ✗ Not found: {sys_config_path}")

    # ─── PART 2 SETUP ────────────────────────────────────
    print("\n══════════════════════════════════════════════════")
    print("▶ PART 2: Offline Cryptographic Tampering")
    print("══════════════════════════════════════════════════")
    print("  With the FIM stack online, disk-level state is integrity-checked in memory.")
    print("  A sophisticated attacker takes the agent OFFLINE before tampering with the")
    print("  encrypted state file on disk — bypassing any in-memory defenses.")
    print()
    print("  🔴 Terminating FIM GUI and Admin Daemon...")
    kill_fim()
    wait_for_fim_dead(timeout=30)

    # Restore valid config so the daemon re-attaches to the correct directory on restart
    if os.path.exists(sys_config_path + '.bak'):
        print_step(
            "Config Restoration [pre-Attack 5]",
            "Silently restoring a valid system_config.json so FIM re-attaches to the target\n"
            "   -> directory on restart — making the cryptographic attacks harder to notice."
        )
        shutil.move(sys_config_path + '.bak', sys_config_path)

    # Seed the queue with mock history if it drained while online
    if os.path.exists(state_file):
        try:
            temp_state = FIMState(state_file)
            temp_state.state.setdefault('event_queue', [])
            if len(temp_state.state['event_queue']) == 0:
                for i in range(5):
                    temp_state.state['event_queue'].append({
                        'type': 'file_created', 'file_path': f'sensitive_doc_{i}.pdf', 'idx': i
                    })
                temp_state.save()
                print("\n   [Staging 5 historical events in local queue for the purge demo]")
        except Exception:
            pass

    # ─── ATTACK 5: Queue Deletion + Hash Anchor Poison ────
    print_step(
        "Queue Wipe + Chain Corruption [5/7]",
        "Decrypting state.json directly on disk. Purging all pending server-bound events\n"
        "   -> AND poisoning the last_valid_hash anchor to break forward chain verification."
    )
    if os.path.exists(state_file):
        try:
            hacked_state = FIMState(state_file)
            q_size = len(hacked_state.state.get('event_queue', []))
            print(f"   -> Decrypted DPAPI state. Found {q_size} queued event(s).")
            print("   -> PURGING all pending events (history the server will never see)...")
            hacked_state.state['event_queue'] = []
            corrupted_anchor = 'ATTACKER_INJECTED_' + hashlib.sha256(b'attacker_key').hexdigest()
            hacked_state.state['last_valid_hash'] = corrupted_anchor
            hacked_state.save()
            print(f"   -> Queue cleared. Hash anchor overwritten: {corrupted_anchor[:40]}...")
            print("   -> When the daemon restarts, every new event will chain from this fake anchor.")
            print("   -> The server will detect the mismatch and log a chain_conflict!")
        except Exception as e:
            print(f"   -> ✗ Failed: {e}")
    else:
        print(f"   -> ✗ State file not found: {state_file}")

    # ─── ATTACK 6: Fake Event Injection ───────────────────
    print_step(
        "Cryptographic Forgery [6/7]",
        "Crafting and injecting a fake file_modified event directly into the DPAPI-encrypted\n"
        "   -> queue — bypassing all network-layer protections. The forged event carries an\n"
        "   -> invalid RSA-PSS signature and a fabricated hash chain."
    )
    if os.path.exists(state_file):
        try:
            hacked_state = FIMState(state_file)
            fake_event = {
                'id': hacked_state.state.get('last_event_id', 0) + 1,
                'client_id': 'attacker_implant',
                'event_type': 'file_modified',
                'file_path': 'C:/Windows/System32/drivers/etc/hosts',
                'old_hash': hashlib.sha256(b'real_hosts').hexdigest(),
                'new_hash': hashlib.sha256(b'poisoned_hosts').hexdigest(),
                'root_hash': 'FORGED_MERKLE_ROOT',
                'last_valid_hash': hacked_state.state.get('last_valid_hash', 'none'),
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'signature': 'FORGED_RSA_PSS_SIGNATURE — NOT_VERIFIABLE_BY_SERVER'
            }
            hasher = hashlib.sha256()
            hasher.update(str(fake_event['id']).encode())
            hasher.update(b'forged_prev_hash')
            hasher.update(fake_event['last_valid_hash'].encode())
            hasher.update(fake_event['new_hash'].encode())
            fake_event['event_hash'] = hasher.hexdigest()
            hacked_state.state.setdefault('event_queue', []).append(fake_event)
            hacked_state.save()
            print("   -> Forged event written into encrypted queue!")
            print(f"     file: {fake_event['file_path']}")
            print(f"     sig : {fake_event['signature'][:55]}...")
            print("   -> Server will reject both the forged signature and the broken chain.")
        except Exception as e:
            print(f"   -> ✗ Failed: {e}")
    else:
        print(f"   -> ✗ State file not found: {state_file}")

    # ─── ATTACK 7: Append-Only Violation ──────────────────
    print_step(
        "Append-Only Violation [7/7]",
        "Inserting a persistence implant event then immediately popping it — demonstrating\n"
        "   -> that an attacker can rewrite local history. The forged event from Attack 6\n"
        "   -> remains, ensuring the server hash chain is definitively broken."
    )
    if os.path.exists(state_file):
        try:
            hacked_state = FIMState(state_file)
            queue = hacked_state.state.get('event_queue', [])
            decoy = {
                'id': hacked_state.state.get('last_event_id', 0) + 2,
                'event_type': 'file_created',
                'file_path': 'C:/Users/brian/AppData/Roaming/malware_persistence.dll',
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            }
            queue.append(decoy)
            print(f"   -> Inserted 'malware_persistence.dll' into queue ({len(queue)} total).")
            popped = queue.pop()
            hacked_state.state['event_queue'] = queue
            hacked_state.save()
            print(f"   -> Popped '{popped['file_path']}' — history erased from local log.")
            print(f"   -> Queue now has {len(queue)} event(s). Forged event from #6 is still in place.")
            print("   -> Append-only guarantee violated: the server hash chain will detect the gap.")
        except Exception as e:
            print(f"   -> ✗ Failed: {e}")
    else:
        print(f"   -> ✗ State file not found: {state_file}")

    # ─── PART 3 ───────────────────────────────────────────
    print("\n══════════════════════════════════════════════════")
    print("▶ PART 3: Server-Side Integrity Detection")
    print("══════════════════════════════════════════════════")
    print("  Relaunching FIM stack. The daemon will load the poisoned state.json from disk,")
    print("  then submit the queued forged event with the broken hash anchor to the server.")
    print("  The server's rolling chain verification will immediately detect the mismatch")
    print("  and log a chain_conflict event — catching all offline tampering in one shot.")
    print()
    launch_fim()
    wait_for_fim_live(timeout=90)

    # Give the daemon a moment to connect and process the queued forged event
    time.sleep(3)

    print_step(
        "Sync Trigger [post-attack]",
        "Creating a canary file to flush any remaining queue state to the server."
    )
    trigger = os.path.join(watch_dir, "trigger_sync.txt")
    with open(trigger, "w") as f:
        f.write(f"Sync triggered at {time.strftime('%H:%M:%S')}")

    print("\n══════════════════════════════════════════════════")
    print("  SIMULATION COMPLETE")
    print("  Check the FIM Dashboard for chain_conflict events!")
    print("══════════════════════════════════════════════════")


if __name__ == "__main__":
    main()

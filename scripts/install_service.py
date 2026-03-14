#!/usr/bin/env python3
"""
FIM Admin Service Installer
Registers admin_daemon.py as a Windows SCM service (FIMAdmin) with
automatic restart on failure, then removes the daemon path from the
raw-subprocess lifecycle in fim_client.py.

Run as Administrator:
    python scripts/install_service.py         # install + start
    python scripts/install_service.py remove  # stop + remove
"""
import os
import sys
import subprocess
import argparse

SCRIPT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAEMON_SCRIPT = os.path.join(SCRIPT_DIR, 'src', 'daemon', 'admin_daemon.py')
SERVICE_NAME  = 'FIMAdmin'


def run(cmd, check=True):
    """Run a command, printing it first."""
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print(f"    {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"    {result.stderr.strip()}")
    if check and result.returncode not in (0, 1060):  # 1060 = service does not exist (OK on remove)
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    return result


def install():
    if sys.platform != 'win32':
        print("ERROR: Windows SCM service installation is only supported on Windows.")
        print("For Linux, create a systemd unit file instead (see README).")
        sys.exit(1)

    print(f"\n{'='*55}")
    print("  FIMAdmin Windows Service Installer")
    print(f"{'='*55}")
    print(f"  Script : {DAEMON_SCRIPT}")
    print(f"  Python : {sys.executable}")

    if not os.path.exists(DAEMON_SCRIPT):
        print(f"  ERROR: Daemon script not found at: {DAEMON_SCRIPT}")
        sys.exit(1)

    # 1. Register the service via pywin32 service utils
    print("\n[1/4] Registering FIMAdmin service with SCM...")
    run([sys.executable, DAEMON_SCRIPT, '--startup', 'auto', 'install'])

    # 2. Configure failure recovery: restart within 3s on first/second failure,
    #    5s on subsequent failures, reset the failure count after 1 hour.
    print("\n[2/4] Configuring auto-restart on failure...")
    run([
        'sc', 'failure', SERVICE_NAME,
        'reset=', '3600',
        'actions=', 'restart/3000/restart/5000/restart/10000'
    ])

    # 3. Lock down stop permissions: only Administrators can stop the service.
    #    SDDL grants SERVICE_ALL_ACCESS to Administrators (BA) and SYSTEM (SY),
    #    but denies SERVICE_STOP to standard users.
    print("\n[3/4] Restricting service stop permissions to Administrators...")
    sddl = (
        "D:(A;;CCLCSWRPWPDTLOCRSDRCWDWO;;;SY)"   # SYSTEM: full access
        "(A;;CCLCSWRPWPDTLOCRSDRCWDWO;;;BA)"       # Administrators: full access
        "(A;;CCLCSWLOCRRC;;;IU)"                   # Interactive Users: query/start only
    )
    run(['sc', 'sdset', SERVICE_NAME, sddl])

    # 4. Start the service immediately
    print("\n[4/4] Starting FIMAdmin service...")
    run([sys.executable, DAEMON_SCRIPT, 'start'])

    print(f"\n{'='*55}")
    print("  ✓  FIMAdmin service installed and running!")
    print("     The SCM will automatically restart it on failure.")
    print(f"{'='*55}\n")


def remove():
    if sys.platform != 'win32':
        print("ERROR: Only applicable on Windows.")
        sys.exit(1)

    print(f"\n[1/2] Stopping FIMAdmin service...")
    run([sys.executable, DAEMON_SCRIPT, 'stop'], check=False)

    print(f"[2/2] Removing FIMAdmin service from SCM...")
    run([sys.executable, DAEMON_SCRIPT, 'remove'])

    print("\n✓  FIMAdmin service removed.\n")


def main():
    parser = argparse.ArgumentParser(description='FIM Admin Service Installer')
    parser.add_argument('action', nargs='?', default='install',
                        choices=['install', 'remove'],
                        help='install (default) or remove the service')
    args = parser.parse_args()

    if args.action == 'remove':
        remove()
    else:
        install()


if __name__ == '__main__':
    main()

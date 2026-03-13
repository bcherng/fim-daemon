# FIM-Daemon v1.1.0

Cross-platform File Integrity Monitoring (FIM) Client. Real-time monitoring daemons for Windows and Linux with **Hardware-bound Asymmetric Signing**.

## About The Project

This project is a Distributed File Integrity Monitoring (FIM) System designed to detect, track, and respond to file changes in real time. The Milestone 4 release (v1.1.0) introduces significant security upgrades, transforming the system into a production-ready platform.

The daemon watches for file changes using system libraries (Watchdog) and computes SHA-256 cryptographic hashes. These are structured in a Merkle tree to summarize the directory state. All communications are now authenticated via **Dual Asymmetric RSA Signing**, ensuring that every heartbeat and event report is tamper-proof and verified by the server.

Client-side state is protected using **Data-at-Rest Encryption**:
- **Windows**: Uses DPAPI (`win32crypt`) to bind state to the user/machine.
- **Linux**: Uses machine-bound encryption derived from `/etc/machine-id` with the Fernet cipher.

## Features

*   **Asymmetric Message Signing**: RSA-2048 with PSS padding for all event/heartbeat reports.
*   **Data-at-Rest Encryption**: Sensitive state (public keys, hash chains) is encrypted locally (DPAPI/Fernet).
*   **Real-time file monitoring**: via Watchdog and efficient Merkle Tree updates.
*   **Certificate Pinning**: Hardened SSL verification in `NetworkClient`.
*   **Cross-Platform**: Full support for Windows and Linux environments.

## Built With

*   Python 3.12
*   Cryptography (hazmat primitives)
*   PyWin32 (Windows specific)

## Installation

1.  Download latest installers via Github Release, or through the [FIM Dashboard](https://fim-distribution.vercel.app/).
2.  **Windows**: Run the `.exe` installer.
3.  **Linux**: Install the debian package: `sudo dpkg -i fim-daemon-v1.1.0_amd64.deb`.

## Usage
The daemon registers as a persistent service. Once running, it monitors the selected directory and uploads signed hash chains to the server. Administrators can monitor status and review logs via the [web dashboard](https://fim-distribution.vercel.app/).

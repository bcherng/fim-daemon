# FIM-Daemon

Persistent real-time monitoring daemons for Windows and Linux.

## About The Project

A more detailed description. What problem does it solve? What was your motivation?

## Features

*   Real-time file monitoring via Watchdog
*   Efficienct Merkle Tree implementation to reduce hashing time
*   One-stop Windows In/unstaller with InnoSetup

## Built With

*   [Language/Framework] Python

## Installation

1.  Download latest installers via Github Release, or through https://fim-distribution.vercel.app/
2.  Run the Windows .exe installer and follow the prompt - or install the debian package via sudo dpkg -r fim-daemon-v{version}_amd64.deb


## Usage
The daemon will register as a persistent service and monitor the selected directory in real-time and upload hash and timestamp upon file change detection.

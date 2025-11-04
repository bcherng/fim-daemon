[Setup]
AppName=File Integrity Monitor Daemon
AppVersion=1.0
AppPublisher=Brian Cherng (bcherng@github)
DefaultDirName={commonpf}\FIM-Daemon
DefaultGroupName=File Integrity Monitor
OutputDir=Output
OutputBaseFilename=FIM-Daemon-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; All files are in the same directory as the ISS file
Source: "fim_daemon_windows.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_dependencies.bat"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\install_dependencies.bat"; Flags: runhidden waituntilterminated; StatusMsg: "Installing dependencies..."
Filename: "{app}\nssm.exe"; Parameters: "install FIM-Daemon python ""{app}\fim_daemon_windows.py"""; Flags: runhidden waituntilterminated; StatusMsg: "Installing service..."
Filename: "{app}\nssm.exe"; Parameters: "set FIM-Daemon Description ""File Integrity Monitoring Service"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set FIM-Daemon AppDirectory ""{app}"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set FIM-Daemon Start SERVICE_AUTO_START"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "start FIM-Daemon"; Flags: runhidden waituntilterminated; StatusMsg: "Starting service..."

[UninstallRun]
Filename: "{app}\nssm.exe"; Parameters: "stop FIM-Daemon"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "remove FIM-Daemon confirm"; Flags: runhidden waituntilterminated
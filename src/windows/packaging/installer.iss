[Setup]
AppName=File Integrity Monitor Daemon
AppVersion={#Version}
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
Source: "dist\fim-daemon.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "nssm\win64\nssm.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "scripts\install.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "scripts\uninstall.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\install.ps1"""; Flags: runhidden; StatusMsg: "Installing FIM Daemon service..."

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\uninstall.ps1"""; Flags: runhidden; RunOnceId: "UninstallService"
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
; Use absolute paths to eliminate path resolution issues
Source: "D:\a\fim-daemon\fim-daemon\src\windows\packaging\dist\fim-daemon.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\a\fim-daemon\fim-daemon\src\windows\packaging\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\a\fim-daemon\fim-daemon\src\windows\packaging\install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\a\fim-daemon\fim-daemon\src\windows\packaging\uninstall.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\install.ps1"""; Flags: runhidden waituntilterminated; StatusMsg: "Installing FIM Daemon service..."

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\uninstall.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "UninstallService"

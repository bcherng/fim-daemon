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

[InstallDelete]
; Delete any existing files before installation
Type: filesandordirs; Name: "{app}"

[Files]
; Force overwrite all files
Source: "dist\fim-daemon.exe"; DestDir: "{app}"; Flags: ignoreversion overwritereadonly uninsremovereadonly
Source: "nssm.exe"; DestDir: "{app}"; Flags: ignoreversion overwritereadonly uninsremovereadonly
Source: "install.ps1"; DestDir: "{app}"; Flags: ignoreversion overwritereadonly uninsremovereadonly
Source: "uninstall.ps1"; DestDir: "{app}"; Flags: ignoreversion overwritereadonly uninsremovereadonly

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\install.ps1"""; Flags: runhidden waituntilterminated; StatusMsg: "Installing FIM Daemon service..."

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\uninstall.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "UninstallService"
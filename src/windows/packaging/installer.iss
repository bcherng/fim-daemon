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
AlwaysRestart=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Use "ignoreversion dontcopy" to force file copy regardless of existing files
Source: "dist\fim-daemon.exe"; DestDir: "{app}"; Flags: ignoreversion dontcopy
Source: "nssm.exe"; DestDir: "{app}"; Flags: ignoreversion dontcopy
Source: "install.ps1"; DestDir: "{app}"; Flags: ignoreversion dontcopy
Source: "uninstall.ps1"; DestDir: "{app}"; Flags: ignoreversion dontcopy

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\install.ps1"""; Flags: runhidden waituntilterminated; StatusMsg: "Installing FIM Daemon service..."

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\uninstall.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "UninstallService"

[Code]
function InitializeSetup(): Boolean;
begin
  // Force remove any existing installation directory
  DelTree(ExpandConstant('{app}'), True, True, True);
  Result := True;
end;
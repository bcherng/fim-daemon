; =========================================
; FIM-Daemon Inno Setup Installer
; =========================================
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
Source: "nssm.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "install.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "uninstall.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

; We remove [Run] and replace with AfterInstall in [Files] + [Code]

; Run install.ps1 after files are copied
[Files]
; Re-add install.ps1 with AfterInstall hook
Source: "install.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion; AfterInstall: RunInstallScript

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\uninstall.ps1"""; Flags: runhidden; RunOnceId: "UninstallService"

[Code]
procedure RunInstallScript();
var
  ResultCode: Integer;
begin
  if not Exec('powershell.exe',
              '-ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\scripts\install.ps1') + '"',
              ExpandConstant('{app}'),
              SW_HIDE,
              ewWaitUntilTerminated,
              ResultCode) then
  begin
    MsgBox('Failed to run install.ps1. Exit code: ' + IntToStr(ResultCode), mbError, MB_OK);
  end;
end;

[Setup]
AppName=File Integrity Monitor Daemon
AppVersion=1.0
AppPublisher=bcherng
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
Source: "fim_daemon_windows.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion

[Run]
; Install the service using NSSM
Filename: "{app}\nssm.exe"; Parameters: "install FIM-Daemon python ""{app}\fim-daemon-windows.py"""; Flags: runhidden waituntilterminated; StatusMsg: "Installing FIM Daemon service..."
Filename: "{app}\nssm.exe"; Parameters: "set FIM-Daemon Description ""File Integrity Monitoring Service"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set FIM-Daemon AppStdout ""{app}\fim-daemon.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set FIM-Daemon AppStderr ""{app}\fim-daemon-error.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set FIM-Daemon Start SERVICE_AUTO_START"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "start FIM-Daemon"; Flags: runhidden waituntilterminated; StatusMsg: "Starting FIM Daemon service..."

[UninstallRun]
; Stop and remove service during uninstall
Filename: "{app}\nssm.exe"; Parameters: "stop FIM-Daemon"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "remove FIM-Daemon confirm"; Flags: runhidden waituntilterminated

[Code]
// Custom page to select watch directory
var
  WatchDirPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  // Create custom page for watch directory selection
  WatchDirPage := CreateInputDirPage(
    wpSelectDir,
    'Select Watch Directory',
    'Choose the directory to monitor for file integrity',
    'Please select the directory that the File Integrity Monitor should watch for changes.' + #13#10#13#10 +
    'This directory will be monitored for file creations, modifications, and deletions.',
    False,
    ''
  );
  
  WatchDirPage.Add('Watch Directory:');
  WatchDirPage.Values[0] := ExpandConstant('{userdocs}\fim-daemon\watch-folder');
end;

function UpdateConfigFile: Boolean;
var
  ConfigFile: string;
  ConfigContent: string;
  WatchDir: string;
begin
  WatchDir := WatchDirPage.Values[0];
  ConfigFile := ExpandConstant('{app}\config.ini');
  
  // Create config file with selected directory
  ConfigContent := '[Settings]' + #13#10 +
                   'WATCH_DIR=' + WatchDir + #13#10 +
                   'HOST_ID=win01' + #13#10 +
                   'BASELINE_ID=1' + #13#10;
  
  Result := SaveStringToFile(ConfigFile, ConfigContent, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    UpdateConfigFile;
  end;
end;
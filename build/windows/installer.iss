; FIM Client Installer Script for Inno Setup
#define MyAppName "FIM Client"
#define MyAppPublisher "bcherng"
#define MyAppURL "https://github.com/bcherng/fim-daemon"
#define MyAppExeName "FIMClient.exe"
#define MyAppVersion "0.2.22"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
AppId={FIM-CLIENT-99E7-4562-AB89-1234567890AB}
AppName={#MyAppName}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=Output
OutputBaseFilename=FIMClient-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "startupicon"; Description: "Launch FIM Client at Windows startup"; GroupDescription: "Additional tasks:"; Flags: unchecked

[Files]
Source: "..\..\dist\FIMClient\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ServerURLPage: TInputQueryWizardPage;
  ConnectionSuccessful: Boolean;

// Custom page for server URL
procedure InitializeWizard;
begin
  ServerURLPage := CreateInputQueryPage(wpSelectDir,
    'Server Configuration', 'Enter FIM Server URL',
    'Please enter the URL of your FIM server. The installer will attempt to connect before proceeding.');
  
  ServerURLPage.Add('Server URL:', False);
  ServerURLPage.Values[0] := 'https://fim-distribution.vercel.app';
  
  ConnectionSuccessful := False;
end;

// Function to test server connection
function TestServerConnection(ServerURL: String): Boolean;
var
  WinHttpReq: Variant;
  StatusCode: Integer;
begin
  Result := False;
  try
    WinHttpReq := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    WinHttpReq.Open('GET', ServerURL + '/api/health', False);
    WinHttpReq.SetTimeouts(5000, 5000, 10000, 10000);
    WinHttpReq.Send;
    StatusCode := WinHttpReq.Status;
    
    if (StatusCode = 200) or (StatusCode = 404) then
      Result := True;
  except
    Result := False;
  end;
end;

// Validate server URL page
function NextButtonClick(CurPageID: Integer): Boolean;
var
  ServerURL: String;
  RetryCount: Integer;
  WaitTime: Integer;
begin
  Result := True;
  
  if CurPageID = ServerURLPage.ID then
  begin
    ServerURL := Trim(ServerURLPage.Values[0]);
    
    if ServerURL = '' then
    begin
      MsgBox('Please enter a server URL.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    
    // Test connection with exponential backoff
    RetryCount := 0;
    WaitTime := 1000;
    
    while (RetryCount < 5) and (not ConnectionSuccessful) do
    begin
      WizardForm.StatusLabel.Caption := Format('Connecting to server... (Attempt %d/5)', [RetryCount + 1]);
      WizardForm.ProgressGauge.Style := npbstMarquee;
      
      ConnectionSuccessful := TestServerConnection(ServerURL);
      
      if ConnectionSuccessful then
      begin
        MsgBox('Successfully connected to the server!', mbInformation, MB_OK);
        Break;
      end
      else
      begin
        RetryCount := RetryCount + 1;
        if RetryCount < 5 then
        begin
          if MsgBox(Format('Failed to connect to server. Wait %d seconds and retry? (Attempt %d/5)', [WaitTime div 1000, RetryCount]), mbConfirmation, MB_YESNO) = IDYES then
          begin
            Sleep(WaitTime);
            WaitTime := WaitTime * 2;
            if WaitTime > 60000 then
              WaitTime := 60000;
          end
          else
          begin
            Result := False;
            Exit;
          end;
        end;
      end;
    end;
    
    WizardForm.ProgressGauge.Style := npbstNormal;
    
    if not ConnectionSuccessful then
    begin
      if MsgBox('Could not connect to server after 5 attempts. Continue anyway? (Not recommended)', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end;
    
    // Save server URL to registry for the application to use
    RegWriteStringValue(HKEY_CURRENT_USER, 'Software\FIMClient', 'ServerURL', ServerURL);
  end;
end;

// Post-install: Create state directory and initial config
procedure CurStepChanged(CurStep: TSetupStep);
var
  StateDir: String;
  ConfigFile: String;
  ServerURL: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Create state directory
    StateDir := ExpandConstant('{userappdata}\FIMClient');
    if not DirExists(StateDir) then
      CreateDir(StateDir);
    
    // Get server URL from registry
    if RegQueryStringValue(HKEY_CURRENT_USER, 'Software\FIMClient', 'ServerURL', ServerURL) then
    begin
      ConfigFile := StateDir + '\config.json';
      SaveStringToFile(ConfigFile, Format('{"server_url": "%s"}', [ServerURL]), False);
    end;
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\FIMClient"
Type: filesandordirs; Name: "{app}"
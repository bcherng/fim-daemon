[Setup]
AppName=FIM Daemon
AppVersion=1.0
DefaultDirName={pf}\FIM Daemon
OutputBaseFilename=fim-daemon-setup

[Files]
Source: "dist\fim-daemon.exe"; DestDir: "{app}"

[Run]
Filename: "sc"; Parameters: "create FIMDaemon binPath= ""{app}\fim-daemon.exe --server https://your-ec2-domain"" start= auto"; Flags: runhidden
Filename: "sc"; Parameters: "start FIMDaemon"; Flags: runhidden

[UninstallRun]
Filename: "sc"; Parameters: "stop FIMDaemon"; Flags: runhidden
Filename: "sc"; Parameters: "delete FIMDaemon"; Flags: runhidden

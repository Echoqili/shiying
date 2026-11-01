#define AppVersion "1.0.0"
[Setup]
AppId={{7125967A-91D4-4E39-9B63-2AB97388DFA1}
AppName=拾影 Shiying
AppVersion={#AppVersion}
AppPublisher=Echoqili
AppPublisherURL=https://github.com/Echoqili/shiying
AppSupportURL=https://github.com/Echoqili/shiying/issues
DefaultDirName={localappdata}\Programs\Shiying
DefaultGroupName=拾影 Shiying
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\release
OutputBaseFilename=Shiying-{#AppVersion}-windows-x64-setup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\Shiying.exe
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
LicenseFile=..\LICENSE

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\Shiying\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\拾影 Shiying"; Filename: "{app}\Shiying.exe"
Name: "{autodesktop}\拾影 Shiying"; Filename: "{app}\Shiying.exe"

[Run]
Filename: "{app}\Shiying.exe"; Description: "Launch Shiying"; Flags: nowait postinstall skipifsilent

; Inno Setup script to build a simple installer for mdimageembed
[Setup]
AppName=mdimageembed
AppVersion=1.0
DefaultDirName={pf}\mdimageembed
DefaultGroupName=mdimageembed
DisableDirPage=yes
OutputBaseFilename=mdimageembed_setup
OutputDir=.
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\release\mdimageembed.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\release\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\mdimageembed"; Filename: "{app}\mdimageembed.exe"; IconFilename: "{app}\app.ico"
Name: "{userdesktop}\mdimageembed"; Filename: "{app}\mdimageembed.exe"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\mdimageembed.exe"; Description: "Launch mdimageembed"; Flags: nowait postinstall skipifsilent

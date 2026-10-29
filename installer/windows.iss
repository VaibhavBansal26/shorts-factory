; Inno Setup script: wraps the PyInstaller folder into a normal Windows installer (no admin rights needed).
#define AppVer GetEnv("APP_VERSION")
#if AppVer == ""
  #define AppVer "1.0.0"
#endif

[Setup]
AppName=Shorts Factory
AppVersion={#AppVer}
AppPublisher=Vaibhav Bansal
DefaultDirName={autopf}\Shorts Factory
DefaultGroupName=Shorts Factory
OutputDir=..
OutputBaseFilename=Shorts-Factory-Windows-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\desktop-icon.ico
UninstallDisplayIcon={app}\Shorts Factory.exe
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Shorts Factory\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\Shorts Factory"; Filename: "{app}\Shorts Factory.exe"
Name: "{autodesktop}\Shorts Factory"; Filename: "{app}\Shorts Factory.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Shorts Factory.exe"; Description: "Launch Shorts Factory"; Flags: nowait postinstall skipifsilent

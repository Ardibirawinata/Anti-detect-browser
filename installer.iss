; Inno Setup 6 script - menghasilkan installer\PrivacyBrowser-Setup.exe
; Instal per-user (tanpa hak admin / tanpa pop-up UAC).

#define AppName "Privacy Browser"
#define AppVersion "1.0.0"
#define AppExe "PrivacyBrowser.exe"

[Setup]
AppId={{6E4C2A1F-8B3D-4F5E-9A7C-2D1B0E9F8A61}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
DefaultDirName={localappdata}\Programs\PrivacyBrowser
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=PrivacyBrowser-Setup
SetupIconFile=privacy_browser\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "indonesian"; MessagesFile: "tools\Indonesian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\PrivacyBrowser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; Catatan: data profil (%LOCALAPPDATA%\PrivacyBrowser\data) sengaja TIDAK dihapus saat uninstall
; supaya cookie/login pengguna aman jika menginstal ulang.

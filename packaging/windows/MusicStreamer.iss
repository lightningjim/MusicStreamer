; MusicStreamer Inno Setup installer
; Per-user install (PrivilegesRequired=lowest), %LOCALAPPDATA%\MusicStreamer target.
; Version passed in by build.ps1 via /DAppVersion=2.0.0 on iscc.exe command line.
; AppId GUID is pinned — NEVER change it without planning a migration path.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{914e9cb6-f320-478a-a2c4-e104cd450c88}
AppName=MusicStreamer
AppVersion={#AppVersion}
AppPublisher=Kyle Creasey
AppPublisherURL=https://github.com/lightningjim/MusicStreamer

; Per-user install (D-02): no admin elevation, installs under user profile.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
DefaultDirName={localappdata}\MusicStreamer
DefaultGroupName=MusicStreamer
DisableProgramGroupPage=yes
DisableDirPage=yes

; License page (D-05)
LicenseFile=EULA.txt

; Output (D-07)
OutputDir=..\..\dist\installer
OutputBaseFilename=MusicStreamer-{#AppVersion}-win64-setup

; 64-bit only
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Uninstaller icon
SetupIconFile=icons\MusicStreamer.ico
UninstallDisplayIcon={app}\MusicStreamer.exe
UninstallDisplayName=MusicStreamer {#AppVersion}

; Compression
Compression=lzma2/max
SolidCompression=yes

; Upgrade: Inno Setup auto-detects via AppId; on upgrade it silently uninstalls prior version
; then installs new. No custom [Code] needed for the common case.
; Reference: https://jrsoftware.org/ishelp/topic_setup_appid.htm

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Recursively install the entire PyInstaller onedir bundle
; Source paths are relative to the .iss file location.
Source: "..\..\dist\MusicStreamer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; D-04: Start Menu shortcut ONLY — and it's mandatory because it carries the AUMID.
; AppUserModelID must match exactly the string passed to SetCurrentProcessExplicitAppUserModelID
; in musicstreamer/__main__.py::_set_windows_aumid — otherwise SMTC shows "Unknown app".
; Reference: https://jrsoftware.org/ishelp/topic_iconssection.htm
Name: "{userprograms}\MusicStreamer"; Filename: "{app}\MusicStreamer.exe"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\_internal\icons\MusicStreamer.ico"; \
    AppUserModelID: "org.lightningjim.MusicStreamer"

; Uninstaller shortcut in the same group (optional polish)
Name: "{userprograms}\Uninstall MusicStreamer"; Filename: "{uninstallexe}"

[Run]
; Optional: post-install launch checkbox (unchecked by default — Pitfall 6:
; first launch should be via the Start Menu shortcut so the AUMID is bound).
Filename: "{app}\MusicStreamer.exe"; Description: "Launch MusicStreamer"; \
    Flags: nowait postinstall skipifsilent unchecked

; --- D-03: NO uninstall-delete section — preserve user data on uninstall ---
; We deliberately omit any section that would purge %APPDATA%\musicstreamer.
; User data (SQLite DB, cookies, tokens, accent CSS, EQ profiles, logo cache) lives there
; under platformdirs.user_data_dir("musicstreamer") and MUST survive uninstall (D-03).
; Inno Setup's default uninstaller only removes what it installed, so silence = correct.

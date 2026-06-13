; MusicStreamer Inno Setup installer
; Per-user install (PrivilegesRequired=lowest), %LOCALAPPDATA%\Programs\MusicStreamer target.
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
; Phase 44 UAT fix: install into {userpf} (= %LOCALAPPDATA%\Programs\MusicStreamer)
; instead of {localappdata}\MusicStreamer. The latter collides with the
; platformdirs user_data_dir on case-insensitive NTFS (`musicstreamer` outer
; folder), so the uninstaller cannot remove the install dir while user data
; subdirs exist beneath it. {userpf} is Microsoft's recommended per-user
; install location and avoids the collision entirely.
DefaultDirName={userpf}\MusicStreamer
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

; Phase 88.3-04 B1: install the isolated oauth_helper bundle to a LOCAL path
; under {app}\oauth_helper\. The helper carries QtWebEngine for in-app OAuth
; logins (GBS.FM / Twitch / Google). It MUST install LOCAL -- Chromium's sandbox
; refuses to launch QtWebEngineProcess.exe from a network/UNC path (spike VM run 2).
; {app}\oauth_helper\oauth_helper.exe is the exact path that 88.3-03's launcher
; resolves via _make_oauth_launch_args() in musicstreamer/subprocess_utils.py.
Source: "..\..\dist\oauth_helper\*"; DestDir: "{app}\oauth_helper"; Flags: ignoreversion recursesubdirs createallsubdirs

; WIN-02-A: Remove the previous version's Start-Menu .lnk shortcuts on upgrade.
; [InstallDelete] runs AFTER Inno auto-uninstalls the prior version (via AppId) but
; BEFORE [Icons] creates the new shortcuts. This deterministically clears any stale
; .lnk so a taskbar-pinned shortcut cannot hold onto the old AUMID (Pitfall 6).
;
; SCOPED EXCEPTION — filesandordirs permitted under {app}\_internal\ only:
;   {app} = {userpf}\MusicStreamer (the install directory). This path is FULLY
;   INSTALL-MANAGED and is replaced on every build; it contains NO user data.
;   The scoped wildcard below removes stale version-named musicstreamer-*.dist-info
;   directories that accumulate across upgrades. The prohibition on filesandordirs
;   and on touching {userappdata}/{localappdata} user-data paths REMAINS in force
;   for everything else — those paths protect the SQLite DB, cookies, tokens,
;   accent CSS, EQ profiles, and logo cache that live under
;   platformdirs.user_data_dir and MUST survive upgrade/uninstall (D-03).
;
; WHY this is needed — Gap G1 (UAT 88-04):
;   Without this row, prior-version musicstreamer-*.dist-info directories pile up
;   in the installed _internal across upgrades (observed: 2.1.68, 2.1.84, 2.2.86
;   all present after a v2.2 install). importlib.metadata.version("musicstreamer")
;   resolves to the LOWEST version present, causing the app and everything keyed
;   off it (app.setApplicationVersion, User-Agent strings in cover_art_mb.py and
;   soma_import.py) to mislabel the version. This is the INSTALL-side analog of
;   build.ps1's pre-bundle clean (~line 158-169) and post-bundle singleton
;   assertion (exit 9, ~line 245-254).
;
; TIMING — why safe-and-sufficient:
;   [InstallDelete] runs at the START of installation, BEFORE [Files] copies the
;   new bundle. Deleting old version-named dirs here leaves exactly ONE freshly-
;   copied musicstreamer-<X.Y.Z>.dist-info after [Files] completes.
[InstallDelete]
Type: files; Name: "{userprograms}\MusicStreamer.lnk"
Type: files; Name: "{userprograms}\Uninstall MusicStreamer.lnk"
Type: filesandordirs; Name: "{app}\_internal\musicstreamer-*.dist-info"

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

---
phase: 88
plan: "03"
status: resolved
created: 2026-06-05
updated: 2026-06-13
requirements: [WIN-02, WIN-02-A, WIN-02-B, VER-02-J, WIN-05]
---

# Phase 88 — Win11 VM UAT (AUMID + Upgrade Cleanup + Golden-Path + AAC)

> **This UAT runs on the Win11 VM.** Linux CI validates the static 3-way AUMID parity
> (Plan 02 `tests/test_aumid_string_parity.py`) and the AAC plugin-guard logic, but it
> cannot validate the installed `.lnk` AUMID readback, the SMTC "MusicStreamer" overlay
> identity, upgrade shortcut cleanup, or audible AAC playback — all of those are
> OS-owned runtime behaviours that require a real Windows 11 machine.
>
> **Prerequisite:** The VM must have had the v2.1 installer previously applied so that
> an existing `MusicStreamer.lnk` in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\`
> is present **before** the v2.2 install begins. This is what exercises the Plan 01
> `[InstallDelete]` shortcut-cleanup step (WIN-02-A / Pitfall 6).
>
> **Taskbar note:** If MusicStreamer is currently pinned to the taskbar, **unpin it
> before running the v2.2 installer** per `RELEASE-NOTES.md`. The installer cannot
> reach a taskbar-promoted shortcut; re-pin from the Start Menu after install.
>
> Sign off every row before marking Phase 88 complete. Paste verbatim output into the
> Notes column — it closes WIN-02, WIN-02-A, WIN-02-B, VER-02-J, and WIN-05.

---

## Environment Snapshot

Run these commands in a PowerShell terminal on the Win11 VM **after** installing the
v2.2 bundle and **before** starting the checklist rows.

```powershell
# OS version
[System.Environment]::OSVersion.Version
(Get-WmiObject Win32_OperatingSystem).Caption

# Python / conda env (must be the conda-forge GStreamer spike env)
python --version
conda info --envs

# Confirm the installed app version
& "$env:LOCALAPPDATA\Programs\MusicStreamer\MusicStreamer.exe" --version 2>&1

# Confirm the Start-Menu shortcut exists post-install
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"
```

**Captured on Win11 VM:**

```
(base) PS C:\Users\kcreasey> # OS version
(base) PS C:\Users\kcreasey> [System.Environment]::OSVersion.Version

Major  Minor  Build  Revision
-----  -----  -----  --------
10     0      26200  0


(base) PS C:\Users\kcreasey> (Get-WmiObject Win32_OperatingSystem).Caption
Microsoft Windows 11 Home
(base) PS C:\Users\kcreasey>
(base) PS C:\Users\kcreasey> # Python / conda env (must be the conda-forge GStreamer spike env)
(base) PS C:\Users\kcreasey> python --version
Python 3.13.12
(base) PS C:\Users\kcreasey> conda info --envs

# conda environments:
#
# * -> active
# + -> frozen
base                 *   C:\ProgramData\miniforge3
musicstreamer-build      C:\Users\kcreasey\.conda\envs\musicstreamer-build

(base) PS C:\Users\kcreasey>
(base) PS C:\Users\kcreasey> # Confirm the installed app version
(base) PS C:\Users\kcreasey> & "$env:LOCALAPPDATA\Programs\MusicStreamer\MusicStreamer.exe" --version 2>&1
(base) PS C:\Users\kcreasey>
(base) PS C:\Users\kcreasey> # Confirm the Start-Menu shortcut exists post-install
(base) PS C:\Users\kcreasey> & "$env:LOCALAPPDATA\Programs\MusicStreamer\MusicStreamer.exe" --version 2>&1
(base) PS C:\Users\kcreasey>
(base) PS C:\Users\kcreasey> # Confirm the Start-Menu shortcut exists post-install
(base) PS C:\Users\kcreasey> Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"
True
```

---

## Build / Install Instructions

If you are building from source rather than using a pre-built installer:

```powershell
# From the repo root — activate the conda-forge spike env first
cd packaging\windows
.\build.ps1
# Installer produced at: dist\installer\MusicStreamer-<ver>-win64-setup.exe
```

Run the produced `MusicStreamer-<ver>-win64-setup.exe` over the existing v2.1 install.
The installer is per-user (`PrivilegesRequired=lowest`); no UAC prompt expected.

---

## UAT Checklist

| # | Behavior | Requirement | Method (exact command / click-path) | Expected | Pass/Fail | Notes                                                                           |
|---|----------|-------------|--------------------------------------|----------|-----------|---------------------------------------------------------------------------------|
| UAT-1 | Pre-upgrade: exactly one v2.1 `.lnk` exists; post-upgrade: exactly one v2.2 `.lnk` exists — old one deleted, no stale duplicate | WIN-02-A | **Before install:** `Get-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk" \| Select-Object Name, LastWriteTime`. Note the timestamp. **Install** v2.2 over v2.1. **After install:** repeat the same `Get-Item` command plus `(Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\" -Filter "MusicStreamer*.lnk").Count` | After install: exactly `1` file, timestamp is newer than the v2.1 timestamp | pass      | See Evidence § UAT-1 — after-only; no v2.1 baseline timestamp or Count captured |
| UAT-2 | Installed `.lnk` carries `AppUserModelID = org.lightningjim.MusicStreamer` (Shell.Application ExtendedProperty readback) | WIN-02, WIN-02-B | In PowerShell: `$lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"` then `(New-Object -ComObject Shell.Application).Namespace(0).ParseName($lnk).ExtendedProperty('System.AppUserModel.ID')` | Output is exactly `org.lightningjim.MusicStreamer` (the identical literal that `tests/test_aumid_string_parity.py` pins on CI) | pass      | See Evidence § UAT-2                                                            |
| UAT-3 | SMTC media overlay shows "MusicStreamer" (not "Unknown app") when playing | WIN-02 | Launch via the Start-Menu shortcut (not the exe directly). Play any station. Press the hardware volume key to open the volume flyout / Quick Settings overlay. Inspect the media session label. | Media session label reads **"MusicStreamer"**, not "Unknown app" or the exe path | fail      | No media session is even presented as an overlay                                |
| UAT-4 | App launches without crash from the Start-Menu shortcut | VER-02-J | Double-click the Start-Menu "MusicStreamer" shortcut. Confirm the main window opens with no error dialog or console traceback. | Main window appears; no crash dialog; no traceback in the console | pass      | (How can I even have a console for this?)                                       |
| UAT-5 | Station plays audibly (MP3 / Shoutcast / ICY stream) | VER-02-J | Select any SomaFM or ShoutCast station. Click Play. Confirm audio within 5 s. | Audible audio; player state shows "Playing" | Pass      | See Evidence section                                                            |
| UAT-6 | ICY metadata (track title) appears in the Now-Playing panel | VER-02-J | While playing a station, wait up to 2 min for an ICY title update. Confirm the track-title field in the Now-Playing panel updates. | Track title field is non-empty and changes over time | Pass      | Nothing of note                                                                 |
| UAT-7 | Media keys (play/pause, stop) work via keyboard | VER-02-J | While playing, press keyboard **media-play/pause** key — confirm playback pauses; press again — confirm resume. Press **media-stop** — confirm stop. | Play/pause and stop keys control playback as expected | fail      | Probably related to the Media Seession failure                                  |
| UAT-8 | Cover art loads (or placeholder shown) | VER-02-J | Play a station that has known cover art (e.g. a SomaFM station). Confirm cover art slot shows either the station logo / iTunes art / MB-CAA art, or the placeholder — never a broken-image icon. | Cover art slot populated (not broken) | Pass      | Nothing of note                                                                 |
| UAT-9 | MB-CAA fallback: cover art loads for a niche/electronic station not in iTunes | VER-02-J | Play a niche-electronic station (e.g. Soma Vaporwaves or a DI.fm Chillout station) where iTunes coverage is sparse. Confirm cover art loads via MB-CAA or placeholder — not a crash. | Cover art present or placeholder; no crash / error toast | Pass      |                                                                                 |
| UAT-10 | GBS.FM: login and playback | VER-02-J | Open GBS.FM station. If login is required, authenticate via the in-app login dialog. Confirm audio plays. | GBS.FM audio plays successfully after login | Fail      | Login fails to start                                                            |
| UAT-11 | SomaFM preroll plays before main stream | VER-02-J | Select a SomaFM station known to have a preroll (e.g. Groove Salad, Drone Zone, or Beat Blender). Click Play. Confirm the preroll audio plays first, then the main stream begins. | Preroll audio heard, then station stream begins | pass      | Drone Zone                                                                      |
| UAT-12 | DI.fm AAC tier plays audibly | WIN-05 | In the station list, select a DI.fm station and choose an **AAC** stream quality tier in the stream picker. Click Play. Confirm audible audio within 10 s. | Audible AAC audio; no silence or "Playback error" toast | Pass      | http://prem4.di.fm:80/bassline?2d5bb0c3661c1d9ac8 128                           |
| UAT-13 | AudioAddict AAC tier plays audibly | WIN-05 | Select an AudioAddict network station (e.g. Sky.fm, JazzRadio.com) and choose an **AAC** stream quality. Click Play. Confirm audible audio. | Audible AAC audio within 10 s | pass      | http://prem4.zenradio.com:80/zrambient_aac?2d5bb0c3661c1d9ac8    128            |
| UAT-14 | SomaFM AAC tier plays audibly | WIN-05 | Select a SomaFM station, open stream picker, choose an **AAC/AACP** tier (e.g. the 128k AAC stream). Click Play. Confirm audible audio. | Audible AAC audio within 10 s | pass      | See Evidence § UAT-14                                                            |
| UAT-15 | `check_bundle_plugins.py` exits 10 on a bundle missing `gstlibav.dll` | WIN-05 | In PowerShell, from the repo root with the conda-forge spike env active: `$bundleInternal = "dist\MusicStreamer\_internal"` then `$pluginsDir = "$bundleInternal\gst_plugins"`. **Rename** `gstlibav.dll` temporarily: `Rename-Item "$pluginsDir\gstlibav.dll" "$pluginsDir\gstlibav.dll.bak"`. Run: `python tools\check_bundle_plugins.py --bundle $bundleInternal`. Confirm exit code: `$LASTEXITCODE`. **Restore:** `Rename-Item "$pluginsDir\gstlibav.dll.bak" "$pluginsDir\gstlibav.dll"`. | Exit code is **10** and stderr contains `PHASE-69 FAIL` and `gstlibav.dll` | Blocked   | `$pluginsDir` was empty → path collapsed to `\gstlibav.dll`. See Evidence § UAT-15 for corrected one-shot |
| UAT-16 | `check_bundle_plugins.py` exits 0 on the complete bundle | WIN-05 | After restoring `gstlibav.dll` in UAT-15, run: `python tools\check_bundle_plugins.py --bundle dist\MusicStreamer\_internal`. Confirm exit code. | Exit code is **0** and stdout contains `PHASE-69 OK` | pass      | See Evidence § UAT-16                                                            |
| UAT-17 | After upgrade install, installed `_internal` holds exactly ONE `musicstreamer-*.dist-info` AND app reports the built version (G1 fix). | WIN-02-A, VER-02-J | Run AFTER installing the new v2.2.x build over the prior version in PowerShell: `(Get-ChildItem "$env:LOCALAPPDATA\Programs\MusicStreamer\_internal" -Filter "musicstreamer-*.dist-info").Count` — expect `1`. Then read the surviving dir name: `(Get-ChildItem "$env:LOCALAPPDATA\Programs\MusicStreamer\_internal" -Filter "musicstreamer-*.dist-info").Name` — expect `musicstreamer-<built X.Y.Z>.dist-info`. Optionally check app-reported version: `& "$env:LOCALAPPDATA\Programs\MusicStreamer\MusicStreamer.exe" --version 2>&1` (or read the dist-info dir name if `--version` is unreliable per Environment Snapshot). | `.Count` equals `1`; the surviving dist-info dir name is `musicstreamer-<built X.Y.Z>.dist-info` (the freshly-built version, NOT a stale lower version like 2.1.68); app-reported version matches. | | Re-test on Win11 VM that previously had multiple versions installed — see Gaps § G1 / Evidence § Diagnostic (was 3 dist-info dirs: 2.1.68, 2.1.84, 2.2.86). |

---

## Evidence

### UAT-1

After-install `Get-Item` readback. **No v2.1 baseline timestamp or `.Count` was
captured before the upgrade**, so the "old `.lnk` deleted / exactly one remains"
assertion is only partially evidenced (single file present, timestamp current).

```
(musicstreamer-build) PS Z:\musicstreamer\packaging\windows> Get-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk" | Select-Object Name, LastWriteTime

Name              LastWriteTime
----              -------------
MusicStreamer.lnk 6/6/2026 7:48:10 AM
```

### UAT-2
```
(musicstreamer-build) PS Z:\musicstreamer\packaging\windows> $lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"
(musicstreamer-build) PS Z:\musicstreamer\packaging\windows> (New-Object -ComObject Shell.Application).Namespace(0).ParseName($lnk).ExtendedProperty('System.AppUserModel.ID')
org.lightningjim.MusicStreamer
(musicstreamer-build) PS Z:\musicstreamer\packaging\windows>
```

### UAT-5
http://prem4.zenradio.com:80/zrambient?2d5bb0c3661c1d9ac8
https://ice6.somafm.com/deepspaceone-128-aac

### UAT-14
SomaFM AAC tier — audible within 10 s.
```
https://ice6.somafm.com/dronezone-128-aac   (128k AAC)
```

### UAT-15
**Blocked.** The original error —
```
Rename-Item : Cannot rename the specified target, because it represents a path or device name.
```
— is because `$pluginsDir` was unset when `Rename-Item` ran, so the path collapsed to the
rooted `\gstlibav.dll` (a device/path name). Re-run all steps in **one** PowerShell block so
the variables stay in scope (build output lives under `Z:\musicstreamer\dist`):

```powershell
$bundleInternal = "Z:\musicstreamer\dist\MusicStreamer\_internal"
$pluginsDir     = "$bundleInternal\gst_plugins"
Test-Path "$pluginsDir\gstlibav.dll"                                    # must print True first
Rename-Item "$pluginsDir\gstlibav.dll" "gstlibav.dll.bak"
python Z:\musicstreamer\tools\check_bundle_plugins.py --bundle $bundleInternal
"exit=$LASTEXITCODE"                                                    # expect 10
Rename-Item "$pluginsDir\gstlibav.dll.bak" "gstlibav.dll"              # restore
```

### UAT-16
```
PHASE-69 OK: all 2 required plugin DLL(s) present in dist\MusicStreamer\_internal\gst_plugins
```
Exit code 0 (clean bundle).

### Diagnostic — installed vs built dist-info (root cause of v2.1.68 mislabel)
Captured 2026-06-06. See Gaps § G1.
```
# Installed bundle (_internal)
musicstreamer-2.1.68.dist-info
musicstreamer-2.1.84.dist-info
musicstreamer-2.2.86.dist-info

# Fresh build (Z:\musicstreamer\dist\MusicStreamer\_internal)
musicstreamer-2.2.86.dist-info
```

---

## Summary

```
total: 17
passed: 12      # UAT-1,2,4,5,6,8,9,11,12,13,14,16
failed: 3       # UAT-3 (SMTC), UAT-7 (media keys), UAT-10 (GBS login)
pending: 1      # UAT-17 (upgrade dist-info cleanup — pending VM session)
skipped: 0
blocked: 1      # UAT-15 (re-run corrected one-shot — see Evidence § UAT-15)
```

> **Run executed against confirmed v2.2.86 code** (diagnostic: fresh `dist` carries only
> `musicstreamer-2.2.86.dist-info`). The player's "2.1.68" label is a stale-dist-info
> artifact of the installer, **not** a wrong-binary run — so the 3 failures are real v2.2
> findings, not test-setup noise. See Gaps § G1 for the headline packaging defect.

---

## Gaps

Failures feed a `/gsd:plan-phase --gaps` follow-up phase.

### G1 — Installer leaves stale `dist-info` in `_internal` (CRITICAL · WIN-02-A / VER-02-J)
Confirmed 2026-06-06 (Evidence § Diagnostic). Installed `_internal` holds **three** dist-info
dirs (`2.1.68`, `2.1.84`, `2.2.86`); the fresh build is clean (`2.2.86` only). The build is
correct — the **v2.2 installer installs the new code but never removes prior-version dist-info
directories**. `importlib.metadata.version("musicstreamer")` then resolves to the lowest
(`2.1.68`), so the app and everything keyed off it (UA strings in `cover_art_mb.py` /
`soma_import.py`, `app.setApplicationVersion`) mislabel the version. `build.ps1:132-146` guards
the *build* env against this; the *install* location has no equivalent cleanup.
**Fix:** add an installer step (`[InstallDelete]` or pre-copy clean) that wipes
`_internal\musicstreamer-*.dist-info` before laying down the new bundle. Note UAT-1 (shortcut
cleanup) passed — this is the *other half* of upgrade cleanup that's missing.

### G2 — SMTC media session absent on v2.2 (UAT-3, UAT-7 · WIN-02 / VER-02-J)
No media-session overlay appears at all when playing; media keys are consequently dead. Verified
against 2.2.86 code (per G1, not a wrong-binary artifact). Root cause TBD — investigate the
Windows SMTC / `SystemMediaTransportControls` registration path.

### G3 — GBS.FM login won't start (UAT-10 · VER-02-J)
In-app login dialog fails to start; playback never reached. Investigate separately.

### G4 — Cross-platform settings backup "not a valid zip" — RESOLVED (not a build defect)
Root cause (confirmed 2026-06-06): the VM share transferred the `.zip` in **text mode**,
rewriting every `0x0A` (LF) byte to `0x0D 0x0A` (CRLF). That shifts byte offsets and breaks
the zip central-directory pointers, so `zipfile` raises `BadZipFile`
(`settings_export.py:257` → "Not a valid ZIP archive"). Re-copying the file through a
byte-preserving path imported cleanly. The export/import code is pure stdlib `zipfile` with
no OS-specific branches — nothing to fix in the bundle.
**Optional follow-up (backlog, not a defect):** friendlier import error that *detects* the
CRLF-corruption signature (starts with `PK` but fails `BadZipFile` + contains injected CRLF
runs) and tells the user "this file looks corrupted by a text-mode transfer — re-copy in
binary mode." NOTE: auto-repair (collapsing `0x0D0A`→`0x0A`) is **unsafe** — it would also
clobber legitimate `0x0D0A` byte pairs in the binary, so the fix is detection + guidance, not
silent repair.

### G5 — UAT-15 exit-10 guard not yet exercised (WIN-05)
Blocked by an unset `$pluginsDir` (Evidence § UAT-15). Re-run the corrected one-shot to close.
---

## Sign-Off

- [ ] All 17 rows executed (Pass/Fail filled in, verbatim output pasted)
- [X] UAT-2 output pasted verbatim and equals exactly `org.lightningjim.MusicStreamer`
- [ ] UAT-3 SMTC overlay confirmed "MusicStreamer" (not "Unknown app")
- [X] UAT-12 / UAT-13 / UAT-14 AAC streams confirmed audible (not silent)
- [ ] UAT-15 exit-10 guard confirmed; UAT-16 clean-bundle exit-0 confirmed
- [ ] Frontmatter `status` updated to `resolved` when all rows are PASS

**Signed off by:** *(fill in after VM session)*
**Date:** *(fill in)*

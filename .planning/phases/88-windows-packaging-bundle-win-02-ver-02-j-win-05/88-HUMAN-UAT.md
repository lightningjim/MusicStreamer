---
phase: 88
plan: "03"
status: pending
created: 2026-06-05
updated: 2026-06-05
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
[paste output here]
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

| # | Behavior | Requirement | Method (exact command / click-path) | Expected | Pass/Fail | Notes |
|---|----------|-------------|--------------------------------------|----------|-----------|-------|
| UAT-1 | Pre-upgrade: exactly one v2.1 `.lnk` exists; post-upgrade: exactly one v2.2 `.lnk` exists — old one deleted, no stale duplicate | WIN-02-A | **Before install:** `Get-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk" \| Select-Object Name, LastWriteTime`. Note the timestamp. **Install** v2.2 over v2.1. **After install:** repeat the same `Get-Item` command plus `(Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\" -Filter "MusicStreamer*.lnk").Count` | After install: exactly `1` file, timestamp is newer than the v2.1 timestamp | [pending] | Paste both Get-Item outputs and the Count result |
| UAT-2 | Installed `.lnk` carries `AppUserModelID = org.lightningjim.MusicStreamer` (Shell.Application ExtendedProperty readback) | WIN-02, WIN-02-B | In PowerShell: `$lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"` then `(New-Object -ComObject Shell.Application).Namespace(0).ParseName($lnk).ExtendedProperty('System.AppUserModel.ID')` | Output is exactly `org.lightningjim.MusicStreamer` (the identical literal that `tests/test_aumid_string_parity.py` pins on CI) | [pending] | Paste the full output verbatim — even a trailing space would be a failure |
| UAT-3 | SMTC media overlay shows "MusicStreamer" (not "Unknown app") when playing | WIN-02 | Launch via the Start-Menu shortcut (not the exe directly). Play any station. Press the hardware volume key to open the volume flyout / Quick Settings overlay. Inspect the media session label. | Media session label reads **"MusicStreamer"**, not "Unknown app" or the exe path | [pending] | Screenshot recommended. If label shows "Unknown app", confirm launch was via the Start-Menu .lnk, not direct exe |
| UAT-4 | App launches without crash from the Start-Menu shortcut | VER-02-J | Double-click the Start-Menu "MusicStreamer" shortcut. Confirm the main window opens with no error dialog or console traceback. | Main window appears; no crash dialog; no traceback in the console | [pending] | |
| UAT-5 | Station plays audibly (MP3 / Shoutcast / ICY stream) | VER-02-J | Select any SomaFM or ShoutCast station. Click Play. Confirm audio within 5 s. | Audible audio; player state shows "Playing" | [pending] | Station name + URL used |
| UAT-6 | ICY metadata (track title) appears in the Now-Playing panel | VER-02-J | While playing a station, wait up to 2 min for an ICY title update. Confirm the track-title field in the Now-Playing panel updates. | Track title field is non-empty and changes over time | [pending] | |
| UAT-7 | Media keys (play/pause, stop) work via keyboard | VER-02-J | While playing, press keyboard **media-play/pause** key — confirm playback pauses; press again — confirm resume. Press **media-stop** — confirm stop. | Play/pause and stop keys control playback as expected | [pending] | |
| UAT-8 | Cover art loads (or placeholder shown) | VER-02-J | Play a station that has known cover art (e.g. a SomaFM station). Confirm cover art slot shows either the station logo / iTunes art / MB-CAA art, or the placeholder — never a broken-image icon. | Cover art slot populated (not broken) | [pending] | |
| UAT-9 | MB-CAA fallback: cover art loads for a niche/electronic station not in iTunes | VER-02-J | Play a niche-electronic station (e.g. Soma Vaporwaves or a DI.fm Chillout station) where iTunes coverage is sparse. Confirm cover art loads via MB-CAA or placeholder — not a crash. | Cover art present or placeholder; no crash / error toast | [pending] | |
| UAT-10 | GBS.FM: login and playback | VER-02-J | Open GBS.FM station. If login is required, authenticate via the in-app login dialog. Confirm audio plays. | GBS.FM audio plays successfully after login | [pending] | |
| UAT-11 | SomaFM preroll plays before main stream | VER-02-J | Select a SomaFM station known to have a preroll (e.g. Groove Salad, Drone Zone, or Beat Blender). Click Play. Confirm the preroll audio plays first, then the main stream begins. | Preroll audio heard, then station stream begins | [pending] | |
| UAT-12 | DI.fm AAC tier plays audibly | WIN-05 | In the station list, select a DI.fm station and choose an **AAC** stream quality tier in the stream picker. Click Play. Confirm audible audio within 10 s. | Audible AAC audio; no silence or "Playback error" toast | [pending] | Paste the selected stream URL / bitrate |
| UAT-13 | AudioAddict AAC tier plays audibly | WIN-05 | Select an AudioAddict network station (e.g. Sky.fm, JazzRadio.com) and choose an **AAC** stream quality. Click Play. Confirm audible audio. | Audible AAC audio within 10 s | [pending] | Paste the selected stream URL / bitrate |
| UAT-14 | SomaFM AAC tier plays audibly | WIN-05 | Select a SomaFM station, open stream picker, choose an **AAC/AACP** tier (e.g. the 128k AAC stream). Click Play. Confirm audible audio. | Audible AAC audio within 10 s | [pending] | Paste the selected stream URL / bitrate |
| UAT-15 | `check_bundle_plugins.py` exits 10 on a bundle missing `gstlibav.dll` | WIN-05 | In PowerShell, from the repo root with the conda-forge spike env active: `$bundleInternal = "dist\MusicStreamer\_internal"` then `$pluginsDir = "$bundleInternal\gst_plugins"`. **Rename** `gstlibav.dll` temporarily: `Rename-Item "$pluginsDir\gstlibav.dll" "$pluginsDir\gstlibav.dll.bak"`. Run: `python tools\check_bundle_plugins.py --bundle $bundleInternal`. Confirm exit code: `$LASTEXITCODE`. **Restore:** `Rename-Item "$pluginsDir\gstlibav.dll.bak" "$pluginsDir\gstlibav.dll"`. | Exit code is **10** and stderr contains `PHASE-69 FAIL` and `gstlibav.dll` | [pending] | Paste the script output and `$LASTEXITCODE` verbatim |
| UAT-16 | `check_bundle_plugins.py` exits 0 on the complete bundle | WIN-05 | After restoring `gstlibav.dll` in UAT-15, run: `python tools\check_bundle_plugins.py --bundle dist\MusicStreamer\_internal`. Confirm exit code. | Exit code is **0** and stdout contains `PHASE-69 OK` | [pending] | Paste full output |

---

## Summary

```
total: 16
passed: [fill in]
failed: [fill in]
pending: 16
skipped: 0
blocked: 0
```

---

## Gaps

[none yet — fill in after execution; failures feed a /gsd:plan-phase --gaps follow-up phase]

---

## Sign-Off

- [ ] All 16 rows executed (Pass/Fail filled in, verbatim output pasted)
- [ ] UAT-2 output pasted verbatim and equals exactly `org.lightningjim.MusicStreamer`
- [ ] UAT-3 SMTC overlay confirmed "MusicStreamer" (not "Unknown app")
- [ ] UAT-12 / UAT-13 / UAT-14 AAC streams confirmed audible (not silent)
- [ ] UAT-15 exit-10 guard confirmed; UAT-16 clean-bundle exit-0 confirmed
- [ ] Frontmatter `status` updated to `resolved` when all rows are PASS

**Signed off by:** *(fill in after VM session)*
**Date:** *(fill in)*

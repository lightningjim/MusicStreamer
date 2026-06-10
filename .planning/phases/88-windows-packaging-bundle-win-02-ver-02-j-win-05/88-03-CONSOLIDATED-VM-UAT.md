---
status: ready
session: 88-03 (consolidated Win11 VM — Option C)
covers:
  - phase 88   (G1 UAT-17, G5 UAT-15/16)
  - phase 88.1 (G2 — winrt SMTC bundling: build smoke guard + UAT-3 + UAT-7)
  - phase 88.2 (G3 — OAuth-helper launch: oauth guard + UAT-10 + Twitch + Google)
built_version: 2.2.86
created: 2026-06-10
---

# 88-03 — Consolidated Win11 VM UAT Runner

> **One VM session closes three phases.** Phases 88, 88.1, and 88.2 are all
> code-complete and green on Linux/CI. The only thing left is this single Win11 VM
> pass. Run the sections **in order** — build first (the build itself fast-fails if
> either bundling fix regressed), then install, then interactive runtime.
>
> Fill the **Result** column for each row. When every row is PASS, set this file's
> `status: passed`, then update the three source UAT files' frontmatter to
> `resolved` / `complete` and close 88-03.

**Build version under test:** `2.2.86`
**Conda env:** `musicstreamer-build` (conda-forge GStreamer spike env)
**Repo on VM:** `Z:\musicstreamer` (per prior evidence)

---

## Section A — Build (build VM, env `musicstreamer-build`)

The build script now carries two runtime smoke guards that fast-fail if either
bundling fix regressed. **Do not pass `-SkipSmtcGuard` / `-SkipOauthGuard`** — letting
them run IS the test for the 88.1 and 88.2 fixes.

```powershell
cd Z:\musicstreamer\packaging\windows
.\build.ps1
```

| # | Source | What it proves | Expected | Result |
|---|--------|----------------|----------|--------|
| A1 | 88.1 G2 | **Step 4c — SMTC smoke guard.** `MusicStreamer.exe --check-mediakeys` constructs the real `WindowsMediaKeysBackend` from bundled winrt `.pyd` files. | Build prints the step-4c block and continues. **Does NOT `exit 11`.** If it exits 11, read the `MEDIAKEYS_BACKEND=` line + `build.log` ImportError to see which winrt piece is still unbundled. | [ ] |
| A2 | 88.2 G3 | **Step 4d — OAUTH HELPER GUARD.** `MusicStreamer.exe --oauth-helper --self-test` reaches `_run_oauth_helper` and exits 0 with no window. | Build prints `OAUTH HELPER GUARD OK`. **Does NOT `exit 12`.** | [ ] |
| A3 | — | Build completes. | Installer produced at `dist\installer\MusicStreamer-2.2.86-win64-setup.exe`. | [ ] |

### Bundle plugin guard (G5 — UAT-15 / UAT-16, on the build VM before install)

Run as **one** PowerShell block so `$pluginsDir` stays in scope (this was the G5 blocker).

```powershell
$bundleInternal = "Z:\musicstreamer\dist\MusicStreamer\_internal"
$pluginsDir     = "$bundleInternal\gst_plugins"
Test-Path "$pluginsDir\gstlibav.dll"                          # must print True first
Rename-Item "$pluginsDir\gstlibav.dll" "gstlibav.dll.bak"
python Z:\musicstreamer\tools\check_bundle_plugins.py --bundle $bundleInternal
"exit=$LASTEXITCODE"                                          # expect 10
Rename-Item "$pluginsDir\gstlibav.dll.bak" "gstlibav.dll"     # restore
python Z:\musicstreamer\tools\check_bundle_plugins.py --bundle $bundleInternal
"exit=$LASTEXITCODE"                                          # expect 0
```

| # | Source | Expected | Result |
|---|--------|----------|--------|
| UAT-15 | 88 G5 / WIN-05 | First run: exit **10**, stderr contains `PHASE-69 FAIL` + `gstlibav.dll`. | [ ] |
| UAT-16 | 88 WIN-05 | After restore: exit **0**, stdout contains `PHASE-69 OK`. | [ ] |

---

## Section B — Install (over the prior install)

> **Prerequisite:** the VM must already have a prior MusicStreamer install present so
> the upgrade-cleanup steps actually fire.
> **Taskbar:** if MusicStreamer is pinned to the taskbar, **unpin it before installing**
> (the installer can't reach a taskbar-promoted shortcut). Re-pin from Start Menu after.

```powershell
# Run the produced installer over the existing install (per-user, no UAC):
Z:\musicstreamer\dist\installer\MusicStreamer-2.2.86-win64-setup.exe
```

| # | Source | Method | Expected | Result |
|---|--------|--------|----------|--------|
| UAT-17 | 88 G1 / WIN-02-A | After install: `(Get-ChildItem "$env:LOCALAPPDATA\Programs\MusicStreamer\_internal" -Filter "musicstreamer-*.dist-info").Count` then `.Name` | `.Count` = **1**; surviving dir = `musicstreamer-2.2.86.dist-info` (NOT a stale lower version like 2.1.68). This is the `[InstallDelete]` G1 fix. | [ ] |
| UAT-1b | 88 WIN-02-A | `(Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\" -Filter "MusicStreamer*.lnk").Count` | Exactly **1** shortcut, timestamp newer than the prior install. | [ ] |

---

## Section C — Interactive runtime (launch via Start-Menu shortcut)

> Launch via the **Start-Menu shortcut**, not the exe directly — the shortcut carries
> the AUMID that the SMTC overlay identity depends on.

### C1 — SMTC / media keys (88.1 G2 — WIN-02 / VER-02-J)

| # | Source | Method | Expected | Result |
|---|--------|--------|----------|--------|
| UAT-3 | 88.1 / WIN-02 | Play any station. Open the Win media flyout / Quick Settings overlay. | Media session label reads **"MusicStreamer"** — not "Unknown app", not absent. | [ ] |
| UAT-7 | 88.1 / VER-02-J | While playing, press keyboard **media play/pause** (toggles), then **media stop**. | Play/pause and stop keys control playback. | [ ] |

### C2 — OAuth logins (88.2 G3 — VER-02-J)

The 88.2 fix routes all three logins through the frozen-aware `_make_oauth_launch_args`
launcher. GBS.FM is the anchor; Twitch and Google are free consequences of the same fix.

| # | Source | Method | Expected | Result |
|---|--------|--------|----------|--------|
| UAT-10 | 88.2 / VER-02-J | Open GBS.FM station → AccountsDialog → click the **GBS.FM login** button. Authenticate. | QtWebEngine login window **opens**, auth completes, GBS.FM audio plays. The `_on_gbs_login_error` cookie-import fallback should NOT trigger on a working bundle. | [ ] |
| UAT-10b | 88.2 / D-01 | AccountsDialog → click **Connect Twitch**. | Twitch QtWebEngine login window opens from the frozen exe. | [ ] |
| UAT-10c | 88.2 / CR-01 | Open CookieImportDialog → click the **Google/YouTube login** button. | Google QtWebEngine login window opens. If it can't start, `_on_google_process_error` surfaces a warning pointing to the File/Paste tabs — never a silent dead-end. | [ ] |

---

## Sign-Off

- [ ] Section A: A1 (no exit 11), A2 (OAUTH HELPER GUARD OK), A3 (installer built)
- [ ] Section A: UAT-15 (exit 10) + UAT-16 (exit 0)
- [ ] Section B: UAT-17 (single 2.2.86 dist-info) + UAT-1b (single shortcut)
- [ ] Section C1: UAT-3 (SMTC "MusicStreamer") + UAT-7 (media keys)
- [ ] Section C2: UAT-10 (GBS.FM) + UAT-10b (Twitch) + UAT-10c (Google)

**On all-pass:** set this file `status: passed`; set `88-HUMAN-UAT.md` frontmatter
`status: resolved` (fill UAT-3/7/10/15/17 rows); set `88.1-HUMAN-UAT.md` and
`88.2-HUMAN-UAT.md` to `complete`; then run `/gsd:verify-work 88` (or `88.1`/`88.2`)
to record results and close the phases.

**Signed off by:** *(fill in after VM session)*
**Date:** *(fill in)*

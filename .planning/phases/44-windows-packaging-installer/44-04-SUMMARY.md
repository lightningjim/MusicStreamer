---
phase: 44-windows-packaging-installer
plan: 04
subsystem: packaging
tags: [pyinstaller, inno-setup, gstreamer, windows, aumid, packaging, build-driver]

requires:
  - phase: 43-gstreamer-windows-spike
    provides: canonical .spec, runtime_hook.py, build.ps1 patterns (D-17 verbatim copy)
  - phase: 44-windows-packaging-installer (Plan 01)
    provides: tools/check_subprocess_guard.py, tools/check_spec_entry.py, tests/test_spec_hidden_imports.py
provides:
  - PyInstaller spec for MusicStreamer onedir bundle (Qt + GStreamer 1.28 MSVC)
  - Runtime hook for GIO/typelib/scanner env wiring
  - PowerShell build driver (pre-flight + PKG-03 guard via Python tool + spec-entry guard + PyInstaller + Inno Setup compile + diagnostic)
  - Inno Setup installer script (per-user %LOCALAPPDATA%, AppId pinned, Start-Menu shortcut with AUMID)
  - EULA.txt with LGPL/yt-dlp/streamlink/Qt/Node.js attributions
  - README.md build runbook with DI.fm and AUMID notes
  - Multi-resolution Windows .ico (16/32/48/64/128/256)
affects: [44-05-uat, 44-windows-packaging-installer]

tech-stack:
  added: [pyinstaller-hooks-contrib>=2026.2 (declared in build.ps1), Inno Setup 6.3+, ImageMagick (.ico build-time tool)]
  patterns:
    - "Verbatim-copy invariant for canonical spike artifacts (D-17)"
    - "Single source of truth for PKG-03 regex (Python tool, not duplicated PowerShell Select-String)"
    - "AppId double-open-brace literal (Inno Setup constant escape)"
    - "AUMID literal match between __main__.py and .iss (Pitfall 1 mitigation)"
    - "Per-user %LOCALAPPDATA% install with Start-Menu-only shortcut (no Desktop, no Pin-to-Taskbar)"

key-files:
  created:
    - packaging/windows/MusicStreamer.spec
    - packaging/windows/runtime_hook.py
    - packaging/windows/build.ps1
    - packaging/windows/MusicStreamer.iss
    - packaging/windows/EULA.txt
    - packaging/windows/README.md
    - packaging/windows/icons/MusicStreamer.ico
  modified:
    - .gitignore

key-decisions:
  - "PKG-03 guard in build.ps1 invokes the Python tool (tools/check_subprocess_guard.py) instead of duplicating the regex via Select-String — single source of truth per checker issue 6"
  - "Runtime-hook diag prefix renamed SPIKE_DIAG_RTHOOK -> MUSICSTREAMER_DIAG_RTHOOK (cosmetic only, allowed by D-17)"
  - "Smoke step intentionally skipped in build.ps1 for the GUI app (BUILD_INFO note); UAT (Plan 05) covers functional verification"
  - "Spec-entry guard (tools/check_spec_entry.py) runs BEFORE PyInstaller to fail fast with exit 7 if entry-point reference is missing"

patterns-established:
  - "Build driver invariants: BUILD_FAIL reason=<token> hint='<advice>' format with stable exit-code legend in header"
  - ".spec excludes mpv/Gtk/Adw defensively (Phase 35-06 retired these)"

requirements-completed: [PKG-01, PKG-02, PKG-03]

duration: 22min
completed: 2026-04-25
---

# Phase 44 Plan 04: Windows Packaging Artifacts Summary

**Windows packaging pipeline lands: PyInstaller .spec + GStreamer runtime hook + PowerShell build driver (with Python-tool PKG-03 guard) + Inno Setup per-user installer + EULA + README + multi-resolution .ico, all wired to the AUMID `org.lightningjim.MusicStreamer` and the pinned AppId GUID `914e9cb6-f320-478a-a2c4-e104cd450c88`.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-04-25T11:18:00Z
- **Completed:** 2026-04-25T11:40:00Z
- **Tasks:** 2
- **Files modified:** 8 (7 new + 1 .gitignore edit)

## Accomplishments

- Copied .spec/runtime_hook/build.ps1 from Phase 43 spike with the documented Pattern 4/5 diff applied (D-17 verbatim discipline preserved for runtime_hook.py).
- Built the Inno Setup installer script with all D-02/D-03/D-04/D-05/D-07/D-23 invariants in place: per-user `{localappdata}\MusicStreamer`, no UninstallDelete, EULA license page, versioned `OutputBaseFilename`, Start-Menu shortcut only (no Desktop, no Pin-to-Taskbar), `[Run]` launch entry `unchecked` (Pitfall 6).
- Eliminated the PKG-03 regex-drift risk per checker issue 6: build.ps1 calls `python tools/check_subprocess_guard.py` and exits 4 on non-zero — the canonical Python tool is the single source of truth.
- Generated a 6-resolution Windows icon (16/32/48/64/128/256) via ImageMagick 7 `magick` (NOT `convert` or PIL — checker issue 5).
- All static guards green: `tools/check_spec_entry.py`, `tools/check_subprocess_guard.py`, `tests/test_spec_hidden_imports.py` (no longer skipped), `tests/test_pkg03_compliance.py`. AUMID literal match between `musicstreamer/__main__.py` and `packaging/windows/MusicStreamer.iss` confirmed.

## Task Commits

1. **Task 1: Copy .spec + runtime_hook + build.ps1 verbatim from Phase 43 with documented edits** — `890b93c` (feat)
2. **Task 2: Create Inno Setup script + EULA + README + Windows .ico** — `ad5f8d6` (feat)

_Plan metadata commit pending after this SUMMARY lands._

## Files Created/Modified

- `packaging/windows/MusicStreamer.spec` (164 lines) — PyInstaller onedir bundle, entry `../../musicstreamer/__main__.py`, full PySide6/winrt hidden imports, `console=False`, `upx=False`, `icon="icons/MusicStreamer.ico"`.
- `packaging/windows/runtime_hook.py` (54 lines) — verbatim from Phase 43 (D-17), only cosmetic diag-prefix rename.
- `packaging/windows/build.ps1` (173 lines) — Phase 43 driver extended with PKG-03 (Python tool), spec-entry guard, Inno Setup compile + version-from-pyproject extraction + INNO_SETUP_PATH override, BUILD_DIAG bundle/dll/installer-size diagnostic; new exit codes 4/5/6/7.
- `packaging/windows/MusicStreamer.iss` (80 lines) — pinned AppId double-brace, per-user install, AUMID match, no Desktop/Pin-to-Taskbar.
- `packaging/windows/EULA.txt` (20 lines) — LGPL/yt-dlp/streamlink/Qt/Node.js attributions.
- `packaging/windows/README.md` (120 lines) — build runbook + DI.fm + AUMID + Node.js + SmartScreen notes.
- `packaging/windows/icons/MusicStreamer.ico` (~117 KB, 6 resolutions) — generated via ImageMagick 7 `magick`.
- `.gitignore` — added `dist/installer/`, `packaging/windows/artifacts/`, `packaging/windows/build/`.

## Decisions Made

- **PKG-03 guard via Python tool only.** RESEARCH §Pattern 5 lines 762-775 originally proposed a duplicated PowerShell `Select-String` regex; the plan's checker issue 6 explicitly rejected that approach and the action body mandates `python ../../tools/check_subprocess_guard.py`. Implemented as specified — `! grep -E 'Select-String.*subprocess'` confirms no regression.
- **Smoke step skipped in build.ps1.** MusicStreamer is a GUI app and there is no headless smoke harness. The driver emits `BUILD_INFO smoke_skipped=ui_app reason='UAT covers functional verification'` and continues to Inno Setup. Plan 05 UAT will cover functional verification on the Win11 VM.
- **Diag prefix renamed.** `SPIKE_DIAG_RTHOOK` → `MUSICSTREAMER_DIAG_RTHOOK` in `runtime_hook.py` — the only edit allowed by D-17 (cosmetic, matches the build context). Action body explicitly notes this is optional but cleaner for diagnostics.
- **README scope.** Mirrors the Phase 43 `README.md` role (build runbook). Added install behavior, Node.js prerequisite, DI.fm/SmartScreen/AUMID notes per acceptance criteria.

## Deviations from Plan

None — plan executed exactly as written. The `! grep -q 'UninstallDelete' packaging/windows/MusicStreamer.iss` verification (label A) required slightly rewording an explanatory comment that originally contained the literal token `[UninstallDelete]`; the rewording preserves the same semantic explanation (D-03 user-data preservation) without violating the verification regex. This was a wording choice within Task 2 to make the plan's verification pass on first run, not a deviation from any plan directive.

## Issues Encountered

- ImageMagick `auto-resize` on Linux produced a 6-resolution .ico where `file` only reported "6 icons, 16x16, 32 bits/pixel, 32x32, 32 bits/pixel" in its summary line — `identify` confirmed all 6 entries (16/32/48/64/128/256) are present. Acceptance criterion E (per-resolution `identify` grep) passed on the first try.
- No other issues. Static guards all green.

## User Setup Required

None at this point — Plan 05 (UAT on Win11 VM) is where the user runs `.\build.ps1` and verifies the installer end-to-end. Build prerequisites (Miniforge env, Inno Setup 6.3+) are documented in `packaging/windows/README.md`.

## Next Phase Readiness

- All Wave 2 artifacts in place; depends-on Plan 01 contracts (Python guard tool + scaffolded test) are exercised and green.
- Ready for Plan 05 UAT on the Windows 11 VM. The build driver will need:
  - Miniforge env with `pygobject`, `gstreamer=1.28`, `pyinstaller>=6.19`, `pyinstaller-hooks-contrib>=2026.2`.
  - Inno Setup 6.3+ on PATH (or `INNO_SETUP_PATH` set).
  - `pyproject.toml` `[project].version` set to the release version (currently surfaced via existing version).
- AUMID + AppId invariants are in place; UAT D-21 verifications (SMTC display name, uninstall preserves user data, upgrade detection by AppId) are unblocked.

## Self-Check

- [x] `packaging/windows/MusicStreamer.spec` exists
- [x] `packaging/windows/runtime_hook.py` exists
- [x] `packaging/windows/build.ps1` exists
- [x] `packaging/windows/MusicStreamer.iss` exists
- [x] `packaging/windows/EULA.txt` exists
- [x] `packaging/windows/README.md` exists
- [x] `packaging/windows/icons/MusicStreamer.ico` exists (6-resolution, MS Windows icon resource)
- [x] `.gitignore` updated
- [x] Commit `890b93c` (Task 1) present in `git log`
- [x] Commit `ad5f8d6` (Task 2) present in `git log`
- [x] `python tools/check_spec_entry.py` exits 0
- [x] `python tools/check_subprocess_guard.py` exits 0
- [x] `pytest tests/test_spec_hidden_imports.py tests/test_pkg03_compliance.py -x -q` passes
- [x] AUMID literal match between `musicstreamer/__main__.py` and `packaging/windows/MusicStreamer.iss`

## Self-Check: PASSED

---
*Phase: 44-windows-packaging-installer*
*Completed: 2026-04-25*

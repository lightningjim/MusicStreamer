---
phase: 86-linux-flatpak-build
plan: "02"
subsystem: flatpak-first-launch
tags: [flatpak, first-launch, import, settings-export, offer-once, security]
dependency_graph:
  requires:
    - musicstreamer/settings_export.py (preview_import, commit_import, build_zip — Phase 25)
    - musicstreamer/paths.py (data_dir() for sandbox flag path)
    - musicstreamer/repo.py (Repo, db_connect)
    - musicstreamer/ui_qt/settings_import_dialog.py (layout + threading pattern)
    - musicstreamer/ui_qt/_theme.py (ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR)
  provides:
    - musicstreamer/flatpak_first_launch.py (detection + offer-once API)
    - musicstreamer/ui_qt/flatpak_import_wizard.py (Qt wizard for FP-06)
  affects:
    - PKG-LIN-FP-06 (first-launch import wizard requirement satisfied in source)
tech_stack:
  added: []
  patterns:
    - TDD (RED/GREEN commit sequence)
    - Pure module (no Qt at import time, mirrors paths.py)
    - _ImportCommitWorker(QThread) background-worker pattern (from SettingsImportDialog)
    - Phase 25 settings-export preview_import + commit_import reuse (D-04)
    - Offer-once flag file in sandbox data dir (D-03)
key_files:
  created:
    - musicstreamer/flatpak_first_launch.py
    - musicstreamer/ui_qt/flatpak_import_wizard.py
    - tests/test_flatpak_first_launch.py
  modified: []
decisions:
  - "Detection uses literal os.path.expanduser('~/.local/share/musicstreamer') constant — never paths.data_dir() which remaps to sandbox path inside Flatpak (Pitfall 7)"
  - "Wizard builds preview via _BuildPreviewWorker: opens host Repo, calls build_zip to temp ZIP, then preview_import — full Phase 25 reuse (D-04)"
  - "write_offered_flag() called on ALL dismiss paths (cancel, X, successful import) to guarantee offer-once (D-03)"
  - "Temp ZIP created in _BuildPreviewWorker.run() and deleted in _cleanup_tmp_zip() after commit — avoids orphaned temp files"
  - "reject() override calls write_offered_flag() + cleanup so the offer-once contract holds even if dialog is closed via window manager X button"
metrics:
  duration_min: 20
  completed_date: "2026-06-02"
  tasks_completed: 2
  files_changed: 3
---

# Phase 86 Plan 02: First-Launch Flatpak Import Wizard Summary

Pure detection module + Qt wizard for Flatpak FP-06: literal host-path detection via narrow `:ro` mount, offer-once flag in sandbox data dir, Phase 25 settings-export ZIP import reuse.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Pure first-launch detection module + offer-once flag | `413b218` | `musicstreamer/flatpak_first_launch.py`, `tests/test_flatpak_first_launch.py` |
| 1 (RED) | TDD failing tests | `39491a3` | `tests/test_flatpak_first_launch.py` |
| 2 | Flatpak import wizard Qt dialog | `17b8736` | `musicstreamer/ui_qt/flatpak_import_wizard.py` |

## What Was Built

### Task 1: `musicstreamer/flatpak_first_launch.py` (pure module)

Module-level constants for the literal host path:
```python
_HOST_DATA_DIR = os.path.expanduser("~/.local/share/musicstreamer")
_HOST_DB = os.path.join(_HOST_DATA_DIR, "musicstreamer.sqlite3")
```

Public API:
- `has_unsandboxed_data()` — `os.path.isfile(_HOST_DB)` — never routed through `paths.data_dir()`
- `import_offered_flag_path()` — returns `paths.data_dir() + "/.flatpak-import-offered"` (sandbox writable path)
- `should_offer_import_wizard()` — True iff host DB exists AND flag absent
- `write_offered_flag()` — idempotent flag creation using `open(..., "a").close()`

11 unit tests covering all five behaviors from the plan's `<behavior>` block — all pass.

### Task 2: `musicstreamer/ui_qt/flatpak_import_wizard.py` (Qt dialog)

`_BuildPreviewWorker(QThread)`:
- Opens a `Repo` against `_HOST_DATA_DIR` (the `:ro` mount)
- Calls `settings_export.build_zip(host_repo, tmp_zip)` to export to a temp ZIP
- Calls `settings_export.preview_import(tmp_zip, sandbox_repo)` → `ImportPreview`
- T-86-04: `_validate_zip_members()` is called by `preview_import` internally

`_ImportCommitWorker(QThread)`:
- Mirrors `SettingsImportDialog._ImportCommitWorker` exactly
- Calls `settings_export.commit_import(preview, repo, mode)` with QueuedConnection signals

`FlatpakImportWizard(QDialog)`:
- Layout: loading label → mode radio (Merge/Replace All) + replace warning → summary counts + detail tree → button box
- `write_offered_flag()` called on: cancel button, window X button (via `reject()` override), successful commit
- `_cleanup_tmp_zip()` called on all exit paths to remove the temp ZIP
- Constructor accepts `sandbox_db_path` + optional `toast_callback` — invokable from first-launch and from a menu

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test commit) | `39491a3` | test(86-02): add failing tests |
| GREEN (implementation) | `413b218` | feat(86-02): implement module |

## Verification Results

- `pytest tests/test_flatpak_first_launch.py -x` exits 0 — 11/11 passed
- `grep -c "from PySide6" musicstreamer/flatpak_first_launch.py` → 0 (pure module, no Qt)
- `ast.parse(flatpak_import_wizard.py)` succeeds
- `preview_import` + `commit_import` present in wizard source (Phase 25 reuse, D-04)
- `write_offered_flag` present in wizard source (offer-once on all dismiss paths, D-03)
- No `zipfile.extractall` or `.extract(` AST calls in wizard (no `_validate_zip_members` bypass, T-86-04)
- `_ImportCommitWorker` + `QThread` count > 0 (background-worker pattern reused)

## Deviations from Plan

### Auto-added: _BuildPreviewWorker

**[Rule 2 - Missing critical functionality] Added separate background worker for preview build**
- **Found during:** Task 2 implementation
- **Issue:** The plan says "wizard builds it on the fly" but doesn't specify threading. Building the preview synchronously on the main thread would block the UI while opening a Repo against the host DB and calling `build_zip` — potentially multi-second for large libraries.
- **Fix:** Added `_BuildPreviewWorker(QThread)` that builds the preview in the background. The wizard shows a "Scanning host settings…" loading label until ready, then populates the import UI.
- **Files modified:** `musicstreamer/ui_qt/flatpak_import_wizard.py`
- **Commit:** `17b8736` (included in Task 2 commit)

### Auto-added: `reject()` override

**[Rule 2 - Missing critical functionality] Override `reject()` to guarantee offer-once on all dismiss paths**
- **Found during:** Task 2 implementation
- **Issue:** QDialog can be closed via the window manager X button (which calls `reject()` directly, bypassing `_on_cancel`). Without the override, the offer-once flag would not be written.
- **Fix:** Overrode `reject()` to call `write_offered_flag()` + `_cleanup_tmp_zip()` before delegating to `super().reject()`. The `_on_cancel` slot also calls these before `self.reject()`, but since `reject()` guards with `os.path.isfile` check via `open(..., "a").close()` (idempotent), double-calling is safe.
- **Commit:** `17b8736`

## Known Stubs

None. Both files wire real behavior — detection probes the filesystem, wizard wires to Phase 25 import path.

## Threat Flags

No new network endpoints, auth paths, or filesystem trust boundaries beyond those explicitly modeled in the plan's `<threat_model>`:

| Modeled Threat | Status |
|---|---|
| T-86-04: ZIP path traversal | Mitigated — all import routes through `preview_import` + `commit_import` which call `_validate_zip_members()` internally |
| T-86-05: Copy-don't-delete | Mitigated — host mount is `:ro`; wizard only reads from `_HOST_DATA_DIR`, writes only to sandbox via `commit_import` |
| T-86-06: Offer-once flag bypass | Accepted — deleting the flag re-triggers the offer, no privilege gain |

## Self-Check: PASSED

| Item | Result |
|------|--------|
| `musicstreamer/flatpak_first_launch.py` | FOUND |
| `musicstreamer/ui_qt/flatpak_import_wizard.py` | FOUND |
| `tests/test_flatpak_first_launch.py` | FOUND |
| `86-02-SUMMARY.md` | FOUND |
| commit `39491a3` (RED: tests) | FOUND |
| commit `413b218` (GREEN: detection module) | FOUND |
| commit `17b8736` (Task 2: wizard) | FOUND |

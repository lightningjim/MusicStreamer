---
phase: 15-audioaddict-import
plan: 02
subsystem: ui
tags: [gtk4, adw, notebook, audioaddict, import, threading]

# Dependency graph
requires:
  - phase: 15-01
    provides: aa_import.fetch_channels, aa_import.import_stations backend
provides:
  - Unified tabbed ImportDialog (Gtk.Notebook) with YouTube Playlist and AudioAddict tabs
  - AudioAddict import UI: API key entry, quality toggle, spinner + progress feedback, error handling
  - PLS-to-direct-URL resolution at import time
affects: [ui, 13-radio-browser-discovery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thread-local DB connection in import worker (open db_connect() in thread, close in finally)"
    - "Module-level tab index for cross-instance tab persistence"
    - "GLib.idle_add for all GTK state updates from worker threads"

key-files:
  created: []
  modified:
    - musicstreamer/ui/import_dialog.py
    - musicstreamer/aa_import.py

key-decisions:
  - "Set Adw.ToggleGroup active name after all toggles appended — order matters"
  - "Resolve PLS to direct stream URL (File1) at fetch time in aa_import.py, not in the dialog"
  - "Module-level _last_tab_index persists across dialog instances within the same process"

patterns-established:
  - "Thread-local DB: open db_connect() inside worker thread, wrap in try/finally to close"
  - "GLib.idle_add for all GTK updates from background threads"

requirements-completed: [IMPORT-02, IMPORT-03]

# Metrics
duration: multi-session
completed: 2026-04-03
---

# Phase 15 Plan 02: ImportDialog Tabbed Layout Summary

**Tabbed ImportDialog (Gtk.Notebook) with fully wired AudioAddict tab: API key entry, Hi/Med/Low quality toggle, threaded import worker with spinner + progress, and PLS-to-direct-URL resolution**

## Performance

- **Duration:** multi-session (with human-verify checkpoint)
- **Started:** 2026-04-03
- **Completed:** 2026-04-03
- **Tasks:** 2 (1 auto + 1 human-verify)
- **Files modified:** 2

## Accomplishments

- Refactored ImportDialog to Gtk.Notebook with YouTube Playlist and AudioAddict tabs; YouTube tab fully preserved
- AudioAddict tab: API key entry (pre-fills from settings), Hi/Med/Low quality toggle (persisted), Import Stations button with spinner + real-time progress label, inline error handling, Done button after success
- PLS resolution fix: aa_import.fetch_channels now resolves .pls URLs to direct stream URLs (File1) at fetch time so GStreamer can play them directly
- Human verification approved: stations import and play correctly

## Task Commits

1. **Task 1: Refactor ImportDialog to tabbed layout with AudioAddict tab** - `7929a7d` (feat)
2. **Post-checkpoint fix: Resolve PLS to direct stream URL** - `1411e6e` (fix)
3. **Task 2: Human verify** - approved by user (no code commit)

## Files Created/Modified

- `musicstreamer/ui/import_dialog.py` - Refactored to Gtk.Notebook; YouTube tab extracted to `_build_yt_tab()`; AudioAddict tab added via `_build_aa_tab()` with full import flow
- `musicstreamer/aa_import.py` - Added `_resolve_pls()` helper; `fetch_channels` now resolves PLS URLs to direct stream URLs before returning

## Decisions Made

- Resolve PLS URLs in `aa_import.fetch_channels` rather than in the dialog — keeps UI code free of HTTP logic and makes the returned channel dicts immediately playable
- Use module-level `_last_tab_index` for tab persistence — simplest approach, works within a process session
- Set `Adw.ToggleGroup.set_active_name()` only after all toggles are appended — GTK requirement

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PLS URLs not playable by GStreamer**
- **Found during:** Post-Task 1 human verify
- **Issue:** AudioAddict returns `.pls` playlist URLs; GStreamer cannot open these as a stream directly, so imported stations would not play
- **Fix:** Added `_resolve_pls(pls_url)` in `aa_import.py` that fetches the PLS file and extracts `File1=` to return the direct stream URL. Called inside `fetch_channels` before returning channel dicts.
- **Files modified:** `musicstreamer/aa_import.py`
- **Verification:** Human verified stations play after import
- **Committed in:** `1411e6e`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix — without PLS resolution, imported stations are silent. No scope creep.

## Issues Encountered

- PLS URL indirection not anticipated in plan; resolved inline before proceeding to human verify

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AudioAddict import fully functional; stations appear grouped by provider after import
- Phase 13 (Radio-Browser Discovery) can proceed independently
- No blockers

---
*Phase: 15-audioaddict-import*
*Completed: 2026-04-03*

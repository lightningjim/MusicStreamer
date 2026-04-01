---
phase: 13-radio-browser-discovery
plan: "02"
subsystem: ui
tags: [gtk4, adwaita, radio-browser, discovery, preview]

# Dependency graph
requires: ["13-01"]
provides:
  - DiscoveryDialog modal window with search, tag/country filters, preview, save
  - Discover button in main window header bar
  - Preview-with-resume playback behavior
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - PLS/M3U stream URL resolution via _resolve_stream_url helper
    - Active play button tracking for multi-preview state management
    - GLib.markup_escape_text for Radio-Browser station names with &, <, > chars

key-files:
  created:
    - musicstreamer/ui/discovery_dialog.py
  modified:
    - musicstreamer/ui/main_window.py

key-decisions:
  - "url_resolved preferred over url from Radio-Browser API — url is often a PLS/M3U playlist"
  - "PLS/M3U files resolved to direct stream URLs before preview or save"
  - "Active play button tracked directly (self._active_play_btn) instead of walking widget tree"
  - "GLib.markup_escape_text applied to all Radio-Browser strings displayed in ActionRows"

patterns-established:
  - "_resolve_stream_url helper for PLS/M3U → direct stream URL resolution"

requirements-completed: [DISC-01, DISC-02, DISC-03, DISC-04]

# Metrics
duration: ~20min
completed: 2026-03-31
---

# Phase 13 Plan 02: Discovery Dialog UI Summary

**DiscoveryDialog with live search, tag/country dropdowns, preview-with-resume, and save-to-library — human-verified end-to-end**

## Performance

- **Duration:** ~20 min (including human verification and bug fixes)
- **Completed:** 2026-03-31
- **Tasks:** 3 (2 auto, 1 human-verify)
- **Files created:** 1 (discovery_dialog.py ~400 lines)
- **Files modified:** 1 (main_window.py)

## Accomplishments

- DiscoveryDialog (Adw.Window) with search entry, tag/country Gtk.DropDown filters
- Live search with 500ms GLib.timeout_add debounce
- Results as Adw.ActionRow with escaped markup, country/tags/bitrate subtitle
- Preview playback with play/stop per-row buttons, auto-resume on dialog close
- Save to library with duplicate URL detection (Adw.MessageDialog error)
- Provider name extracted from Radio-Browser network field or homepage domain
- Discover button in main window header bar

## Task Commits

1. **Task 1: DiscoveryDialog with search, filters, preview, save** - `74bf48d` (feat)
2. **Task 2: Wire Discover button into main window** - `3f6fc10` (feat)
3. **Task 3: Human verification** - approved by user

## Post-commit Fixes

1. `set_width_request` → `set_size_request(140, -1)` on Gtk.DropDown (no such method)
2. GLib.markup_escape_text for station names containing &, <, > characters
3. Use `url_resolved` instead of `url` from Radio-Browser API (avoids PLS/M3U files)
4. Add `_resolve_stream_url()` helper to parse PLS/M3U playlists to direct stream URLs
5. Track `_active_play_btn` directly instead of walking widget tree (fixes multi-preview button state bug)

## Files Created/Modified

- `musicstreamer/ui/discovery_dialog.py` — New: DiscoveryDialog with full search/filter/preview/save flow
- `musicstreamer/ui/main_window.py` — Added Discover button + _open_discovery method

## Deviations from Plan

### Post-execution Fixes

**1. [API] Gtk.DropDown.set_width_request does not exist**
- **Fix:** Use `set_size_request(140, -1)` instead

**2. [Markup] Radio-Browser station names contain &, <, > characters**
- **Fix:** Apply GLib.markup_escape_text to title and subtitle in ActionRow

**3. [Playback] Radio-Browser url field returns PLS/M3U playlists, not direct streams**
- **Fix:** Prefer url_resolved; add _resolve_stream_url helper for PLS/M3U parsing

**4. [UI State] Clicking preview on second station leaves first button in stop state**
- **Fix:** Track _active_play_btn directly, reset it when switching previews

---

**Total deviations:** 4 post-execution fixes
**Impact on plan:** All functional — required for correct behavior with real Radio-Browser data.

## User Setup Required

None.

## Phase Completion

Phase 13 (Radio-Browser Discovery) is now complete. Both plans delivered:
- Plan 01: Data layer (API client, repo methods, 17 tests)
- Plan 02: UI layer (discovery dialog, main window wiring, human-verified)

All requirements (DISC-01 through DISC-04) satisfied.

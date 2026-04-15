# Phase 46 — Notes for planner

Pre-planning scope notes. Planner should fold these into 46-CONTEXT.md / 46-01-PLAN.md.

## Source

- 40.1-UI-REVIEW.md (21/24)
- 45-UI-REVIEW.md (23/24)
- User observation 2026-04-14: `QThread: Destroyed while thread '' is still running` warning on app launch with YT station auto-fetch

## Items in scope

1. **Theme tokens** — centralize hardcoded error-red `#c0392b` (6+ sites across `import_dialog.py`, `edit_station_dialog.py`, `cookie_import_dialog.py`, `accent_color_dialog.py`) into a theme module. Blocks future dark-mode work.

2. **EditStationDialog fetch status polish:**
   - Distinguish "AA URL, use Choose File" from "truly unsupported URL" in the fetch status label. Today both paths emit `"Fetch not supported for this URL"` from `_on_logo_fetched`, even when the URL IS recognized as AA but channel-key can't be derived.
   - Auto-clear `_logo_status` label after 3s or on next `textChanged` (currently sticks on "Fetched" indefinitely).
   - Add fetch-in-flight spinner (today only the "Fetching…" text changes, no visual indicator).

3. **Logo empty-state glyph** — when a station has no logo, the preview QLabel is blank. Show a dimmed music-note placeholder so the 64×64 slot is never empty.

4. **Station icon size constant** — export `STATION_ICON_SIZE = 32` from `musicstreamer/ui_qt/_art_paths.py` and replace the three hardcoded `QSize(32, 32)` call sites to prevent drift.

5. **`_LogoFetchWorker` teardown warning** — `QThread: Destroyed while thread '' is still running` appears when Edit Station is closed within 2s of opening a YT/AA station (the auto-fetch is still running; `_shutdown_logo_fetch_worker`'s 2s cap expires before yt_dlp returns). Fix: reparent the worker to `QApplication.instance()` (or similar long-lived object) so it can outlive the dialog and self-terminate via the stale-token branch. Drop the 2s bounded wait in `_shutdown_logo_fetch_worker` — token logic already handles stale emissions + tmp cleanup. Benign but noisy warning; folding here to keep core phase 40.1 stable.

## Items out of scope (deferred further)

- Discard-during-fetch 2s hang cue (minor, not worth scope)
- Inline-label dismiss affordance (would require rethinking the status label UX)
- `now_playing_panel.py` local `_FALLBACK_ICON` constant — 45 audit flagged this but it's a different code path (cover-art fallback, not station-logo fallback) so leave alone

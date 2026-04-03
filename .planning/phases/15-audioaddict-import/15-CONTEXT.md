# Phase 15: AudioAddict Import - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Users bulk-import AudioAddict network channels via API key with quality selection. The import is triggered from a unified Import dialog (shared with YouTube import, tab-switched). All supported AudioAddict networks are imported at once — no network selection step. Stations already in the library (URL match) are silently skipped.

</domain>

<decisions>
## Implementation Decisions

### Entry Point
- **D-01:** The existing "Import" button in the header bar is expanded into a **unified Import dialog** with two tabs: "YouTube Playlist" and "AudioAddict". Both sources share one dialog — the `ImportDialog` class is refactored to support tab switching rather than creating a second dialog class.

### API Key
- **D-02:** API key is **persisted in SQLite** using the existing app settings/config pattern (same mechanism as volume persistence). The AudioAddict tab pre-fills the key on open if previously saved. User only types it once.

### Network Scope
- **D-03:** Import **all supported networks at once** — no network selection step. User sees a single "Import" action; if they want to remove channels from a particular network, they delete stations after import. Keeps the flow minimal.

### Quality Selection
- **D-04:** Quality is selected via an **`Adw.ToggleGroup`** with three buttons: Hi | Med | Low. Matches the existing Stations/Favorites toggle pattern in the app. Default: Hi.

### Progress Feedback
- **D-05:** Import runs with real-time progress feedback matching Phase 14 pattern: spinner + label updating as each station is processed ("3 imported, 1 skipped"). Duplicate stations (URL match) are counted in "skipped" — quiet skip, no error shown.

### Claude's Discretion
- Exact AudioAddict API endpoint, network identifiers, and PLS URL construction — researcher must verify against the live API before any code is written (research flag in STATE.md)
- How to handle invalid/expired API key (inline error label in the dialog)
- Whether quality setting persists between sessions (reasonable to save alongside the API key)
- Dialog widget hierarchy and sizing within the new tabbed structure
- How the existing `ImportDialog` is refactored to accommodate the tab view

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above and REQUIREMENTS.md (IMPORT-02, IMPORT-03).

### Codebase
- `musicstreamer/ui/import_dialog.py` — Existing YouTube import dialog; Phase 15 refactors this to add an AudioAddict tab
- `musicstreamer/ui/discovery_dialog.py` — Dialog structure reference (Adw.Window, threading, GLib.idle_add pattern)
- `musicstreamer/ui/main_window.py` — Header bar wiring; `import_btn` at line 41–43; `_open_import` at line 832
- `musicstreamer/repo.py` — `create_station()` for saving imported stations; URL uniqueness check; settings/config storage pattern (check for existing volume/settings keys)
- `musicstreamer/models.py` — Station and Provider dataclasses
- `musicstreamer/yt_import.py` — Import backend pattern (scan + import_stations functions); AudioAddict backend should follow same structure

### Research Flag (from STATE.md)
- **Verify `api.audioaddict.com/v1/{network}/channels` endpoint, exact network identifiers, and PLS auth pattern against a live account before writing any code.** The researcher must confirm: (1) correct API base URL, (2) network slug list (e.g., "di", "radiotunes", "jazzradio", "rockradio", "classicalradio"), (3) how the API key is passed (query param? header?), (4) the PLS stream URL format for each quality tier.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ImportDialog` (`ui/import_dialog.py`): Existing YouTube import dialog — Phase 15 extends this with an AudioAddict tab rather than creating a second class
- `DiscoveryDialog` (`ui/discovery_dialog.py`): Threading model reference (daemon thread + GLib.idle_add)
- `repo.py` settings storage: Existing pattern for persisting volume — same mechanism for API key and quality preference
- `yt_import.py`: Backend module pattern (`scan_playlist`, `import_stations`) — AudioAddict backend (`aa_import.py` or similar) should mirror this structure

### Established Patterns
- Modal dialogs: `Adw.Window` subclasses with `set_transient_for` + `set_modal(True)`
- Background work: daemon threads call `GLib.idle_add(callback, result)` to update UI
- `Adw.ToggleGroup`: Already used for Stations/Favorites toggle — same pattern for Hi/Med/Low quality
- Settings persistence: Check `repo.py` for how `volume` is stored; use same mechanism for `audioaddict_api_key` and `audioaddict_quality`

### Integration Points
- `import_btn` in `main_window.py` header → `_open_import` → unified `ImportDialog` (refactored)
- AudioAddict tab calls `repo.create_station()` for each imported channel
- After import completes, triggers `main_window.reload_list()` to refresh the station list
- API key + quality saved to SQLite settings table via `repo` after successful import (or on change)

</code_context>

<specifics>
## Specific Ideas

- The unified Import dialog defaults to whichever tab was last used (or YouTube as default on first open)
- Quality default is Hi — most likely what a user paying for AudioAddict wants
- The AudioAddict tab flow mirrors YouTube tab: enter credentials → "Import" button → spinner + progress label → done

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 15-audioaddict-import*
*Context gathered: 2026-04-03*

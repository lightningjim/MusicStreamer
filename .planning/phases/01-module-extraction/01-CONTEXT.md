# Phase 1: Module Extraction - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Split the 512-line `main.py` monolith into a `musicstreamer/` Python package with discrete modules. Zero user-visible behavior change — the app must run identically after the split. This phase creates the clean structural homes that Phases 2–4 will build features into.

</domain>

<decisions>
## Implementation Decisions

### Project layout
- Use a `musicstreamer/` package subdirectory (not flat files in root)
- Structure:
  ```
  MusicStreamer/
  ├── musicstreamer/
  │   ├── __init__.py
  │   ├── __main__.py       ← entry point
  │   ├── models.py         ← Station, Provider dataclasses
  │   ├── repo.py           ← Repo class, all SQLite access
  │   ├── player.py         ← GStreamer Player (extracted from MainWindow)
  │   ├── assets.py         ← asset file copying, path management
  │   └── ui/
  │       ├── __init__.py
  │       ├── main_window.py
  │       ├── edit_dialog.py
  │       └── station_row.py   ← StationRow widget (extracted now, Phase 2 will touch heavily)
  ├── org.example.Streamer.desktop
  └── stations.json
  ```
- No `main.py` shim — entry point is `musicstreamer/__main__.py`

### Launch method
- App is launched via `python3 -m musicstreamer`
- Update `org.example.Streamer.desktop` to use `python3 -m musicstreamer`
- Remove top-level `main.py` entirely (or keep as a one-liner shim if the .desktop update is deferred)

### Test scaffolding
- Add pytest to the project alongside the extraction
- Write basic smoke tests for `Repo` (create/list/get station) and `models` (dataclass instantiation)
- Tests go in `tests/` directory
- Tests verify the extraction didn't break data layer behavior
- GTK/GStreamer UI code is NOT unit tested (GTK requires a display; defer to manual verification)

### Claude's Discretion
- Exact contents of `__init__.py` files
- Import structure and ordering within modules
- How to handle `APP_ID`, `DATA_DIR`, `DB_PATH`, `ASSETS_DIR` constants (module-level in a `constants.py` or inline in relevant modules)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project requirements
- `.planning/REQUIREMENTS.md` — CODE-01 acceptance criteria
- `.planning/ROADMAP.md` — Phase 1 success criteria (app runs identically, no circular imports, each module readable in isolation)

### Existing codebase
- `main.py` — the full monolith being split; read line ranges per module before extracting
- `.planning/codebase/ARCHITECTURE.md` — layer boundaries and data flow already analyzed
- `.planning/codebase/CONVENTIONS.md` — naming and style patterns to preserve
- `.planning/research/ARCHITECTURE.md` — recommended component split with Player extraction rationale

No external ADRs or design docs — all requirements captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main.py` lines 70–86: `Station` and `Provider` dataclasses → move to `models.py` as-is
- `main.py` lines 88–180: `Repo` class → move to `repo.py` as-is
- `main.py` lines 182–197: `copy_asset_for_station()` and asset path helpers → move to `assets.py`
- `main.py` lines 411–447: `_resolve_stream_url()` and GStreamer playbin setup → extract to `player.py`
- `main.py` lines 200–282: `EditStationDialog` → move to `ui/edit_dialog.py`
- `main.py` lines 358–493: `MainWindow` → move to `ui/main_window.py`; extract `StationRow` to `ui/station_row.py`

### Established Patterns
- Single SQLite connection passed at construction time (Repo takes `conn` in `__init__`)
- Dataclasses are immutable — no setters, no mutation after creation
- GTK4 signal-based event handling — preserve `connect()` patterns
- `shutil.copy2` for asset file management

### Integration Points
- `App.do_activate()` (lines 499–506) instantiates `Repo`, creates `MainWindow` — this becomes the wiring point in `__main__.py`
- `MainWindow._play_row()` → `_play_station()` → GStreamer playbin — this is where `Player` extraction hooks in
- `EditStationDialog._save()` callback pattern → stays the same, just in a different file

</code_context>

<specifics>
## Specific Ideas

- StationRow extracted now because Phase 2 (filtering) will need to add filter-function support to individual rows — cleaner if it's already its own class
- The `.desktop` file (`org.example.Streamer.desktop`) is currently empty and needs to be properly populated with `python3 -m musicstreamer` as the exec command

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-module-extraction*
*Context gathered: 2026-03-18*

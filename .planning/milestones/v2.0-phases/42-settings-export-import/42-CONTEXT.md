# Phase 42: Settings Export/Import - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

User can export all stations, streams, favorites, and config to a portable `.zip` file and import it on another machine with merge control. Export/Import accessible from the hamburger menu (placeholders already exist in main_window.py lines 100–107).

</domain>

<decisions>
## Implementation Decisions

### Export Content & Structure
- **D-01:** Full DB dump — settings.json contains all stations, streams (station_streams), favorites (both ICY track favorites and station star flags), providers, and settings table entries.
- **D-02:** Station logos stored as `logos/<sanitized_station_name>.<ext>` in the ZIP — human-readable, filesystem-safe names.
- **D-03:** Include `last_played_at` timestamps — full fidelity round-trip preserves recently-played section on the target machine.
- **D-04:** Include `is_favorite` station star flags alongside ICY track favorites table.
- **D-05:** Cookies (`cookies.txt`), Twitch OAuth tokens (`twitch-token.txt`), and AudioAddict API keys are explicitly excluded from the export (SYNC-02 credential risk).

### Import Merge Behavior
- **D-06:** Merge key is **stream URL** — match imported stations against existing by any URL in `station_streams`. Aligns with existing `Repo.station_exists_by_url()`.
- **D-07:** Import dialog has a **Merge / Replace All toggle** (radio buttons or segmented control), defaulting to Merge. "Merge" adds new + updates matches. "Replace All" wipes library and restores from ZIP.
- **D-08:** On URL match in Merge mode, **replace everything** on the existing station — name, provider, tags, streams list, logo, ICY flag, star status all update from import.
- **D-09:** Favorites merge as **union** — `INSERT OR IGNORE` by `(station_name, track_title)`. Existing favorites untouched, new ones added. (Replace All mode replaces favorites too.)

### Summary Dialog UX
- **D-10:** Import summary dialog shows **counts + expandable list** — "12 added, 3 replaced, 1 skipped, 0 errors" at top with an expandable section listing each station and its action (added/replaced/skipped).
- **D-11:** **All-or-nothing** — no per-station cherry-picking. User sees the summary and clicks OK or Cancel.
- **D-12:** Malformed/invalid ZIPs get a **toast + abort** — "Invalid settings file" toast, no partial import. Consistent with existing `ToastOverlay` pattern.

### File Picker & Defaults
- **D-13:** Export produces a standard `.zip` file with default filename `musicstreamer-export-YYYY-MM-DD.zip`.
- **D-14:** File dialog defaults to **user's Documents folder** — `QStandardPaths::DocumentsLocation` resolves correctly on both Linux and Windows.

### Claude's Discretion
- JSON schema design within settings.json (field names, nesting structure)
- Station name sanitization strategy for logo filenames in the ZIP
- Exact layout of the import summary dialog (widget choices, sizing)
- Whether "Replace All" mode prompts a confirmation before wiping

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §SYNC — SYNC-01 through SYNC-05 define the export/import contract

### Phase 44 Cross-Platform UAT
- `.planning/ROADMAP.md` §Phase 44 success criteria #6 — Linux↔Windows settings-export round-trip UAT (export on Linux → import on Windows and reverse)

### Existing Code
- `musicstreamer/repo.py` — `Repo` class with all data accessors (`list_stations`, `list_streams`, `list_favorites`, `get_setting`, `station_exists_by_url`)
- `musicstreamer/models.py` — `Station`, `StationStream`, `Favorite`, `Provider` dataclasses
- `musicstreamer/paths.py` — `platformdirs`-based path resolution (data_dir, assets_dir, cookies_path, twitch_token_path)
- `musicstreamer/ui_qt/main_window.py` lines 100–107 — disabled hamburger menu placeholders for Export/Import Settings

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Repo.list_stations()` / `list_streams()` / `list_favorites()` / `get_setting()` — all data accessors for export
- `Repo.station_exists_by_url()` — merge key lookup already exists
- `Repo.insert_station()` / `insert_stream()` / `add_favorite()` / `set_setting()` — all write accessors for import
- `ToastOverlay` widget — error display pattern for invalid ZIPs
- `paths.assets_dir()` — resolves station art directory cross-platform

### Established Patterns
- Hamburger menu actions: `self._menu.addAction("Label")` + `.triggered.connect(self._handler)` — enable existing placeholders
- File dialogs: `QFileDialog.getSaveFileName` / `getOpenFileName` used in cookie import dialog
- Thread workers: `ThreadPoolExecutor` pattern from AA import for potentially slow ZIP operations
- INSERT OR IGNORE for dedup: used in favorites and station import already

### Integration Points
- `main_window.py` lines 100–107: enable `act_export` and `act_import_settings`, connect to new handlers
- `Repo` class: may need new bulk-export and bulk-import methods
- `paths.py`: `assets_dir()` for resolving logo file paths during export/import

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 42-settings-export-import*
*Context gathered: 2026-04-16*

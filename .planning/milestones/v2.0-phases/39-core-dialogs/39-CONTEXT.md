# Phase 39: Core Dialogs - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Port the four remaining dialog-based features from v1.5 to Qt: EditStationDialog (station CRUD with multi-stream management), DiscoveryDialog (Radio-Browser.info search/preview/save), ImportDialog (YouTube + AudioAddict tabbed import), and the stream picker dropdown on the now-playing panel. All backend modules (`radio_browser.py`, `yt_import.py`, `aa_import.py`, `repo.py`) are stable and reused as-is — this phase is pure UI work.

Out of scope for Phase 39 (explicit cut-lines — DO NOT PULL FORWARD):
- AccountsDialog (Twitch OAuth), YouTube cookie import, accent color picker, hamburger menu → Phase 40 (UI-08..UI-11)
- Platform media keys → Phase 41 (MEDIA-01..05)
- Settings export/import → Phase 42 (SYNC-01..05)

</domain>

<decisions>
## Implementation Decisions

### EditStation Dialog
- **D-01:** Single `EditStationDialog(QDialog)` containing all fields — no sub-dialog for streams. Fields: station name, URL, editable provider combo, tag chips (FlowLayout), ICY disable toggle (`QCheckBox`), stream management table, delete button.
- **D-02:** Provider picker is a `QComboBox` with `setEditable(True)`. Populated from `repo.list_providers()`. Typed value takes precedence over dropdown selection (matches v1.5 key decision: "new_provider_entry takes precedence").
- **D-03:** Tag editor reuses Phase 38's `FlowLayout` widget. Existing tags from the DB shown as toggleable chips (selected = assigned to this station). A `QLineEdit` + "Add" button below for creating new tags inline.
- **D-04:** Multi-stream management via `QTableWidget` inside the dialog. Columns: URL, Quality (QComboBox: hi/med/low/custom), Codec, Position. Buttons beside the table: Add, Remove, Move Up, Move Down. Maps to `repo.list_streams()`, `repo.insert_stream()`, `repo.update_stream()`, `repo.reorder_streams()`.
- **D-05:** Delete button at bottom of dialog with a confirmation prompt. Blocked (disabled or hidden) when the station is currently playing — check `player.current_station`.
- **D-06:** ICY metadata toggle is a `QCheckBox` ("Disable ICY metadata"). Maps to `station.icy_disabled` field.
- **D-07:** YouTube thumbnail auto-fetch on URL paste (daemon thread + signal, same pattern as v1.5). AudioAddict logo auto-fetch on URL paste using `_normalize_aa_image_url` pattern.
- **D-08:** Edit button inserted on the now-playing panel at the `# Plan 39` marker (line 174). `QToolButton` with `document-edit-symbolic` icon, enabled only when a station is playing.

### Discovery Dialog
- **D-09:** `DiscoveryDialog(QDialog)` with search bar at top (QLineEdit + tag/country filter QComboBoxes + Search button). Results in a `QTableView` below showing name, tags, country, bitrate columns.
- **D-10:** Tag and country combos populated on dialog open via `radio_browser.fetch_tags()` and `radio_browser.fetch_countries()` on a daemon thread (non-blocking).
- **D-11:** Per-row play/stop toggle icon in the results table. Clicking triggers `player.play()` with a temporary station object (not saved to library). Playing a preview stops any currently-playing library station — reuses the main Player instance.
- **D-12:** Per-row "Save" button/icon. Saves to library via `repo.insert_station()` with the resolved stream URL (`url_resolved` preferred over `url` — matches v1.5 key decision). Button disables after save (no duplicate adds). Toast feedback: "Saved [name] to library".
- **D-13:** Search runs on a daemon thread. UI shows a loading indicator (spinner or indeterminate progress bar) while the search request is in-flight.

### Import Dialog
- **D-14:** `ImportDialog(QDialog)` with `QTabWidget` — two tabs: "YouTube" and "AudioAddict".
- **D-15:** YouTube tab flow: URL `QLineEdit` + "Scan" button → scan runs on daemon thread → results shown as checkable `QListWidget` (each row: checkbox + title) → "Import" button imports checked entries via `yt_import.import_stations()`. Matches ROADMAP success criterion #3.
- **D-16:** AudioAddict tab flow: API key `QLineEdit` + quality `QComboBox` (hi/med/low) → "Import" button → `aa_import.fetch_channels_multi()` on daemon thread → `aa_import.import_stations_multi()` with progress callback.
- **D-17:** Inline `QProgressBar` + status label within each tab. YouTube: determinate during scan (if entry count known) then determinate during import (N/M). AudioAddict: indeterminate during channel fetch, determinate during station+logo import. Inputs disabled during active import.
- **D-18:** Error handling: invalid API key → inline error label ("Invalid API key"); network errors → toast; empty playlist → inline message ("No live streams found").

### Stream Picker (Now-Playing Panel)
- **D-19:** `QComboBox` on the now-playing panel's control row (at the Plan 39 marker). Shows the current stream's label/quality (e.g., "hi — AAC", "med — MP3"). Dropdown lists all streams for the playing station via `repo.list_streams(station_id)`.
- **D-20:** Hidden (`setVisible(False)`) when the current station has only 1 stream. Appears only for multi-stream stations.
- **D-21:** Changing selection triggers `player.play(station, stream=selected_stream)` to switch streams.
- **D-22:** Failover sync: when `player.failover` signal fires with a non-None stream, the combo box selection updates to reflect the now-active stream. Uses `blockSignals(True)` during the programmatic update to avoid re-triggering play.

### Claude's Discretion
- Exact dialog dimensions and minimum sizes
- QTableWidget column widths and resize policies
- Whether the Discovery results table is read-only or selectable
- Stream table styling (alternating row colors, header style)
- Edit dialog field ordering within the form layout
- Whether to show station art preview in the edit dialog
- Loading indicator style (spinner widget vs indeterminate progress bar)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` § "Phase 39: Core Dialogs" — goal, success criteria, depends on Phase 38
- `.planning/REQUIREMENTS.md` § UI-05 (EditStationDialog), UI-06 (DiscoveryDialog), UI-07 (ImportDialog), UI-13 (stream picker)

### Phase 37/38 output to build on
- `musicstreamer/ui_qt/now_playing_panel.py` — line 174 `# Plan 39: insert edit button + stream picker here`
- `musicstreamer/ui_qt/flow_layout.py` — `FlowLayout` widget for tag chips (reuse in EditStation)
- `musicstreamer/ui_qt/toast.py` — `ToastOverlay` for feedback toasts
- `musicstreamer/ui_qt/main_window.py` — signal wiring patterns, dialog launch patterns
- `musicstreamer/ui_qt/station_list_panel.py` — station selection context for "edit current station"
- `musicstreamer/ui_qt/icons/` + `icons.qrc` — icon pattern; Phase 39 adds `document-edit-symbolic.svg`

### Backend modules (stable, reuse as-is)
- `musicstreamer/radio_browser.py` — `search_stations()`, `fetch_tags()`, `fetch_countries()` — all blocking, call from daemon threads only
- `musicstreamer/yt_import.py` — `is_yt_playlist_url()`, `scan_playlist()`, `import_stations()` — blocking
- `musicstreamer/aa_import.py` — `fetch_channels_multi()`, `import_stations_multi()` — blocking, multi-quality with logo download
- `musicstreamer/repo.py` — `insert_station()`, `update_station()`, `delete_station()`, `list_streams()`, `insert_stream()`, `update_stream()`, `reorder_streams()`, `list_providers()`, `station_exists_by_url()`
- `musicstreamer/models.py` — `Station`, `StationStream`, `Provider` dataclasses
- `musicstreamer/assets.py` — `copy_asset_for_station()` for logo management
- `musicstreamer/url_helpers.py` — URL normalization utilities

### v1.5 Key Decisions (behavioral guidance)
- `url_resolved` preferred over `url` for Radio-Browser results
- `new_provider_entry` typed value takes precedence over combo selection
- `is_live is True` strict identity check for YouTube playlist scanning
- Thread-local `db_connect()` in import workers (SQLite thread safety)
- `ValueError('no_channels')` for empty AudioAddict response (expired key detection)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`FlowLayout`** (`ui_qt/flow_layout.py`) — wrapping layout for tag chips; reuse in EditStation tag editor
- **`ToastOverlay`** (`ui_qt/toast.py`) — feedback toasts for save/delete/import completion
- **`StationTreeModel`** + **`StationFilterProxy`** — station selection for "which station to edit"
- **`repo.list_providers()`** — populates provider combo in EditStation
- **All three backend modules** — `radio_browser.py`, `yt_import.py`, `aa_import.py` are pure Python with blocking I/O, ready for daemon-thread calling from Qt

### Established Patterns
- Qt signals + queued connections for worker-thread → UI updates (Phase 35 pattern)
- `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` fallback (Phase 36)
- `icons.qrc` + `icons_rc.py` regeneration for new SVGs
- Bound-method signal slots (QA-05 — no self-capturing lambdas)
- `FlowLayout` chip pattern from Phase 38 filter strip

### Integration Points
- `MainWindow` — launches dialogs (Edit, Discovery, Import) from menu/button actions
- `NowPlayingPanel` line 174 — edit button + stream picker insertion point
- `Player` — preview playback in Discovery, stream switching from picker, failover signal for picker sync
- `StationListPanel` — refresh after import/edit/delete operations

</code_context>

<specifics>
## Specific Ideas

- User chose all recommended options — continues the "port faithfully, keep it simple" pattern from Phase 37/38.
- Single EditStation dialog (no sub-dialog) simplifies the flow vs. v1.5's two-dialog approach.
- Preview playback reuses the main Player instance rather than spinning up a second pipeline.
- Stream picker is a standard QComboBox that syncs with failover state via `blockSignals`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 39-core-dialogs*
*Context gathered: 2026-04-13*

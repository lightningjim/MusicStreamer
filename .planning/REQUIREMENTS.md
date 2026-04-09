# Requirements: MusicStreamer

**Defined:** 2026-04-05
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## v1.5 Requirements

Requirements for this polish milestone. New items added as issues are discovered (deadline: 2026-04-19).

### Bug Fixes

- [ ] **FIX-01**: YouTube 16:9 thumbnail does not inflate now-playing panel when window is maximized/fullscreen
- [ ] **FIX-02**: yt-dlp/mpv cookie invocations use a temporary copy of cookies.txt so the original imported file is never overwritten
- [ ] **FIX-03**: If mpv exits immediately (~2s) with cookies, retry once without cookies to handle corrupted cookie files
- [ ] **FIX-04**: Tag chip container in edit dialog does not overflow or overlap adjacent buttons; chips wrap to multiple lines via FlowBox
- [ ] **FIX-05**: Provider and tag filter chip containers in main window do not overflow horizontally; chips wrap to multiple lines via FlowBox
- [ ] **FIX-06**: Standalone Edit button in filter bar replaced with now-playing edit icon button; edit icon sensitive only when a station is playing or paused

### Cookie Management (Phase 22)

- [ ] **COOKIE-01**: Users can import YouTube cookies via file picker or paste textarea
- [ ] **COOKIE-02**: Cookies stored at ~/.local/share/musicstreamer/cookies.txt with 0o600 permissions; manual lifecycle with last-imported date display; clear button to remove
- [ ] **COOKIE-03**: yt-dlp subprocess calls include --cookies flag when cookies.txt exists and always include --no-cookies-from-browser
- [ ] **COOKIE-04**: mpv subprocess calls include --ytdl-raw-options=cookies=<path> when cookies.txt exists
- [ ] **COOKIE-05**: Hamburger menu in header bar with "YouTube Cookies..." item opens the cookie dialog
- [ ] **COOKIE-06**: Google login flow via embedded WebKit2 browser captures YouTube cookies and saves as cookies.txt

### Multi-Stream Support (Phase 27)

- [ ] **STR-01**: `station_streams` table created by `db_init()` with columns: id, station_id, url, label, quality, position, stream_type, codec
- [ ] **STR-02**: Existing `stations.url` data migrated into `station_streams` at position=1 during db_init
- [ ] **STR-03**: `stations.url` column removed after migration (table recreation)
- [ ] **STR-04**: `station_exists_by_url()` queries `station_streams` table instead of `stations`
- [ ] **STR-05**: `insert_station()` creates a `station_streams` row when url is non-empty
- [ ] **STR-06**: AudioAddict import creates hi/med/low quality streams per channel
- [ ] **STR-07**: `get_preferred_stream_url()` returns position=1 stream when no quality preference set
- [ ] **STR-08**: `get_preferred_stream_url()` returns quality-matched stream when preference set
- [ ] **STR-09**: "Manage Streams..." button in station editor opens sub-dialog for stream CRUD
- [ ] **STR-10**: ManageStreamsDialog supports add/edit/delete/reorder with Up/Down buttons
- [ ] **STR-11**: Quality dropdown in stream editor offers hi/med/low/custom presets
- [ ] **STR-12**: Radio-Browser discovery offers "Add as new station" or "Add stream to existing station"
- [ ] **STR-13**: Attach-to-existing auto-detects matching station by name with manual override
- [ ] **STR-14**: YouTube import works with new stream-based model (single stream per station)

### Hamburger Menu Consolidation (Phase 29)

- [ ] **MENU-01**: Hamburger menu has two sections: station actions (Discover Stations, Import Stations) and settings (Accent Color, YouTube Cookies), separated by a visual divider
- [ ] **MENU-02**: Menu items are text-only with no icons, using ellipsis labels ("Discover Stations...", "Import Stations...", "Accent Color...", "YouTube Cookies...")
- [ ] **MENU-03**: Discover, Import, and Accent Color header bar buttons are removed; header bar contains only search entry and hamburger MenuButton
- [ ] **MENU-04**: Each menu item is a Gio.SimpleAction on the app, wired to existing handler methods
- [ ] **MENU-05**: All four menu items open their respective dialogs (discovery, import, accent color, cookies)

## Future Requirements

### v2.0 — OS-Agnostic Revamp

- **V2-01**: Cross-platform support (not GNOME-only)

## Out of Scope

| Feature | Reason |
|---------|--------|
| New features | v1.5 is bug-fix/polish only; new features deferred to v2.0 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | Phase 21 | Pending |
| FIX-02 | Phase 23 | Pending |
| FIX-03 | Phase 23 | Pending |
| FIX-04 | Phase 24 | Pending |
| FIX-05 | Phase 25 | Pending |
| FIX-06 | Phase 26 | Pending |
| COOKIE-01 | Phase 22 | Pending |
| COOKIE-02 | Phase 22 | Pending |
| COOKIE-03 | Phase 22 | Pending |
| COOKIE-04 | Phase 22 | Pending |
| COOKIE-05 | Phase 22 | Pending |
| COOKIE-06 | Phase 22 | Pending |
| STR-01 | Phase 27 | Pending |
| STR-02 | Phase 27 | Pending |
| STR-03 | Phase 27 | Pending |
| STR-04 | Phase 27 | Pending |
| STR-05 | Phase 27 | Pending |
| STR-06 | Phase 27 | Pending |
| STR-07 | Phase 27 | Pending |
| STR-08 | Phase 27 | Pending |
| STR-09 | Phase 27 | Pending |
| STR-10 | Phase 27 | Pending |
| STR-11 | Phase 27 | Pending |
| STR-12 | Phase 27 | Pending |
| STR-13 | Phase 27 | Pending |
| STR-14 | Phase 27 | Pending |
| MENU-01 | Phase 29 | Pending |
| MENU-02 | Phase 29 | Pending |
| MENU-03 | Phase 29 | Pending |
| MENU-04 | Phase 29 | Pending |
| MENU-05 | Phase 29 | Pending |

**Coverage:**
- v1.5 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-09 after Phase 29 planning*

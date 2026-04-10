# Requirements: MusicStreamer

**Defined:** 2026-04-05
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## v1.5 Requirements

Requirements for this polish milestone. New items added as issues are discovered (deadline: 2026-04-19).

### Bug Fixes

- [x] **FIX-01**: YouTube 16:9 thumbnail does not inflate now-playing panel when window is maximized/fullscreen
- [ ] **FIX-02**: yt-dlp/mpv cookie invocations use a temporary copy of cookies.txt so the original imported file is never overwritten
- [ ] **FIX-03**: If mpv exits immediately (~2s) with cookies, retry once without cookies to handle corrupted cookie files
- [ ] **FIX-04**: Tag chip container in edit dialog does not overflow or overlap adjacent buttons; chips wrap to multiple lines via FlowBox
- [ ] **FIX-05**: Provider and tag filter chip containers in main window do not overflow horizontally; chips wrap to multiple lines via FlowBox
- [ ] **FIX-06**: Standalone Edit button in filter bar replaced with now-playing edit icon button; edit icon sensitive only when a station is playing or paused
- [x] **FIX-07**: YouTube streams get a 15s minimum wait window before `_try_next_stream` can fire; a "Connecting…" Adw.Toast fires on every `play()` / `play_stream()` call for all stream types. Sub-criteria:
  - (a) YT mpv exit at < 15s after attempt start does NOT call `_try_next_stream`
  - (b) YT mpv alive at >= 15s clears `_yt_poll_timer_id` and `_yt_attempt_start_ts`
  - (c) Cookie-retry substitution re-seeds `_yt_attempt_start_ts` so replacement mpv gets its full 15s
  - (d) `_show_toast("Connecting\u2026", ...)` invoked on `_on_play` before `player.play(...)` and on `_on_stream_picker_row_activated` before `player.play_stream(...)`
  - (e) `_cancel_failover_timer` clears `_yt_attempt_start_ts`

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

### Elapsed Time Counter (Phase 30)

- [ ] **TIMER-01**: Timer row (icon + label) displayed between station_name_label and controls_box in now-playing center column
- [ ] **TIMER-02**: Timer uses GLib.timeout_add_seconds(1, callback) to tick every second; source ID tracked for cleanup
- [ ] **TIMER-03**: Timer pauses when stream paused, resumes on unpause with accumulated seconds preserved
- [ ] **TIMER-04**: Timer resets to 0:00 on station change; stream failover does NOT reset
- [ ] **TIMER-05**: Timer hidden when nothing playing; shows 0:00 immediately on play start
- [ ] **TIMER-06**: Adaptive format: M:SS for <1h, H:MM:SS for >=1h; dim-label CSS class on icon and label

### Twitch Streaming via Streamlink (Phase 31)

- [ ] **TWITCH-01**: Twitch URLs (containing "twitch.tv") auto-detected and routed to streamlink resolution in player.py
- [ ] **TWITCH-02**: streamlink invoked as `streamlink --stream-url <url> best` with list args (no shell=True); ~/.local/bin on PATH
- [ ] **TWITCH-03**: Resolved HLS URL from streamlink fed to GStreamer playbin3 via existing _set_uri path
- [ ] **TWITCH-04**: Offline channel ("No playable streams found") shows toast "[channel] is offline" without triggering failover; station stays selected
- [ ] **TWITCH-05**: GStreamer error on Twitch stream re-resolves URL once via streamlink before falling through to normal failover
- [ ] **TWITCH-06**: Failover timeout NOT armed for Twitch URLs (streamlink handles its own resolution timing)
- [ ] **TWITCH-07**: Offline state pauses elapsed timer (does not reset); timer resumes if stream is retried
- [ ] **TWITCH-08**: on_offline callback wired from main_window.py to player.play() and player.play_stream()

### Twitch Authentication (Phase 32)

- [ ] **TAUTH-01**: TWITCH_TOKEN_PATH constant in constants.py resolves to ~/.local/share/musicstreamer/twitch-token.txt
- [ ] **TAUTH-02**: clear_twitch_token() deletes twitch-token.txt if it exists and returns True; returns False when absent
- [ ] **TAUTH-03**: _play_twitch() includes --twitch-api-header Authorization=OAuth <token> when token file exists and has content; omits when absent or empty
- [ ] **TAUTH-04**: CookiesDialog renamed to AccountsDialog in accounts_dialog.py; hamburger menu entry renamed from "YouTube Cookies..." to "Accounts..."
- [ ] **TAUTH-05**: AccountsDialog uses Gtk.Notebook with "YouTube" tab (existing cookie UI) and "Twitch" tab
- [ ] **TAUTH-06**: Twitch tab has: status label (Logged in / Not logged in), "Log in to Twitch" button spawning WebKit2 subprocess, "Log out" button deleting token
- [ ] **TAUTH-07**: WebKit2 subprocess opens twitch.tv/login, captures auth-token cookie from .twitch.tv domain, writes raw token to TWITCH_TOKEN_PATH with 0o600 permissions

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
| FIX-01 | Phase 21 | Complete |
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
| TIMER-01 | Phase 30 | Pending |
| TIMER-02 | Phase 30 | Pending |
| TIMER-03 | Phase 30 | Pending |
| TIMER-04 | Phase 30 | Pending |
| TIMER-05 | Phase 30 | Pending |
| TIMER-06 | Phase 30 | Pending |
| TWITCH-01 | Phase 31 | Pending |
| TWITCH-02 | Phase 31 | Pending |
| TWITCH-03 | Phase 31 | Pending |
| TWITCH-04 | Phase 31 | Pending |
| TWITCH-05 | Phase 31 | Pending |
| TWITCH-06 | Phase 31 | Pending |
| TWITCH-07 | Phase 31 | Pending |
| TWITCH-08 | Phase 31 | Pending |
| TAUTH-01 | Phase 32 | Pending |
| TAUTH-02 | Phase 32 | Pending |
| TAUTH-03 | Phase 32 | Pending |
| TAUTH-04 | Phase 32 | Pending |
| TAUTH-05 | Phase 32 | Pending |
| TAUTH-06 | Phase 32 | Pending |
| TAUTH-07 | Phase 32 | Pending |
| FIX-07 | Phase 33 | Complete |

**Coverage:**
- v1.5 requirements: 53 total
- Mapped to phases: 53
- Unmapped: 0

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-10 after Phase 33 planning*

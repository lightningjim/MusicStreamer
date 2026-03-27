# Architecture Research

**Domain:** GTK4/Python desktop radio player — v1.3 Discovery & Favorites integration
**Researched:** 2026-03-27
**Confidence:** HIGH (existing codebase is the ground truth; external API patterns are well-established)

## Current Architecture (v1.2 baseline)

```
musicstreamer/
├── constants.py        — DATA_DIR, DB_PATH, ASSETS_DIR
├── models.py           — Station, Provider dataclasses
├── repo.py             — Repo class: all SQLite read/write
├── player.py           — Player: GStreamer pipeline + mpv subprocess
├── cover_art.py        — iTunes Search API fetch (daemon thread + callback)
├── assets.py           — Station art persistence
├── filter_utils.py     — normalize_tags, matches_filter_multi
└── ui/
    ├── main_window.py  — MainWindow: all layout, state, playback wiring
    ├── station_row.py  — StationRow (ListBoxRow wrapping ActionRow)
    └── edit_dialog.py  — EditStationDialog
```

State is held in `MainWindow`. `Repo` is stateless (connection-holding) and called synchronously from the GTK main thread. All background work (cover art, YT thumbnail) uses `threading.Thread(daemon=True)` + `GLib.idle_add` to return results to the GTK thread.

## v1.3 Target Structure

### New modules (pure additions)

```
musicstreamer/
├── favorites_repo.py        — FavoritesRepo: DB CRUD for favorites table
├── importers/
│   ├── __init__.py
│   ├── radio_browser.py     — RadioBrowserClient: DNS server discovery + REST search
│   ├── audioaddict.py       — AudioAddictImporter: channel list + PLS fetch/parse
│   └── youtube.py           — YouTubeImporter: yt-dlp extract_info, live filter
└── ui/
    ├── favorites_view.py    — FavoritesView: ListBox of favorited tracks + delete
    ├── discovery_dialog.py  — DiscoveryDialog: Radio-Browser browse/search/play/save
    └── import_dialog.py     — ImportDialog: AudioAddict + YouTube import (tabbed)
```

### Modified modules

| Module | What changes |
|--------|-------------|
| `repo.py` | `db_init` migration adds `favorites` table. No method changes — favorites CRUD lives in `FavoritesRepo`. |
| `models.py` | Add `Favorite` dataclass. `Station` unchanged. |
| `cover_art.py` | Extend callback signature from `(path)` to `(path, genre_or_None)` so genre can be stored in favorites. |
| `main_window.py` | Add: star button in now-playing panel; Stations/Favorites toggle; "Discover" and "Import" buttons; track `_current_icy_title`. |

`station_row.py` and `edit_dialog.py` are untouched.

## Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `favorites_repo.py` | CRUD for `favorites` table (add, list, delete) | Shares `repo.con` — no separate connection |
| `importers/radio_browser.py` | DNS-discover server, HTTP search/browse, map result to dict | `discovery_dialog.py` via callback |
| `importers/audioaddict.py` | Fetch channel list JSON, fetch PLS per channel, parse 2-server URLs | `import_dialog.py` |
| `importers/youtube.py` | Run yt-dlp `extract_info(flat)`, filter `is_live`, return station dicts | `import_dialog.py` |
| `ui/favorites_view.py` | Render favorited tracks, inline delete button per row | `main_window.py` |
| `ui/discovery_dialog.py` | Search UI, result list, Play preview, Save to library | `radio_browser.py`, `repo.py`, `player.py` (via callback) |
| `ui/import_dialog.py` | Two-tab import UI, progress feedback, bulk station creation | `audioaddict.py`, `youtube.py`, `repo.py` |

## Data Model Changes

### New table: `favorites`

```sql
CREATE TABLE IF NOT EXISTS favorites (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  track_title   TEXT NOT NULL,
  station_id    INTEGER,
  station_name  TEXT NOT NULL,    -- denormalized: station may be deleted later
  provider_name TEXT,             -- denormalized for same reason
  itunes_genre  TEXT,             -- from iTunes API response if available
  created_at    TEXT DEFAULT (datetime('now')),
  FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE SET NULL
);
```

Denormalize `station_name` and `provider_name` at insert time. The station may be deleted after favoriting, but the user still needs display data. `station_id` remains as a nullable FK for potential cross-reference.

### New model

```python
@dataclass
class Favorite:
    id: int
    track_title: str
    station_id: Optional[int]
    station_name: str
    provider_name: Optional[str]
    itunes_genre: Optional[str]
    created_at: str
```

## Data Flow

### Favorites: star current ICY track

```
ICY TAG arrives → Player._on_gst_tag → GLib.idle_add(_on_title, title)
    ↓
MainWindow._on_title(title):
    - self._current_icy_title = title
    - title_label.set_text(title)
    - star_btn.set_sensitive(True)  [non-junk title]

User clicks star button
    ↓
MainWindow._on_star():
    - reads self._current_station, self._current_icy_title, self._last_itunes_genre
    - FavoritesRepo.add_favorite(track_title, station, genre)
    - star_btn.add_css_class("accent")  [filled appearance]
```

### Favorites: view and delete

```
User clicks "Favorites" toggle
    ↓
MainWindow._show_favorites_view():
    - shell.set_content(favorites_scroller)   [same swap pattern as empty_page]
    - FavoritesView.load() → FavoritesRepo.list_favorites()
    - chip strip + search hidden/insensitive

User clicks delete on a row
    ↓ FavoritesRepo.delete_favorite(id) → FavoritesView.load()

User clicks "Stations" toggle
    ↓ shell.set_content(scroller) → chip strip re-enabled
```

### Radio-Browser: browse, play preview, save

```
User clicks "Discover" button
    ↓
DiscoveryDialog.present()
    ↓ on first show: daemon thread → RadioBrowserClient.get_server()
      DNS: all.api.radio-browser.info → random server URL
    ↓ GLib.idle_add → enable search entry

User types query or selects tag
    ↓ daemon thread:
      GET https://{server}/json/stations/search
          ?name={q}&limit=50&hidebroken=true&order=votes
    ↓ GLib.idle_add → populate result ListBox (Adw.ActionRow per result)

User clicks Play on result
    ↓ construct throwaway Station(id=-1, name=..., url=...)
    ↓ Player.play(transient_station)  [no DB write; guard update_last_played against id<0]

User clicks Save
    ↓ Repo.create_station() + Repo.update_station() with result fields
    ↓ GLib.idle_add → show "Saved" toast; Save button becomes "Saved" (greyed)
    ↓ on dialog close → MainWindow.reload_list()
```

### AudioAddict import

```
User opens Import dialog → AudioAddict tab → enters API key → clicks Fetch Channels
    ↓ daemon thread:
      GET https://api.audioaddict.com/v1/di/channels
      GET https://api.audioaddict.com/v1/radiotunes/channels
      GET https://api.audioaddict.com/v1/jazzradio/channels
      GET https://api.audioaddict.com/v1/rockradio/channels
    ↓ GLib.idle_add → populate channel checklist

User selects quality (hi/med/low) → selects channels → clicks Import
    ↓ daemon thread:
      for each selected channel:
        GET http://listen.di.fm/premium_{quality}/{slug}.pls?api_key={key}
        parse .pls → extract File1= (primary), File2= (failover)
        append both URLs; primary used as station URL
      Repo.upsert_station({name, url, provider, tags})
    ↓ GLib.idle_add → progress bar increment
    ↓ on complete → MainWindow.reload_list()
```

### YouTube playlist import

```
User opens Import dialog → YouTube tab → pastes playlist URL → clicks Import
    ↓ daemon thread:
      yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True})
        .extract_info(url, download=False)
      filter entries: is_live == True OR live_status == 'is_live'
    ↓ GLib.idle_add → show found count
    ↓ for each live entry:
      Repo.create_station() + Repo.update_station({name, url, provider='YouTube'})
    ↓ on complete → MainWindow.reload_list()
```

## Cross-Thread Pattern

All new network operations extend the established pattern from `cover_art.py`:

```python
def _on_some_action(self):
    def _worker():
        result = blocking_network_call()
        GLib.idle_add(self._update_ui, result)
    threading.Thread(target=_worker, daemon=True).start()
```

No new threading primitives needed. Radio-Browser search, AudioAddict fetch, and YouTube import all use this exact pattern. For multi-step imports with progress, `GLib.idle_add` is called once per station inserted.

## UI Integration Points in `main_window.py`

### 1. Star button in now-playing panel

Add `Gtk.Button` with `starred-symbolic` icon to the center column of the now-playing panel (between track title label and stop button). Sensitive only when `self._current_icy_title` is set and non-junk. `_on_title` callback must store `self._current_icy_title = title` on each call.

### 2. Stations / Favorites toggle

Add two `Gtk.ToggleButton` forming a `Gtk.ToggleGroup` (or exclusive manual wiring) in the filter bar. "Stations" active by default. Switching to "Favorites" calls `shell.set_content(favorites_scroller)` and hides the chip strip. Switching back restores `shell.set_content(scroller)`.

### 3. Discover and Import buttons in toolbar

Append to `filter_box` alongside Add Station / Edit. "Discover" → `DiscoveryDialog.present()`; "Import" → `ImportDialog.present()`. Keep `set_hexpand(False)`.

### 4. Genre capture from cover_art.py

`_on_cover_art` in `main_window.py` currently discards the iTunes response after extracting artwork URL. Change `cover_art.py::_worker` to also parse `primaryGenreName` from the JSON result. Change callback signature to `callback(path_or_None, genre_or_None)`. Store genre as `self._last_itunes_genre` for use when the user stars a track.

## Module Boundary Rules

- `importers/*` modules have zero GTK imports. They return plain Python dicts/lists. All `GLib.idle_add` wiring lives in the dialog layer.
- `FavoritesRepo` shares `repo.con`. Construct as `FavoritesRepo(repo.con)` in `MainWindow.__init__`. Do NOT open a second SQLite connection.
- `DiscoveryDialog` receives a `Repo` reference and calls `repo.create_station()` + `repo.update_station()` on save. It does not have its own repo.
- Transient (unsaved) Radio-Browser playback uses `Station(id=-1, ...)`. Guard `Repo.update_last_played` and `_refresh_recently_played` against `station.id < 0`.

## Recommended Build Order

```
Phase A: Favorites (DB + UI)
  Dependencies: none
  1. models.py: add Favorite dataclass
  2. repo.py: db_init migration (favorites table)
  3. favorites_repo.py: add_favorite, list_favorites, delete_favorite
  4. cover_art.py: extend callback to (path, genre_or_None)
  5. ui/favorites_view.py: FavoritesView widget
  6. main_window.py: _current_icy_title tracking, star button,
     Stations/Favorites toggle, wire FavoritesRepo

Phase B: Radio-Browser Discovery
  Dependencies: none (independent of Phase A)
  1. importers/radio_browser.py: RadioBrowserClient
  2. ui/discovery_dialog.py: DiscoveryDialog
  3. main_window.py: Discover button

Phase C: AudioAddict Import
  Dependencies: Phase B (shares ImportDialog shell; or standalone if dialog is separate)
  1. importers/audioaddict.py: AudioAddictImporter
  2. ui/import_dialog.py: ImportDialog with AudioAddict tab
  3. main_window.py: Import button

Phase D: YouTube Playlist Import
  Dependencies: Phase C (adds tab to existing ImportDialog)
  1. importers/youtube.py: YouTubeImporter
  2. ui/import_dialog.py: add YouTube tab
```

Phases A and B are fully independent. If parallelizing work, those are the natural split. C and D must be sequential since they share `ImportDialog`.

## Anti-Patterns to Avoid

### Separate SQLite connection per feature

RadioBrowserClient, AudioAddictImporter, or FavoritesRepo opening their own `sqlite3.connect(DB_PATH)` creates write-lock contention when the main Repo is mid-transaction. Share `repo.con` by passing it at construction.

### Blocking the GTK main thread with network calls

Any `urllib.request.urlopen`, `yt_dlp.YoutubeDL().extract_info`, or PLS fetch that runs synchronously in a GTK signal handler will freeze the UI. All network calls go to daemon threads.

### Inserting a DB row just to preview a Radio-Browser station

Playback requires a `Station` object but not a saved DB row. Construct `Station(id=-1, name=..., url=..., provider_id=None, provider_name=None, tags='', station_art_path=None, album_fallback_path=None)` for transient playback. Guard `update_last_played` and `_refresh_recently_played` against `id < 0`.

### Storing only station_id in favorites

Station can be deleted after favoriting. Denormalize `station_name` and `provider_name` into the `favorites` row at insert time.

### Calling `reload_list()` after every individual imported station

Bulk imports (AudioAddict can bring in 30+ channels) should batch all `Repo` writes first, then call `reload_list()` once at the end. Call `GLib.idle_add` with a progress callback per station, but defer the list rebuild until the thread finishes.

## Integration Points

### External Services

| Service | Integration Pattern | Key Fields |
|---------|---------------------|------------|
| Radio-Browser.info | DNS `all.api.radio-browser.info` → random server → `GET /json/stations/search?name=&limit=50&hidebroken=true` | `name`, `url`, `favicon`, `tags`, `country`, `bitrate`, `codec`, `votes` |
| AudioAddict channel API | `GET https://api.audioaddict.com/v1/{network}/channels` → JSON array | `key` (slug), `name`, `description` |
| AudioAddict PLS | `GET http://listen.di.fm/premium_{quality}/{slug}.pls?api_key={key}` | `File1=` primary URL, `File2=` failover |
| yt-dlp Python API | `YoutubeDL({'extract_flat': True}).extract_info(url, download=False)` | `entries[].is_live`, `entries[].url`, `entries[].title` |
| iTunes Search API | Existing `cover_art.py` — extend to parse `primaryGenreName` | `primaryGenreName` alongside `artworkUrl100` |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `main_window` ↔ `FavoritesRepo` | Direct call, GTK main thread | Share `repo.con` |
| `main_window` ↔ importer dialogs | Callback on completion (`reload_list`) | Dialog owns thread lifecycle |
| `discovery_dialog` ↔ `radio_browser` | daemon thread + `GLib.idle_add` | Dialog drives search; client is stateless |
| `import_dialog` ↔ `audioaddict`/`youtube` | daemon thread + `GLib.idle_add` progress | Dialog shows `Gtk.ProgressBar` |
| `cover_art` ↔ `main_window` | callback `(path, genre)` from daemon thread | Existing pattern extended |

## Sources

- Existing codebase `musicstreamer/` — PRIMARY, HIGH confidence
- Radio-Browser.info REST API — stable public API, DNS-based server discovery pattern is standard across open-source radio clients; HIGH confidence
- AudioAddict PLS URL pattern: `http://listen.di.fm/premium_{quality}/{slug}.pls?api_key={key}` — MEDIUM confidence; verify at implementation time whether auth is query param or header
- yt-dlp Python API `extract_flat=True` + `is_live` field — HIGH confidence; stable feature in current yt-dlp
- GTK4 `GLib.idle_add` cross-thread pattern — HIGH confidence; proven in existing code
- iTunes `primaryGenreName` field — MEDIUM confidence; present in most results but not guaranteed

---
*Architecture research for: MusicStreamer v1.3 Discovery & Favorites*
*Researched: 2026-03-27*

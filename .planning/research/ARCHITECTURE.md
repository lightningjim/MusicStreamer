# Architecture Patterns

**Domain:** GNOME desktop music streaming app
**Researched:** 2026-03-18
**Scope:** ICY metadata, cover art fetching, and station list filtering — integration into existing GTK4/GStreamer monolith

---

## Context: What Exists Today

The app is a single file (`main.py`, 512 lines) with four logical layers that are not yet separated into modules:

| Layer | Location | What It Does |
|-------|----------|--------------|
| Domain models | lines 70–86 | `Station` and `Provider` dataclasses |
| Repository | lines 88–180 | All SQLite access via `Repo` class |
| Business logic | scattered | DB init, asset copying, yt-dlp URL resolution |
| UI | lines 200–493 | `MainWindow` + `EditStationDialog` |

**Critical gap for new features:** `MainWindow` owns the GStreamer `playbin` element directly. There is no GStreamer bus listener — TAG messages from ICY streams are never read. There is no filter state — `Gtk.ListBox` is populated once and reloaded wholesale on edit. Cover art is static (user-supplied files only); no dynamic fetch exists.

---

## Recommended Architecture

The three incoming features — ICY metadata, cover art, and filtering — each need a clear home that is not `MainWindow`. The recommended split is:

```
App
 └─ MainWindow
     ├─ FilterBar  (new UI component)
     │    ├─ provider dropdown  → filter state
     │    ├─ tag dropdown       → filter state
     │    └─ search entry       → filter state
     │
     ├─ StationList  (extracted from MainWindow)
     │    ├─ Gtk.ListBox with set_filter_func
     │    └─ reads filter state from FilterBar
     │
     ├─ Player  (extracted from MainWindow)
     │    ├─ GStreamer playbin element
     │    ├─ GStreamer bus watcher (TAG messages → callbacks)
     │    └─ emits: track_changed(artist, title)
     │
     └─ NowPlayingBar  (new UI component)
          ├─ track title label  (fed by Player.track_changed)
          └─ cover art image    (fed by CoverArtFetcher)

CoverArtFetcher  (new background service)
     ├─ receives (artist, title) from Player.track_changed
     ├─ queries iTunes Search API or MusicBrainz
     ├─ fetches image bytes on background thread
     └─ delivers pixbuf to NowPlayingBar via GLib.idle_add
```

---

## Component Boundaries

### Player (extracted from `MainWindow`)

**Responsibility:** Owns the GStreamer pipeline. Translates pipeline events into Python signals/callbacks. Has no GTK widget imports.

**Communicates with:**
- `MainWindow` — receives play/stop commands
- `NowPlayingBar` — emits `track_changed(artist: str, title: str)` callback
- `CoverArtFetcher` — feeds (artist, title) pairs for lookup

**Key implementation detail:** GStreamer TAG messages arrive on the GStreamer bus, not the GTK main loop. The correct pattern is:

```python
bus = self.player.get_bus()
bus.add_signal_watch()
bus.connect("message::tag", self._on_tag_message)

def _on_tag_message(self, bus, message):
    taglist = message.parse_tag()
    title = taglist.get_string("title")[1]      # ICY StreamTitle
    artist = taglist.get_string("artist")[1]    # sometimes present
    # GLib.idle_add ensures UI update runs on main thread
    GLib.idle_add(self._notify_track_changed, artist, title)
```

`bus.add_signal_watch()` routes bus messages into the GLib main loop, so `_on_tag_message` fires on the GTK main thread — no explicit threading needed for the TAG callback itself.

Confidence: HIGH — this is the standard PyGObject GStreamer bus pattern; `message::tag` is documented signal syntax.

---

### FilterBar (new widget)

**Responsibility:** Owns filter state. Provides a `matches(station: Station) -> bool` method that `StationList` uses as its `set_filter_func` predicate. Emits a `filters_changed` signal (or calls a callback) when state updates.

**Communicates with:**
- `StationList` — pushes filter changes via callback
- `Repo` — reads provider list once at construction to populate dropdown

**Key implementation detail:** `Gtk.ListBox.set_filter_func(func, user_data)` is the correct GTK4 API. The function signature is `func(row, user_data) -> bool`. To re-evaluate, call `self.listbox.invalidate_filter()`. This does not reload data from SQLite — it only re-applies the predicate in-memory.

```python
def _filter_func(self, row, _data):
    st = row.station   # Station object attached to row at build time
    if self._provider_id and st.provider_id != self._provider_id:
        return False
    if self._tag and self._tag not in (st.tags or "").split(","):
        return False
    if self._search:
        return self._search.lower() in st.name.lower()
    return True
```

Tags are stored as comma-separated strings in the current schema. Splitting on `,` and stripping whitespace is sufficient for filtering at the 50–200 station scale. A junction table migration is correct long-term but not required for this milestone.

Confidence: HIGH — `set_filter_func` / `invalidate_filter` are stable GTK4 ListBox APIs.

---

### StationList (extracted from `MainWindow.reload_list`)

**Responsibility:** Builds and owns the `Gtk.ListBox`. Attaches `Station` objects to rows at build time. Delegates filter decisions to `FilterBar`.

**Communicates with:**
- `Repo` — reads station list on `reload()`
- `FilterBar` — registers as listener; calls `invalidate_filter()` on filter change
- `MainWindow` — emits station activation events (row-activated)

**Key implementation detail:** Attach the full `Station` dataclass to each `Gtk.ListBoxRow` as a Python attribute (the existing code already does `listrow.station_id = st.id`; extend this to `listrow.station = st` so the filter function can inspect all fields without a DB round-trip).

---

### NowPlayingBar (new widget)

**Responsibility:** Displays current track title and cover art. Purely reactive — only updated by incoming callbacks; owns no playback logic.

**Communicates with:**
- `Player` — receives `track_changed(artist, title)` callback
- `CoverArtFetcher` — receives `cover_ready(pixbuf)` callback

**Key implementation detail:** Use `Adw.ActionRow` or a custom `Gtk.Box` with a `Gtk.Picture` for the art and a `Gtk.Label` for the title. Keep a "loading" state (spinner or placeholder) between a track change and when cover art arrives.

---

### CoverArtFetcher (new background service)

**Responsibility:** Given (artist, title), return a cover art image. Runs HTTP requests off the GTK main thread. Delivers results safely back via `GLib.idle_add`.

**Communicates with:**
- `Player` / `NowPlayingBar` — triggered by `track_changed`, delivers `cover_ready`

**Recommended API:** iTunes Search API — no key required, returns JSON with `artworkUrl100`.

```
GET https://itunes.apple.com/search?term={artist}+{title}&entity=song&limit=1
→ results[0].artworkUrl100  (replace "100x100" with "600x600" in URL for higher res)
```

MusicBrainz is more complete but has stricter rate limits (1 req/sec) and requires a two-step lookup (search → release → cover art). iTunes Search is faster for the common case.

**Threading pattern:**

```python
import threading

def fetch(self, artist: str, title: str, on_ready):
    def _worker():
        pixbuf = self._do_http_fetch(artist, title)
        if pixbuf:
            GLib.idle_add(on_ready, pixbuf)
    threading.Thread(target=_worker, daemon=True).start()
```

Use `urllib.request` or `requests` for the HTTP call. Do not use `GLib.idle_add` inside the worker except to deliver the final result — all GTK/GLib calls must be on the main thread.

Confidence: MEDIUM — iTunes Search API behavior confirmed via training data and prior research; no official SLA. MusicBrainz rate limits documented at musicbrainz.org.

---

## Data Flow

### ICY Metadata Flow

```
GStreamer pipeline (audio thread)
  → TAG bus message
  → bus.add_signal_watch() routes to GLib main loop
  → Player._on_tag_message() called on main thread
  → Player calls track_changed_callback(artist, title)
  → NowPlayingBar updates title label
  → CoverArtFetcher.fetch(artist, title, on_ready=NowPlayingBar.set_cover)
       └─ background thread: HTTP request to iTunes Search
            └─ GLib.idle_add(NowPlayingBar.set_cover, pixbuf)  [back on main thread]
```

### Filter Flow

```
User changes FilterBar dropdown or search entry
  → FilterBar updates internal state (_provider_id, _tag, _search)
  → FilterBar calls registered callback
  → StationList.invalidate_filter()
  → GTK calls _filter_func(row, _) for each row
  → _filter_func reads row.station (in-memory Station object)
  → Rows show/hide without DB query
```

### Playback Flow (unchanged core, but Player is now a separate object)

```
User activates StationList row
  → MainWindow._play_station(station)
  → Player.play(station)
       ├─ YouTube: yt-dlp resolution (background thread) → Player.set_uri()
       └─ Direct URL: Player.set_uri() immediately
  → Player sets GStreamer state PLAYING
  → TAG messages flow once stream connects (see ICY metadata flow above)
```

---

## Module Boundaries for File Split

When splitting `main.py`, the natural module boundaries are:

| Module | Contents | Depends On |
|--------|----------|------------|
| `models.py` | `Station`, `Provider` dataclasses | nothing |
| `repo.py` | `Repo` class, `db_connect`, `db_init` | `models.py`, `sqlite3` |
| `assets.py` | `copy_asset_for_station`, `ensure_dirs` | `models.py`, `os`, `shutil` |
| `player.py` | `Player` class, GStreamer pipeline, TAG bus | `models.py`, `gi.Gst`, `GLib`, `threading` |
| `cover_art.py` | `CoverArtFetcher` | `urllib`, `threading`, `GLib` |
| `ui/filter_bar.py` | `FilterBar` widget | `models.py`, `gi.Gtk` |
| `ui/station_list.py` | `StationList` widget | `models.py`, `repo.py`, `gi.Gtk` |
| `ui/now_playing.py` | `NowPlayingBar` widget | `gi.Gtk`, `gi.Adw` |
| `ui/main_window.py` | `MainWindow` | all ui/ modules, `player.py` |
| `ui/edit_dialog.py` | `EditStationDialog` | `repo.py`, `assets.py`, `gi.Gtk` |
| `app.py` | `App` entry point | `repo.py`, `ui/main_window.py` |

This split is additive — `main.py` can be migrated incrementally. Nothing in the existing architecture requires a rewrite; the changes are extraction and wiring.

---

## Suggested Build Order

Dependencies determine this order. Each step is independently testable before the next begins.

**Step 1: Module extraction (no new features)**
- Extract `models.py`, `repo.py`, `assets.py` — pure logic, no GTK, unit-testable
- Verify app still runs with imports rewired

**Step 2: Player extraction + GStreamer bus**
- Extract `Player` class to `player.py`
- Wire `bus.add_signal_watch()` + `message::tag` handler
- Emit `track_changed` callback when TAG arrives
- Update `now_label` in `MainWindow` from callback (existing behavior, now wired correctly)

**Step 3: Filtering**
- Extract `StationList` with `station` object attached to each row
- Add `FilterBar` widget with provider + tag dropdowns + search entry
- Wire `set_filter_func` / `invalidate_filter` loop
- Requires Step 1 (Station in-memory) but not Step 2

**Step 4: Cover art fetching**
- Add `CoverArtFetcher` with iTunes Search API
- Add `NowPlayingBar` widget with art + title
- Wire `Player.track_changed` → `CoverArtFetcher.fetch` → `NowPlayingBar.set_cover`
- Requires Step 2 (Player emitting track_changed)

Steps 3 and 4 are independent of each other and can be built in parallel if needed.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Fetching Cover Art on the GTK Main Thread

**What:** Calling `urllib.request.urlopen()` or `requests.get()` directly in a GTK signal handler or `GLib.idle_add` callback.

**Why bad:** HTTP calls can take 200ms–5s. GTK main loop is single-threaded. Any blocking call freezes the entire UI including audio controls and the filter bar.

**Instead:** Always run HTTP in `threading.Thread(daemon=True)`, deliver result back via `GLib.idle_add(callback, result)`.

---

### Anti-Pattern 2: Calling `reload_list()` on Every Filter Change

**What:** Re-querying SQLite and rebuilding all `Gtk.ListBoxRow` widgets every time the user types a character in the search box.

**Why bad:** Rebuilding the list destroys and recreates every widget — this is expensive at 200 stations and causes visible flicker. It also makes smooth incremental search impossible.

**Instead:** Build the list once (or on station edits only). Use `Gtk.ListBox.set_filter_func` + `invalidate_filter()` which re-evaluates the predicate in-memory without touching the DOM.

---

### Anti-Pattern 3: Polling GStreamer for TAG Messages

**What:** Using `GLib.timeout_add` to periodically query `player.get_bus().poll()` for new TAG messages.

**Why bad:** Introduces latency proportional to poll interval. Misses rapid message bursts. `bus.add_signal_watch()` already integrates the GStreamer bus into the GLib main loop — polling is unnecessary.

**Instead:** Use `bus.add_signal_watch()` + `bus.connect("message::tag", handler)`.

---

### Anti-Pattern 4: Fetching Cover Art on Every TAG Message

**What:** Launching an HTTP request for every ICY TAG message received.

**Why bad:** ICY streams send TAG messages every 8–32 KB of audio (i.e., every few seconds). Unthrottled fetching will hammer the iTunes API and create a backlog of inflight requests.

**Instead:** Cache the last (artist, title) pair. Only fetch when the pair changes. Cancel or ignore in-flight requests if the track changes again before the previous fetch completes.

---

## Scalability Considerations

These features are designed for 50–200 stations. Scaling implications are minimal:

| Concern | At 50–200 stations | At 1000+ stations |
|---------|-------------------|-------------------|
| Filter performance | `invalidate_filter` over in-memory rows is instantaneous | Still fine; GTK row recycling handles long lists |
| Cover art cache | One image in memory at a time; no cache needed | Add an LRU cache of ~20 images if browsing history matters |
| ICY metadata | One active stream; one TAG listener | No change; per-stream not per-station |
| iTunes Search | ~1 request per track change; well within rate limits | Rate limit concern only if batch-fetching many stations |

---

## Sources

- GTK4 `Gtk.ListBox.set_filter_func` / `invalidate_filter`: GTK4 API documentation — HIGH confidence
- GStreamer bus `add_signal_watch` + `message::tag` signal pattern: GStreamer Python tutorials, PyGObject docs — HIGH confidence
- ICY metadata via GStreamer TAG messages: established pattern in GStreamer-based radio players — HIGH confidence
- iTunes Search API (no key, `artworkUrl100`): publicly documented at developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI — MEDIUM confidence (no official SLA; treat as best-effort)
- MusicBrainz rate limits (1 req/sec): musicbrainz.org/doc/MusicBrainz_API — HIGH confidence
- `GLib.idle_add` for cross-thread GTK updates: PyGObject documentation — HIGH confidence

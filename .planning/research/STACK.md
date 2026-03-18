# Technology Stack

**Project:** MusicStreamer — milestone additions
**Researched:** 2026-03-18
**Scope:** Three specific additions to an existing GTK4/Libadwaita/Python/GStreamer app:
  1. ICY metadata reading from mp3/aac streams
  2. Cover art lookup from track metadata
  3. Filtering/search UI in GTK4/Libadwaita

---

## Existing Stack (Do Not Change)

| Technology | Version | Role |
|------------|---------|------|
| Python | 3.x | Application language |
| GTK | 4.0 | GUI framework |
| Libadwaita (Adw) | 1 | GNOME design widgets |
| GStreamer | 1.0 (`playbin`) | Streaming playback engine |
| PyGObject (`gi`) | system | GObject introspection bindings |
| SQLite3 | built-in | Persistence |
| yt-dlp | latest | YouTube URL resolution |

All of the above are already in place. No changes to these are needed or recommended.

---

## New Stack: ICY Metadata

### Approach: GStreamer Bus Watch + TAG Message Handling

**No new libraries required.** ICY metadata from ShoutCast/Icecast mp3/aac streams is delivered by GStreamer's `icydemux` element (auto-inserted by `playbin` when the stream is detected as ICY) as `Gst.MessageType.TAG` messages on the pipeline bus.

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| `Gst.Bus.add_watch()` | GStreamer 1.0 (existing) | Poll bus messages on GLib main loop | Integrates with GTK main loop; no threading needed |
| `Gst.Message.parse_tag()` | GStreamer 1.0 (existing) | Extract TagList from a TAG message | Standard GStreamer API for reading stream tags |
| `Gst.TagList.get_string()` | GStreamer 1.0 (existing) | Read individual tag values | Returns `(success: bool, value: str)` tuple |

**Tag constants to use (GStreamer standard tag names):**

| Constant | String value | Maps to ICY field |
|----------|-------------|-------------------|
| `Gst.TAG_TITLE` | `"title"` | Stream title (often "Artist - Title" from Icecast) |
| `Gst.TAG_ARTIST` | `"artist"` | Artist name (when split by demuxer) |
| `Gst.TAG_ALBUM` | `"album"` | Album name |
| `Gst.TAG_ORGANIZATION` | `"organization"` | Station name (ICY name field) |

**Implementation pattern:**

```python
# In _play_station(), after setting pipeline to PLAYING:
bus = self.player.get_bus()
bus.add_watch(GLib.PRIORITY_DEFAULT, self._on_bus_message)

def _on_bus_message(self, bus, message):
    if message.type == Gst.MessageType.TAG:
        taglist = message.parse_tag()
        ok, title = taglist.get_string(Gst.TAG_TITLE)
        if ok and title:
            # title is often "Artist - Title" for ICY streams
            GLib.idle_add(self._update_now_playing, title)
    elif message.type == Gst.MessageType.ERROR:
        err, _ = message.parse_error()
        GLib.idle_add(self._handle_error, err)
    return True  # keep watch active
```

**ICY stream specifics:** ShoutCast/Icecast streams deliver the `StreamTitle` metadata field. `icydemux` maps this to `GST_TAG_TITLE`. The value is typically the raw "Artist - Title" string without splitting. `Gst.TAG_ARTIST` may be empty for many stations — plan for title-only parsing.

**Confidence:** HIGH — GStreamer TAG messages are a stable, well-documented API. `playbin` + `icydemux` auto-negotiation for ICY streams is the canonical approach. The bus watch pattern integrates cleanly with the existing `playbin` in `main.py`.

**What NOT to use:**
- Do not poll `get_state()` in a timer loop to detect metadata changes — wasteful
- Do not use `Gst.Bus.pop()` in a manual loop — misses messages and blocks the main thread
- Do not attempt to parse raw HTTP headers for ICY metadata manually — unnecessary, GStreamer handles it

---

## New Stack: Cover Art Lookup

### Approach: iTunes Search API (primary) + MusicBrainz CAA (fallback, optional)

**No new libraries beyond `urllib` (stdlib).** Both APIs are free and require no API keys. HTTP requests must be dispatched off the GTK main thread using `threading.Thread` + `GLib.idle_add` for UI updates.

### Primary: iTunes Search API

| Component | Purpose | Why |
|-----------|---------|-----|
| `https://itunes.apple.com/search` | Artwork URL lookup by artist+title | Free, no key, returns `artworkUrl100` directly in JSON, well-suited to track-level queries |
| `urllib.request` (stdlib) | HTTP GET | No extra dependency; sufficient for simple JSON fetches |
| `threading.Thread` (stdlib) | Off-thread HTTP | Keep GTK main loop unblocked |
| `GLib.idle_add()` | Marshal result back to UI thread | Required for GTK widget updates from threads |
| `urllib.parse.urlencode` (stdlib) | Build query string | Encode "Artist - Title" term |

**Query pattern:**
```
GET https://itunes.apple.com/search?term={artist}+{title}&media=music&entity=musicTrack&limit=1
```
Response field: `results[0].artworkUrl100` — replace `100x100` with `600x600` for better resolution:
`artworkUrl100.replace("100x100", "600x600")`

**Rate limit:** ~20 requests/minute (confirmed from official Apple docs). For this app's use case (one lookup per track change on a stream), this is never a concern.

**Confidence:** HIGH — API behavior and `artworkUrl100` field confirmed via official Apple iTunes Search API documentation (no key required, ~20 calls/min limit).

### Fallback: MusicBrainz Cover Art Archive

Use only if iTunes returns no results (e.g., for obscure artists or stations with unusual metadata).

| Component | Purpose | Why |
|-----------|---------|-----|
| `https://musicbrainz.org/ws/2/recording/` | Recording search by artist+title | Returns release MBIDs needed for CAA lookup |
| `https://coverartarchive.org/release/{mbid}/front` | Cover art image | Free, no key, redirects to actual image file |

**Two-step lookup:**
1. `GET https://musicbrainz.org/ws/2/recording/?query=recording:"{title}" AND artist:"{artist}"&fmt=json` → extract `releases[0].id`
2. `GET https://coverartarchive.org/release/{mbid}/front-250` → image bytes

**Rate limit:** MusicBrainz requires 1 request/second and a descriptive `User-Agent` header (e.g., `MusicStreamer/1.0 (user@host)`). Violating this causes 503 throttling.

**Confidence:** MEDIUM — MusicBrainz API structure is well-established but the query syntax details (Lucene query format, field names) rely on training data knowledge rather than verified docs in this session.

**What NOT to use:**
- `requests` library — unnecessary added dependency; `urllib` covers this completely
- Last.fm API — requires an API key
- Spotify API — requires OAuth, not suitable for a no-auth desktop app
- Deezer API — technically keyless but less reliable artwork coverage and undocumented rate limits
- `musicbrainzngs` Python library — correct tool for heavy MusicBrainz use, but overkill for two endpoints; adds a pip dependency when urllib suffices

---

## New Stack: Filtering and Search UI

### Approach: GTK4 native filter widgets + ListBox.set_filter_func

**No new libraries required.** All needed widgets are in GTK 4.0 and Libadwaita 1.

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| `Gtk.SearchBar` | GTK 4.0 | Collapsible search bar container | Standard GTK4 pattern for search toggle; handles Escape key dismissal automatically |
| `Gtk.SearchEntry` | GTK 4.0 | Text input with search icon and clear button | Emits `search-changed` signal on debounced input; `activate` for Enter key |
| `Gtk.DropDown` | GTK 4.0 | Provider filter dropdown | GTK4's replacement for `Gtk.ComboBoxText`; uses `Gtk.StringList` as model |
| `Gtk.StringList` | GTK 4.0 | Model for DropDown options | Simple string list model, no boilerplate |
| `Gtk.ListBox.set_filter_func()` | GTK 4.0 | Row visibility predicate | Efficient — GTK calls it per-row on `invalidate_filter()`; no manual row management |
| `Gtk.ListBox.invalidate_filter()` | GTK 4.0 | Trigger re-evaluation of all rows | Call this whenever filter state changes |

**Implementation pattern:**

```python
# Filter state on MainWindow
self._search_text = ""
self._active_provider = None  # None = "All"
self._active_tag = None       # None = "All"

# Connect signals
self.search_entry.connect("search-changed", self._on_search_changed)
self.provider_dropdown.connect("notify::selected-item", self._on_provider_changed)
self.tag_dropdown.connect("notify::selected-item", self._on_tag_changed)

# Register filter function once
self.listbox.set_filter_func(self._filter_row)

def _filter_row(self, row) -> bool:
    st = row.station  # attach Station dataclass to row at build time
    if self._search_text and self._search_text not in st.name.lower():
        return False
    if self._active_provider and st.provider_name != self._active_provider:
        return False
    if self._active_tag and self._active_tag not in (st.tags or "").split(","):
        return False
    return True

def _on_search_changed(self, entry):
    self._search_text = entry.get_text().lower().strip()
    self.listbox.invalidate_filter()
```

**SearchBar toggle pattern (standard GNOME pattern):**
```python
search_btn = Gtk.ToggleButton(icon_name="system-search-symbolic")
search_bar = Gtk.SearchBar()
search_bar.connect_entry(self.search_entry)
search_bar.bind_property("search-mode-enabled", search_btn, "active",
                          GObject.BindingFlags.BIDIRECTIONAL)
```

**DropDown construction:**
```python
providers = ["All"] + [p.name for p in self.repo.list_providers()]
model = Gtk.StringList.new(providers)
dropdown = Gtk.DropDown(model=model)
```

**Confidence:** HIGH — `Gtk.ListBox.set_filter_func`, `Gtk.SearchBar`, `Gtk.SearchEntry`, and `Gtk.DropDown` are stable GTK 4.0 APIs. `Gtk.DropDown` replaced `Gtk.ComboBox`/`Gtk.ComboBoxText` in GTK4 — this is the correct current widget. The filter_func pattern is the canonical GTK4 approach for in-memory list filtering.

**What NOT to use:**
- `Gtk.ComboBox` or `Gtk.ComboBoxText` — deprecated in GTK4, use `Gtk.DropDown`
- `Gtk.SearchBar.connect_entry()` with a plain `Gtk.Entry` — use `Gtk.SearchEntry` specifically (adds search icon, clear button, and correct signal semantics)
- Manual show/hide of rows by calling `row.set_visible(False)` — fragile, breaks when reloading the list; `set_filter_func` is authoritative
- `Adw.SearchBar` — there is no such widget in Libadwaita 1; `Gtk.SearchBar` is the correct widget even in Adwaita-styled apps

---

## Threading Model for Network Calls

Cover art lookups are the only network calls not handled by GStreamer. These must be off-thread.

| Component | Purpose | Why |
|-----------|---------|-----|
| `threading.Thread` (stdlib) | Run HTTP fetch off GTK main thread | GTK main loop blocks on synchronous I/O |
| `GLib.idle_add(callback, data)` | Marshal UI update back to main thread | Only safe way to update GTK widgets from a non-main thread |
| In-memory cache (`dict`) | Avoid redundant lookups for the same artist+title | ICY metadata fires repeatedly; cache prevents API hammering |

**Pattern:**
```python
self._art_cache: dict[str, Optional[str]] = {}  # "Artist - Title" -> image URL or None

def _fetch_art_async(self, track_title: str):
    if track_title in self._art_cache:
        GLib.idle_add(self._set_cover_art, self._art_cache[track_title])
        return
    def worker():
        url = self._lookup_art_url(track_title)  # blocking HTTP
        self._art_cache[track_title] = url
        GLib.idle_add(self._set_cover_art, url)
    threading.Thread(target=worker, daemon=True).start()
```

**Confidence:** HIGH — `GLib.idle_add` for cross-thread UI dispatch is the established GTK/GLib pattern, well-documented and stable.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Cover art API | iTunes Search API | Last.fm API | Requires API key |
| Cover art API | iTunes Search API | Spotify Web API | Requires OAuth2, not suitable for keyless desktop app |
| Cover art API | iTunes Search API | MusicBrainz CAA | Two-step lookup (slower); MusicBrainz rate limits need careful handling; iTunes is simpler and faster for this use case |
| Cover art HTTP | `urllib` (stdlib) | `requests` | Adds pip dependency; `urllib` handles simple JSON GETs without issues |
| List filter | `Gtk.ListBox.set_filter_func` | Manual row `.set_visible()` | Breaks on list reload; not composable |
| Dropdowns | `Gtk.DropDown` | `Gtk.ComboBoxText` | `Gtk.ComboBoxText` is deprecated in GTK4 |
| ICY metadata | GStreamer TAG bus watch | Manual HTTP ICY header parsing | GStreamer already parses ICY via `icydemux`; duplicating this is unnecessary |

---

## No New pip Dependencies Required

All three features can be implemented with:
- Existing system GObject/GStreamer bindings (already present)
- Python stdlib (`urllib.request`, `threading`, `json`)
- No new `pip install` needed

This is deliberate — the project has no `requirements.txt` or `pyproject.toml`, and adding a pip dependency for simple HTTP calls would be disproportionate.

---

## Sources

| Source | Confidence | Notes |
|--------|------------|-------|
| Apple iTunes Search API official docs (fetched 2026-03-18) | HIGH | Confirmed: no API key, ~20 calls/min, `artworkUrl100` field in response |
| GStreamer `playbin` + `icydemux` TAG message behavior | HIGH | Based on GStreamer application development guide patterns; `Gst.TAG_TITLE` for ICY StreamTitle is canonical |
| GTK4 `Gtk.ListBox.set_filter_func` + `Gtk.SearchBar` + `Gtk.DropDown` | HIGH | Stable GTK 4.0 API since GTK 4.0 release; no deprecations affecting these widgets |
| MusicBrainz API Lucene query syntax details | MEDIUM | Confirmed keyless, confirmed rate limit (1 req/sec); query field names from training data, not verified against current docs in this session |
| `GLib.idle_add` cross-thread dispatch pattern | HIGH | Fundamental GLib/GTK threading contract, unchanged |

---

*Research: 2026-03-18*

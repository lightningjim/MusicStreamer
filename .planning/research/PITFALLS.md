# Domain Pitfalls

**Domain:** GTK4/Python/GStreamer internet radio app — ICY metadata, album art, list filtering
**Researched:** 2026-03-18
**Confidence:** MEDIUM (training-data + codebase inspection; external search unavailable)

---

## Critical Pitfalls

Mistakes that cause rewrites or major UI breakage.

---

### Pitfall 1: GStreamer Bus Watch Not Wired — TAG Messages Never Arrive

**What goes wrong:** GStreamer emits TAG messages on the pipeline bus when ICY metadata arrives. If `bus.add_watch()` (or `bus.connect("message::tag", ...)`) is never called, the tags are silently discarded. The code currently sets up `self.player` (a `playbin`) but has no bus watch — ICY metadata is already flowing, it just has nowhere to go.

**Why it happens:** `playbin` creates an internal bus automatically. The caller must explicitly retrieve it with `self.player.get_bus()`, enable watch signals with `bus.add_signal_watch()`, and connect a handler. Missing any of these three steps means zero messages arrive.

**Consequences:** The "Now Playing" track title never updates. The feature appears broken even when GStreamer is delivering data correctly, which wastes debugging time looking in the wrong place.

**Prevention:**
- Call `bus.add_signal_watch()` before entering `PLAYING` state — not after.
- Connect `bus.connect("message::tag", self._on_bus_tag)` immediately after `add_signal_watch()`.
- In `_on_bus_tag`, call `msg.parse_tag()` to get a `Gst.TagList`, then iterate with `taglist.foreach()` or extract `Gst.TAG_TITLE` / `Gst.TAG_ARTIST` directly.
- Bus watch is per-`playbin` instance and survives state changes, so it only needs to be set up once at construction time (in `__init__`, not in `_play_station`).

**Detection:**
- Add a temporary catch-all `bus.connect("message", lambda bus, msg: print(msg.type))` — if you never see `Gst.MessageType.TAG` printed, the watch is not attached.
- Wireshark / `tcpdump` can confirm the ICY headers and in-stream title updates are arriving at the network layer.

**Phase:** ICY metadata wiring phase.

---

### Pitfall 2: GTK Label Updated from Background Thread Crashes or Corrupts UI

**What goes wrong:** GStreamer bus callbacks fire on the GLib main loop thread when using `add_signal_watch()` — this is safe. But if cover art is fetched on a worker thread (as it must be, to avoid freezing the UI), and that thread calls `self.now_label.set_text(...)` or `Gtk.Picture.set_paintable(...)` directly, it will either silently corrupt widget state or crash with an assertion failure.

**Why it happens:** GTK is not thread-safe. All widget mutations must happen on the main thread. A common mistake is: fetch art on thread → call widget method in the same thread callback → works intermittently in testing → crashes under load or on different hardware.

**Consequences:** Intermittent crashes or label/art getting stuck displaying stale data. These bugs are timing-dependent and hard to reproduce consistently.

**Prevention:**
- Fetch cover art on a `threading.Thread` (or via `GLib.idle_add` with a generator coroutine), but schedule UI updates exclusively via `GLib.idle_add(self._apply_art, pixbuf)`.
- `GLib.idle_add` queues the callable onto the main loop — it is the correct cross-thread callback mechanism in GTK Python.
- Never touch a GTK widget from the art-fetch thread, not even to read a property.

**Detection:**
- Run with `G_DEBUG=fatal-criticals` set in the environment — GTK thread violations that would otherwise be silent assertions become hard crashes with a clear stack trace.
- Watch for "GLib-GObject-CRITICAL: g_object_unref: assertion" messages in output.

**Phase:** Cover art fetching phase.

---

### Pitfall 3: Rebuilding the Entire ListBox on Every Filter Change

**What goes wrong:** The current `reload_list()` method clears and rebuilds every `Gtk.ListBoxRow` from scratch. If filtering is implemented by calling `reload_list()` after each keystroke (filtering in the DB query), the app will stutter noticeably at 50-200 rows because it destroys and recreates all GTK widgets, re-fetches images from disk, and repaints the entire list on every character typed.

**Why it happens:** It feels natural to "just re-query" since the existing path already works. The performance cost isn't obvious in a test database with 5 stations.

**Consequences:** Visible lag of 50-200ms per keystroke at the target station count. Image files re-loaded from disk on every filter event causes extra disk I/O. At 200 stations with 48×48 art, this becomes a janky, unusable search box.

**Prevention:**
- Use `Gtk.ListBox.set_filter_func(func, None)` instead of rebuilding. This lets GTK show/hide existing rows without destroying widgets. Call `listbox.invalidate_filter()` after the search text changes to trigger re-evaluation.
- The filter function receives each `Gtk.ListBoxRow` and returns `True` (show) or `False` (hide). Attach station data to the row object at build time (the existing `row.station_id` pattern already does this).
- Build the list once on startup (or after edits), never on filter changes.
- Alternatively, use `Gtk.FilterListModel` + `Gtk.StringFilter` with a `Gtk.ListView` if a full MVC rewrite is acceptable — but `set_filter_func` is the lower-risk incremental path given the current `Gtk.ListBox` structure.

**Detection:**
- Add `time.perf_counter()` traces around `reload_list()` during typing — if it exceeds ~16ms (one frame) you'll see jank.
- Test with 100+ stations loaded in the DB before declaring the implementation complete.

**Phase:** Search and filter UI phase.

---

### Pitfall 4: ICY Metadata Encoding is Latin-1, Not UTF-8

**What goes wrong:** ICY streams (ShoutCast/Icecast protocol) historically transmit metadata in Latin-1 (ISO-8859-1). GStreamer's ICY demuxer typically exposes the raw bytes as a Python `str`, but the encoding depends on the stream source. AudioAddict stations and Soma.FM both have inconsistent encoding — some send UTF-8, some send Latin-1. Displaying bytes interpreted as the wrong encoding produces mojibake ("Ã©" instead of "é") in the now-playing label.

**Why it happens:** GStreamer's `TAG_TITLE` value comes out of the TagList as a Python string. Whether it has been correctly decoded depends on the GStreamer ICY plugin version and the stream's actual encoding, which is unspecified by the protocol.

**Consequences:** Station titles with non-ASCII characters (accented letters, em-dashes, curly quotes common in song titles) display as garbage characters. This is not a crash — it looks like a minor cosmetic bug but erodes trust in the feature.

**Prevention:**
- After extracting the tag string, defensively re-encode to `bytes` with `'latin-1'` and decode as `'utf-8'` with `errors='replace'`. If that raises, fall back to the original value.
- Example heuristic: `title.encode('latin-1', errors='replace').decode('utf-8', errors='replace')` — if the result contains fewer replacement characters, use it; otherwise keep the original.
- Log the raw bytes in development to determine which streams are which.

**Detection:**
- Test with a Soma.FM station that plays music with accented artist names (e.g., "Café del Mar" tracks).
- Add a raw-bytes debug log of the tag value before display.

**Phase:** ICY metadata wiring phase.

---

## Moderate Pitfalls

---

### Pitfall 5: Cover Art Requests Fired on Every Tag Update, Not Debounced

**What goes wrong:** ICY TAG messages arrive frequently — some streams fire them every few seconds, not just on track change. If each TAG message triggers a cover art HTTP request, the app will hammer the iTunes Search API or MusicBrainz with dozens of identical queries per minute. iTunes Search will rate-limit (HTTP 429) and MusicBrainz enforces 1 req/sec strictly.

**Prevention:**
- Track `(artist, title)` as `self._last_track`. Only fire a cover art lookup when the pair differs from the previous TAG message.
- Add a minimum cooldown (e.g., 10 seconds) before issuing another lookup even if the track changes, using `GLib.timeout_add`.
- Cache the most recently fetched art keyed by `(artist, title)` in a small in-memory dict to avoid refetching within the same session.

**Detection:**
- Monitor network requests in development — if you see repeated identical HTTP requests during continuous playback, debounce is missing.

**Phase:** Cover art fetching phase.

---

### Pitfall 6: Composing Provider + Tag Filters Naively Breaks When Both Are Active

**What goes wrong:** Provider filtering and tag filtering are separate requirements that must compose. A common mistake is to implement them as independent `if` blocks that each independently reset or override the other. The result: selecting a provider clears any active tag filter, or vice versa.

**Prevention:**
- Store filter state as a single struct: `self._filter = {"provider_id": None, "tag": None, "search": ""}`.
- The `set_filter_func` callback reads all three fields and applies them with `AND` logic.
- All three UI controls (provider dropdown, tag dropdown, search entry) update fields in this struct, then call `listbox.invalidate_filter()` — never rebuild the list.
- The existing comma-separated tags string (e.g., `"jazz, chill"`) needs consistent normalization before comparison. Strip whitespace from each token when reading from DB.

**Detection:**
- Test all four combinations: provider only, tag only, both, neither. Confirm the intersection is correct.
- Add stations with overlapping and non-overlapping tags to the test dataset.

**Phase:** Search and filter UI phase.

---

### Pitfall 7: `Gtk.Picture` in List Rows Loads Full-Resolution Images Every Time

**What goes wrong:** `reload_list()` currently creates a new `Gtk.Picture.new_for_filename(abs_path)` for each row. GTK4's `Gtk.Picture` loads the image at its natural resolution and then scales to the requested size at paint time. For 48×48 display, loading a 500×500 PNG on every list rebuild is wasted I/O. This is already noted in CONCERNS.md but becomes worse when the list is rebuilt frequently.

**Prevention:**
- Pre-scale images to their display size (48×48 for list rows) at asset-copy time using `GdkPixbuf.Pixbuf.new_from_file_at_scale()`, or store a `_thumb` variant alongside the full asset.
- If pre-scaling at ingest time is too complex for this milestone, at minimum use `GdkPixbuf.Pixbuf.new_from_file_at_size()` when constructing the row, and cache the `Pixbuf` per station ID in a dict on the window.
- This is a prerequisite for the "station art inline per row" feature being performant.

**Detection:**
- Run with `MALLOC_CHECK_=1` and watch RSS growth while scrolling a list of 100 stations with art.

**Phase:** Station art in list rows (inline display) phase.

---

### Pitfall 8: Existing `reload_list()` Called from `on_saved` Clears Playing-Row Highlight

**What goes wrong:** `EditStationDialog` calls `on_saved=self.reload_list` after a save. This destroys and rebuilds all rows. Any visual indication of the currently-playing station (row highlight, bold text, icon) is lost. With the existing code there is no such indicator, but the moment one is added it will be wiped on every edit.

**Prevention:**
- Track `self._playing_station_id` on `MainWindow`.
- After `reload_list()` completes, re-select or re-highlight the row matching `_playing_station_id`.
- This is cheap: iterate `listbox.get_first_child()` once and `listbox.select_row()` on the match.

**Detection:**
- Play a station, open its editor, save without changes — verify playback indicator persists.

**Phase:** Search and filter UI phase (when visual playing indicator is added).

---

## Minor Pitfalls

---

### Pitfall 9: TAG Messages Arrive Before `PLAYING` State Fully Established

**What goes wrong:** GStreamer may emit `TAG` messages during buffering (before `STATE_CHANGED` to `PLAYING`). If the handler tries to access `self._playing_station` to associate the tag with the current station, it may find `None` or the previous station if state assignment races with the first tag delivery.

**Prevention:**
- Accept and display TAG title regardless of whether a station reference is available — the title is self-contained in the message.
- Set `self._playing_station_id` before calling `player.set_state(Gst.State.PLAYING)`, not after.

**Phase:** ICY metadata wiring phase.

---

### Pitfall 10: MusicBrainz Requires a Descriptive User-Agent or Returns 403

**What goes wrong:** MusicBrainz's Web Service explicitly requires a non-generic `User-Agent` header of the form `ApplicationName/version (contact)`. Requests with a generic or missing User-Agent return HTTP 403. This is a common first-run surprise when testing the cover art endpoint.

**Prevention:**
- Set `User-Agent: MusicStreamer/0.1 (local GNOME desktop app)` on all requests to `musicbrainz.org`.
- If using iTunes Search API instead, this is not required — iTunes is more permissive.

**Detection:**
- HTTP 403 response from `musicbrainz.org` with no other error message.

**Phase:** Cover art fetching phase.

---

### Pitfall 11: Tag Filtering Broken by Whitespace in Stored Tags

**What goes wrong:** The existing DB stores tags as comma-separated strings with potential leading/trailing spaces (e.g., `"jazz, chill, ambient"` or `"jazz,chill,  ambient"`). A filter for "chill" may not match `" chill"` depending on how split/strip is applied.

**Prevention:**
- Normalize on write: strip and lowercase each tag token before storing (fix in `ensure_provider` or the equivalent tag-parsing path).
- Normalize on read: apply `.strip().lower()` to each split token before comparison in the filter function.
- Do not assume existing data is clean — the migration to a `station_tags` junction table (noted in CONCERNS.md) would solve this permanently, but tag normalization during filtering provides an immediate fix.

**Phase:** Search and filter UI phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| ICY metadata wiring | Bus watch not attached (Pitfall 1) | Set up `add_signal_watch()` + `connect("message::tag")` in `__init__` |
| ICY metadata wiring | Latin-1/UTF-8 encoding mojibake (Pitfall 4) | Defensive re-encode heuristic on every tag string |
| ICY metadata wiring | TAG arrives before `PLAYING` state (Pitfall 9) | Set station ID before `set_state(PLAYING)` |
| Cover art fetching | GTK widget update from worker thread (Pitfall 2) | Always `GLib.idle_add` for widget mutations |
| Cover art fetching | Hammering external API on every TAG (Pitfall 5) | Debounce on `(artist, title)` pair change + cooldown |
| Cover art fetching | MusicBrainz 403 on generic User-Agent (Pitfall 10) | Set descriptive `User-Agent` header |
| Search/filter UI | Rebuilding list on every keystroke (Pitfall 3) | Use `set_filter_func` + `invalidate_filter()` |
| Search/filter UI | Filters not composing (Pitfall 6) | Single filter-state struct; `AND` all conditions |
| Search/filter UI | Tag whitespace mismatches (Pitfall 11) | Normalize on write and on comparison |
| Station art in rows | Full-res images in list rows (Pitfall 7) | Cache/pre-scale to display size |
| Any edit that calls `reload_list` | Playing indicator lost (Pitfall 8) | Restore selection after rebuild |

---

## Sources

- Codebase inspection: `/home/kcreasey/OneDrive/Projects/MusicStreamer/main.py` (511 lines, 2026-03-18)
- Codebase concerns audit: `.planning/codebase/CONCERNS.md` (2026-03-18)
- GStreamer bus/TAG handling: training data (MEDIUM confidence — GStreamer 1.x Python API stable since 1.18)
- GTK4 `set_filter_func` vs `FilterListModel`: training data (MEDIUM confidence — GTK 4.x API)
- GLib thread safety (`idle_add`): training data (HIGH confidence — GTK thread model is well-established)
- ICY encoding behavior: training data (LOW confidence — stream-source dependent, validate against real Soma.FM/AudioAddict streams)
- MusicBrainz User-Agent requirement: training data (MEDIUM confidence — documented policy, verify against current docs)
- iTunes Search API rate limits: training data (LOW confidence — undocumented, validate empirically)

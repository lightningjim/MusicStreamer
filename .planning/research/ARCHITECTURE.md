# Architecture Patterns

**Domain:** GTK4/Python desktop radio player — v1.4 Media & Art Polish
**Researched:** 2026-04-03
**Confidence:** HIGH (existing codebase is ground truth; external unknowns flagged explicitly)

---

## Current Architecture (v1.3 baseline)

```
musicstreamer/
├── constants.py        — DATA_DIR, DB_PATH, ASSETS_DIR
├── models.py           — Station, Provider, Favorite dataclasses
├── repo.py             — Repo: all SQLite reads/writes; get_setting/set_setting
├── player.py           — Player: GStreamer playbin3 pipeline + mpv subprocess (YT)
├── cover_art.py        — iTunes Search API fetch (daemon thread + GLib.idle_add callback)
├── assets.py           — copy_asset_for_station: copies image to DATA_DIR/assets/<id>/
├── filter_utils.py     — normalize_tags, matches_filter_multi
├── aa_import.py        — fetch_channels, import_stations (AudioAddict backend)
├── yt_import.py        — YouTube playlist import backend
├── radio_browser.py    — Radio-Browser.info search client
└── ui/
    ├── main_window.py  — MainWindow: all layout, state, playback wiring
    ├── station_row.py  — StationRow (ListBoxRow wrapping ActionRow)
    ├── edit_dialog.py  — EditStationDialog (URL focus-out auto-fetches YT thumbnail)
    ├── discovery_dialog.py
    └── import_dialog.py
```

State lives in `MainWindow`. `Repo` is stateless (holds connection). All background work uses
`threading.Thread(daemon=True)` + `GLib.idle_add` to return results to the GTK thread.

---

## Feature Integration Map

### Feature 1: GStreamer Buffer Tuning (STREAM-01)

**Files changed:** `player.py` only

**Where:** `Player.__init__`, after `self._pipeline = Gst.ElementFactory.make("playbin3", "player")`.

playbin3 exposes buffer-size (bytes) and buffer-duration (nanoseconds) properties directly on
the playbin3 element. Set both immediately after construction, before any URI is assigned.

```python
# After line 19 (pipeline construction):
self._pipeline.set_property("buffer-size", 2 * 1024 * 1024)   # 2 MB
self._pipeline.set_property("buffer-duration", 5 * Gst.SECOND)  # 5 s
```

These apply only to HTTP/ShoutCast streams. YouTube playback uses the mpv subprocess path
(`_play_youtube`), which bypasses GStreamer entirely — buffer tuning there is a separate mpv
concern and out of scope for this feature.

**New components:** none
**Dependencies:** none — fully isolated


### Feature 2: AudioAddict Station Art (ART-01)

**Files changed:** `aa_import.py` (primary), `edit_dialog.py` (secondary / bonus)

#### 2a. At import time (aa_import.py)

The current `fetch_channels` loop uses only `ch["name"]` and `ch["key"]`. The AA API channel
response is known to include image/logo fields but the exact field names must be confirmed from
a live API response at implementation time.

**Known candidate fields** (from community reverse-engineering of AA API; MEDIUM confidence):
- `asset_url` — used in some third-party clients for channel artwork
- `images` — object or array of image variants (seen in newer API versions)
- A base URL pattern of `https://assets.di.fm/static/images/default_channel_images/<key>.png`
  is commonly referenced as a fallback even when no explicit image field exists

**Verification step (required before coding):** Call
`https://listen.di.fm/premium_high?listen_key=<key>` with a real key and `print(json.dumps(data[0], indent=2))`
to see the complete first channel object. Identify the image field name, then add extraction to
`fetch_channels` and pass it through the channel dict.

**Change to `fetch_channels`:** Add `"art_url": ch.get("<field_name>", "")` to each result dict.

**Change to `import_stations`:** When `art_url` is non-empty and the station is newly inserted,
fetch the image URL in a subprocess/thread, write it to a tempfile, then call
`copy_asset_for_station(station_id, tmp_path, "station_art")` and
`repo.update_station(..., station_art_path=rel_path, ...)`.

**Threading note:** `import_stations` runs in an import dialog thread already. Image fetches can
run inline in that thread (blocking per-channel). Keep `on_progress` call after art fetch to
avoid confusing progress count.

**New components:** none (art download is `urllib.request.urlopen` inline — same pattern as YT
thumbnail fetch in `edit_dialog.py`)

#### 2b. Edit dialog AA URL detection (edit_dialog.py) — optional enhancement

`_on_url_focus_out` currently gates on `_is_youtube_url()`. Add a parallel `_is_aa_url()`
check: if the URL contains `di.fm`, `radiotunes.com`, `jazzradio.com`, etc., derive the channel
key from the URL path, construct the logo URL (using the confirmed base pattern), and fetch it.
This is the same code path as the YT thumbnail fetch — same spinner, same `copy_asset_for_station`.

This is a bonus UX path; the import-time fetch (2a) is the requirement.

**Dependencies:** Field name discovery must happen before coding. Block Phase 2 on that.


### Feature 3: YouTube Thumbnail 16:9 (ART-02)

**Files changed:** `main_window.py` only

**Where:** The now-playing panel's right slot (cover_stack) is currently 160×160, square. The
`cover_image` Gtk.Image is loaded via `GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 160, 160, False)`.

**Change:** Make the right art slot aspect-ratio-aware for YouTube stations:

1. The `cover_stack` and `cover_image` need a wider size_request when a YouTube station is
   playing. Natural 16:9 at panel height 160px → width 284px.
2. In `_play_station`, detect `"youtube.com" in st.url or "youtu.be" in st.url`. If true:
   - `cover_stack.set_size_request(284, 160)`
   - Load pixbuf with `new_from_file_at_scale(path, 284, 160, False)` (preserve ratio)
   - `cover_image.set_content_fit(Gtk.ContentFit.FILL)` or use `Gtk.Picture` instead of
     `Gtk.Image` for better aspect-ratio handling (see note below)
3. On `_stop()` or when playing a non-YT station, reset to `(160, 160)`.

**Gtk.Image vs Gtk.Picture:** The now-playing slots use `Gtk.Image`, which requires explicit
pixbuf scaling. Switching `cover_image` to `Gtk.Picture` would let GTK handle aspect-ratio
fitting natively via `set_content_fit(Gtk.ContentFit.CONTAIN)`. This is a moderate refactor of
the cover slot only — no change to the logo slot or list rows.

**Panel layout impact:** The panel is a horizontal `Gtk.Box` with `set_size_request(-1, 160)`.
Widening the right slot shrinks the center column since center has `set_hexpand(True)`. This is
acceptable: the panel already has defined fixed-size left (160) and right (160) slots; going to
284 on the right reduces center space by ~124px at 900px window width. Flag for visual review.

**New components:** none
**Dependencies:** none — independent of other v1.4 features


### Feature 4: Custom Accent Color (ACCENT-01)

**Files changed:** `main_window.py` (CSS provider wiring + settings load/save), new
`ui/accent_dialog.py` (color picker dialog)

**Persistence:** `repo.get_setting("accent_color", "")` / `repo.set_setting("accent_color", value)`.
The `settings` table already exists via `db_init`. No schema migration needed.

**CSS injection pattern:**

```python
# In MainWindow.__init__ (or a helper):
self._css_provider = Gtk.CssProvider()
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(),
    self._css_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
)

def _apply_accent(self, hex_color: str):
    if hex_color:
        css = f":root {{ --accent-color: {hex_color}; }}"
        # Libadwaita 1.2+ supports accent-color override:
        css = f"* {{ --accent-bg-color: {hex_color}; }}"
    else:
        css = ""
    self._css_provider.load_from_data(css.encode())
```

**Libadwaita accent color API:** Libadwaita 1.6 (GNOME 47+) introduced
`Adw.StyleManager.set_accent_color(Adw.AccentColor)` for first-class accent control, but it
uses a fixed enum of named colors, not arbitrary hex. For arbitrary hex input, CSS injection via
`--accent-bg-color` custom property remains the correct approach for GTK4/Libadwaita. (MEDIUM
confidence — verify `Adw.StyleManager` availability at target GNOME version.)

**UI entry point:** Add an "Accent" button or icon button to the header bar in `main_window.py`.
Opens `AccentColorDialog` (new `Adw.Window` or `Adw.Dialog`).

**AccentColorDialog contents:**
- Row of preset color swatches (6–8 named colors as `Gtk.ColorButton` or custom square buttons)
- `Gtk.Entry` for hex input
- "Reset to default" option (empty string → remove CSS override)
- Apply callback → `_apply_accent(hex)` + `repo.set_setting("accent_color", hex)`

**Load on startup:** In `MainWindow.__init__`, after CSS provider is registered:
```python
saved = self.repo.get_setting("accent_color", "")
if saved:
    self._apply_accent(saved)
```

**New components:** `musicstreamer/ui/accent_dialog.py` (new file)
**Modified:** `main_window.py` — CSS provider setup, accent button, load-on-startup
**Dependencies:** none — fully independent

---

## Files Changed Per Feature

| Feature | Files Modified | New Files |
|---------|---------------|-----------|
| STREAM-01: Buffer tuning | `player.py` | none |
| ART-01: AA station art | `aa_import.py` | none |
| ART-01 bonus: edit dialog | `edit_dialog.py` | none |
| ART-02: YT thumbnail 16:9 | `main_window.py` | none |
| ACCENT-01: Accent color | `main_window.py` | `ui/accent_dialog.py` |

No new DB migrations required. No new modules required except `accent_dialog.py`.

---

## Recommended Build Order

```
Phase 16: GStreamer buffer tuning  (STREAM-01)
  Scope: player.py only, 2-3 lines
  Dependencies: none
  Risk: LOW — property names are GStreamer standard; easy to verify at test time

Phase 17: AudioAddict station art  (ART-01)
  Scope: aa_import.py + optional edit_dialog.py
  Dependencies: REQUIRES live API response inspection first to identify image field name
  Risk: MEDIUM — field name unknown, fetch-and-store pattern is established

Phase 18: YouTube thumbnail 16:9  (ART-02)
  Scope: main_window.py cover slot only
  Dependencies: none
  Risk: LOW-MEDIUM — layout change needs visual QA; Gtk.Image vs Gtk.Picture decision

Phase 19: Accent color  (ACCENT-01)
  Scope: main_window.py + new accent_dialog.py
  Dependencies: none
  Risk: MEDIUM — Libadwaita CSS injection approach needs version check
```

**Rationale for order:**
- Phase 16 first: smallest scope, zero risk, immediately improves stream reliability for all testing of subsequent phases.
- Phase 17 second: blocked on API field discovery, so start the live-response check during Phase 16 build.
- Phase 18 third: standalone layout change, easy to verify visually before adding UI chrome.
- Phase 19 last: new dialog + CSS wiring; most surface area, most QA needed.

All four phases are independent and could be built in any order. The order above is risk-ascending.

---

## Integration Notes

### AA Image Field — MUST VERIFY BEFORE CODING

The `aa_import.py` `fetch_channels` function currently extracts only `ch["name"]` and `ch["key"]`
from the channel JSON. Before writing ART-01, print the full first channel object from a live
API call to identify the image field. Common candidates seen in third-party clients:
- `asset_url` (string)
- `images` (dict with size variants)
- `channel_director` (unrelated — ignore)

If no image field exists in the quality-tier endpoint (`listen.di.fm/premium_high?listen_key=...`),
try the channel metadata endpoint `https://api.audioaddict.com/v1/di/channel_filters/0/channels`
which is a richer response format used by the web player.

### GStreamer buffer-size vs buffer-duration

Set both. `buffer-size` caps memory usage; `buffer-duration` is what controls pre-roll/rebuffer
behavior on ShoutCast streams. For typical 128–320 kbps streams, 2 MB / 5 s is a reasonable
default. These can be exposed as `repo.get_setting` values later if user-tuning is wanted.

### CSS Provider Scope

`Gtk.StyleContext.add_provider_for_display` applies CSS globally to the entire display. This is
correct for accent color (which should affect all widgets). Do not use
`widget.get_style_context().add_provider()` — that applies only to one widget.

### YT Thumbnail Aspect Ratio in now-playing panel

The panel uses `Gtk.Box` (horizontal) with a fixed height constraint. The cover_stack currently
has `set_size_request(160, 160)`. For 16:9 display:
- Change `set_size_request` to `(285, 160)` when YouTube station plays
- Reset to `(160, 160)` on stop or non-YT station
- The center column has `set_hexpand(True)` — it will absorb the width change automatically

The `now-playing-art` CSS class has `border-radius` applied at the Stack level (confirmed from
PROJECT.md decisions). Changing size_request does not break the border-radius.

---

## Anti-Patterns to Avoid

### Setting GStreamer buffer properties after PLAYING state
Set buffer-size and buffer-duration on the pipeline while in NULL state (construction time).
Setting them after `set_state(PLAYING)` may have no effect on the current playback.

### Fetching AA art on the GTK main thread
Any `urllib.request.urlopen` for art images must stay in the import thread. The import already
runs in a daemon thread. Do not use `GLib.idle_add` for the fetch itself — only for UI updates.

### Hardcoding the AA image base URL without verifying
Multiple community clients use different URL patterns. Confirm the actual field from a live
response rather than assuming a URL template.

### Using Adw.StyleManager.set_accent_color for arbitrary hex
This API only supports a fixed enum (`Adw.AccentColor.BLUE`, etc.), not hex strings. Use
CSS custom property injection for arbitrary color support.

---

## Sources

- Existing codebase `musicstreamer/` — PRIMARY, HIGH confidence
- GStreamer playbin3 `buffer-size`, `buffer-duration` properties — standard GStreamer 1.x API; HIGH confidence
- GTK4 `Gtk.StyleContext.add_provider_for_display` — standard GTK4 CSS injection pattern; HIGH confidence
- Libadwaita `--accent-bg-color` CSS custom property — MEDIUM confidence; verify against installed Adw version
- AudioAddict channel JSON image field name — LOW confidence; must inspect live API response
- `copy_asset_for_station` pattern for art persistence — existing codebase, HIGH confidence

---
*Architecture research for: MusicStreamer v1.4 Media & Art Polish*
*Researched: 2026-04-03*

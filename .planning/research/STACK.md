# Technology Stack — v1.4 Media & Art Polish

**Project:** MusicStreamer v1.4
**Researched:** 2026-04-03
**Scope:** New capabilities only. Existing stack (GTK4/Libadwaita, GStreamer, SQLite, yt-dlp, urllib, threading/GLib.idle_add) is validated and unchanged.

---

## No New Dependencies Required

All 4 v1.4 features are achievable with the existing stack. No new packages, no pip changes, uv.lock unchanged.

| Feature | Libraries Needed | Status |
|---------|-----------------|--------|
| GStreamer buffer tuning | `Gst` — already imported in player.py | Existing |
| AA channel logos | `urllib.request` + `json` — already in aa_import.py | Existing |
| GTK4 CSS accent color | `Gtk.CssProvider`, `Gdk.Display` — already used in `__main__.py` | Existing |
| YouTube 16:9 thumbnail | `GdkPixbuf.Pixbuf` — already imported in main_window.py | Existing |

---

## Feature 1: GStreamer Buffer Tuning (STREAM-01)

### Integration Point

`musicstreamer/player.py` — `Player.__init__()`, immediately after `playbin3` is created and before URI is ever set.

### Properties on `playbin3`

| Property | Type | Recommended Value | Notes |
|----------|------|------------------|-------|
| `buffer-duration` | int (nanoseconds) | `5 * Gst.SECOND` = 5,000,000,000 | Primary lever. Playbin uses rate estimate to scale buffered data. Takes effect on next NULL→PLAYING cycle. |
| `buffer-size` | int (bytes) | `2 * 1024 * 1024` (2 MB) | Fallback when rate estimate unavailable. |
| `ring-buffer-max-size` | int (bytes) | leave at 0 (default disabled) | Progressive download ring buffer — not applicable to live HTTP/ShoutCast streams. Do not set. |

**Call site (in `__init__`, after creating `_pipeline`):**
```python
self._pipeline.set_property("buffer-duration", 5 * Gst.SECOND)
self._pipeline.set_property("buffer-size", 2 * 1024 * 1024)
```

These are set once at construction. They persist across URI changes as long as the pipeline is reused (the current pattern: `set_state(NULL)` → `set_property("uri", ...)` → `set_state(PLAYING)`).

**Confidence:** HIGH — `buffer-size` and `buffer-duration` confirmed in official GStreamer playbin3 docs. `ring-buffer-max-size` confirmed as progressive-download-only (not applicable here).

**Sources:**
- https://gstreamer.freedesktop.org/documentation/playback/playbin3.html
- https://gstreamer.freedesktop.org/documentation/application-development/advanced/buffering.html

---

## Feature 2: AudioAddict Channel Logo (ART-01)

### Integration Point

`musicstreamer/aa_import.py` — `fetch_channels()` and `import_stations()`.

### API Endpoint for Images

The existing `fetch_channels()` call hits `https://{net['domain']}/{tier}?listen_key={listen_key}` — this is the stream/PLS listing endpoint and does **not** include image data.

Image data lives on a separate public endpoint (no auth required):

```
https://api.audioaddict.com/v1/{network_slug}/channels
```

e.g. `https://api.audioaddict.com/v1/di/channels`

The `network_slug` maps directly to the `slug` field already in the `NETWORKS` list in `aa_import.py` (`"di"`, `"radiotunes"`, `"jazzradio"`, `"rockradio"`, `"classicalradio"`, `"zenradio"`).

### Image Field

The extended channel object from this endpoint includes a `channel_images` dict. Based on third-party plugin analysis (Kodi addon issue trace referencing `KeyError: 'default'` on `channel_images`), the structure is:

```json
{
  "key": "ambient",
  "name": "Ambient",
  "channel_images": {
    "default": "https://cdn-radioassets.audioaddict.com/...",
    "compact": "...",
    "horizontal_banner": "..."
  }
}
```

Access via `ch.get('channel_images', {}).get('default')`.

**MUST VERIFY at implementation time:** Print raw channel dict from `/v1/di/channels` before writing production code. The `channel_images.default` field name is inferred from plugin error traces, not confirmed against live API response.

### Recommended Implementation

1. In `fetch_channels()`, add one request per network to `https://api.audioaddict.com/v1/{slug}/channels` to build a `channel_key → image_url` lookup dict.
2. When constructing each channel dict, add `"image_url": image_lookup.get(ch['key'])`.
3. In `import_stations()`, download the image bytes via `urllib.request.urlopen`, save to `DATA_DIR/art/`, and pass the relative path to `repo.insert_station()`.
4. Check `repo.insert_station()` signature — the `art` or image parameter name needs to match what was wired in v1.1 (station art storage).

**Confidence:** MEDIUM — endpoint URL pattern confirmed by multiple community AA clients. `channel_images.default` field inferred from plugin error traces, not from live API response inspection.

---

## Feature 3: GTK4 CSS Accent Color (ACCENT-01)

### Integration Point

`musicstreamer/__main__.py` — `App.do_activate()`. The exact pattern already exists for `_APP_CSS`.

### Existing Pattern (already working in codebase)

```python
css_provider = Gtk.CssProvider()
css_provider.load_from_string(_APP_CSS)
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(),
    css_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
)
```

### Accent Color Override

Libadwaita exposes accent color via CSS named colors. Override at runtime with a second provider:

```python
accent_css = f"@define-color accent_color {hex_color}; @define-color accent_bg_color {hex_color};"
accent_provider = Gtk.CssProvider()
accent_provider.load_from_string(accent_css)
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(),
    accent_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
)
```

**CSS variables to override:**

| Variable | Role |
|----------|------|
| `accent_color` | Standalone use (accent text on regular background) |
| `accent_bg_color` | Background for accent-colored widgets (buttons, highlights) |
| `accent_fg_color` | Foreground over accent background — Libadwaita derives this automatically; leave unset unless contrast issues arise |

**Priority:** `STYLE_PROVIDER_PRIORITY_APPLICATION + 1` ensures accent provider beats the base `_APP_CSS` provider. CSS overrides always win over `AdwStyleManager` — the style manager API returns system color, but visual rendering uses the CSS value.

**Dynamic update:** Hold the `accent_provider` object at module or app level. Call `load_from_string()` again on the same object when the user picks a new color — GTK automatically re-applies all providers after a reload.

**Persistence:** Store hex string in SQLite via `repo.set_setting("accent_color", "#FF5733")`. Load on startup between `Gst.init()` and `win.present()`.

**Preset swatches:** Define a small fixed list of named hex values in `constants.py` (e.g. `ACCENT_PRESETS = {"Blue": "#3584e4", "Teal": "#2190a4", "Green": "#26a269", ...}`). No library needed.

**Confidence:** HIGH — `load_from_string()` is already live in this codebase; `@define-color` override confirmed in Libadwaita CSS variable docs and GTK4 CSS docs.

**Sources:**
- https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/styles-and-appearance.html
- https://docs.gtk.org/gtk4/method.CssProvider.load_from_string.html

---

## Feature 4: YouTube 16:9 Thumbnail Display (ART-02)

### Integration Point

`musicstreamer/ui/main_window.py` — wherever `GdkPixbuf.Pixbuf.new_from_file_at_scale` is called to load cover art into `cover_image`.

### Root Cause of Current Squash

All art loading currently uses:
```python
pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 160, 160, False)
```
`preserve_aspect_ratio=False` distorts 16:9 thumbnails (284×160 squashed to 160×160).

### Fix

Change to preserve aspect ratio, scale to height=160:

```python
pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, -1, 160, True)
```

- Passing `-1` for width means: scale height to 160, derive width proportionally.
- A 16:9 thumbnail scales to ~284×160. A square image scales to 160×160. No distortion in either case.
- `cover_stack` already has `set_overflow(Gtk.Overflow.HIDDEN)` and `set_size_request(160, 160)` — the wider 16:9 image clips horizontally within the 160px slot boundary. This is the intended behavior (show full height, clip excess width).
- No layout changes required.

**`new_from_file_at_scale` signature:**
```python
GdkPixbuf.Pixbuf.new_from_file_at_scale(filename: str, width: int, height: int, preserve_aspect_ratio: bool) -> Pixbuf
```

**Confidence:** HIGH — passing `-1` for one dimension to force proportional scaling is the documented behavior of `new_from_file_at_scale`. The existing `Gtk.Overflow.HIDDEN` on `cover_stack` provides the clip without additional work.

**Source:** https://docs.gtk.org/gdk-pixbuf/ctor.Pixbuf.new_from_file_at_scale.html

---

## Summary

| Feature | Key API / Property | File | Confidence |
|---------|-------------------|------|------------|
| Buffer tuning | `set_property("buffer-duration", 5 * Gst.SECOND)` | player.py | HIGH |
| Buffer tuning | `set_property("buffer-size", 2*1024*1024)` | player.py | HIGH |
| AA logo endpoint | `api.audioaddict.com/v1/{slug}/channels` | aa_import.py | MEDIUM |
| AA logo field | `ch['channel_images']['default']` | aa_import.py | MEDIUM — verify live |
| Accent color CSS | `@define-color accent_color {hex}; @define-color accent_bg_color {hex};` | `__main__.py` | HIGH |
| Accent CSS method | `Gtk.CssProvider.load_from_string()` at priority APPLICATION+1 | `__main__.py` | HIGH |
| 16:9 pixbuf | `new_from_file_at_scale(path, -1, 160, True)` | main_window.py | HIGH |

---

## What NOT to Add

| Avoid | Why |
|-------|-----|
| `requests` library | urllib covers all HTTP needs for AA image fetch |
| Any color picker library | Gtk.ColorButton is stdlib GTK4; swatches are plain Gtk.Button with CSS styling |
| New GStreamer elements | Only properties on existing `playbin3` — no new elements needed |
| `ring-buffer-max-size` changes | For progressive download only; live streams don't benefit |

---

## Sources

| Source | Confidence |
|--------|------------|
| GStreamer playbin3 docs — buffer-size, buffer-duration properties | HIGH |
| GdkPixbuf.new_from_file_at_scale — width=-1 behavior | HIGH |
| Gtk.CssProvider.load_from_string — GTK4 official docs | HIGH |
| Libadwaita CSS variables — accent_color, accent_bg_color | HIGH |
| AA channel_images field — inferred from ssapalski/plugin.audio.addict issue #8 KeyError trace | MEDIUM |

---

*Stack research for: MusicStreamer v1.4 Media & Art Polish*
*Researched: 2026-04-03*

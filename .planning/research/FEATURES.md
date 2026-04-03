# Feature Research

**Domain:** Personal GNOME desktop internet radio — v1.4 Media & Art Polish
**Researched:** 2026-04-03
**Overall confidence:** MEDIUM–HIGH (code read + web verification where possible)

---

## Scope Boundary

This file covers the four v1.4 features only. Prior v1.3 feature research is preserved in
git history. Existing behavior is documented here only where it affects edge-case handling
or implementation decisions for new features.

---

## Feature 1: GStreamer Buffer Tuning (STREAM-01)

### What the user experiences

ShoutCast/HTTP streams (AudioAddict, Soma.FM, etc.) occasionally produce a brief audible
drop-out — a fraction of a second of silence or glitch — when network delivery is momentarily
slow. This is distinct from a full stream failure (which would produce an error and stop).
The user hears it as a subtle pop or gap. On good connections it may never happen. On
congested Wi-Fi or VPN it can happen several times per minute.

### Root cause in the current implementation

`player.py` uses `playbin3` with no explicit buffer configuration. GStreamer's default
buffer size for HTTP audio streams is very small (typically ~2s or less). When a burst of
network jitter exceeds that window the queue empties and GStreamer either mutes briefly or
resets. The fix is to raise `buffer-duration` (and optionally `buffer-size`) so GStreamer
pre-buffers more before starting and tolerates longer network bursts.

### Table-stakes behavior

| Behavior | Notes |
|----------|-------|
| No audible glitches on typical home network streams | The primary requirement |
| Start-up latency increase is imperceptible (<1s) | A 5s buffer pre-loads quickly at 128–320kbps |
| Behavior unchanged for YouTube streams | YT uses mpv subprocess — completely separate code path, not affected |
| No behavior change for the user | Internal-only change; no UI needed |

### Recommended values (MEDIUM confidence — from community sources)

`buffer-duration = 5 * Gst.SECOND` (5,000,000,000 ns) is the most commonly cited value
in pithos, Mopidy, and GStreamer forum threads for resolving HTTP audio drop-outs. Some
sources combine it with `buffer-size = 1024 * 1024` (1 MB) as an upper bound. The
duration approach is preferred because it scales with bitrate; size alone can be too small
for high-bitrate streams.

`playbin3` (used in the app) exposes the same `buffer-duration` and `buffer-size`
properties as `playbin`. Both should be set.

### Edge cases

| Case | Expected behavior |
|------|-------------------|
| Stream bitrate lower than GStreamer's rate estimate | Buffering takes longer at startup; tolerable |
| Metered / slow connection where 5s of audio is large | Still correct — larger buffer helps, never hurts |
| YouTube station played | mpv subprocess handles it; `buffer-duration` setting ignored for that code path |
| Setting applied mid-stream (not at startup) | Must set before `set_state(PLAYING)`. Already the case in `_set_uri`. |
| GStreamer can't determine bitrate (rate estimate = 0) | Buffer-duration fallback is buffer-size; set both to be safe |

### Anti-feature

Do NOT expose a buffer-size slider to the user. This is an internal reliability fix. Adding
UI for it would be scope creep — the only expected outcome is that drop-outs stop happening.

---

## Feature 2: AudioAddict Station Art (ART-01 + implicit ART-01b)

### Sub-feature A: Fetch logo at bulk import time (ART-01)

**What the user experiences:** After running the AudioAddict import dialog, each imported
station has its channel logo as station art — the same square logo visible in the station
list row and now-playing left slot. Without this, all ~200 imported stations show the
generic audio icon.

**How the AA API provides images:**

The existing `aa_import.py` calls `https://listen.{domain}/{tier}?listen_key={key}` and
gets a JSON array of channel objects. Each object currently uses only `name` and `key`.

Based on community client code (Plex/Kodi plugins, mopidy-audioaddict) and the archived
api-rev-5 documentation, the channel objects in this response also contain image-related
fields. The exact field name is LOW confidence (not verified against a live response) but
community implementations reference:
- `asset_url` — a CDN URL to a square channel logo image (noted in v1.3 research)
- `images` — an object with nested keys like `default`, `compact`, etc. (seen in Kodi plugin)
- Direct URL construction: `https://cdn-radiotime-logos.tunein.com/` pattern is NOT used
  by AA; AA uses its own CDN (typically `cdn-images.audioaddict.com` or similar)

**Recommended approach:** Extract whatever image URL field is present in the response and
download it during `import_stations()`. Store via the existing `copy_asset_for_station()`
path. If the field is absent or download fails, silently skip (no logo is fine; the import
should not fail because of missing art).

**Edge cases:**

| Case | Expected behavior |
|------|-------------------|
| Channel JSON has no image field | Skip art silently; station imported with no logo |
| Image URL returns 404 or times out | `try/except` around download; skip art, continue import |
| Image is not square (e.g., 16:9 banner) | `copy_asset_for_station` + `Gtk.ContentFit.COVER` crops to 1:1 correctly |
| Re-import of existing station (dedup by URL) | Station is skipped entirely; no art update. User can manually set art if needed. |
| Image download is slow (N=200 channels) | Must be async or background; cannot block the import progress UI |
| CDN requires cookies or auth | Extremely unlikely for logo images; if it happens, silently skip |
| Image MIME is WebP (not PNG/JPEG) | GdkPixbuf supports WebP; `copy_asset_for_station` stores as-is |

**Important implementation constraint:** `import_stations()` runs in a background thread
(see `aa_import.py` usage in `ImportDialog`). Image downloads must happen on that same
thread — they cannot call GTK. All SQLite writes must use a thread-local connection (same
pattern as existing import code: `db_connect()` per-thread).

### Sub-feature B: Auto-fetch logo when user pastes an AudioAddict URL in station editor (ART-01b)

**What the user experiences:** User adds or edits a station and pastes an AudioAddict
stream URL (e.g., `https://listen.di.fm/premium_high/deephouse.pls?listen_key=...`).
The station art is auto-populated with the DI.fm channel logo — same UX as the existing
YouTube thumbnail auto-fetch when a YouTube URL is pasted.

**Trigger:** `_on_url_focus_out` in `edit_dialog.py` already calls `_start_thumbnail_fetch`
for YouTube URLs. The same hook should detect AA URLs and trigger an AA logo fetch.

**URL detection:** AA stream URLs contain `listen.di.fm`, `listen.radiotunes.com`,
`listen.jazzradio.com`, `listen.rockradio.com`, `listen.classicalradio.com`, or
`listen.zenradio.com`. A helper `_is_audioaddict_url(url)` should be added alongside the
existing `_is_youtube_url()`.

**Channel key extraction:** The stream URL path contains the channel key:
`/premium_high/deephouse.pls` → key = `deephouse`. The network domain identifies which
AA network to query.

**Logo retrieval:** Once key + network are known, either:
1. Call the AA channels API for that network and find the matching channel's image URL, OR
2. Construct a CDN URL directly if a stable pattern exists (LOW confidence — verify first)

Option 1 is safer but requires the user's API key to be available. If the station editor
doesn't have access to the stored API key, this sub-feature may need the key to be stored
in the repo settings table (not just in the import dialog's in-flight state).

**Alternative simpler approach:** If the AA API channel image URL is a predictable pattern
(e.g., `https://cdn-images.audioaddict.com/.../{key}.jpg`), a direct URL construction
avoids needing the API key at all. This must be confirmed against a live response.

**Edge cases:**

| Case | Expected behavior |
|------|-------------------|
| URL is an AA URL but channel key not found in API | Show spinner, silently revert to spinner→no-image (same as YT fail) |
| URL is an AA URL, API key not stored | Cannot fetch — silently skip; show no spinner (don't mislead user) |
| User pastes AA URL then immediately changes it | `_fetch_cancelled` flag (already exists) handles this |
| URL matches `listen.*.com` but is not actually AA | Detection is best-effort; worst case a fetch attempt fails silently |
| User pasted a non-PLS direct stream URL from AA | Channel key extraction may fail; fallback: skip logo fetch |
| Logo already set (station has existing art) | Do NOT overwrite existing art on focus-out. Only auto-populate if `station_art_rel` is currently None/empty |

---

## Feature 3: YouTube Thumbnail 16:9 Display (ART-02)

### What the user experiences

YouTube live stream stations (e.g., Lofi Girl) have wide 16:9 thumbnails. Currently the
now-playing right slot is a fixed 160×160 square with `ContentFit.COVER`, which crops
the thumbnail to its center — cutting off the sides of a 16:9 image, sometimes cropping
out the subject entirely.

The fix: show the full 16:9 image in the now-playing panel, either by letterboxing it
within the 160×160 slot or by giving it a wider slot (e.g., 284×160 for 16:9).

### Display options

| Approach | UX | Notes |
|----------|----|-------|
| `ContentFit.CONTAIN` in existing 160×160 slot | Full image, letterboxed with bars top/bottom | Simplest code change; image shrinks noticeably |
| Widen the cover art slot to 284×160 (true 16:9) | Full image, no bars | Panel width increases for YT stations only — layout shifts |
| Detect aspect ratio; conditionally adjust | Correct for each image type | More complex; covers the mixed-content case |
| `ContentFit.CONTAIN` in 284×160 slot, constrained | Full image within wider slot; ICY art still 160×160 COVER | Works if the slot is physically wider than for ICY art |

**Recommended approach:** The cleanest approach that fits the existing panel layout is to
change the `cover_image` widget to use `ContentFit.CONTAIN` and give it a fixed 284×160
size. For ICY stations, square cover art will have slight side letterboxing — acceptable.
For YT stations, the full 16:9 shows. No conditional logic needed.

Alternative: keep 160×160 for ICY art (which is always square album art) and only widen
for YouTube. This requires knowing at display time whether the current station is YouTube.
That information is available via `_current_station.url` — but adds branching.

**Simplest correct answer:** `ContentFit.CONTAIN` in the existing 160×160 slot. No layout
change. 16:9 thumbnail will be letterboxed but fully visible. This is table-stakes — just
show the whole image.

### Table-stakes behavior

| Behavior | Notes |
|----------|-------|
| Entire 16:9 thumbnail visible in now-playing | Core requirement |
| No crash or UI layout break when thumbnail loads | Verify widget size_request is honored |
| ICY station cover art still displays correctly | Square iTunes art must not be distorted |
| Transition from station logo → thumbnail works correctly | Same Gtk.Stack swap; content_fit change is on the Gtk.Image inside |

### Edge cases

| Case | Expected behavior |
|------|-------------------|
| YT thumbnail is 4:3 or 1:1 (rare but possible) | `ContentFit.CONTAIN` handles all aspect ratios correctly — bars appear as needed |
| ICY station playing, then YT station selected | Cover stack resets to fallback on play; thumbnail loads when ready |
| Thumbnail fetch fails | Stack shows fallback icon (existing behavior, unchanged) |
| Panel height constrained by window resize | `set_size_request` is a minimum — layout already handles this |
| GdkPixbuf.new_from_file_at_scale called with False (don't preserve aspect) | Currently called this way in `_on_cover_art`. For 16:9, the pixbuf scale should preserve aspect OR the Gtk.Picture/Image content_fit should do it. Don't double-scale. |

**Note on existing code:** `_on_cover_art` currently calls
`GdkPixbuf.Pixbuf.new_from_file_at_scale(temp_path, 160, 160, False)` (no aspect
preservation). For 16:9 thumbnails this stretches them to 160×160 before they reach the
widget. The fix must happen at the pixbuf scale call too: either pass `True` (preserve
aspect) or use `Gtk.Picture` directly with `set_filename` and let GTK handle scaling.
The latter is simpler and already done in the station editor (`station_pic` uses
`Gtk.Picture.set_filename`).

---

## Feature 4: Custom Accent Color (ACCENT-01)

### What the user experiences

A settings panel (or dialog) with:
- A row of preset color swatches (e.g., 6–8 named colors matching GNOME's system accent
  palette: Blue, Teal, Green, Yellow, Orange, Red, Pink, Purple, Slate)
- A hex input field for custom colors
- Changes apply immediately (live preview)
- Color persists across app restarts

The accent color affects highlighted widgets: the active chip filters, the "Save" button,
the Stop button's suggested-action style, the star when active — all the elements that use
Adwaita's `--accent-bg-color` CSS variable.

### How CSS override works in GTK4/Libadwaita (MEDIUM confidence)

Libadwaita defines `--accent-bg-color` and `--accent-color` as CSS custom properties.
Applications can override them by loading a `Gtk.CssProvider` with higher priority than
the default theme. The standard way:

```python
provider = Gtk.CssProvider()
provider.load_from_string(":root { --accent-bg-color: #e01b24; --accent-color: #ffffff; }")
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(),
    provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
)
```

`STYLE_PROVIDER_PRIORITY_APPLICATION` (600) overrides the default Adwaita theme (400)
and user `gtk.css` (500). This is the documented correct priority for app-level overrides.

To update the accent color at runtime: call `provider.load_from_string(new_css)` again
on the same provider object — GTK4 re-applies automatically without needing to re-add
the provider.

### Persistence

Store the accent color as a hex string in the existing SQLite settings table (already
used for `volume` and `recently_played_count`). Key: `"accent_color"`. Load on startup,
apply before the window is shown to avoid flash of default color. If not set, use the
system accent (no override applied).

### Deriving `--accent-color` from `--accent-bg-color`

Libadwaita states that standalone accent colors are automatically derived from the
background color. In practice: when overriding `--accent-bg-color`, also override
`--accent-color` with either `#ffffff` or `#000000` based on the luminance of the
background. This ensures text on accent-colored buttons remains readable.

Simple luminance formula: `0.2126*R + 0.7152*G + 0.0722*B > 0.5` → use black text,
else white text.

### Preset swatch values

Use GNOME 47+ system accent colors for familiarity:

| Name | Hex |
|------|-----|
| Blue (default) | `#3584e4` |
| Teal | `#2190a4` |
| Green | `#3a944a` |
| Yellow | `#c88800` |
| Orange | `#e66100` |
| Red | `#e01b24` |
| Pink | `#d56199` |
| Purple | `#9141ac` |
| Slate | `#6f8396` |

### Table-stakes behavior

| Behavior | Notes |
|----------|-------|
| Preset swatches visually show the color | Color buttons with the actual background color |
| Hex input accepts valid 6-char hex (with or without `#`) | Validate before applying |
| Invalid hex input silently rejected (no crash) | Show no visual feedback or show a brief error label |
| Selected color applied immediately on click/confirm | No "apply" button needed; live preview |
| Color persists after app restart | Read from `settings` table on init |
| No color set = system/default Adwaita colors | When no setting stored, do not load a CSS override |

### Edge cases

| Case | Expected behavior |
|------|-------------------|
| User enters pure white or pure black hex | Apply it. Edge case but valid. Text contrast may look bad — user's responsibility. |
| User enters a color that makes text unreadable | Derive fg as described above; best-effort readability |
| Hex field loses focus mid-typing (partial hex) | Do not apply partial hex. Apply only when length == 6 (or 7 with `#`). |
| Settings DB migration (new `accent_color` key) | `get_setting` already handles missing keys with a default; no schema change needed (key-value table) |
| App launched for first time (no stored color) | Libadwaita default accent (blue) used; no override applied |
| User removes color (reset to default) | Set stored value to empty string or delete the key; do not load a CSS provider |
| Adwaita version that doesn't support `--accent-bg-color` variable | Older libadwaita (<1.0) doesn't have this variable. Since v1.0+ is required for the app anyway (uses Adw.ToggleGroup, Adw.SwitchRow), this is safe. |
| Dark mode: accent color readable on dark background | Libadwaita auto-adapts accent saturation for dark mode when using the CSS variable; custom hex may not. This is acceptable. |

---

## Feature Dependencies (v1.4)

```
STREAM-01 (buffer tuning)
    requires: player.py (set_property on playbin3 before PLAYING state)
    no new DB, no UI

ART-01 (AA logo at import time)
    requires: aa_import.py fetch_channels + import_stations
    requires: assets.copy_asset_for_station (already exists)
    requires: urllib.request (already used in aa_import.py)
    new: image download in background thread at import time

ART-01b (AA logo in station editor)
    requires: edit_dialog.py _on_url_focus_out (already exists)
    requires: new _is_audioaddict_url() helper
    requires: channel key extraction from URL
    requires: AA API image lookup (may need stored API key from settings)
    dependency on ART-01: shares the same image URL lookup logic

ART-02 (YT thumbnail 16:9)
    requires: main_window.py cover_image + _on_cover_art
    requires: GdkPixbuf scale call change (preserve aspect or remove explicit scaling)
    no new DB, no new threads

ACCENT-01 (accent color)
    requires: Gtk.CssProvider + Gtk.StyleContext.add_provider_for_display
    requires: settings table (already exists)
    new: color picker UI (new dialog or header popover)
    new: CSS string generation at runtime
```

---

## Anti-Features (v1.4 specific)

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| Buffer size slider in UI | Internal reliability fix, not a user-facing setting | Hard-code 5s buffer; no UI |
| Full color theme editor (font size, spacing, etc.) | Scope creep — this is an audio app, not a theming tool | Accent color only |
| Per-station accent color | Adds significant state complexity for marginal value | Single app-wide color |
| Overwrite existing station art during AA import re-run | Destructive and unexpected | Skip art if station already exists (already the dedup behavior) |
| Animated color picker (hue wheel, sliders) | Complex GTK widget for a personal app | Preset swatches + hex input is sufficient |
| Store accent color as RGB floats in DB | Unnecessary complexity | Hex string is human-readable and sufficient |

---

## Sources

- `player.py`, `aa_import.py`, `edit_dialog.py`, `main_window.py`: direct code read — HIGH confidence
- `.planning/PROJECT.md` v1.4 requirements: direct source — HIGH confidence
- GStreamer buffer-duration: [GStreamer Playback Tutorial 4](https://gstreamer.freedesktop.org/documentation/tutorials/playback/progressive-streaming.html), [pithos issue #393](https://github.com/pithos/pithos/issues/393), [Mopidy discourse](https://discourse.mopidy.com/t/buffer-size-and-buffer-duration-configurable-where-to-post-my-patch/4591) — MEDIUM confidence (community, not official measurement)
- AudioAddict channel image fields: prior v1.3 research (`asset_url` mention), community Kodi/Plex plugin code — LOW confidence (not verified against live API; must confirm field name before implementation)
- GTK4 `ContentFit` enum: [GTK4 docs](https://docs.gtk.org/gtk4/enum.ContentFit.html) — HIGH confidence
- Libadwaita CSS variable override: [Adw CSS Variables](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.6/css-variables.html), [GNOME Discourse](https://discourse.gnome.org/t/how-to-get-accent-color-in-gtk-4-10/24489/2) — MEDIUM confidence (API verified; runtime behavior of `load_from_string` update not tested)
- GNOME accent color hex values: [Adwaita-Accent-Tint](https://github.com/pakovm-git/Adwaita-Accent-Tint) — MEDIUM confidence

---

*Feature research for: MusicStreamer v1.4 Media & Art Polish*
*Researched: 2026-04-03*

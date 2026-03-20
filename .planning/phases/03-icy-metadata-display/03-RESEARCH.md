# Phase 3: ICY Metadata Display - Research

**Researched:** 2026-03-19
**Domain:** GStreamer TAG bus / GTK4 + Libadwaita UI layout
**Confidence:** HIGH

## Summary

This phase wires the GStreamer TAG bus message into the UI and rebuilds the now-playing area as a three-column panel inserted as a second `Adw.ToolbarView` top bar. The implementation is almost entirely plumbing and widget construction — no new libraries, no schema changes, no external APIs.

All key technical questions were verified directly against the running Python environment:
- `Gst.TagList.get_string(Gst.TAG_TITLE)` returns `(bool, str)` and the constant `Gst.TAG_TITLE` equals the string `"title"`.
- `Gtk.Picture.set_filename()` and `Gtk.ContentFit.COVER` exist on this system.
- `Gtk.Image.set_pixel_size(96)` works for the symbolic icon fallback path.
- `label.add_css_class("title-3")` and `Pango.EllipsizeMode.END` are available.
- ICY encoding heuristic (re-encode latin-1 → decode utf-8, fall back on exception) correctly fixes mojibake while passing clean ASCII and genuine latin-1 through unchanged.

**Primary recommendation:** Follow the UI-SPEC layout contract exactly — it is complete and verified. The only non-trivial implementation decision is whether to apply the ICY encoding heuristic inside `Player._on_gst_tag` (recommended) or in the UI lambda (keep Player free of encoding concerns — put it in Player since it is stream-layer behavior).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Two-zone layout: now-playing panel (~120px fixed height) on top, station list + filter controls below
- `Adw.ToolbarView` top bars: HeaderBar → now-playing panel → filter strip → station list (content)
- Three columns: `[96px station logo] | [center: track title + station name + Stop button] | [96px cover art placeholder]`
- Panel is always visible at full height, even when nothing is playing
- Stop button moves from the HeaderBar into the center column
- Add Station + Edit buttons move to the filter strip left side
- Station logo source: `station.station_art_path` — Gtk.Picture, 96x96, COVER fit; fallback: `audio-x-generic-symbolic`
- Cover art right slot: 96x96 placeholder only (Phase 4 fills it)
- GStreamer TAG: add `message::tag` to bus; read `Gst.TAG_TITLE` only; ignore absent tags; never clear title on missing TAG
- Reuse existing `on_title` callback pattern — no new callback
- `_play_youtube` already calls `on_title(station.name)` — no change needed (satisfies NOW-03)

### Claude's Discretion
- Exact GTK widget types for the panel (Gtk.Box, Adw.Bin, or a custom composite)
- Precise margin/spacing/padding values for the 120px panel
- Whether to use Gtk.Picture or Gtk.Image for the logo slot
- Animation or transition when track title updates (or none — simple set_text is fine)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NOW-01 | User sees currently playing track title from ICY metadata for mp3/aac streams | `bus.connect("message::tag", handler)` + `taglist.get_string(Gst.TAG_TITLE)` → `on_title` callback → label `set_text()` |
| NOW-02 | Track title display updates automatically when ICY metadata changes mid-stream | TAG messages fire continuously as stream metadata updates; same handler path handles updates — no polling needed |
| NOW-03 | When no ICY metadata available (YouTube), now-playing shows station name | `_play_youtube` already calls `on_title(station.name)` — zero code change required |
| NOW-04 | Station brand logo displayed top-left (1:1 aspect, from existing station art) | `Gtk.Picture.set_filename(station.station_art_path)` with `ContentFit.COVER`; fallback to symbolic icon when path is None or missing |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GStreamer (gi.repository.Gst) | 1.0 (already in use) | TAG bus message handling | Already wired for error messages; same pattern for TAG |
| GTK4 (gi.repository.Gtk) | 4.0 (already in use) | Widget construction (Picture, Label, Button, Box) | Project standard |
| Libadwaita (gi.repository.Adw) | 1 (already in use) | ToolbarView top bars, style classes | Project standard |
| Pango (gi.repository.Pango) | (system) | EllipsizeMode.END on labels | Needed for overflow control |

No new dependencies. All are already imported and available.

**Installation:** none required.

**Version verification (on this system):**
```
Gst.TAG_TITLE = "title"  (verified live)
Gtk.ContentFit.COVER     (verified live)
Gtk.Picture.set_filename (verified live)
Gtk.Image.set_pixel_size (verified live)
label.add_css_class()    (verified live)
28 existing tests pass   (verified live)
```

## Architecture Patterns

### Recommended Project Structure

No new files required. Changes touch two existing files:

```
musicstreamer/
├── player.py          # Add _on_gst_tag method + bus.connect("message::tag", ...)
└── ui/
    └── main_window.py # Rebuild __init__: insert now-playing panel, relocate buttons
```

### Pattern 1: GStreamer TAG Bus Handler

**What:** Connect a second signal handler to the existing bus watch; extract TAG_TITLE and call the stored `on_title` callback.

**When to use:** Whenever a TAG message arrives from the playbin3 pipeline.

```python
# In Player.__init__ — alongside existing error handler:
bus.connect("message::tag", self._on_gst_tag)
self._on_title = None  # set by play()

# In Player.play() — store the callback:
self._on_title = on_title

# New method:
def _on_gst_tag(self, bus, msg):
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    if not found:
        return
    title = _fix_icy_encoding(value)
    if self._on_title:
        GLib.idle_add(self._on_title, title)
```

**Thread safety note:** GStreamer TAG messages fire on the GStreamer bus thread. `GLib.idle_add()` marshals the call to the main GTK loop — required for safe widget updates. The existing `_on_gst_error` handler does NOT use `idle_add` because it only prints; any handler that touches GTK widgets MUST use `idle_add`.

### Pattern 2: ICY Encoding Heuristic

**What:** Some ShoutCast servers send UTF-8 bytes but the HTTP layer (or GStreamer's demuxer) decodes them as Latin-1, producing mojibake. The standard fix is to re-encode as Latin-1 then decode as UTF-8; if either step fails, return the string unchanged.

**Where to apply:** In `Player._on_gst_tag` before calling `on_title` — this is stream-layer behavior, not UI-layer behavior.

```python
def _fix_icy_encoding(s: str) -> str:
    """Re-encode latin-1 mojibake back to proper UTF-8."""
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s
```

Verified: corrects `RÃ¶yksopp` → `Röyksopp`; passes `Artist - Title` unchanged; passes `café` (genuine latin-1) unchanged.

### Pattern 3: Now-Playing Panel Construction

**What:** Third `Adw.ToolbarView` top bar containing a horizontal Box with three columns.

```python
# Panel container
panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
panel.set_margin_top(4)
panel.set_margin_bottom(4)
panel.set_margin_start(8)
panel.set_margin_end(8)

# Left slot — logo (Gtk.Picture for real art, Gtk.Image for fallback)
self.logo_picture = Gtk.Picture()
self.logo_picture.set_content_fit(Gtk.ContentFit.COVER)
self.logo_picture.set_size_request(96, 96)
self.logo_fallback = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
self.logo_fallback.set_pixel_size(96)
# Use Gtk.Stack to swap between them, or just hide/show

# Center column
center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
center.set_hexpand(True)
self.title_label = Gtk.Label(label="Nothing playing")
self.title_label.add_css_class("dim-label")  # idle state — switched to title-3 when playing
self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
self.station_name_label = Gtk.Label()
self.station_name_label.add_css_class("dim-label")
self.station_name_label.set_ellipsize(Pango.EllipsizeMode.END)
self.station_name_label.set_visible(False)
self.stop_btn = Gtk.Button(label="Stop")
self.stop_btn.add_css_class("destructive-action")  # or accent — see Stop button note
self.stop_btn.set_sensitive(False)
self.stop_btn.connect("clicked", lambda *_: self._stop())

# Right slot — cover art placeholder
cover_placeholder = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
cover_placeholder.set_pixel_size(96)
```

**Stop button style class:** The UI-SPEC designates `@accent_color` for the Stop button. In GTK4/Adw use `suggested-action` CSS class for accent. `destructive-action` renders in red. Use `suggested-action`.

### Pattern 4: Logo Slot Swap

Two approaches. Recommended: use a `Gtk.Stack` with two pages (picture + fallback image). Simple alternative: swap children manually.

**Simpler approach (hide/show):** Keep both widgets in a container, show only one at a time. `Gtk.Overlay` or just two widgets in a `Gtk.Stack`. Since the slot is fixed-size 96x96, a `Gtk.Stack` is cleanest:

```python
self.logo_stack = Gtk.Stack()
self.logo_stack.set_size_request(96, 96)
self.logo_stack.add_named(self.logo_fallback, "fallback")
self.logo_stack.add_named(self.logo_picture, "logo")
self.logo_stack.set_visible_child_name("fallback")  # idle default
```

On play: `self.logo_stack.set_visible_child_name("logo")` or `"fallback"`.

### Anti-Patterns to Avoid

- **Touching GTK widgets from GStreamer thread:** TAG handler runs off the main loop — always use `GLib.idle_add()` for any widget update triggered from `_on_gst_tag`.
- **Clearing title on every TAG without TAG_TITLE:** Some TAG messages carry only bitrate or codec info. Only act when `Gst.TAG_TITLE` is present — ignore otherwise (locked decision).
- **Setting `_on_title` callback only at play time and not clearing it at stop:** If a stale TAG arrives after `_stop()`, it will try to update the panel. Clear `self._on_title = None` in `Player.stop()`.
- **Using `Gtk.Image` for the logo slot when art is present:** `Gtk.Picture` handles HiDPI scaling and aspect ratio natively; `Gtk.Image` at a fixed pixel size does not scale correctly from large source images.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe widget update | Manual threading | `GLib.idle_add()` | GTK is single-threaded; idle_add is the standard marshal |
| ICY encoding repair | Complex charset detection | `encode('latin-1').decode('utf-8')` with fallback | Covers 99% of real-world mojibake with 3 lines |
| Logo display with aspect ratio | Manual scaling | `Gtk.Picture` + `ContentFit.COVER` | GTK handles HiDPI, aspect ratio, and file loading |
| Muted/secondary text style | Inline alpha or color | `.dim-label` CSS class | Libadwaita semantic class — adapts to dark/light theme |

**Key insight:** Every non-trivial problem here has a one-line GTK/GLib solution. Any custom widget logic for sizing, threading, or styling is a sign of going off the rails.

## Common Pitfalls

### Pitfall 1: GStreamer Bus Thread → GTK Widget Update Race

**What goes wrong:** `_on_gst_tag` fires on the GStreamer streaming thread. Calling `self._on_title(title)` directly updates a GTK widget from a non-main-loop thread, causing intermittent crashes or visual corruption.

**Why it happens:** GStreamer bus signal watches fire on whichever thread owns the bus; the main loop is separate.

**How to avoid:** `GLib.idle_add(self._on_title, title)` — the call is queued to the GTK main loop and executes safely.

**Warning signs:** Intermittent crashes during metadata-heavy streams; title updates that sometimes don't appear.

### Pitfall 2: Stale on_title Callback After Stop

**What goes wrong:** User stops playback; a delayed TAG message arrives and calls the still-set `_on_title` callback, updating the panel to show a track title when nothing is playing.

**Why it happens:** GStreamer may deliver buffered TAG messages even after `set_state(NULL)`.

**How to avoid:** Set `self._on_title = None` in `Player.stop()`. Guard with `if self._on_title:` in `_on_gst_tag`.

### Pitfall 3: ICY Metadata Encoding Mojibake

**What goes wrong:** Track title displays as `RÃ¶yksopp` instead of `Röyksopp` for stations that send UTF-8 ICY metadata over HTTP/1.0 with no charset declaration.

**Why it happens:** Some stream servers send raw UTF-8 bytes in ICY headers; the demuxer (or HTTP layer) decodes them as Latin-1, producing double-encoded garbage.

**How to avoid:** Apply `_fix_icy_encoding()` to the title before passing to `on_title`. Verified heuristic above.

**Warning signs:** Accented characters (ä, ö, ü, é, ñ) always appear as two-character sequences.

### Pitfall 4: Gtk.Image vs Gtk.Picture for Logo Slot

**What goes wrong:** Using `Gtk.Image.set_from_file()` with `set_pixel_size(96)` on a large station art image (e.g. 512x512 PNG) renders blurry or at wrong size on HiDPI displays.

**Why it happens:** `Gtk.Image` pixel_size applies to symbolic icons, not raster images. For file-backed raster images, `Gtk.Picture` is the correct widget.

**How to avoid:** Use `Gtk.Picture.set_filename()` + `set_content_fit(Gtk.ContentFit.COVER)` + `set_size_request(96, 96)` for the logo slot. Reserve `Gtk.Image` for the symbolic icon fallback.

### Pitfall 5: Stop Button CSS Class

**What goes wrong:** Using `destructive-action` CSS class on the Stop button renders it red, which signals "dangerous action" to the user — semantically wrong for a stop/playback control.

**How to avoid:** Use `suggested-action` for the Stop button to get the accent color. `destructive-action` is for delete/remove actions only.

## Code Examples

Verified patterns from live Python environment on this system:

### TAG Bus Handler (verified)
```python
# Source: live gi.repository.Gst verification 2026-03-19
def _on_gst_tag(self, bus, msg):
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    if not found:
        return
    title = _fix_icy_encoding(value)
    if self._on_title:
        GLib.idle_add(self._on_title, title)
```

### Gtk.Picture Logo Slot (verified)
```python
# Source: live Gtk 4.0 verification 2026-03-19
logo = Gtk.Picture()
logo.set_content_fit(Gtk.ContentFit.COVER)
logo.set_size_request(96, 96)
logo.set_filename("/path/to/station_art.png")  # None-safe: clears picture
```

### Label Style Classes (verified)
```python
# Source: live GTK4/Pango verification 2026-03-19
import gi
gi.require_version("Pango", "1.0")
from gi.repository import Pango
label = Gtk.Label()
label.add_css_class("title-3")
label.set_ellipsize(Pango.EllipsizeMode.END)
```

### ICY Encoding Fix (verified)
```python
# Source: live Python 3 verification 2026-03-19
def _fix_icy_encoding(s: str) -> str:
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Gtk.Image` for raster art display | `Gtk.Picture` for file-backed images | GTK4 | `Gtk.Picture` handles HiDPI and aspect ratio; `Gtk.Image` is for icons |
| Manual CSS for label styles | Libadwaita CSS classes (`.title-3`, `.dim-label`) | Adw 1.0 | Theme-adaptive, no hardcoded colors |

**Deprecated/outdated:**
- `Gtk.Image.set_from_file()` for station art: replaced by `Gtk.Picture.set_filename()` in GTK4.

## Open Questions

1. **`Gtk.Picture.set_filename(None)` behavior**
   - What we know: The method accepts a filename string.
   - What's unclear: Whether passing `None` cleanly clears the picture or raises TypeError.
   - Recommendation: Conditional — if `station_art_path` is None or path doesn't exist, call `logo_stack.set_visible_child_name("fallback")` rather than passing None to set_filename.

2. **`Adw.ToolbarView` visual treatment of second top bar**
   - What we know: `add_top_bar()` works for HeaderBar and the filter strip (Phase 2).
   - What's unclear: Whether a plain `Gtk.Box` as the second top bar gets the same `@headerbar_bg_color` background as the first top bar, or a different treatment.
   - Recommendation: Verify visually during implementation. If the panel background looks wrong, wrap the panel `Gtk.Box` in an `Adw.Bin` or apply the `toolbar` CSS class.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (uv run --with pytest) |
| Config file | none — inline discovery |
| Quick run command | `uv run --with pytest pytest tests/ -q` |
| Full suite command | `uv run --with pytest pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOW-01 | `_on_gst_tag` extracts TAG_TITLE and calls on_title | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | Wave 0 |
| NOW-02 | Multiple TAG messages each call on_title with new value | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | Wave 0 |
| NOW-03 | YouTube path calls on_title with station.name | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | Wave 0 |
| NOW-04 | Logo slot loads station_art_path; fallback on None/missing | manual | visual inspection — GTK widget rendering | n/a |
| ICY encoding | `_fix_icy_encoding` corrects mojibake, passes clean ASCII | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | Wave 0 |
| Stale callback guard | `_on_title` is None after `stop()`; no update after stop | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | Wave 0 |

**NOW-04 note:** The logo loading is GTK widget behavior (file → Gtk.Picture render). It cannot be tested without a display. Mark as manual-only; smoke-test by running the app against a station with known station art.

### Sampling Rate
- **Per task commit:** `uv run --with pytest pytest tests/ -q`
- **Per wave merge:** `uv run --with pytest pytest tests/ -q`
- **Phase gate:** Full suite green (28 existing + new player tag tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_player_tag.py` — covers NOW-01, NOW-02, NOW-03, ICY encoding heuristic, stale callback guard

*(Existing test infrastructure covers filter and repo logic; only the player TAG behavior requires new test file.)*

## Sources

### Primary (HIGH confidence)
- Live GStreamer Python verification (2026-03-19) — `Gst.TAG_TITLE`, `TagList.get_string()` return signature
- Live GTK4 Python verification (2026-03-19) — `Gtk.Picture.set_filename`, `Gtk.ContentFit.COVER`, `Gtk.Image.set_pixel_size`, `label.add_css_class`
- Existing project code read directly — Player, MainWindow, models, assets

### Secondary (MEDIUM confidence)
- GStreamer documentation pattern — `bus.connect("message::tag")` mirrors `message::error` pattern already in codebase
- GTK4 API documentation — `Gtk.Picture` is the GTK4 replacement for raster image display

### Tertiary (LOW confidence)
- ICY encoding heuristic — empirically verified on this system; stream behavior may vary by server implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all APIs verified live on this system
- Architecture: HIGH — mirrors patterns already used in the codebase
- Pitfalls: HIGH (thread safety, stale callback) / MEDIUM (ICY encoding — empirical)

**Research date:** 2026-03-19
**Valid until:** 2026-09-19 (stable GTK4/GStreamer APIs)

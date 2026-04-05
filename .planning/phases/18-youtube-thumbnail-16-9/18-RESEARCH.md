# Phase 18: YouTube Thumbnail 16:9 - Research

**Researched:** 2026-04-05
**Domain:** GTK4 Python — Gtk.Picture ContentFit, art slot widget restructuring
**Confidence:** HIGH

## Summary

This is a narrow GTK4 widget swap. The current now-playing art slots use `Gtk.Image + GdkPixbuf.new_from_file_at_scale(path, 160, 160, False)` which always produces a 160×160 square regardless of source aspect ratio. YouTube thumbnails are 16:9 (e.g. 1280×720), so this crops them.

The fix is to detect YouTube stations at play time and use `Gtk.Picture` with `ContentFit.CONTAIN` instead. `Gtk.ContentFit.CONTAIN` is confirmed present on this system [VERIFIED: live Python import]. `Gtk.Picture` is already used in the station list rows (`_build_station_row`, `_build_discovery_row`) with `ContentFit.COVER` — so the widget type and API are proven in-project. The only change is using `CONTAIN` instead of `COVER`, and targeting the now-playing slots instead of list rows.

All decisions are locked in CONTEXT.md. No alternatives to research.

**Primary recommendation:** In `_play_station()`, branch on `is_youtube` — for YouTube stations add a `Gtk.Picture` child to each stack and switch to it; for non-YouTube stations keep the existing GdkPixbuf path unchanged. `_on_cover_art()` requires no changes (only fires for non-YouTube ICY streams).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Detect YouTube by `"youtube.com" in st.url or "youtu.be" in st.url` at play time. No image aspect ratio inspection.
- **D-02:** Both `logo_stack` and `cover_stack` use CONTAIN for YouTube thumbnails (both show same `station_art_path`).
- **D-03:** Non-YouTube stations keep current 160×160 GdkPixbuf behavior. No change to square art display.
- **D-04:** 160×160 slot size does NOT change. CONTAIN letterboxes within existing container (~160×90 image, ~35px bands top and bottom).
- **D-05:** Use `Gtk.Picture + ContentFit.CONTAIN` for YouTube branch. Non-YouTube may keep `Gtk.Image` or unify — Claude's discretion.

### Claude's Discretion
- Whether to unify all art loading onto `Gtk.Picture` (cleaner long-term) or only switch the YT branch
- Exact slot widget restructuring (Gtk.Stack child swap vs. conditional widget construction)
- `_on_cover_art` — no change needed; only fires for non-YouTube ICY streams

### Deferred Ideas (OUT OF SCOPE)
- None from discussion
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ART-03 | YouTube thumbnails displayed as full 16:9 in now-playing art slot; non-YouTube stations display square art correctly | `Gtk.ContentFit.CONTAIN` on verified system; existing `Gtk.Picture` usage in same file confirms API works |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyGObject / GTK4 | system (gi 3.x) | Widget toolkit | Project's entire UI layer [VERIFIED: pyproject.toml] |
| Gtk.Picture | GTK 4.8+ | Display images with ContentFit | Native CONTAIN/COVER support, already used in project [VERIFIED: codebase grep] |
| Gtk.ContentFit.CONTAIN | GTK 4.8+ | Fit image within bounds, preserve aspect ratio | Confirmed present on this system [VERIFIED: live Python import] |
| GdkPixbuf | system | Pixbuf scaling for non-YT path | Already in use, no change needed [VERIFIED: codebase] |

No new packages to install — this phase uses only what is already imported.

**Installation:** None required.

---

## Architecture Patterns

### Current Art Slot Structure (both logo_stack and cover_stack)

```
Gtk.Stack (set_size_request(160, 160), Overflow.HIDDEN)
├── "fallback"  → Gtk.Image (audio-x-generic-symbolic, pixel_size=160)
└── "logo"/"art" → Gtk.Image (set_from_pixbuf — 160×160 GdkPixbuf)
```

### Target Art Slot Structure (after Phase 18)

```
Gtk.Stack (set_size_request(160, 160), Overflow.HIDDEN)
├── "fallback"  → Gtk.Image (audio-x-generic-symbolic, pixel_size=160)  [unchanged]
├── "logo"/"art" → Gtk.Image (GdkPixbuf 160×160)                        [non-YT, unchanged]
└── "yt"        → Gtk.Picture (ContentFit.CONTAIN)                      [YT branch, new]
```

**Or** (Claude's discretion alternative — unified approach): replace the `Gtk.Image` "logo"/"art" child with `Gtk.Picture` for all cases, using `ContentFit.FILL` for non-YT (equivalent to current stretch behavior) and `ContentFit.CONTAIN` for YT. This avoids adding a third stack child but changes non-YT rendering path — slightly more risk.

Recommended: add a named "yt" child, swap to it for YouTube stations. Safer, non-YT path completely untouched.

### Pattern: Conditional Stack Child at Play Time

```python
# Source: CONTEXT.md D-05, existing pattern in _build_station_row (line 524-526)

is_youtube = "youtube.com" in st.url or "youtu.be" in st.url

if is_youtube and st.station_art_path and os.path.exists(abs_path):
    # Add Gtk.Picture child if not already present (or build it fresh)
    pic = Gtk.Picture.new_for_filename(abs_path)
    pic.set_content_fit(Gtk.ContentFit.CONTAIN)
    pic.set_size_request(160, 160)
    # Add to stack if not already named "yt"
    if self.logo_stack.get_child_by_name("yt") is None:
        self.logo_stack.add_named(pic, "yt")
    else:
        self.logo_stack.get_child_by_name("yt").set_filename(abs_path)
    self.logo_stack.set_visible_child_name("yt")
else:
    # Existing GdkPixbuf path — unchanged
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(abs_path, 160, 160, False)
    self.logo_image.set_from_pixbuf(pixbuf)
    self.logo_stack.set_visible_child_name("logo")
```

Note: `Gtk.Picture` does not have `set_filename()` in GTK4 Python bindings — use `set_file()` with a `Gio.File`, or simply create a new widget each call and replace the stack child. Creating fresh is simpler and avoids stale state.

### Simpler approach (recommended): create Gtk.Picture on demand, remove old "yt" child first

```python
# Remove previous yt child if it exists
existing = self.logo_stack.get_child_by_name("yt")
if existing:
    self.logo_stack.remove(existing)

pic = Gtk.Picture.new_for_filename(abs_path)
pic.set_content_fit(Gtk.ContentFit.CONTAIN)
pic.set_size_request(160, 160)
self.logo_stack.add_named(pic, "yt")
self.logo_stack.set_visible_child_name("yt")
```

Apply same logic to `cover_stack` (using child name "yt-cover" or just "yt" — each stack is separate).

### Anti-Patterns to Avoid
- **Changing slot size:** D-04 is locked — 160×160 stays. CONTAIN produces letterbox bands, which is correct.
- **Aspect ratio inspection:** D-01 is locked — use URL pattern, not image dimension checks.
- **Touching `_on_cover_art`:** It only fires for non-YT ICY streams. No change needed.
- **Using `ContentFit.COVER` for YT:** COVER crops — that's the current broken behavior. Must use CONTAIN.
- **Using `ContentFit.FILL` for non-YT Gtk.Picture:** FILL stretches without preserving aspect ratio — equivalent to current GdkPixbuf behavior, but switching non-YT path to Gtk.Picture adds risk with no benefit unless unifying intentionally.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Aspect-ratio-preserving display | Manual pixbuf math (get_width, scale calculations) | `Gtk.Picture + ContentFit.CONTAIN` | GTK handles all layout, overflow, and scaling natively |
| YouTube URL detection | Regex or urllib parse | `"youtube.com" in url or "youtu.be" in url` | Project-established pattern — consistent with player.py and edit_dialog.py |

---

## Common Pitfalls

### Pitfall 1: Gtk.Picture.set_filename() doesn't exist
**What goes wrong:** Attempting to update an existing `Gtk.Picture` via `set_filename()` raises `AttributeError`.
**Why it happens:** GTK4 Python bindings expose `set_file(Gio.File)` and `new_for_filename()` — no `set_filename()` setter.
**How to avoid:** Create a new `Gtk.Picture` each time (remove old from stack, add fresh). Or use `pic.set_file(Gio.File.new_for_path(abs_path))`.
**Warning signs:** `AttributeError: 'Picture' object has no attribute 'set_filename'`

### Pitfall 2: Stack child name collision across play calls
**What goes wrong:** Calling `add_named(..., "yt")` on a stack that already has a "yt" child raises a GTK warning and may not update the image.
**Why it happens:** `Gtk.Stack.add_named` errors if name already exists.
**How to avoid:** Check `get_child_by_name("yt")` and remove before re-adding. [VERIFIED: GTK4 Stack API — add_named requires unique names]

### Pitfall 3: cover_stack "yt" child left stale after Stop
**What goes wrong:** After stopping, the stack is set back to "fallback" but the "yt" child with the old station's image persists in the widget tree.
**Why it happens:** `_stop()` calls `set_visible_child_name("fallback")` but does not remove non-standard children.
**How to avoid:** In `_stop()`, also remove any "yt" children from both stacks (or just let them persist invisibly — functionally fine since they're hidden).

### Pitfall 4: Non-YT station played after YT station shows wrong child
**What goes wrong:** After a YouTube station, playing a non-YT station leaves the "yt" stack child resident; if `set_visible_child_name("logo")` is called correctly, this is fine — but if the branch logic has a bug, the old YT image shows.
**Why it happens:** Stack children persist until explicitly removed.
**How to avoid:** Ensure the non-YT branch explicitly calls `set_visible_child_name("logo")` / `set_visible_child_name("art")` — don't rely on fallthrough.

---

## Code Examples

### Existing Gtk.Picture with ContentFit in this codebase
```python
# Source: main_window.py lines 524-526 (_build_station_row / _build_discovery_row)
pic = Gtk.Picture.new_for_filename(abs_path)
pic.set_size_request(40, 40)
pic.set_content_fit(Gtk.ContentFit.COVER)
```
CONTAIN works identically — just substitute `Gtk.ContentFit.CONTAIN`.

### Confirmed ContentFit values on this system
```
Gtk.ContentFit.CONTAIN  — fits within bounds, letterbox bands, no crop
Gtk.ContentFit.COVER    — fills bounds, center-crop
Gtk.ContentFit.FILL     — stretch to fill, no aspect preservation
Gtk.ContentFit.SCALE_DOWN — like CONTAIN but won't upscale
```
[VERIFIED: live `dir(Gtk.ContentFit)` on target system]

### Existing YouTube URL detection pattern (project standard)
```python
# Source: edit_dialog.py line 19, player.py line 60
is_youtube = "youtube.com" in st.url or "youtu.be" in st.url
```

### _play_station() current art-loading block (lines 687-715) — integration point
Both the logo and cover blocks have identical structure: check `st.station_art_path`, check file exists, try GdkPixbuf scale, set stack child. Phase 18 wraps each block with an `is_youtube` branch before the try/except.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml (no pytest section — uses defaults) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ART-03 | YouTube URL detection returns True for YT URLs, False for non-YT | unit | `pytest tests/test_yt_thumbnail.py -x -q` | Yes (test_is_youtube_url covers edit_dialog._is_youtube_url) |
| ART-03 | Rendering behavior (CONTAIN vs GdkPixbuf) | manual-only | visual inspection — GTK widget rendering cannot be unit-tested without display | n/a |

Note: `test_is_youtube_url` in `tests/test_yt_thumbnail.py` tests the URL detection function in `edit_dialog.py`. Phase 18 uses an inline check in `main_window.py` (not a separate function). The existing test validates the same logic — no new test strictly required, but adding a test for the inline branch in main_window is not feasible without GTK test infrastructure.

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- None — existing test suite runs; rendering validation is manual (GTK widget display).

---

## Security Domain

No security-relevant changes. This phase modifies only which GTK widget renders an already-downloaded local image file. No network calls, no new inputs, no authentication paths. ASVS categories do not apply.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| GTK4 / PyGObject | All UI | Yes | system gi | — |
| Gtk.ContentFit.CONTAIN | YouTube CONTAIN display | Yes | confirmed | — |

[VERIFIED: live Python import on target system]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Gtk.Stack.get_child_by_name()` returns None (not raises) when name absent | Common Pitfalls | Would need try/except instead of None check |
| A2 | Creating a new `Gtk.Picture` per play call and adding to stack has no noticeable memory/performance issue | Architecture Patterns | Negligible risk — one widget per play event |

---

## Open Questions

None — all implementation details resolved by CONTEXT.md decisions and codebase inspection.

---

## Sources

### Primary (HIGH confidence)
- Live codebase — `musicstreamer/ui/main_window.py` lines 55-154, 600-641, 685-715
- Live Python import — `Gtk.ContentFit` enum values confirmed on target system
- CONTEXT.md — all locked decisions

### Secondary (MEDIUM confidence)
- GTK4 Python documentation pattern — `Gtk.Picture.new_for_filename()` + `set_content_fit()` usage consistent with in-project examples at lines 524-526

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed via live import and existing in-project usage
- Architecture: HIGH — codebase is fully readable, integration points are explicit
- Pitfalls: MEDIUM — GTK4 Stack API behavior for `add_named` collision based on training knowledge (A1 in assumptions log)

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (GTK4 stable API, no risk of churn)

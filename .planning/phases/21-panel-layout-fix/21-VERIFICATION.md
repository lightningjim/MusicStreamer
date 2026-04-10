---
phase: 21
slug: panel-layout-fix
status: passed
verified: 2026-04-10
requirements_verified:
  - FIX-01
---

# Phase 21 Verification: Panel Layout Fix

## Goal
The now-playing panel maintains its intended dimensions at all window sizes.

## Must-Haves

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | YouTube maximized does not widen panel | passed | `panel.set_size_request(-1, 160)` + `set_vexpand(False)` (main_window.py:87-88); YT thumb uses fixed-size pixbuf not scalable Picture |
| 2 | YouTube fullscreen does not widen panel | passed | Thumb pre-scaled to 320×180 pixbuf via `GdkPixbuf.new_from_file_at_scale` (main_window.py:901); `Gtk.Image` natural size == pixbuf size, cannot expand regardless of parent space |
| 3 | 16:9 thumbnails sized to 320×180 edge-to-edge | passed | `set_pixel_size(320)` + `set_size_request(320, 180)` on the YT image (main_window.py:903-904); logo_stack grows to 320×180 for YT stations |
| 4 | Non-YouTube layout unaffected | passed | Non-YouTube branch removes stale "yt" child from stack before switching (main_window.py:912-914); non-YT slot stays at 160×160 |

## Regression Note (2026-04-10)

FIX-01 was initially marked retroactively complete based on code inspection during v1.5 audit. User reported the regression during post-audit UAT: the panel **was** inflating on fullscreen because `Gtk.Picture` reports its natural size as the full image dimensions (e.g. 1280×720 for a YouTube thumbnail), bypassing `set_size_request(160, 160)` which is only a minimum. GTK sized the logo_stack to the Picture's natural size, and `hexpand=False` / `vexpand=False` on the Picture only controlled whether it wanted EXTRA space — not its natural measurement.

**Root cause:** `Gtk.Picture` is unsuitable for fixed-size slots when the source image is larger than the slot. Its measure() returns the image dimensions as natural size, and no widget-level property overrides that.

**Fix:** Replaced `Gtk.Picture.new_for_filename(path)` + `ContentFit.CONTAIN` with `Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 320, 320, True))` + `set_pixel_size(320)` + `set_size_request(320, 180)`. The pixbuf is pre-scaled at load time so the resulting texture is bounded, and `Gtk.Image`'s natural size is the pixbuf size — no growth possible.

**Sizing decision:** User preferred 320×180 over the original 160×90 for better visual presence. YT stations now get a 320×180 slot; non-YT stations keep the 160×160 square slot. Panel height adapts to the taller slot when YT is playing.

**Fix commits:** `23cdb19` (replace Picture with pixbuf), `40e9098` (add set_pixel_size), `6929acf` (size slot to 320×180).

## Requirements Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | 21 | Verified (fixed 2026-04-10 after UAT regression report) |

## Test Suite

264 passing (full suite). One pre-existing Twitch test failure (Phase 32 `--twitch-api-header` staleness) is tracked separately in `deferred-items.md` and is unrelated to panel layout. No automated regression test exists for panel sizing because GTK layout requires a live display — verified by manual UAT with user approval after 320×180 fix applied.

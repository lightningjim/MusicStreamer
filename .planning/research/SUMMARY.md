# Project Research Summary

**Project:** MusicStreamer v1.4 — Media & Art Polish
**Domain:** GTK4/GStreamer Python desktop internet radio
**Researched:** 2026-04-03
**Confidence:** MEDIUM–HIGH

## Executive Summary

v1.4 targets four focused improvements to an established, working codebase: stream reliability (STREAM-01), AudioAddict station logos at import time (ART-01) and in the editor (ART-01b), YouTube thumbnail aspect ratio (ART-02), and user-selectable accent color (ACCENT-01). No new dependencies are required — all four features are achievable with the existing stack (GTK4/Libadwaita, GStreamer playbin3, GdkPixbuf, urllib, SQLite). The only new file is `ui/accent_dialog.py`.

The recommended implementation approach is risk-ascending: buffer tuning first (2–3 lines, zero UI, fully isolated), then AA logo fetch (blocked on live API inspection), then 16:9 thumbnail fix (layout-only, high-confidence), then accent color (new dialog, most surface area). All four are independent and can be reordered if needed.

The primary risk in v1.4 is the AudioAddict logo field name — inferred from community plugin error traces (`channel_images.default`), not confirmed against a live API response. Everything else is HIGH confidence. Secondary risks are the ICY/buffer tension (larger buffers delay metadata delivery) and the 16:9 slot breaking square iTunes art display. Both have clear, low-effort mitigations.

## Key Findings

### Stack Additions

None. No uv.lock changes. All features use existing imports.

| Feature | Existing Library Used |
|---------|----------------------|
| STREAM-01 | `Gst` (already in player.py) |
| ART-01 | `urllib.request`, `json` (already in aa_import.py) |
| ART-02 | `GdkPixbuf.Pixbuf` (already in main_window.py) |
| ACCENT-01 | `Gtk.CssProvider`, `Gdk.Display` (already in `__main__.py`) |

### Implementation Decisions Per Feature

**STREAM-01 — GStreamer Buffer Tuning**
Set `buffer-duration = 5 * Gst.SECOND` and `buffer-size = 2 * 1024 * 1024` on the `playbin3` pipeline in `Player.__init__`, immediately after pipeline construction, before any URI is set. Both persist across URI changes with the existing NULL→PLAYING reuse pattern. Do NOT access `souphttpsrc` properties directly — that element is created lazily; use the `source-setup` signal if source-level properties are ever needed. Do NOT set `ring-buffer-max-size` — progressive-download only, not applicable to live streams.

**ART-01 — AA Logo at Import Time**
The public endpoint `https://api.audioaddict.com/v1/{slug}/channels` (no auth required) returns channel objects including `channel_images`. Access via `ch.get('channel_images', {}).get('default')`. Store the URL during `fetch_channels`; decouple image download from the insert loop to avoid blocking the progress UI for 2–5 minutes on ~300 channels. Download images in a separate pass or bounded thread pool after all DB inserts complete. Only write art on initial insert — skip if station already exists.

**ART-01b — AA Logo Auto-Fetch in Editor (bonus)**
Add `_is_audioaddict_url()` to `edit_dialog.py` matching against the explicit domain list from `aa_import.NETWORKS`. Extract channel key from the URL path (`/premium_high/deephouse.pls` → key `deephouse`). Trigger via the same `_on_url_focus_out` hook used for YouTube. Only auto-populate if `station_art_rel` is currently empty. If the stored AA API key is unavailable, silently skip. This is a convenience feature — if reliability is uncertain, defer it and rely on ART-01 alone.

**ART-02 — YouTube 16:9 Thumbnail**
Change `GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 160, 160, False)` to `new_from_file_at_scale(path, -1, 160, True)` in `_on_cover_art`. Use `ContentFit.CONTAIN` in the existing 160×160 slot. This shows the full thumbnail letterboxed with minimal bars — acceptable for v1.4. Do NOT widen the slot to 284px without conditional sizing logic; a fixed wider slot breaks square iTunes art on all non-YouTube stations.

**ACCENT-01 — Custom Accent Color**
Inject CSS via a second `Gtk.CssProvider` at `STYLE_PROVIDER_PRIORITY_APPLICATION + 1`. Use `:root` selector: `@define-color accent_color {hex}; @define-color accent_bg_color {hex};`. Reload via `load_from_string()` on the same provider object for live preview. Validate hex in Python (`re.fullmatch(r'#[0-9a-fA-F]{6}', value)`) before passing to GTK — silent parse failures will not raise. Store as hex string in the existing settings table; load before window is presented. New file: `ui/accent_dialog.py`.

### Architecture Approach

All four features are additive changes to existing modules. State lives in `MainWindow` as before; all background work uses `threading.Thread(daemon=True)` + `GLib.idle_add`. The only new module is `ui/accent_dialog.py`.

**Files changed per feature:**

| Feature | Files Modified | New Files |
|---------|---------------|-----------|
| STREAM-01 | `player.py` | none |
| ART-01 | `aa_import.py` | none |
| ART-01b | `edit_dialog.py` | none |
| ART-02 | `main_window.py` | none |
| ACCENT-01 | `main_window.py` | `ui/accent_dialog.py` |

### Critical Pitfalls

1. **ICY/buffer tension** — A larger buffer delays ICY metadata TAG messages. Keep `buffer-duration` at or below 5s. Validate by measuring time from PLAYING state to first TAG message after tuning.

2. **AA logo field name unverified** — `channel_images.default` is inferred from plugin error traces, not confirmed against a live response. Print the raw channel dict from `/v1/di/channels` before writing production code. Fall back gracefully if absent.

3. **AA logo fetch must be async** — Inline `urlopen` in the `import_stations` loop turns a 5-second import into a 5-minute one. Decouple: store URL during insert loop, fetch images in a separate pass after inserts complete.

4. **souphttpsrc via source-setup signal** — `pipeline.get_by_name("source")` returns None at construction. For STREAM-01 this is sidestepped by using playbin3-level properties instead. Note for future: if source-level config is ever needed, use the `source-setup` signal.

5. **16:9 slot breaks square art** — Widening `cover_stack` to 284px permanently degrades non-YouTube stations. Use `ContentFit.CONTAIN` in the existing 160×160 slot as the safe default.

6. **CSS variable scope** — Accent override must use `:root` selector at `PRIORITY_APPLICATION` (600). A scoped selector only affects widget subtrees. Invalid hex silently no-ops in GTK — validate in Python first.

## Implications for Roadmap

### Phase 16: GStreamer Buffer Tuning (STREAM-01)
**Rationale:** Smallest scope (2 lines, player.py only), zero risk, zero UI. Improves stream reliability baseline for all subsequent testing. Start the AA API inspection in parallel so Phase 17 is not blocked by idle time.
**Delivers:** Reduction in audible drop-outs on ShoutCast/HTTP streams.
**Avoids:** Pitfall #1 (ICY delay) — keep duration ≤ 5s, validate TAG latency after change.
**Research flag:** None — standard GStreamer playbin3 API, HIGH confidence.

### Phase 17: AudioAddict Station Art (ART-01 + ART-01b)
**Rationale:** Blocked on live API field discovery; overlapping that check with Phase 16 removes idle wait. ART-01b shares lookup logic with ART-01 and should follow it.
**Delivers:** Channel logos on all ~300 AA imported stations; auto-logo on URL paste in editor.
**Avoids:** Pitfall #3 (blocking import via inline urlopen), Pitfall #4 (URL format assumptions), Pitfall #12 (overwriting user-set art on re-import).
**Research flag:** REQUIRED — verify `channel_images` field name from live `/v1/di/channels` response before writing any fetch logic. If absent, check `asset_url` or static CDN fallback pattern.

### Phase 18: YouTube Thumbnail 16:9 (ART-02)
**Rationale:** Single-call change (`new_from_file_at_scale` args), no API unknowns, easy visual QA. Goes before ACCENT-01 to keep QA surfaces small and sequential.
**Delivers:** Full YouTube 16:9 thumbnails visible without cropping in now-playing panel.
**Avoids:** Pitfall #6 (square art regression) — CONTAIN + existing 160×160 slot, not widened slot.
**Research flag:** None — GdkPixbuf `-1` width behavior is documented; existing `Gtk.Overflow.HIDDEN` on `cover_stack` provides horizontal clipping.

### Phase 19: Custom Accent Color (ACCENT-01)
**Rationale:** Most surface area (new dialog + CSS subsystem). Goes last so visual QA catches any interaction with Phase 11 corner radii and panel borders. Fully independent of other v1.4 phases.
**Delivers:** Preset swatches + hex input, live preview, persistence across restarts.
**Avoids:** Pitfall #8 (CSS scope — use `:root`), Pitfall #9 (hex validation before GTK), Pitfall #10 (GNOME 47 system accent at PRIORITY_APPLICATION to win).
**Research flag:** Resolve `@define-color` vs `--accent-bg-color` CSS mechanism at Phase 19 start — STACK.md and ARCHITECTURE.md are inconsistent on this. Test both on the installed Libadwaita version; `@define-color` is the documented GTK4 mechanism.

### Phase Ordering Rationale

- Phase 16 first: zero-risk, improves test baseline, parallel-starts the AA API discovery needed for Phase 17.
- Phase 17 requires a live API call to unblock — overlap with Phase 16 to avoid dead time.
- Phase 18 is fully independent; inserting it before Phase 19 keeps QA checkpoints tight and avoids stacking two uncertain features.
- Phase 19 last: new file, new dialog, new CSS subsystem — most likely surface area for rework.

All four phases are independent. If the AA field name is confirmed quickly, Phases 17 and 18 can proceed concurrently.

### Research Flags

Phases needing live validation before coding:
- **Phase 17 (ART-01):** AA `channel_images` field name must be confirmed from a live API response. No-op on the field fails silently.
- **Phase 19 (ACCENT-01):** Confirm `@define-color accent_color` vs CSS custom property `--accent-bg-color` behavior on installed Libadwaita version. The two research files disagree on the exact CSS mechanism.

Phases with standard patterns (skip research-phase):
- **Phase 16 (STREAM-01):** GStreamer playbin3 property API, HIGH confidence.
- **Phase 18 (ART-02):** GdkPixbuf scale API, HIGH confidence.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new deps; all existing APIs verified against official docs |
| Features | HIGH | Code-read of existing hooks + GTK4/GStreamer official docs |
| Architecture | HIGH | Existing codebase is ground truth; integration points identified with file and line precision |
| Pitfalls | MEDIUM | GStreamer/GTK pitfalls HIGH; AA API field name LOW; CSS variable behavior MEDIUM |

**Overall confidence:** MEDIUM–HIGH

### Gaps to Address

- **AA `channel_images` field name:** Inspect live `/v1/di/channels` response before writing ART-01. If absent, fall back in order: `asset_url`, then static CDN pattern `https://assets.di.fm/static/images/default_channel_images/{key}.png`.
- **Libadwaita CSS mechanism:** `@define-color` (STACK.md) vs `--accent-bg-color` custom property (ARCHITECTURE.md/FEATURES.md). Resolve at Phase 19 start by testing both on the installed version.
- **ART-01b API key access in editor:** `edit_dialog.py` may not have access to the stored AA API key. Gate ART-01b on `repo.get_setting("aa_listen_key")` returning non-empty; silently skip if missing.

## Sources

### Primary (HIGH confidence)
- Existing codebase (`player.py`, `main_window.py`, `edit_dialog.py`, `aa_import.py`, `assets.py`) — integration points, threading patterns, existing hook locations
- GStreamer playbin3 docs — `buffer-size`, `buffer-duration` properties
- GdkPixbuf `new_from_file_at_scale` — width=-1 proportional scaling behavior
- GTK4 `Gtk.CssProvider.load_from_string` — CSS injection and live reload
- Libadwaita CSS variables — `accent_color`, `accent_bg_color`

### Secondary (MEDIUM confidence)
- Pithos issue #393, Mopidy discourse — GStreamer buffer values for HTTP audio streams
- Libadwaita `@define-color` override — GNOME Discourse confirmation
- GNOME 47 accent color hex values — Adwaita-Accent-Tint repo

### Tertiary (LOW confidence — needs live verification)
- AA `channel_images.default` field — inferred from ssapalski/plugin.audio.addict issue #8 `KeyError` trace; not confirmed against live response
- AA static CDN URL fallback pattern — community implementations; cross-network consistency unverified

---
*Research completed: 2026-04-03*
*Ready for roadmap: yes*

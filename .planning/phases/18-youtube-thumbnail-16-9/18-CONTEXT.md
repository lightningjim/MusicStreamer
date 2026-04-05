# Phase 18: YouTube Thumbnail 16:9 - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Display YouTube thumbnails as full 16:9 in the now-playing panel without center-cropping. Square station art and iTunes cover art must continue to display correctly without letterboxing. No changes outside the now-playing art display path.

</domain>

<decisions>
## Implementation Decisions

### 16:9 Detection
- **D-01:** Detect YouTube stations by URL pattern at play time — check if `st.url` contains `youtube.com` or `youtu.be`. No image aspect ratio inspection. This is simple, zero file I/O, and matches the same detection pattern used for YouTube-specific behaviors elsewhere in the codebase.

### Slot Behavior
- **D-02:** Both the **left logo slot** and the **right cover slot** use CONTAIN display for YouTube thumbnails. Both slots show the same station_art_path for YouTube stations, so both get the same treatment. Symmetric and consistent.
- **D-03:** Non-YouTube stations keep the current 160×160 behavior (GdkPixbuf scale with preserve_aspect=False for logo; iTunes cover art for cover slot). No change to square art display.
- **D-04 (pre-decided, STATE.md):** The 160×160 slot size does NOT change. CONTAIN is applied within the existing 160×160 container — this letterboxes the 16:9 content (160×90 image, ~35px transparent bands top and bottom). Do not widen the slot.

### Widget Strategy
- **D-05:** Switch affected slots from `Gtk.Image + GdkPixbuf.new_from_file_at_scale` to `Gtk.Picture + ContentFit.CONTAIN` for YouTube thumbnail display. `Gtk.Picture` natively supports `set_content_fit()` — no manual pixbuf math needed. Non-YouTube paths can keep existing Gtk.Image approach or also switch to Gtk.Picture (Claude's discretion, whichever is cleaner).

### Claude's Discretion
- Whether to unify all art loading onto Gtk.Picture (cleaner long-term) or only switch the YT branch
- Exact slot widget restructuring (Gtk.Stack child swap vs. conditional widget construction)
- Cover art from iTunes (_on_cover_art) — this only fires for non-YouTube ICY streams; no change needed there

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase — now-playing display
- `musicstreamer/ui/main_window.py` — `_build_now_playing_panel()` (logo_stack/cover_stack construction, lines ~55–154), `_play()` (art loading on station start, lines ~687–715), `_on_cover_art()` (iTunes art replacement, lines ~600–641)

### Requirements
- `.planning/REQUIREMENTS.md` — ART-02 (success criteria: YT full 16:9, non-YT no distortion, iTunes art unaffected)
- `.planning/ROADMAP.md` — Phase 18 description and plan 18-01

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Gtk.Picture.new_for_filename(abs_path)` + `set_content_fit(Gtk.ContentFit.COVER)` — already used in station list rows (`_build_discovery_row`, `_build_station_row`). Same widget, different ContentFit value needed here.
- `GdkPixbuf.Pixbuf.new_from_file_at_scale(abs_path, 160, 160, False)` — current logo/cover loading; stays for non-YT path if keeping dual approach.

### Established Patterns
- Art slots: `Gtk.Stack` with named children `"fallback"` (Gtk.Image symbolic icon) and `"logo"`/`"art"` (Gtk.Image with pixbuf). Phase 18 may need to restructure the non-fallback child from Gtk.Image to Gtk.Picture.
- YouTube URL check: `"youtube.com" in st.url or "youtu.be" in st.url` — used in player.py and yt_import.py for YT-specific logic. Follow the same pattern.

### Integration Points
- `_play()` in main_window.py: sets both `logo_stack` and `cover_stack` from `st.station_art_path` at play start — this is the primary integration point
- `_on_cover_art()`: replaces cover_stack content with iTunes art mid-playback — must not be broken; only fires for non-YT stations

</code_context>

<specifics>
## Specific Ideas

No specific visual references — standard CONTAIN behavior (image fits within 160×160, letterbox bands transparent/background-colored) is acceptable.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 18-youtube-thumbnail-16-9*
*Context gathered: 2026-04-05*

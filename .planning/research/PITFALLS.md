# Domain Pitfalls — MusicStreamer v1.4

**Domain:** GTK4/GStreamer Python internet radio app
**Researched:** 2026-04-03
**Scope:** 4 features — GStreamer buffer tuning, AudioAddict logo fetch, YouTube 16:9 art, custom accent color
**Confidence:** HIGH for GStreamer/GTK4 pitfalls (verified against official docs + codebase); MEDIUM for AA API URL format (undocumented API, inferred from community implementations)

---

## Critical Pitfalls

### Pitfall 1: Buffer Tuning Delays ICY Metadata Delivery

**Feature:** STREAM-01

**What goes wrong:** Increasing `buffer-size` or `buffer-duration` on `playbin3` fills the internal queue before emitting TAG bus messages. ICY metadata is interleaved in the HTTP byte stream at fixed intervals (typically every 8–16 KB). When the buffer fills before the first metadata interval passes through the demuxer, users see a stale title or "Nothing playing" for several seconds after audio starts.

**Why it happens:** `playbin3` buffers the incoming HTTP stream in a `queue2` element before demuxing. ICY metadata is embedded at byte intervals in the raw HTTP body — the larger the buffer, the more data must pass through `icydemux` before the first TAG message fires. This is a pipeline ordering issue, not a timing fluke.

**Consequences:** Audio plays but `title_label` stays stale. Degrades a core existing feature. Only manifests on first play after a station switch; hard to catch in casual testing.

**Prevention:** Set `buffer-duration` in the 2–5 second range, not higher. Avoid setting `buffer-size` above ~64 KB for ShoutCast streams. Prefer `buffer-duration` over `buffer-size` — the former scales with stream bitrate rather than raw bytes. Validate by measuring time from `PLAYING` state to first TAG message when testing buffer values.

**Codebase note:** `Player._on_gst_tag` dispatches via `GLib.idle_add` — no app-side delay is introduced. The issue is purely pipeline-level.

---

### Pitfall 2: `souphttpsrc` Properties Not Accessible at Pipeline Construction Time

**Feature:** STREAM-01

**What goes wrong:** The natural approach is to get the `souphttpsrc` element from the pipeline and call `set_property("buffer-time", ...)` directly. With `playbin3`, the source element is created lazily when the URI is set and the state transitions. Calling `pipeline.get_by_name("source")` or accessing the `source` property before the pipeline reaches `READY` state returns `None`.

**Why it happens:** `playbin3` creates and destroys the source element on each URI change. The element does not exist at `__init__` time or between playback sessions.

**Consequences:** Crash (`AttributeError` on `None`) or silent no-op — the property call is lost and buffering is unchanged.

**Prevention:** Connect to the `source-setup` signal on `playbin3`, which fires after the source element is created but before it starts fetching. This is the correct hook:

```python
self._pipeline.connect("source-setup", self._on_source_setup)

def _on_source_setup(self, pipeline, source):
    if hasattr(source.props, 'buffer_time'):
        source.set_property("buffer-time", 5_000_000)  # microseconds
```

Alternatively, set `buffer-size` and `buffer-duration` as properties directly on `playbin3` — these proxy to the internal queue and do not require `source-setup`.

**Detection:** Property setter appears to succeed but stream behavior is unchanged. Add a `print(source.get_name())` in `source-setup` to confirm which element you are configuring.

---

### Pitfall 3: AA Logo Fetch Blocks the Import Worker (Unacceptable Wall Time)

**Feature:** ART-01

**What goes wrong:** `aa_import.import_stations` is a synchronous loop already called from a daemon thread (import dialog). Adding `urllib.request.urlopen(logo_url)` inside the loop extends per-channel time from ~1ms (DB insert) to ~500ms+ (HTTP fetch). With 300+ AA channels across 6 networks, sequential logo fetching takes 2–5 minutes. The progress bar will advance, but the import appears hung.

**Why it happens:** The import loop is fast because it only does DB inserts. Image fetching is network I/O and is fundamentally different in cost. The existing on-progress callback goes through `GLib.idle_add` so the UI stays alive, but the wall clock time is unacceptable.

**Consequences:** Import runs for 5 minutes instead of 5 seconds. Users force-quit. If the import thread is a daemon, forced app exit kills it mid-write, potentially leaving partial state.

**Prevention:** Decouple logo fetch from the import loop. Two viable patterns:
1. Store the logo URL as a DB field during import (fast), then fetch the image lazily on first station display.
2. After all stations are inserted, run a separate batch fetch pass using a thread pool with bounded concurrency (3–5 workers max).

Do not add `urlopen` inside the `import_stations` loop. Keep that loop at DB-insert speed.

**Codebase note:** The AA channel JSON returned by `fetch_channels` already includes image URL fields. No extra API call is needed to get the URL — only to download the image bytes. The URL is available in the `channels` list; store it, don't fetch it inline.

---

### Pitfall 4: AA API Logo URL Format Is Undocumented and Field Names Are Unstable

**Feature:** ART-01

**What goes wrong:** The AudioAddict API is unofficial with no current public documentation. The logo URL format in the JSON response may use relative paths, inconsistent domains, CDN token parameters, or sizing suffixes (e.g. `?size=100`). Assuming a simple absolute `https://...jpg` format will fail for some channels silently.

**Why it happens:** Community implementations (Plex plugins, CLI tools) suggest the API returns `asset_url`, `images`, or similar fields — but these have varied across API versions. The field may contain a relative path requiring a base domain to be prepended.

**Consequences:** Silent partial failure — some channels get art, others don't, with no visible error. The pattern is hard to notice without inspecting the DB directly.

**Prevention:** Log the raw channel JSON during development and inspect the actual image URL structure before writing the fetch logic. Write a normalizer that handles both relative and absolute URLs. Treat a missing or 404 logo as a non-fatal no-op — fall through to no station art without raising.

**Detection:** Some stations have art, others don't, with no pattern by provider or network. 404 errors appear in `urllib` exception logs.

---

### Pitfall 5: AA URL Detection in Edit Dialog Produces False Positives/Negatives

**Feature:** ART-01 — auto-fetch on URL paste in editor

**What goes wrong:** The existing `_on_url_focus_out` handler in `EditStationDialog` auto-fetches YouTube thumbnails via `_is_youtube_url`. Adding AA logo auto-fetch with a naively broad pattern (e.g. checking for `"listen."` or `"di.fm"` substrings) produces false positives on URLs like `listen.soma.fm` (a non-AA station). It can also miss AA stream URLs if the detection pattern doesn't cover all 6 network domains after PLS resolution (the resolved URL may point to a CDN, not the `listen.*` domain).

**Why it happens:** AA streams span 6 different `listen.*` domains. After PLS resolution in `aa_import._resolve_pls`, the final URL may be a CDN hostname that contains no recognizable AA marker.

**Consequences:** False positive: fetch fires for non-AA stations, hits the AA API (key required), silently fails. False negative: user pastes an AA URL and no auto-fetch happens.

**Prevention:** Gate auto-fetch against the explicit domain list from `NETWORKS` in `aa_import.py`. Match before PLS resolution (i.e., match against the URL the user typed, not the resolved URL). Apply the same `_thumb_fetch_in_progress` guard pattern already used for YouTube. Accept that auto-fetch is a convenience, not a requirement — if detection reliability is uncertain, defer it and rely on fetch-at-import-time only.

---

## Moderate Pitfalls

### Pitfall 6: 16:9 Slot Displays Square iTunes Art Incorrectly

**Feature:** ART-02 — YouTube 16:9 in now-playing

**What goes wrong:** `cover_stack` is currently `160x160`. Changing it to a 16:9 container (e.g. `284x160`) makes the now-playing panel wider. When a non-YouTube station is playing and cover art comes from the iTunes API (square ~160x160), the image will either be center-cropped (if `ContentFit.COVER`) or letterboxed with grey bars (if `ContentFit.CONTAIN`). Both are regressions from current behavior where square art fills the square slot cleanly.

**Why it happens:** The slot is now-playing cover art, shared between YouTube stations (16:9 thumbnails) and ShoutCast stations (square iTunes art). The two content types have incompatible aspect ratios. A single fixed-size container cannot display both well.

**Consequences:** iTunes cover art looks wrong for the majority of stations (all non-YouTube stations). Center crop cuts off text or subjects; letterbox looks unfinished.

**Prevention:** Keep the slot adaptive. Track whether the current station is YouTube-based (`_current_station` is already available on `MainWindow`) and conditionally resize the container, or use `ContentFit.CONTAIN` as the default and accept slight letterboxing for YouTube thumbnails rather than breaking the common case. The simplest safe choice: keep the slot `160x160` and let `ContentFit.CONTAIN` handle 16:9 thumbnails with minimal bars. This degrades gracefully without breaking existing stations.

**Codebase note:** `cover_stack.set_size_request(160, 160)` is at line 142–143 of `main_window.py`. The `panel.set_size_request(-1, 160)` at line 53 constrains the row height. Changing the slot width will reflow the center column width — test the full panel layout after any change.

---

### Pitfall 7: Changing `cover_stack` Size Breaks `now-playing-panel` Layout

**Feature:** ART-02

**What goes wrong:** The now-playing panel is a 3-column `Gtk.Box` (logo | center | cover). The center column has `set_hexpand(True)` and expands to fill remaining space. If `cover_stack` changes from 160px wide to 284px wide, the center column shrinks by 124px, which may compress the `title_label`, `station_name_label`, volume slider, and controls box. On smaller window sizes this causes truncation or widget overlap.

**Prevention:** After changing the art slot size, test at the minimum window size (`900x650`, the current default). Verify that the `title_label` still has enough horizontal space to show a meaningful portion of a long track title. Check that the volume slider doesn't collapse to near-zero width.

---

### Pitfall 8: CSS Variable Override Scope — `--accent-bg-color` Must Be on `:root`

**Feature:** ACCENT-01

**What goes wrong:** Setting `--accent-bg-color` in a rule scoped to a widget class (e.g. `.suggested-action { --accent-bg-color: ... }`) only affects descendants of that specific widget. Most accent-colored widgets elsewhere in the app (buttons in other dialogs, focus rings, selection highlights) won't pick it up because GTK CSS custom properties scope to the subtree of the selector.

**Why it happens:** `Gtk.StyleContext.add_provider_for_display` loads the CSS globally, but the variable's effective scope is still determined by the selector in the CSS string. Adding a scoped rule globally doesn't make it global in scope.

**Consequences:** Accent color changes in some widgets but not others. Partial effect is hard to debug — not an obvious failure.

**Prevention:** Declare `--accent-bg-color` on `:root` or `*`:

```css
:root {
    --accent-bg-color: #ff6a00;
    --accent-color: #ff6a00;
    --accent-fg-color: #ffffff;
}
```

Use `Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)` — not per-widget `add_provider`. This priority (600) is higher than Libadwaita's theme provider and wins on conflict.

---

### Pitfall 9: Invalid Hex Input Causes Silent No-Op or Strips Existing Styles

**Feature:** ACCENT-01

**What goes wrong:** `Gtk.CssProvider.load_from_string` (or `load_from_data`) silently ignores invalid CSS rules. Passing an invalid hex (`#xyz`, incomplete `#ff0`, empty string) causes the rule to be dropped without raising a Python exception. The `parsing-error` signal fires but only if connected. A structurally malformed CSS string (e.g. missing closing brace) can invalidate the entire stylesheet, stripping previously applied styles including Phase 11 corner radii and panel borders.

**Why it happens:** GTK CSS parsing is lenient by design — it skips invalid rules rather than failing hard.

**Consequences:** Accent color silently stays at previous value with no user feedback. In the worst case (malformed CSS structure), Phase 11 visual polish is wiped out.

**Prevention:**
1. Validate the hex string in Python before passing to GTK: `re.fullmatch(r'#[0-9a-fA-F]{6}', value)` — reject 3-char, uppercase-only, or prefixless values.
2. Derive `--accent-fg-color` (white or black) from luminance rather than hardcoding.
3. Keep the CSS string minimal — only the variable declarations — to minimize structural parse risk.
4. During development, connect `provider.connect("parsing-error", lambda p, s, e: print(e.message))` to surface parse errors.

---

### Pitfall 10: GNOME 47+ System Accent Color Overwrites App-Level Override

**Feature:** ACCENT-01

**What goes wrong:** GNOME 47+ introduced system-level accent color via the settings portal. Libadwaita reads this at startup and injects `--accent-bg-color`. If the app loads its CSS provider at a lower priority, or reloads it at the wrong time, the system accent will overwrite the user's custom value.

**Prevention:** Always use `Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION` (600) — this is above Libadwaita's theme provider. Reload the provider on every settings change (re-call `load_from_string` and re-add via `add_provider_for_display`), not just at startup. Test on a GNOME installation with a non-default system accent color active.

---

## Minor Pitfalls

### Pitfall 11: AA Logo Fetch Leaves Temp Files on Import Interruption

**Feature:** ART-01

**What goes wrong:** The existing `fetch_yt_thumbnail` pattern writes to a `NamedTemporaryFile` and calls `os.unlink` after `copy_asset_for_station`. An AA batch logo fetch will follow the same pattern. If the import is cancelled mid-batch or the app is closed, partially downloaded logos leave orphan `/tmp/*.jpg` files.

**Prevention:** Always wrap `os.unlink(temp_path)` in `try/except OSError`. Use a `finally` block to ensure cleanup regardless of whether `copy_asset_for_station` succeeded.

---

### Pitfall 12: AA Logo Fetch Overwrites User-Set Station Art on Re-Import

**Feature:** ART-01

**What goes wrong:** `copy_asset_for_station` writes to `assets/<station_id>/station_art<ext>`. If a new fetch path updates logos for stations already in the DB (e.g. a "refresh logos" action), it silently overwrites art the user manually chose.

**Prevention:** Only write station art during initial import (when `imported += 1`), never during the skipped-duplicate path. Add an explicit guard: only write if `station_art_path` is `None` or empty in the DB.

---

### Pitfall 13: GStreamer State Transition Race More Audible With Larger Buffers

**Feature:** STREAM-01

**What goes wrong:** `Player._set_uri` calls `set_state(NULL)` then immediately sets the URI and calls `set_state(PLAYING)`. With larger buffers, the pipeline may not fully drain to NULL before the new URI is set, leaving buffered audio that plays briefly before the new stream starts. This pre-exists the buffer tuning work but larger buffers make the artifact more audible.

**Prevention:** Do not change the existing state transition pattern unless glitches are observed after tuning. If glitches appear on station switch, flush the pipeline explicitly with `Gst.Event.new_flush_start()` / `flush_stop` before setting the new URI.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| GStreamer buffer tuning | ICY metadata latency regression (#1) | Measure time to first TAG message; keep buffer-duration ≤5s |
| GStreamer buffer tuning | `souphttpsrc` property timing (#2) | Use `source-setup` signal; verify which element owns the property |
| AA logo fetch at import | UI blocking from inline HTTP (#3) | Decouple fetch from import loop |
| AA logo fetch at import | Undocumented URL format (#4) | Inspect raw JSON in development, normalize URLs |
| AA logo auto-fetch in editor | URL detection false pos/neg (#5) | Match against explicit `NETWORKS` domain list only |
| YouTube 16:9 now-playing | Square iTunes art breakage (#6) | Conditional sizing or CONTAIN fallback |
| YouTube 16:9 now-playing | Panel layout reflow (#7) | Test at min window size after dimension change |
| Custom accent color | CSS variable scope (#8) | Use `:root` selector, `PRIORITY_APPLICATION` |
| Custom accent color | Invalid hex silent failure (#9) | Validate hex in Python before passing to GTK |
| Custom accent color | System accent conflict (#10) | Test on GNOME with non-default system accent |

---

## Sources

- GStreamer playbin3 docs: https://gstreamer.freedesktop.org/documentation/playback/playbin3.html
- GStreamer buffering guide: https://gstreamer.freedesktop.org/documentation/application-development/advanced/buffering.html
- souphttpsrc docs: https://gstreamer.freedesktop.org/documentation/soup/souphttpsrc.html
- Pithos buffer-size real-world issue: https://github.com/pithos/pithos/issues/393
- Libadwaita CSS variables: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.2/css-variables.html
- GTK4 CSS overview: https://docs.gtk.org/gtk4/css-overview.html
- AudioAddict community implementation (phrawzty): https://github.com/phrawzty/AudioAddict.bundle
- Codebase analysis: `player.py`, `main_window.py`, `edit_dialog.py`, `aa_import.py`, `cover_art.py`, `assets.py`

---

## Archived — v1.3 Pitfalls (Discovery & Favorites)

The following pitfalls were researched for v1.3 and remain valid as historical reference. They are addressed in Phases 12–15.

<details>
<summary>Expand v1.3 pitfalls</summary>

### P1: Radio-Browser.info — Hardcoded Server IP
Use DNS round-robin via `all.api.radio-browser.info`. Do not hardcode `de1.api.radio-browser.info`.

### P2: Radio-Browser.info — Sync HTTP on Main Thread
All Radio-Browser calls must use daemon thread + `GLib.idle_add`. Debounce search-changed 300ms.

### P3: Radio-Browser.info — Unbounded Response
Always pass `limit=100` to search endpoint.

### P4: AudioAddict API Key Security
Store in settings table; mask in UI (`set_visibility(False)`); never log.

### P5: AudioAddict PLS URL Per Quality Tier
Re-fetch PLS for each quality tier; never substitute subdomains.

### P6: YouTube Import Blocking Main Loop
Daemon thread + `GLib.idle_add` for results. Spinner while running.

### P7: YouTube Non-Live Filter
`is_live == True` strict identity check (non-live entries return `None`, not `False`).

### P8: Favorites Duplicate Detection
`INSERT OR IGNORE` + `UNIQUE(station_id, title)` constraint.

### P9: Favorites Junk Title Guard
Gate star action on `not is_junk_title(current_title)`.

### P10: Favorites DB Migration
`CREATE TABLE IF NOT EXISTS favorites` in `db_init` executescript.

### P11: Radio-Browser Click-Count Side Effect
Only call `/json/url/{uuid}` on play/save, not on browse display.

</details>

---

*Pitfalls research for: GTK4/Python internet radio — v1.4 Media & Art Polish*
*Researched: 2026-04-03*

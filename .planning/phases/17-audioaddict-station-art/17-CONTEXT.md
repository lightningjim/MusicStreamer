# Phase 17: AudioAddict Station Art - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Fetch AudioAddict channel logo images during bulk import (ART-01) and auto-populate station art in the editor when an AA stream URL is pasted (ART-02). No changes to non-AA stations, no changes to the now-playing art slot display, and no changes to YouTube thumbnail handling.

</domain>

<decisions>
## Implementation Decisions

### Logo Download in Bulk Import
- **D-01:** Logo downloads run **concurrently** with station insert during bulk import — image URLs are extracted from the channels API response, downloads are dispatched in parallel threads, and the import loop does not wait for each download before moving on.
- **D-02:** The import dialog **waits for all logo downloads before showing "done"**. Progress label shows "Importing stations…" during insert phase, then "Fetching logos…" during download phase, then "Done — N imported, M skipped". Art is ready the moment the dialog closes.
- **D-03:** Logo download failures (network error, missing field, unexpected structure) are **silent** — station is still imported without art; no error is surfaced. Consistent with Phase 15 silent-skip pattern.

### repo.insert_station Art Wiring
- **D-04:** Bulk import uses an **insert-then-update** pattern: `insert_station()` (or `repo.insert_station()`) is called first and returns the new station ID. After the logo is downloaded and processed via `copy_asset_for_station()`, a lightweight `repo.update_station_art(station_id, art_path)` call attaches the art. This requires adding `update_station_art()` to `repo.py`.
- **D-05:** Downloaded logos follow the same path as YouTube thumbnails: download to a temp file → `copy_asset_for_station(station_id, temp_path, "station_art")` → pass result path to `update_station_art()` → delete temp file. No deviation from the established asset pattern.

### Editor AA URL Detection (ART-02)
- **D-06:** In the station editor, an AudioAddict URL is detected by matching known AA stream domains against the URL entry on focus-out (same `_on_url_focus_out` hook). Known domains: `listen.di.fm`, `listen.radiotunes.com`, `listen.jazzradio.com`, `listen.rockradio.com`, `listen.classicalradio.com`, `listen.zenradio.com` (matches `NETWORKS` in `aa_import.py`).
- **D-07:** Logo fetch uses the **"Fetch from URL" button popover** when no API key is stored. If the user pastes an AA URL and clicks "Fetch from URL" with no saved key, a popover appears asking for the key. The key is saved to the DB on successful fetch (same persistence as Phase 15 import). If a key is already stored, the fetch proceeds silently on focus-out, same as YouTube thumbnails.
- **D-08:** The editor resolves the channel key from the AA stream URL path (e.g., `di_house` from `prem2.di.fm/…/di_house?listen_key=…`) and calls the AA channels API to retrieve the logo URL, then downloads it. If the channel key cannot be parsed or the API returns no image, fetch is skipped silently.

### Claude's Discretion
- Exact AA API field name for channel images (`channel_images.default` per STATE.md flag — researcher must verify against live API before any code is written)
- Whether `fetch_channels()` in `aa_import.py` is extended to include image URLs, or a separate lookup is made — researcher decides based on live API response shape
- Thread pool size for concurrent logo downloads during bulk import
- Exact widget hierarchy for the "Fetch from URL" API key popover in the editor
- Whether `update_station_art()` is a dedicated SQL UPDATE or reuses an existing update path in `repo.py`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### AudioAddict API
- **Verify live API response shape before writing any code** (STATE.md research flag): inspect `https://api.audioaddict.com/v1/{network}/channels` or the existing `https://{domain}/{tier}?listen_key={key}` endpoint to confirm (1) exact field name for channel images, (2) whether image URLs are inline in the channels list response or require a separate call, (3) whether image URLs are publicly accessible (no auth needed to download the image itself).

### Codebase
- `musicstreamer/aa_import.py` — Existing AA backend; `fetch_channels()` and `import_stations()` are the targets for ART-01 changes
- `musicstreamer/ui/edit_dialog.py` — Station editor; `_on_url_focus_out()`, `_on_fetch_clicked()`, `_start_thumbnail_fetch()`, `_on_thumbnail_fetched()` are the hook points for ART-02
- `musicstreamer/yt_import.py` — `fetch_yt_thumbnail()` function: the threading + temp-file + callback pattern to mirror for AA logo fetch
- `musicstreamer/assets.py` — `copy_asset_for_station()`: the function that moves a temp file to the persistent station art path; used by both bulk import and editor fetch
- `musicstreamer/repo.py` — `insert_station()` (check current signature and return value), settings persistence pattern (used for API key storage in Phase 15), and the update path for adding `update_station_art()`
- `musicstreamer/ui/import_dialog.py` — Existing import dialog with progress feedback (Phase 14/15 pattern); Phase 17 adds a logo-fetch phase to the AA import flow

### Requirements
- `REQUIREMENTS.md` — ART-01, ART-02 (acceptance criteria and success criteria)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `fetch_yt_thumbnail(url, callback)` in `yt_import.py`: daemon thread + GLib.idle_add callback pattern — AA logo fetch function should follow this exactly
- `copy_asset_for_station(station_id, temp_path, "station_art")` in `assets.py`: moves temp download to persistent path — used as-is for AA logos
- `_on_url_focus_out()` / `_on_fetch_clicked()` in `edit_dialog.py`: existing URL-change hook — add AA URL detection branch here
- `_art_stack` (Gtk.Stack with "pic"/"spinner") in `edit_dialog.py`: existing spinner/image toggle — AA fetch reuses this directly
- `NETWORKS` list in `aa_import.py`: the six AA domain/slug/name entries — use for URL pattern matching in editor

### Established Patterns
- Background work: daemon threads + `GLib.idle_add(callback, result)` for UI updates
- Temp file download → `copy_asset_for_station()` → delete temp: the full asset persistence sequence
- Settings persistence: `repo.py` stores `audioaddict_api_key` and `audioaddict_quality` (Phase 15) — same mechanism for reading the key in the editor

### Integration Points
- `import_stations()` in `aa_import.py` → needs to return station IDs and trigger parallel logo downloads → `update_station_art()` in `repo.py`
- `_on_url_focus_out()` in `edit_dialog.py` → detect AA URL → read stored API key from `repo` → fetch logo (or trigger key prompt via "Fetch from URL" popover)
- `ImportDialog` progress phase: add a "Fetching logos…" phase after station insert phase completes

</code_context>

<specifics>
## Specific Ideas

- Progress label sequence in import dialog: "Importing stations… (N/total)" → "Fetching logos…" → "Done — N imported, M skipped"
- Editor "Fetch from URL" popover for missing API key: small popover on the button, single text entry, "Fetch" confirm. Key saved on success.
- Focus-out auto-trigger for AA URLs follows the exact same UX as YouTube: user pastes URL → tabs out → spinner appears → logo populated. No extra user action needed if key is already stored.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 17-audioaddict-station-art*
*Context gathered: 2026-04-03*

# Phase 74: SomaFM full station catalog + art - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a **SomaFM bulk importer** that pulls all ~40 SomaFM channels into the library with multiple stream qualities per channel and station art. Same UX shape as the existing AudioAddict importer (multi-quality, logos, dedup-by-URL, manual idempotent re-import); same UI affordance as the existing GBS.FM import (hamburger-menu action, toast-driven progress).

The phase touches:
- NEW `musicstreamer/soma_import.py` — public-API client + bulk importer (mirrors `aa_import.py` shape; no auth, no listen_key — SomaFM API is public).
- `musicstreamer/ui_qt/main_window.py` — new hamburger menu entry "Import SomaFM" + worker dispatch (parity with the existing "Add GBS.FM" handler at `main_window.py:1420-1465`).
- Possibly `musicstreamer/__main__.py` logger registration (current line 234 lists `aa_import / gbs_api / mpris2`; add `soma_import`).
- `tests/test_soma_import.py` (NEW) + `tests/fixtures/soma_channels_*.json` (NEW) — mocked SomaFM API responses for deterministic testing.
- `tests/test_main_window_*.py` — extend hamburger-menu test to cover the new action wiring.

**Out of scope** (deferred — see Deferred Ideas):
- In-memory / browse-modal SomaFM UX (rejected — poll-to-install per Area 1).
- ImportDialog tab for SomaFM (rejected — hamburger action only per Area 3).
- Auto-refresh on app start / weekly refresh / etag toast (rejected — manual only per Area 2).
- Discovery-dialog SomaFM curated source (rejected — not a discovery problem; it's a bulk-import problem).
- Metadata refresh on URL match (rejected — true AA parity is full no-op per Area 4 reconciliation).
- Truncate-and-reset for `provider_name = 'SomaFM'` stations (rejected — too invasive).
- Notification when SomaFM publishes a new channel.
- SomaFM premium-tier / paid feature integration (Phase 74 is free public API only).

</domain>

<decisions>
## Implementation Decisions

### Catalog architecture

- **D-01: Poll-to-install.** Bulk insert all ~40 SomaFM channels as real Station rows in SQLite on user-initiated import. Multi-quality streams per channel + per-station logo downloaded to the library's logos directory (same dir as AA logos). Closest parity with AudioAddict + GBS.FM importers.
- **D-02: Provider name pinning.** Every SomaFM-imported station has `provider_name = "SomaFM"` (canonical brand string — matches `"GBS.FM"`, `"DI.fm"`, `"JazzRadio"` etc.).
- **D-03: Multi-stream per channel — 4 tiers × 5 ICE relays = 20 streams/station.** Per RESEARCH live-probe (2026-05-13), every SomaFM channel exposes exactly 4 uniform tiers: `(mp3, highest=128 kbps)`, `(aac, highest=128 kbps)`, `(aacp, high=64 kbps)`, `(aacp, low=32 kbps)`. Each tier's PLS file expands to 5 ICE relay URLs (ice1..ice5.somafm.com). Insert all 4 tiers × all 5 relays = 20 stream rows per station. Total across 46 channels = ~920 stream rows. **Tier→quality mapping** (locked 2026-05-13 by user): tier 0 `(mp3, highest)` → `quality="hi"`, codec `"MP3"`, bitrate 128; tier 1 `(aac, highest)` → `quality="hi2"`, codec `"AAC"`, bitrate 128; tier 2 `(aacp, high)` → `quality="med"`, codec `"AAC"`, bitrate 64; tier 3 `(aacp, low)` → `quality="low"`, codec `"AAC"`, bitrate 32. **Position numbering** mirrors AA's pattern (`aa_import._POSITION_MAP`): `position = tier_base * 10 + relay_index` where tier_base = {hi: 1, hi2: 2, med: 3, low: 4} and relay_index = 1..5, so primary relays sort above fallback relays within each tier.

### Refresh policy

- **D-04: Manual re-import only.** No auto-refresh on startup, no scheduled refresh, no etag-check toast. User clicks the hamburger action again to refresh.
- **D-05: Full no-op on URL match (true AA parity).** Re-import semantics: for each SomaFM channel, if ANY of its stream URLs already exist in the library, SKIP the entire channel — no metadata refresh, no logo redownload, no stream reset. New (never-imported) SomaFM channels insert normally. Mirrors `aa_import.py:import_stations_multi` semantics. **The only way to refresh an existing SomaFM station's logo/description is delete-and-reimport.**

### UI entry point

- **D-06: Hamburger menu action.** Add `"Import SomaFM"` to the hamburger menu near the existing `"Add GBS.FM"` action. One-click invocation, no dialog. Status surfaced via toasts (parity with GBS.FM `import_station` toast pattern at `main_window.py:1429-1453`):
  - "Importing SomaFM…"
  - "SomaFM import: N stations added" (or "no changes" if all channels were dedup-skipped)
  - "SomaFM import failed: <truncated message>"
- **D-07: Worker-thread dispatch.** Network calls run on a worker thread (parity with GBS.FM `_start_gbs_import` at `main_window.py:1420-1465`). Worker retention pattern follows Phase 60 D-02's `SYNC-05` precedent so the QThread isn't GC'd mid-flight.
- **D-08: No progress bar.** Toast-only feedback (parity with GBS.FM). Phase 74's 40-channel import is faster than AA's import-dialog progress-bar pattern justifies. If real-world UAT shows the import takes >5 sec, planner can revisit.

### Dedup behavior

- **D-09: Skip-if-URL-exists across the WHOLE library.** For each fetched SomaFM channel, check if ANY of its candidate stream URLs match an existing station's stream URL (any provider). If MATCH found, skip the channel entirely — regardless of the matched station's `provider_name`. Preserves user's hand-curated SomaFM stations (with custom tags / provider / name) untouched. Possible visible duplicates (e.g., hand-curated "Groove Salad" + SomaFM-canonical "Groove Salad" not imported) are accepted; user manually deletes one to resolve.
- **D-10: Atomic per-channel insert.** A SomaFM channel either inserts fully (station row + ALL its stream rows + logo) or not at all (channel-level skip). Mirror AA's `import_stations_multi` ordering: insert station → insert streams → fire logo download (background — non-blocking).
- **D-11: Logo failure is non-fatal.** If the logo HTTP fetch fails, the station + streams stay inserted; logo download is best-effort (mirror AA pattern). User can manually edit the station to set a logo later.

### MB protocol awareness (no MB calls in this phase)

- **D-12: No MusicBrainz integration here.** Phase 73 added the per-station `cover_art_source` field with default `"auto"`. SomaFM-imported stations get `cover_art_source = "auto"` (zero-config — they'll use iTunes-then-MB fallback at playback time per Phase 73's Auto-mode).
- **D-13: Station logos vs cover art.** SomaFM channel logos (station-level, square brand image) are different from track-level cover art. SomaFM logos download to the logos directory and populate `station_art_path`. Phase 73's `cover_art_source` is unaffected.

### Failure handling

- **D-14: Network error / 5xx / JSON parse error → entire import aborts cleanly.** Surface a single toast "SomaFM import failed: <truncated reason>". Do NOT partially import (no half-fetched channels). Mirror AA's exception path.
- **D-15: Per-channel best-effort within a successful catalog fetch.** Once the channels.json call succeeds, a per-channel exception during stream/logo extraction skips THAT channel but continues with the rest. Final toast counts only successful inserts.

### Logging

- **D-16: Add `soma_import` to the per-logger registration in `__main__.py:234`.** Same INFO-level treatment as `aa_import`, `gbs_api`, `mpris2`.

### Claude's Discretion

- **Quality tier mapping — LOCKED in D-03 (2026-05-13).** `hi`, `hi2`, `med`, `low` per the 4-tier scheme above. `hi2` is a new quality label introduced for SomaFM's two-tiers-at-128-kbps (MP3 + AAC); `stream_ordering._CODEC_RANK` will sort AAC above MP3 within the same bitrate (AAC=2, MP3=1) so `hi2` (128 AAC) actually plays ABOVE `hi` (128 MP3) when both are present. **Planner decision needed**: either rename to `hi=AAC-128, med=MP3-128, med2=AAC-64, low=AAC-32` to match codec-rank order, OR accept the slight quality-label-vs-rank inversion. Recommend the rename for ordering clarity.
- **Codec field population.** SomaFM API exposes format → infer codec: `mp3` → "MP3", `aac` → "AAC", `aacp` → "AAC" (HE-AAC; verified working on Windows per WIN-05/Phase 69). Bitrate is in the API response; copy verbatim.
- **Channel-fetch concurrency.** `channels.json` returns all 40 channels in one HTTP call (1 request total). No per-channel HTTP needed for streams (they're in the channels.json response). Logo downloads are per-channel (~40 GETs) — sequential is fine for ~40 small images, but parallel-with-threading-pool is also acceptable.
- **Logo file naming + persistence.** Mirror AA's `_download_logo` pattern (`aa_import.py:257-280`). Use SomaFM channel `id` slug as the filename basis.
- **Stream `label` field.** Either empty (AA pattern) or "MP3 128 kbps" / "AAC 64 kbps" / "AAC+ 32 kbps" labels (more informative). Planner picks; prefer empty for AA parity.
- **API endpoint.** `https://api.somafm.com/channels.json` is the documented public endpoint. The mobile-app's `https://somafm.com/channels.json` may also work. Either is acceptable; planner verifies which is current and uses one consistently.
- **User-Agent on SomaFM requests.** SomaFM doesn't require a UA, but for politeness use `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` (the same string Phase 73 codified for MB/CAA). One-line constant share or duplicate — planner picks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone

- `.planning/PROJECT.md` — current stack, AA + GBS importer history, WIN-05 (AAC-on-Windows) closed in Phase 69.
- `.planning/REQUIREMENTS.md` — Phase 74 will register new requirement IDs (likely `SOMA-NN` family). Coverage block bump needed in Plan 01 Task 1 (mirror Phase 73's read-then-add procedure).

### Codebase maps

- `.planning/codebase/STRUCTURE.md` — module boundaries; confirms a new `soma_import.py` next to `aa_import.py` and `yt_import.py` is the right home.
- `.planning/codebase/INTEGRATIONS.md` — existing external HTTP services + importer patterns.
- `.planning/codebase/CONVENTIONS.md` — worker-thread + Qt-queued signal pattern; toast-driven progress for hamburger actions.

### Closest analogs (read in full)

- `musicstreamer/aa_import.py` — multi-quality channels, logo download, dedup-by-URL, idempotent re-import. THE primary analog. Public functions to mirror: `fetch_channels_multi`, `import_stations_multi`, `_download_logo`.
- `musicstreamer/gbs_api.py:1118-1170` — single-station idempotent import + toast-driven UX. Use for hamburger-menu wiring shape.
- `musicstreamer/ui_qt/main_window.py:1420-1465` — `_start_gbs_import` + `_on_gbs_import_done` hamburger handlers. Direct analog for `_start_soma_import` + `_on_soma_import_done`.
- `musicstreamer/ui_qt/main_window.py:125-200` — Phase 60 D-02 worker-thread retention pattern (`SYNC-05`). Soma's worker MUST follow this to avoid mid-import GC.
- `musicstreamer/stream_ordering.py:1-46` — `_CODEC_RANK`, `quality_rank`, `order_streams`. Informs quality-tier mapping for SomaFM streams.
- `musicstreamer/__main__.py:234` — per-logger INFO registration. Add `soma_import` to the existing list.
- `musicstreamer/repo.py:79-181` — Station insert + Stream insert primitives.
- `tests/test_aa_import.py` (existing) — pytest pattern for importer testing with monkeypatched `urlopen`. THE template for `tests/test_soma_import.py`.

### Prior-phase decisions worth knowing

- **Phase 73 (just shipped)**: introduced per-station `cover_art_source` field defaulting to `"auto"`. SomaFM stations inherit this default — no Phase 74 change needed.
- **Phase 69 (WIN-05)**: AAC + HE-AAC streams work on Windows post the gst-libav bundling fix. SomaFM's HE-AAC streams are already verified working.
- **Phase 47 (stream ordering)**: `stream_ordering.py` provides codec+bitrate ordering. SomaFM importer just needs to populate `codec` + `bitrate_kbps` + optional `quality` — sort happens automatically.
- **Phase 71 (sibling stations)**: SomaFM channels are NOT siblings of each other (they're discrete stations). No siblings work needed.

### External (planner verifies live)

- `https://api.somafm.com/channels.json` — primary endpoint. Returns channel list with `id`, `title`, `description`, `image`, `xlimage`, `playlists` (array of {url, format, quality, listeners}).
- `https://somafm.com/channels.json` — possibly mirror. Verify both are current.
- `https://somafm.com/linktoplay.html` — channel listing for user-facing reference (NOT used by importer).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`aa_import.fetch_channels_multi(listen_key) -> list[dict]`** — exact shape to mirror. SomaFM's version has NO `listen_key` (public API), so signature is `fetch_channels(timeout: int = 15) -> list[dict]`.
- **`aa_import.import_stations_multi(channels, repo, on_progress=None, on_logo_progress=None) -> tuple[int, int]`** — exact shape to mirror. Returns `(imported, skipped)`. Soma can drop the `on_logo_progress` callback since there's no progress dialog.
- **`aa_import._download_logo(station_id, image_url)`** — mirror verbatim. Same logos directory.
- **GBS.FM `import_station(repo, on_progress=None) -> tuple` (single station)** — different shape (one row) but same toast-driven UX. Reference for hamburger handler wiring.
- **`main_window._start_gbs_import` + `_on_gbs_import_done`** — copy-paste-modify into `_start_soma_import` + `_on_soma_import_done`. Worker-thread retention (Phase 60 `SYNC-05`) is the critical pattern.
- **`__main__.py:DEFAULT_SMOKE_URL`** — already points at `ice1.somafm.com/groovesalad-128-mp3` (smoke-test default). After Phase 74, the smoke test can optionally pull from the imported library; out of scope for now.

### Established Patterns

- **Public-API HTTP client** — `urllib.request.urlopen` with `timeout=15` (AA pattern, NOT `timeout=5` from cover_art — AA uses 15 for catalog fetches).
- **Module-level constants** for codec/bitrate mappings (mirror `aa_import._CODEC_MAP` etc.).
- **Toast pattern** — `self.show_toast(...)` from `main_window` for status; worker thread surfaces results via Qt signal back to main thread.
- **Worker retention** — store the QThread on `self._soma_import_thread` so it's not GC'd mid-flight (Phase 60 `SYNC-05` learned this the hard way).
- **Dedup-by-URL** — `aa_import.import_stations_multi` already implements this. Lift the logic.
- **Logo download** — best-effort, exceptions swallowed, station inserted regardless.

### Integration Points

- New module `musicstreamer/soma_import.py` with public API:
  - `fetch_channels(timeout: int = 15) -> list[dict]`
  - `import_stations(channels: list[dict], repo: Repo, on_progress=None) -> tuple[int, int]`  *(returns `(imported, skipped)`)*
  - `_download_logo(station_id, image_url)` (private, mirror AA)
  - Module-level `_CODEC_MAP`, `_QUALITY_MAP` constants (planner discretion)
- New hamburger menu entry: `act_soma_import = self._menu.addAction("Import SomaFM")` in `main_window.py` near the existing GBS actions.
- New main_window handler methods: `_start_soma_import()` + `_on_soma_import_done(inserted, skipped)`.
- New worker-thread field: `self._soma_import_thread: Optional[QThread] = None`.
- New logger registration: append `"soma_import"` to the existing list at `__main__.py:234`.

### Threading + Qt notes (carry forward from Phase 73 lessons)

- Soma worker runs on `QThread`, NOT raw `threading.Thread` — main_window already uses QThread for GBS import. Reuse that pattern.
- Cross-thread result delivery via Qt `Signal` (not direct callback) — auto-marshalls to main thread.
- Test mocking pattern: monkeypatch `musicstreamer.soma_import.urllib.request.urlopen` (parity with `tests/test_cover_art.py` pattern).

</code_context>

<specifics>
## Specific Ideas

- **Provider brand string is exactly `"SomaFM"`** (CamelCase, no space, no period). Matches `"GBS.FM"` / `"DI.fm"` / `"JazzRadio"` capitalization convention.
- **Toast on success: "SomaFM import: N stations added"** (not "N channels imported"). Use the project's existing "station" vocabulary in user-visible text. If `inserted == 0`, toast "SomaFM import: no changes" (mirror GBS.FM).
- **WIN-05 / Phase 69 closure means HE-AAC is supported.** SomaFM imports AAC+ 32 kbps streams without a special path. The codec field can carry "AAC" (since AAC+ is HE-AAC, which decodes via the same `aacparse` + `avdec_aac` chain). Don't introduce an "AAC+" codec label — it'd break `stream_ordering.py:_CODEC_RANK`.
- **Phase 74 will register new requirement IDs in REQUIREMENTS.md.** Likely `SOMA-01` through `SOMA-NN` (count TBD by planner). Mirror Phase 73's Plan 01 read-then-add Coverage-block update procedure.
- **REQUIREMENTS.md `ART-04` (note: not `STATION-ART-04`).** Phase 74 is a strict subset of `ART-04` ("Station art fetching beyond YouTube/iTunes/AudioAddict (additional sources) — `.planning/notes/2026-04-03-station-art-fetching-beyond-youtube.md`"). Phase 74 does NOT close `ART-04` — that note covers multiple sources (favicon, ICY metadata, etc.). Note for planner: don't claim `ART-04` closure on this phase.

</specifics>

<deferred>
## Deferred Ideas

- **In-memory / browse-modal SomaFM UX** — rejected per Area 1 (poll-to-install wins). Could re-open as a future phase if user wants curated browsing without library pollution.
- **SomaFM tab in ImportDialog** — rejected per Area 3 (hamburger only). Could re-open if user wants progress-bar UX for slow imports.
- **Auto-refresh on app start / weekly refresh / etag-check toast** — rejected per Area 2 (manual only). If SomaFM publishes a major catalog reshuffle, user re-runs the import.
- **Discovery dialog SomaFM curated source** — rejected per Area 3 (different paradigm than Phase 74).
- **Refresh metadata on URL match** — rejected per Area 4 (true AA parity is full no-op).
- **Truncate-and-reset for `provider_name = 'SomaFM'` stations** — rejected per Area 4 (too invasive — would clobber user edits).
- **Notification toast when SomaFM publishes a new channel** — out of scope.
- **SomaFM premium / paid integration** — out of scope (Phase 74 is public API only).
- **Merge-by-name dedup (collapse hand-curated 'Groove Salad' into SomaFM-canonical)** — rejected; risk of false positives on common channel names.
- **Quality-label fallback when SomaFM API drops a tier** — out of scope; current channel list is stable.
- **Progress bar UX** — rejected per D-08 (toast-only). Could re-open if real-world import takes >5 sec.

</deferred>

---

*Phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-*
*Context gathered: 2026-05-13*

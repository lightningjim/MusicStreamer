# Phase 73: MusicBrainz album-cover lookup — complement iTunes with smart routing - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Add **MusicBrainz + Cover Art Archive** as an additive cover-art source that complements the existing iTunes Search lookup. Cover-art behavior becomes a **per-station preference** with three modes (Auto / iTunes-only / MB-only); `Auto` is the default for new and existing stations and means *iTunes → MB fallback on miss*.

All MB traffic respects:
- **1 req/sec** rate limit (enforced in-process; no SLA tolerance)
- **Required User-Agent**: `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)`
- **Strict matching**: artist+title query only; MB score threshold ≥ 80; bare-title ICY strings skip MB entirely

The phase touches:
- `musicstreamer/cover_art.py` — add MB lookup path; keep iTunes path intact
- `musicstreamer/models.py` + `musicstreamer/repo.py` + schema migration — new `cover_art_source` field on stations (Auto/iTunes-only/MB-only)
- `musicstreamer/ui_qt/edit_station_dialog.py` — new selector
- `musicstreamer/ui_qt/now_playing_panel.py` — pass station's preference into the worker; honor it for both the genre-handoff (`last_itunes_result`) and the art source
- `musicstreamer/settings_export.py` — round-trip the new field in ZIP export/import

**Out of scope** (deferred — see Deferred Ideas):
- Cover-art caching (in-memory OR persistent SQLite). This phase stays stateless.
- AudioAddict / favicon / ICY-metadata art fetching (ART-04 parent note untouched here).
- Editing favorites' `genre` retroactively when a track's source changes.
- A global hamburger-menu "Cover art source" toggle. Per-station only this phase.

</domain>

<decisions>
## Implementation Decisions

### Routing — when MB gets called

- **D-01: Per-station selector with 3 modes.** A new `cover_art_source` field on each station: `Auto` (default), `iTunes-only`, `MB-only`. No global toggle.
- **D-02: `Auto` semantics.** Try iTunes first. If iTunes returns no result (or the result is rejected as junk), try MB. If both miss, fall through to the station-logo placeholder (existing behavior).
- **D-03: `iTunes-only` semantics.** Legacy behavior — never call MB. Iceberg-clean: lets the user keep the historic path for stations that have always worked well via iTunes.
- **D-04: `MB-only` semantics.** Never call iTunes. Skip the iTunes network call entirely (do **not** call iTunes solely for genre — see D-13).
- **D-05: Default for new and existing stations is `Auto`.** Migration backfills every existing row with `Auto`; new stations get `Auto` at insert time. Zero-config improvement for the whole library.
- **D-06: Selector placement.** EditStationDialog — exact section/row is planner's discretion (close to the existing per-station "ICY disable toggle" feels natural). Persisted to `stations.cover_art_source` and round-tripped by `settings_export.py`.

### Match acceptance — when an MB result is good enough to show

- **D-07: ICY must contain `" - "` to qualify for MB.** Split into `artist` and `recording` parts. Bare-title ICY strings (e.g. SomaFM tracks that emit just the song name) **skip MB entirely** and fall through to the station-logo placeholder when iTunes also misses (or in MB-only mode, immediately).
- **D-08: Query shape.** MB recording search using a Lucene-style query: `artist:"<artist>" AND recording:"<title>"`. URL: `https://musicbrainz.org/ws/2/recording/?query=<encoded>&fmt=json&limit=5`. (Pull a few results so D-09 can filter; planner picks `limit` value within that bound.)
- **D-09: Accept threshold.** Accept the first recording whose MB-reported `score` is **≥ 80**. Reject everything below. If no recording in the top results clears 80, the lookup is a miss (no fallback to a lower bar).
- **D-10: Release selection.** From the accepted recording's `releases[]`:
  1. Prefer `status == "Official"` AND `release-group.primary-type == "Album"`, earliest `date` first.
  2. Fall back to any `status == "Official"` release.

  (Step 3 — any release with CAA art on HEAD probe — deferred per user decision 2026-05-13; see Deferred Ideas.)
- **D-11: Cover Art Archive endpoint.** Once a release MBID is chosen, fetch `https://coverartarchive.org/release/<mbid>/front`. Image-size variant is planner's discretion (250 / 500 / 1200) — current cover slot is 160×160 in `now_playing_panel.py` so 250 or 500 is sufficient; bias toward the smallest variant that still scales cleanly.

### Caching & rate-limit behavior

- **D-12: No caching this phase.** No in-memory dict, no SQLite cache, no on-disk image cache. Every ICY-title change that doesn't get short-circuited (by D-07 or routing) hits the network. Defer caching to a future phase (see Deferred Ideas).
- **D-13: Rate limit via latest-wins queue, max 1 in-flight + 1 queued.** MB calls are serialized through a 1-req/sec gate. When a new ICY arrives while an MB call is in-flight, replace any *queued* call with the new query; the in-flight call continues but its result is dropped by the existing token guard at the Qt slot (`now_playing_panel.py:1189` — `_cover_fetch_token`). Net effect: at most one wasted MB call per skip burst.
- **D-14: Gate enforcement.** Planner's discretion on the mechanism (`time.monotonic()` floor in the worker, a `threading.Semaphore` with a sleep, or a single-slot queue). Whatever ships must guarantee MB sees ≤ 1 request per second over any 1-second window — including across station changes.

### Genre handoff on MB-source path

- **D-15: MB tags first, empty fallback.** When MB is the art source, populate `last_itunes_result['genre']` from MB's recording or release-group tags — pick the **highest-count** tag (most-voted by MB users). If MB returns no tags, leave genre as `""`.
- **D-16: No iTunes-for-genre-only call in MB-only mode.** Honor the user's `MB-only` choice strictly — don't sneak in a side iTunes call.
- **D-17: In Auto mode, the genre source matches the art source.** If iTunes wins (returns a result that's accepted), genre comes from iTunes' `primaryGenreName` (today's behavior, unchanged). If iTunes misses and MB wins the fallback, genre comes from MB tags per D-15.

### MB protocol compliance (locked by phase title — listed for downstream visibility)

- **D-18: User-Agent.** Exact string: `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)`. `<version>` is read from `importlib.metadata` (consistent with VER-02 / hamburger version line). Set on **both** the MB API request and the CAA image request.
- **D-19: 1 req/sec applies to MB API only, not CAA.** The 1/sec ceiling is for `musicbrainz.org/ws/2/*`. The `coverartarchive.org` host is a separate service with no published 1/sec limit; treat its calls as part of the same logical "MB lookup" pipeline for token-guard purposes but they do not have to share the MB gate.
- **D-20: Failure handling.** Network error, HTTP 503/429, JSON parse error, or any unexpected condition → log + fall through to station-logo placeholder. Never raise out of the worker. Mirrors the existing iTunes path (`cover_art.py:98` — bare `except Exception`).

### Claude's Discretion

- Schema migration shape — new column on `stations` table with `DEFAULT 'auto'`, or a small lookup table. Planner picks.
- `cover_art.py` refactor — keep one big function vs. split into `cover_art_itunes.py` + `cover_art_musicbrainz.py` + a small router. Planner picks; prefer reuse of existing worker-thread + callback shape over a wholesale rewrite.
- Whether to add a unit-test fixture for MB JSON responses (likely yes — see TESTING.md patterns).
- CAA image size variant (250 vs 500 vs 1200) — pick the smallest that scales cleanly to 160×160 on standard DPR=1.0 (deployment target).
- Whether the EditStationDialog selector is a `QComboBox` vs three radio buttons — match whatever the dialog's existing layout idiom uses.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone

- `.planning/PROJECT.md` — current state, stack (PySide6 + GStreamer + SQLite + urllib), current iTunes pipeline. Read the "Cover art" line specifically.
- `.planning/REQUIREMENTS.md` — note the v2.1 "Out of Scope" line *"MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found"*. This phase is the revisit; gaps were found.
- `.planning/notes/2026-04-03-station-art-fetching-beyond-youtube.md` — parent note (ART-04) describing the broader station-art expansion. Phase 73 is a strict subset focused on track-level (ICY-driven) art only, not station-logo art.

### Codebase maps

- `.planning/codebase/STRUCTURE.md` — module boundaries; confirms `cover_art.py` is the right home.
- `.planning/codebase/INTEGRATIONS.md` — existing external HTTP services.
- `.planning/codebase/CONVENTIONS.md` — worker-thread + Qt-queued signal pattern.

### MusicBrainz / Cover Art Archive (external, planner to fetch via WebFetch)

- `https://musicbrainz.org/doc/MusicBrainz_API` — REST API, query syntax, rate-limit policy.
- `https://musicbrainz.org/doc/MusicBrainz_API/Search` — Lucene query syntax for `recording`.
- `https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting` — confirms 1 req/sec for the public endpoint, requires User-Agent.
- `https://musicbrainz.org/doc/Cover_Art_Archive/API` — image variant endpoints (`/front`, `/front-250`, `/front-500`, `/front-1200`).

### Source files (read before planning)

- `musicstreamer/cover_art.py` — current iTunes-only implementation; established worker shape.
- `musicstreamer/ui_qt/now_playing_panel.py:1176-1212` — `_fetch_cover_art_async`, `_on_cover_art_ready`, `_set_cover_pixmap`. Token-guard pattern lives here.
- `musicstreamer/ui_qt/now_playing_panel.py:825-883` — `on_title_changed` integration site.
- `musicstreamer/models.py` — `Station` dataclass (where `cover_art_source` will live).
- `musicstreamer/repo.py:421-461` — settings + favorites flow; `last_itunes_result['genre']` consumer side.
- `musicstreamer/settings_export.py:142,462` — favorites round-trip; new station field must round-trip too.
- `musicstreamer/migration.py` — schema-bump precedent.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`fetch_cover_art(icy_string, callback)`** (`cover_art.py:67`) — the worker-thread shape (urlopen on background thread, callback marshalled to Qt main via a Signal) is the model; MB path should reuse it rather than invent a new async story.
- **`is_junk_title()`** (`cover_art.py:17`) — applies to MB path too. Same junk gate, same skip.
- **`_cover_fetch_token` + `cover_art_ready` Signal** (`now_playing_panel.py:1176-1198`) — stale-response token guard. Already handles "newer fetch supersedes older" — D-13 leverages this directly.
- **`last_itunes_result` module global** (`cover_art.py:37`) — already the genre handoff channel. Rename optional but the surface (a dict with `artwork_url` + `genre`) is the right shape for both sources.

### Established Patterns

- **No-deps HTTP** — `urllib.request.urlopen` with explicit `timeout=5`. MB calls follow suit.
- **Bare `except Exception` in workers, callback(None) on failure** (`cover_art.py:98`). MB worker mirrors this.
- **Token-guard stale-response discard at Qt slot** (`now_playing_panel.py:1189-1198`). MB result passes through the same slot.
- **Settings export/import round-trip** for any new station field (`settings_export.py`).
- **Schema migration via `migration.py`** — established precedent for adding a column (see `siblings` join-table, `cover_art_source` and others added in prior phases).

### Integration Points

- New field `Station.cover_art_source: Literal["auto","itunes_only","mb_only"] = "auto"` (models.py).
- New SQLite column on `stations` table (migration.py).
- New `repo.update_station_cover_art_source(station_id, mode)` (or fold into existing update path).
- New row/section in `EditStationDialog`.
- `cover_art.fetch_cover_art()` accepts an additional `source: str` parameter (or routes via a small wrapper).
- `now_playing_panel._fetch_cover_art_async()` passes `self._station.cover_art_source` through.
- `settings_export` serializes the new field; import preserves it (default to `"auto"` if absent for older ZIPs).

### Threading note (carry forward from Phase 70 incident)

Per the memory `feedback_gstreamer_mock_blind_spot.md`: pipeline mocks can pass through any signal call. Not directly applicable here (no GStreamer in this phase), but the broader lesson — **add source-level grep tests for protocol-required strings** — applies: a test should assert the User-Agent header literal contains both `MusicStreamer/` and `https://github.com/lightningjim/MusicStreamer`, and the rate gate has an actual time-keeping mechanism (not just a comment).

</code_context>

<specifics>
## Specific Ideas

- **User-Agent contact: GitHub URL, not email.** `https://github.com/lightningjim/MusicStreamer`. Privacy-conscious choice (see `project_publishing_history.md` memory — the user has previously scrubbed sensitive data from git history).
- **"Strict matching"** in the phase title is realized concretely by D-07 + D-09 + D-10 — three independent gates: (1) artist+title shape required, (2) MB score ≥ 80, (3) prefer original-album releases over compilations.
- **REQUIREMENTS.md OoS line reversal.** The original v2.1 OoS line said *"MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found"*. This phase **is** the revisit. The OoS line should be removed (or rewritten) as part of phase completion — flag for the planner.

</specifics>

<deferred>
## Deferred Ideas

- **D-10 step 3 (CAA art existence probe on any release)** — deferred 2026-05-13. RESEARCH OQ-1 rationale: D-10 steps 1+2 cover the common case; releases without CAA art fall through to station-logo placeholder cleanly. Re-open if real-world usage shows frequent "official-album-has-no-CAA-art" cases.
- **Cover-art caching** (in-memory dict + persistent SQLite + on-disk image cache, negative caching for misses, TTL'd hits). Strong UX win on rapid channel-surfing and repeat tracks across sessions, but explicit out-of-scope for Phase 73 to keep the surface tight. Re-open as a future phase if Kyle hits the 1-req/sec gate visibly.
- **Global cover-art-source toggle in hamburger menu.** Per-station is the chosen scope. A global "set all stations to MB-only" power-user knob could ship later, alongside a bulk-edit dialog.
- **Editing favorites' genre after-the-fact** (e.g. when a track is re-encountered and the new source provides a different genre). Phase 73 writes genre to favorites at star-time and leaves it; not retroactively updated.
- **AudioAddict / ICY-metadata / favicon station-art fetching** — covered by the broader `2026-04-03-station-art-fetching-beyond-youtube.md` note (ART-04). Different problem (station-logo art, not track art). Future phase.
- **MB tag → genre normalization** (e.g. mapping "alt-rock" → "Alternative Rock"). For now, raw MB tag string is written verbatim. Polish later if it bothers the user.
- **CAA image-size selection as a setting.** Hardcoded for now (planner's discretion D-11). Could become a setting if HiDPI displays land.

</deferred>

---

*Phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-*
*Context gathered: 2026-05-13*

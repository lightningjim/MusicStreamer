# Phase 73: MusicBrainz album-cover lookup — Research

**Researched:** 2026-05-13
**Domain:** External HTTP API integration (MusicBrainz + Cover Art Archive), Qt worker-thread refactor, SQLite schema migration, settings round-trip
**Confidence:** HIGH (MB+CAA API shape live-verified; threading patterns are project-canonical from prior phases)

## Summary

Phase 73 wires MusicBrainz `/ws/2/recording/?query=` + Cover Art Archive `/release/<mbid>/front-<size>` into `musicstreamer/cover_art.py` as an **additive** lookup path that runs only when the per-station `cover_art_source` field selects it. The architecture is dominated by four constraints already locked in CONTEXT.md (D-13/D-14 rate gate, D-18 User-Agent, D-09 score ≥ 80, D-10 Official+Album+earliest release selection); the research below confirms each constraint is implementable on the project's existing stack with **zero new third-party dependencies** — `urllib.request`, `json`, `threading`, `time.monotonic` are sufficient.

The biggest surprise from live API probes: **score = 100 is NOT a quality signal** — every top-5 recording for "Hey Jude" / "Karma Police" returns score=100, including bootlegs and live recordings. D-10's release-selection ladder is the real filter. Also, `tags` ARE returned in the recording search response by default (no `inc=` parameter required), and `releases[].date` can be `None`, `""`, `"YYYY"`, `"YYYY-MM"`, or `"YYYY-MM-DD"` — date sorting must handle all five.

**Primary recommendation:** Extract MB/CAA logic into a new `musicstreamer/cover_art_mb.py` module that exposes a single `fetch_mb_cover(artist, title, callback)` entry point. Keep `cover_art.py` as the router with a single source-aware `fetch_cover_art(icy_string, source, callback)` signature. Replace the per-request `threading.Thread` daemons with one module-level worker holding a `time.monotonic()` floor for D-14, and a 1-slot replaceable queue for D-13 latest-wins behavior. All seven validation surfaces below are achievable with deterministic mocks — no live HTTP needed in tests.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Routing — when MB gets called**
- **D-01: Per-station selector with 3 modes.** A new `cover_art_source` field on each station: `Auto` (default), `iTunes-only`, `MB-only`. No global toggle.
- **D-02: `Auto` semantics.** Try iTunes first. If iTunes returns no result (or the result is rejected as junk), try MB. If both miss, fall through to the station-logo placeholder (existing behavior).
- **D-03: `iTunes-only` semantics.** Legacy behavior — never call MB. Iceberg-clean: lets the user keep the historic path for stations that have always worked well via iTunes.
- **D-04: `MB-only` semantics.** Never call iTunes. Skip the iTunes network call entirely (do **not** call iTunes solely for genre — see D-13).
- **D-05: Default for new and existing stations is `Auto`.** Migration backfills every existing row with `Auto`; new stations get `Auto` at insert time. Zero-config improvement for the whole library.
- **D-06: Selector placement.** EditStationDialog — exact section/row is planner's discretion (close to the existing per-station "ICY disable toggle" feels natural). Persisted to `stations.cover_art_source` and round-tripped by `settings_export.py`.

**Match acceptance — when an MB result is good enough to show**
- **D-07: ICY must contain `" - "` to qualify for MB.** Split into `artist` and `recording` parts. Bare-title ICY strings (e.g. SomaFM tracks that emit just the song name) **skip MB entirely** and fall through to the station-logo placeholder when iTunes also misses (or in MB-only mode, immediately).
- **D-08: Query shape.** MB recording search using a Lucene-style query: `artist:"<artist>" AND recording:"<title>"`. URL: `https://musicbrainz.org/ws/2/recording/?query=<encoded>&fmt=json&limit=5`. (Pull a few results so D-09 can filter; planner picks `limit` value within that bound.)
- **D-09: Accept threshold.** Accept the first recording whose MB-reported `score` is **≥ 80**. Reject everything below. If no recording in the top results clears 80, the lookup is a miss (no fallback to a lower bar).
- **D-10: Release selection.** From the accepted recording's `releases[]`:
  1. Prefer `status == "Official"` AND `release-group.primary-type == "Album"`, earliest `date` first.
  2. Fall back to any `status == "Official"` release.
  3. Fall back to any release that has cover art on CAA (`HEAD https://coverartarchive.org/release/<mbid>/front` → 200).
- **D-11: Cover Art Archive endpoint.** Once a release MBID is chosen, fetch `https://coverartarchive.org/release/<mbid>/front`. Image-size variant is planner's discretion (250 / 500 / 1200) — current cover slot is 160×160 in `now_playing_panel.py` so 250 or 500 is sufficient; bias toward the smallest variant that still scales cleanly.

**Caching & rate-limit behavior**
- **D-12: No caching this phase.** No in-memory dict, no SQLite cache, no on-disk image cache. Every ICY-title change that doesn't get short-circuited (by D-07 or routing) hits the network. Defer caching to a future phase.
- **D-13: Rate limit via latest-wins queue, max 1 in-flight + 1 queued.** MB calls are serialized through a 1-req/sec gate. When a new ICY arrives while an MB call is in-flight, replace any *queued* call with the new query; the in-flight call continues but its result is dropped by the existing token guard at the Qt slot (`now_playing_panel.py:1189` — `_cover_fetch_token`). Net effect: at most one wasted MB call per skip burst.
- **D-14: Gate enforcement.** Planner's discretion on the mechanism (`time.monotonic()` floor in the worker, a `threading.Semaphore` with a sleep, or a single-slot queue). Whatever ships must guarantee MB sees ≤ 1 request per second over any 1-second window — including across station changes.

**Genre handoff on MB-source path**
- **D-15: MB tags first, empty fallback.** When MB is the art source, populate `last_itunes_result['genre']` from MB's recording or release-group tags — pick the **highest-count** tag (most-voted by MB users). If MB returns no tags, leave genre as `""`.
- **D-16: No iTunes-for-genre-only call in MB-only mode.** Honor the user's `MB-only` choice strictly — don't sneak in a side iTunes call.
- **D-17: In Auto mode, the genre source matches the art source.** If iTunes wins (returns a result that's accepted), genre comes from iTunes' `primaryGenreName` (today's behavior, unchanged). If iTunes misses and MB wins the fallback, genre comes from MB tags per D-15.

**MB protocol compliance**
- **D-18: User-Agent.** Exact string: `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)`. `<version>` is read from `importlib.metadata` (consistent with VER-02 / hamburger version line). Set on **both** the MB API request and the CAA image request.
- **D-19: 1 req/sec applies to MB API only, not CAA.** The 1/sec ceiling is for `musicbrainz.org/ws/2/*`. The `coverartarchive.org` host is a separate service with no published 1/sec limit; treat its calls as part of the same logical "MB lookup" pipeline for token-guard purposes but they do not have to share the MB gate.
- **D-20: Failure handling.** Network error, HTTP 503/429, JSON parse error, or any unexpected condition → log + fall through to station-logo placeholder. Never raise out of the worker. Mirrors the existing iTunes path (`cover_art.py:98` — bare `except Exception`).

### Claude's Discretion

- Schema migration shape — new column on `stations` table with `DEFAULT 'auto'`, or a small lookup table. Planner picks.
- `cover_art.py` refactor — keep one big function vs. split into `cover_art_itunes.py` + `cover_art_musicbrainz.py` + a small router. Planner picks; prefer reuse of existing worker-thread + callback shape over a wholesale rewrite.
- Whether to add a unit-test fixture for MB JSON responses (likely yes — see TESTING.md patterns).
- CAA image size variant (250 vs 500 vs 1200) — pick the smallest that scales cleanly to 160×160 on standard DPR=1.0 (deployment target).
- Whether the EditStationDialog selector is a `QComboBox` vs three radio buttons — match whatever the dialog's existing layout idiom uses.

### Deferred Ideas (OUT OF SCOPE)

- **Cover-art caching** (in-memory dict + persistent SQLite + on-disk image cache, negative caching for misses, TTL'd hits).
- **Global cover-art-source toggle in hamburger menu.** Per-station is the chosen scope.
- **Editing favorites' genre after-the-fact.**
- **AudioAddict / ICY-metadata / favicon station-art fetching** — covered by ART-04 in a separate phase.
- **MB tag → genre normalization** (e.g. mapping "alt-rock" → "Alternative Rock"). Raw MB tag string written verbatim.
- **CAA image-size selection as a setting.** Hardcoded for now.
</user_constraints>

## Project Constraints (from CLAUDE.md)

- **Routing skill:** `Skill("spike-findings-musicstreamer")` should be loaded by any task touching Windows packaging / GStreamer / PyInstaller / Qt-GLib bus threading. Phase 73 does NOT touch GStreamer or bus threading, but **Qt worker-thread cross-thread signal delivery** is in scope (see Pitfall 5 below). [VERIFIED: `./CLAUDE.md` + `.claude/skills/spike-findings-musicstreamer/SKILL.md`]
- **Deployment target:** Linux Wayland, DPR=1.0 — no fractional scaling. CAA image size 250 is sufficient for a 160×160 slot. [VERIFIED: user memory `project_deployment_target.md`]
- **Mirror "X" decisions must cite source:** Any CONTEXT.md claim about MB / CAA behavior in this RESEARCH.md must quote the doc with a permalink, not paraphrase. [VERIFIED: user memory `feedback_mirror_decisions_cite_source.md`] — applied throughout Sources section.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-station preference storage | SQLite (Repo) | settings_export ZIP | New `stations.cover_art_source` column joins existing schema; export ZIP round-trip mirrors existing `icy_disabled` precedent |
| Preference UI | EditStationDialog (Qt Widgets) | — | Same dialog as `icy_disabled` toggle; matches D-06 |
| Cover-art lookup orchestration | Pure-Python module (`cover_art.py` router) | — | No Qt dependency in the routing layer; matches existing worker-thread + callback pattern |
| iTunes HTTP call | `cover_art.py` worker thread (existing) | — | Untouched — `_build_itunes_query` + `_parse_itunes_result` already work |
| MB HTTP call | New worker-thread module-level singleton | — | Must enforce 1-req/sec gate ACROSS station changes — per-call `threading.Thread` cannot share state cleanly; one persistent gate object is the right shape |
| CAA HTTP call | Same MB worker thread (sequential) | — | Per D-19 not rate-gated separately, but logically part of the MB pipeline; share token guard at Qt slot |
| Cross-thread signal delivery | Qt `Signal.emit` (existing pattern) | — | `cover_art_ready` signal at `now_playing_panel.py:1180`; payload may need to widen (see Open Question 3) |
| Genre handoff to favorites | `last_itunes_result` module dict (existing) | — | Already the channel; semantically rename optional per CONTEXT D-15 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` | stdlib (3.10+) | HTTP GET to MB + CAA | Project-wide convention — no `requests` dep [VERIFIED: `INTEGRATIONS.md`:6] |
| `json` | stdlib | Parse MB JSON response | Project-wide convention |
| `threading` | stdlib | Worker thread + gate primitives (`Lock`, `Event`) | Existing `cover_art.py:101` pattern + canonical Qt-GLib bridging |
| `time.monotonic` | stdlib | 1-req/sec floor; immune to wall-clock jumps | Project-canonical for cooldowns — used by Phase 62 `_BufferUnderrunTracker` [VERIFIED: `STATE.md` Phase 62-03 entry] |
| `importlib.metadata.version` | stdlib | Read `2.1.NN` from pyproject for User-Agent | Project-canonical for VER-02 [VERIFIED: `musicstreamer/__main__.py:9`, `musicstreamer/ui_qt/main_window.py:25`] |
| `urllib.parse.quote` | stdlib | URL-encode Lucene query | Standard |
| `PySide6.QtCore.Signal` | 6.10+ | Cross-thread result delivery to Qt main | Existing `cover_art_ready` Signal at `now_playing_panel.py:1180` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tempfile.NamedTemporaryFile` | stdlib | Materialize CAA image bytes to a file path for `QPixmap` | Mirror existing iTunes pattern at `cover_art.py:94` |
| `unittest.mock.patch` / `MagicMock` | stdlib | Mock `urllib.request.urlopen` + `time.monotonic` in tests | Project-canonical [VERIFIED: `TESTING.md` line 132+] |
| pytest-qt `qtbot` | 4+ | Drive Qt widget tests | Existing pattern [VERIFIED: `tests/test_now_playing_panel.py`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `time.monotonic` floor | `threading.Semaphore` with `time.sleep` | Sleep blocks the worker thread for up to 1s — fine in a daemon, but blocks teardown on QApplication exit unless paired with an interrupt event. Floor + opportunistic-sleep is simpler and matches Phase 62 idiom. |
| Per-request `threading.Thread` (current iTunes pattern) | Persistent worker thread with `queue.Queue` | Per-request is fine for iTunes (stateless) but the MB gate needs to share `_next_allowed_at` state across calls — leaking timers between threads is ugly. **Persistent worker** is cleaner for MB; **keep per-request thread for iTunes** to minimize churn. |
| `python-musicbrainzngs` package | — | Adds a third-party dep for ~50 lines of code we'd write anyway. The project's "no extra deps for HTTP" convention (`PROJECT.md` Key Decisions table line: *"urllib over requests for iTunes fetch"*) argues against. Also: `musicbrainzngs` has a documented 50-req/sec User-Agent throttle penalty for known bot UAs ([CITED](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting)) — staying out of its UA reputation is safer. |
| `inc=tags+release-groups` query parameter | — | **No-op on search endpoint.** Live probe confirmed `inc=` is silently ignored on `/recording/?query=` — only affects `/recording/{mbid}?inc=...` lookup. Tags + release-groups are already in the search response. [VERIFIED: live curl probe 2026-05-13] |

**Installation:** No new dependencies. All required modules ship with Python 3.10+ stdlib or PySide6 (already in `pyproject.toml`). [VERIFIED: `pyproject.toml`]

**Version verification:**
- `urllib.request` follows 307 redirects automatically via `HTTPRedirectHandler`. [VERIFIED: Python 3.14 docs + Python 3.10+ behavior; live probe with curl showed `Location:` header on 307, urllib follows by default]
- `importlib.metadata.version('musicstreamer')` returns `"2.1.72"` today. [VERIFIED: `pyproject.toml:7`]

## Architecture Patterns

### System Architecture Diagram

```
ICY title arrives at NowPlayingPanel.on_title_changed
  │
  ▼
[gate 1: icy_disabled?] ── true ──► (no-op, station name only)
  │ false
  ▼
[gate 2: is_junk_title?] ── true ──► (no-op)
  │ false
  ▼
[gate 3: bridge_window for GBS?] ── true ──► (suppress, /ajax will fire later)
  │ false
  ▼
[gate 4: cover_fetch_token bump + dedup _last_cover_icy]
  │
  ▼
_fetch_cover_art_async(title, station.cover_art_source)        [Qt main thread]
  │
  ▼
cover_art.fetch_cover_art(icy, source, callback)               [router; dispatches per source]
  │
  ├── source == "itunes_only"  ──► [iTunes worker thread (existing)]
  │                                  │ urlopen(itunes_url, UA, timeout=5)
  │                                  │ parse → artwork_url | None
  │                                  │ if hit: fetch image → temp file path
  │                                  ▼
  │                                  callback(path | None)
  │
  ├── source == "mb_only"      ──► [MB pipeline (NEW)]
  │                                  │ gate 5: " - " in icy? — else miss
  │                                  │ split artist / title
  │                                  │
  │                                  ▼
  │                                  [MBQueue: latest-wins, 1 in-flight + 1 queued]
  │                                  │ ── (replace queued if exists)
  │                                  ▼
  │                                  [MBWorker thread, time.monotonic gate]
  │                                  │ sleep until next_allowed_at if needed
  │                                  │ urlopen MB search (UA, fmt=json, limit=5)
  │                                  │ update next_allowed_at = monotonic() + 1.0
  │                                  │ parse JSON → recordings[]
  │                                  │ filter score >= 80
  │                                  │ sort by first-release-date ASC
  │                                  │ pick first recording
  │                                  │ within releases[]: ladder (D-10)
  │                                  │ derive tags → genre (highest count)
  │                                  │
  │                                  ▼
  │                                  CAA: urlopen front-250 (UA, follows 307)
  │                                       (no rate gate — D-19)
  │                                  write bytes → temp file
  │                                  ▼
  │                                  set last_itunes_result = {artwork_url, genre}
  │                                  callback(path | None)
  │
  └── source == "auto"         ──► iTunes first; on miss, MB (both above flows)
       │
       ▼
       callback(path | None)
       │
       ▼ Qt Signal cover_art_ready.emit(f"{token}:{path}")  [worker thread → Qt main]
                  │
                  ▼ _on_cover_art_ready (Qt slot, queued connection)
                  │   discard if token != _cover_fetch_token  (stale)
                  │   else: setPixmap or show station_logo
```

### Recommended Project Structure

```
musicstreamer/
├── cover_art.py             # ROUTER (mostly existing — adds source dispatch)
├── cover_art_mb.py          # NEW: MB + CAA pipeline + rate gate
├── models.py                # ADD: Station.cover_art_source field
├── repo.py                  # ADD: ALTER TABLE migration + accessor methods
├── settings_export.py       # ADD: serialize/deserialize cover_art_source
└── ui_qt/
    ├── edit_station_dialog.py    # ADD: QComboBox selector
    └── now_playing_panel.py      # MODIFY: pass station.cover_art_source through
```

### Pattern 1: Persistent worker with monotonic-floor gate
**What:** A module-level worker thread holds `_next_allowed_at` state; before each MB call it sleeps until `time.monotonic() >= _next_allowed_at`, then performs the call and writes back `_next_allowed_at = time.monotonic() + 1.0`.

**When to use:** Whenever a rate gate must survive across **independent** caller events (here, station changes that don't share a Python object).

**Example (sketch):**
```python
# Source: project pattern, mirrors Phase 62 _BufferUnderrunTracker monotonic discipline
# (musicstreamer/player.py — _close_with_now helper)
import threading, time, queue

class _MbGate:
    """1-req/sec gate for musicbrainz.org/ws/2/* (D-13/D-14/D-19)."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0   # time.monotonic()

    def wait_then_mark(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed_at:
                time.sleep(self._next_allowed_at - now)
            self._next_allowed_at = time.monotonic() + 1.0
```

### Pattern 2: Single-slot replaceable queue (latest-wins)
**What:** `queue.Queue(maxsize=1)` with a custom `put_replace` helper that drains the existing item before putting the new one. Worker pulls forever; superseded items vanish before they reach the worker.

**When to use:** Per D-13, when rapid ICY changes burst in, we want at most ONE pending MB call (the newest). The currently-in-flight call cannot be cancelled (urllib has no async cancel), but its result is discarded by `_cover_fetch_token` at the Qt slot.

**Example:**
```python
# Source: standard Python idiom; matches D-13 latest-wins semantic
import queue

_pending: queue.Queue = queue.Queue(maxsize=1)

def submit(job):
    try:
        _pending.get_nowait()  # drop any superseded queued job
    except queue.Empty:
        pass
    _pending.put_nowait(job)
```

### Pattern 3: Bound-method Signal emit + token-pack payload
**What:** Worker invokes `cover_art_ready.emit(f"{token}:{path}")` — the existing scheme at `now_playing_panel.py:1185`. Token guards stale responses; payload is a single string (Qt cross-thread signals work best with primitives).

**When to use:** Crossing a non-QThread → Qt main thread. Direct widget access from the worker is unsafe.

**Important caveat:** Phase 43.1 PROJECT.md decision logged at `STATE.md` Phase 43.1 cross-OS regression entry: *"`QTimer.singleShot(0, callable)` from a non-`QThread` (GStreamer bus-loop thread) silently drops"*. The same rule applies here: the cover-art worker is a raw `threading.Thread`, NOT a `QThread`. Cross-thread work MUST go through a queued `Signal`. `cover_art_ready` is a `Signal(str)` connected via auto-queued connection — this is the established pattern.

### Anti-Patterns to Avoid

- **`QTimer.singleShot(0, ...)` from the MB worker thread:** Silently drops. Use `Signal.emit(...)` instead. [VERIFIED: `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md`]
- **Per-request `threading.Thread` for MB calls:** Cannot share `_next_allowed_at` across calls — leaks state if cached at module level, races if not.
- **Sleeping with the lock held:** The naive `with lock: time.sleep(...)` pattern serializes ALL callers including the one that's about to drop its result. Acceptable for a 1-second sleep on a daemon thread, but the persistent-worker pattern above avoids the issue entirely — only the worker thread sleeps.
- **`requests` library:** Project convention is stdlib urllib; adding `requests` here would be the first such import for MS-the-app. [VERIFIED: `PROJECT.md` Key Decisions]
- **Trusting `score == 100` as a quality signal:** Top-5 MB recordings often ALL have score=100. The release-status ladder (D-10) is the real filter.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL encoding | Manual `%xx` escaping | `urllib.parse.quote(query, safe='')` | Handles all RFC 3986 reserved chars; `quote_plus` for form encoding |
| 307 redirect chase from CAA | Manual `urllib.request.Request` + parsing `Location` header | Default `urlopen` follows | `urllib.request.HTTPRedirectHandler` is wired into the default opener and follows 307s on GET. [VERIFIED: stdlib docs + live test] |
| Lucene-style query syntax | Don't compose ad-hoc with f-strings | Write a single `_escape_lucene` helper + tested fixtures | The 13 special chars (`+ - && \|\| ! ( ) { } [ ] ^ " ~ * ? : \\ /`) MUST be backslash-escaped. Bare apostrophes, accented chars, ampersands in titles will silently miss without it. [CITED: https://lucene.apache.org/core/4_0_0/queryparser/org/apache/lucene/queryparser/classic/package-summary.html] |
| JSON parsing edge cases | Don't use `try: data[k] except KeyError` everywhere | `data.get(k, default)` with explicit defaults | MB sometimes omits fields entirely (e.g., `tags` absent on recordings with no community tags — confirmed in live probe rec[0,1,2] of "Karma Police") |
| Date sorting with partial dates | Don't write a custom partial-date class | Use `(date or "9999")` as sort key with string compare | YYYY-MM-DD, YYYY-MM, YYYY all sort correctly as strings (lexicographic == chronological). Missing dates sort last via the "9999" sentinel. [VERIFIED: lexicographic property of ISO 8601 + live probe showed `date` values are always ISO-prefixed strings] |
| Version-pinning the User-Agent | Don't hardcode `2.1.72` | `importlib.metadata.version('musicstreamer')` | The existing VER-02 convention (Phase 65) auto-bumps via PreToolUse hook on phase-complete commits. Hardcoding would drift. [VERIFIED: `STATE.md` Phase 63 entries] |

**Key insight:** Every external HTTP integration in this codebase already uses these patterns (radio-browser.py, aa_import, iTunes). Phase 73's job is to MATCH, not reinvent.

## Runtime State Inventory

> Phase 73 is **additive** (new field + new code path), not a rename/migration. The closest "runtime state" question is the schema migration.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | The new `cover_art_source` column added to existing rows via ALTER TABLE; default value `'auto'` MUST backfill so existing stations get the new Auto behavior immediately. | Idempotent ALTER TABLE in `repo.db_init()` mirroring the `icy_disabled` precedent (`repo.py:79`). |
| Live service config | None — no external service config carries the renamed thing. The User-Agent string DOES include the app version, so a stale `2.0` literal in `gbs_api.py:77` is unrelated drift (out of scope for Phase 73). | None for Phase 73. |
| OS-registered state | None. | None. |
| Secrets/env vars | None — MB and CAA both unauthenticated. | None. |
| Build artifacts | None — pure Python additive code. PyInstaller spec untouched. | None. |

**Nothing found in category:** Verified by grepping `cover_art_source` across the codebase — net-new identifier.

## Common Pitfalls

### Pitfall 1: Score ≥ 80 is not enough — release-status ladder is the load-bearing filter
**What goes wrong:** Live probe of "Hey Jude" by The Beatles returns top-5 recordings ALL with score=100, but recordings 0–4 are bootleg/live releases. The canonical 1968 Beatles single is **rec[15]** in `limit=25` results. Filtering by score alone returns bootleg cover art.
**Why it happens:** MB's `score` reflects string-similarity, not "canonical-ness" or popularity.
**How to avoid:** Sort recordings by `first-release-date` ascending (earliest = original), THEN apply the release-status ladder. The canonical single will have `first-release-date='1968-08-26'` for Hey Jude; bootlegs typically have None or modern dates.
**Warning signs:** Test fixture must include "Hey Jude" or similar where top-5 are bootlegs — the implementation that just picks `recordings[0]` will fail this fixture.

### Pitfall 2: `releases[].date` heterogeneity (None, "", "YYYY", "YYYY-MM", "YYYY-MM-DD")
**What goes wrong:** Naive `sorted(releases, key=lambda r: r['date'])` raises `TypeError: '<' not supported between str and NoneType` or sorts empty strings first.
**Why it happens:** MB stores release dates with varying precision based on what's been entered. Live probes confirmed `None`, `''`, `'2007'`, `'2007-11-19'` all appear in the same `releases[]` array.
**How to avoid:** Sort with `key=lambda r: r.get('date') or '9999'`. Lexicographic order of ISO 8601 prefix-strings IS chronological order (`'1968-08-26' < '1968-09' < '1969'`). The `'9999'` sentinel pushes unknown-date releases to the end.
**Warning signs:** Test fixture with mixed date precisions; sort assertion checks "1968 release wins over None release".

### Pitfall 3: `tags` may be absent entirely from the recording dict
**What goes wrong:** `recording['tags']` raises `KeyError` if no community tag exists. Live probe of Radiohead "Karma Police" rec[4] had `tags=[...]` but rec[0..3] had no `tags` key at all.
**Why it happens:** MB only includes the `tags` key when at least one user-tag exists.
**How to avoid:** `recording.get('tags', [])` with explicit default. Then handle the empty-list case per D-15.

### Pitfall 4: Trusting CAA 200 from a HEAD request
**What goes wrong:** D-10 step 3 says "any release that has cover art on CAA (HEAD ... → 200)". Live probe shows CAA returns **307** (not 200) when art exists, with `Location:` pointing to archive.org. A naive `urlopen(method='HEAD')` follows the redirect and may return the final archive.org 200, but **`urllib.request.urlopen` with the default opener strips the body on HEAD — and some versions raise on HEAD method.** Easier: just do `GET front-250` and check status.
**Why it happens:** CAA is a redirect-only service; the actual bytes live on archive.org's CDN.
**How to avoid:** Use `urlopen(Request(url, headers={'User-Agent': UA}))` — GET, follow redirects (default), check `resp.status == 200`. For the D-10 step-3 existence-only check, the planner can either do a GET-and-discard or skip step 3 entirely (it's a fallback to fallback; many recordings without an Official release also won't have CAA art).

### Pitfall 5: Worker thread is a raw `threading.Thread`, NOT a `QThread`
**What goes wrong:** `QTimer.singleShot(0, callable)` from a raw threading.Thread silently drops — there's no Qt event loop on that thread to dispatch the timer. This is the Phase 43.1 lesson documented in `STATE.md`.
**Why it happens:** Qt's timer/event mechanism is bound to QThread or the main thread's event loop. Non-Qt threads have no thread-default loop.
**How to avoid:** Cross-thread work MUST go through a queued `Signal`. The existing `cover_art_ready = Signal(str)` IS the right pattern. Phase 73 should NOT introduce QTimer.singleShot from the worker for any reason (including "deferring to main thread for X").

### Pitfall 6: User-Agent header case sensitivity
**What goes wrong:** Python's `urllib.request.Request(headers={...})` normalizes header names — Python 3.x stores as `User-agent` (capital U, lowercase agent). Wire format is fine (HTTP headers are case-insensitive), BUT test assertions like `req.headers['User-Agent']` will return `None`.
**Why it happens:** urllib's `Request` class title-cases the first letter and lowercases the rest of header names internally.
**How to avoid:** Test assertions should use `req.get_header('User-agent')` or `req.headers.get('User-agent')`. Or test the wire form by mocking `urlopen` and inspecting the `Request` object passed in.

### Pitfall 7: MB 503 vs 429
**What goes wrong:** Spec wording suggests "rate-limit returns 429" (common convention). Live MB docs say **503 Service Unavailable** with body referencing rate limit.
**Why it happens:** MB chose 503 historically. 429 is not part of their response set per the docs.
**How to avoid:** D-20 already covers both — log + fall through. But the rate-gate design must prevent 503s, not just handle them. If 503s appear in practice, the gate is broken.

### Pitfall 8: SQLite migration ordering — new column on `stations` requires the right ALTER TABLE position
**What goes wrong:** Adding `ALTER TABLE stations ADD COLUMN cover_art_source TEXT NOT NULL DEFAULT 'auto'` after the legacy URL-column migration block (`repo.py:122-179`) causes a "no such column" error during the legacy table rebuild — the rebuild's `INSERT INTO stations_new SELECT ... FROM stations` SELECT list doesn't include the new column.
**Why it happens:** The legacy rebuild SELECT is positional; new columns must either be appended to BOTH the new table CREATE and the SELECT, OR added AFTER the rebuild block.
**How to avoid:** Put the new `ALTER TABLE stations ADD COLUMN cover_art_source` BEFORE the legacy URL migration block (with its own try/except sqlite3.OperationalError for idempotency), OR after but ensuring the legacy SELECT doesn't need to know about it (the column is added via separate ALTER after the rebuild — current convention). Mirror the `icy_disabled` precedent at `repo.py:79-82` which appears BEFORE the legacy rebuild. [VERIFIED: `repo.py:79-181`]

### Pitfall 9: Settings export ZIP round-trip with missing field on old ZIPs
**What goes wrong:** A user exports settings on a pre-73 machine and imports on a 73+ machine. The ZIP's `stations[].cover_art_source` key is absent. Naive `station_data['cover_art_source']` raises KeyError.
**Why it happens:** ZIP `version: 1` payload schema doesn't bump on additive fields.
**How to avoid:** `station_data.get('cover_art_source', 'auto')` — defaults to Auto for old ZIPs. Matches the established `int(stream.get('bitrate_kbps', 0) or 0)` forward-compat pattern from Phase 47.2. [VERIFIED: `settings_export.py:528`]

### Pitfall 10: Lucene-escape order matters (`\` first, special chars second)
**What goes wrong:** If you escape `"` to `\"` first and then escape `\` to `\\`, the previously-inserted `\` gets doubled — producing `\\"` instead of `\"`.
**Why it happens:** Two-pass naive replacement.
**How to avoid:** Single-pass character-at-a-time iteration, or sort the escape map so `\\` is handled first. The `lucene_escape` helper sketched in the live probe handles this correctly.

## Code Examples

Verified patterns from official sources or live probes:

### Live MB JSON shape (live probe 2026-05-13)

```python
# Query: artist:"Daft Punk" AND recording:"One More Time"
# Source: live curl probe (sources section)
{
  "created": "2026-05-13T23:11:21.961Z",
  "count": 143,
  "offset": 0,
  "recordings": [
    {
      "id": "35089b45-6223-485c-871e-7b286819053a",
      "score": 100,                                 # int, 0-100
      "title": "One More Time",
      "length": 232333,                             # ms; can be None
      "first-release-date": "2007-11-19",           # str | None ; may be 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'
      "disambiguation": "part of a ... DJ-mix",
      "video": null,
      "artist-credit": [...],
      "tags": [                                     # KEY MAY BE ABSENT — use .get('tags', [])
        {"count": 1, "name": "dance"}
      ],
      "releases": [
        {
          "id": "b9ddde22-fca3-4d94-aee9-f964b34166ce",  # this is the MBID for CAA
          "title": "Anthems: 1991-2008",
          "status": "Official",                     # str | None ; sometimes 'Bootleg', 'Promotion', etc.
          "date": "2007-11-19",                     # str ; may be '', 'YYYY', 'YYYY-MM', 'YYYY-MM-DD'
          "release-group": {
            "primary-type": "Album",                # 'Album' | 'Single' | 'EP' | 'Other' | None
            "secondary-types": ["Compilation", "DJ-mix"]   # list; absence = empty list
          }
        }
      ]
    }
  ]
}
```

### MB search request with required headers

```python
# Source: project pattern + MB rate-limit doc
# https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting
from importlib.metadata import version
from urllib.parse import quote
from urllib.request import urlopen, Request

UA = f"MusicStreamer/{version('musicstreamer')} (https://github.com/lightningjim/MusicStreamer)"

def _build_mb_query(artist: str, title: str) -> str:
    # Lucene-escape both fields (Pitfall 10 handles order)
    artist_esc = _escape_lucene(artist)
    title_esc = _escape_lucene(title)
    q = f'artist:"{artist_esc}" AND recording:"{title_esc}"'
    return f"https://musicbrainz.org/ws/2/recording/?query={quote(q)}&fmt=json&limit=5"

req = Request(_build_mb_query("Daft Punk", "One More Time"), headers={"User-Agent": UA})
with urlopen(req, timeout=5) as resp:
    payload = resp.read()
```

### Lucene escape (Pitfall 10 safe)

```python
# Source: Lucene 4.x query-parser docs
# https://lucene.apache.org/core/4_0_0/queryparser/org/apache/lucene/queryparser/classic/package-summary.html
def _escape_lucene(s: str) -> str:
    """Escape Lucene query syntax special characters with a backslash prefix.

    Special chars per Lucene docs: + - && || ! ( ) { } [ ] ^ " ~ * ? : \\ /
    Single-pass to avoid double-escaping (Pitfall 10).
    """
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        # Two-char operators first
        if ch == "&" and i + 1 < len(s) and s[i + 1] == "&":
            out.append("\\&\\&")
            i += 2
            continue
        if ch == "|" and i + 1 < len(s) and s[i + 1] == "|":
            out.append("\\|\\|")
            i += 2
            continue
        if ch in r'+-!(){}[]^"~*?:\/':
            out.append("\\" + ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)
```

### Release selection (D-10 ladder)

```python
# Source: D-10 + live MB probe findings
def _pick_release_mbid(recording: dict) -> Optional[str]:
    releases = recording.get("releases", []) or []

    # Step 1: Official + Album + no secondary-types, earliest date
    candidates = [
        r for r in releases
        if r.get("status") == "Official"
        and (r.get("release-group") or {}).get("primary-type") == "Album"
        and not ((r.get("release-group") or {}).get("secondary-types") or [])
    ]
    candidates.sort(key=lambda r: r.get("date") or "9999")
    if candidates:
        return candidates[0]["id"]

    # Step 2: Any Official, earliest date
    candidates = [r for r in releases if r.get("status") == "Official"]
    candidates.sort(key=lambda r: r.get("date") or "9999")
    if candidates:
        return candidates[0]["id"]

    # Step 3 (D-10 fallback): any release with CAA art — planner's choice
    # whether to probe CAA HEAD here or defer until first GET.
    # Recommendation: skip step 3 (it's a rare case; CAA GET will succeed or
    # 404 cleanly). See Pitfall 4.
    return None
```

### Recording selection by score + canonical-ness

```python
# Source: live probe of "Hey Jude" (Pitfall 1)
def _pick_recording(data: dict) -> Optional[dict]:
    recordings = data.get("recordings", []) or []
    # Step 1: filter to score >= 80 (D-09)
    accepted = [r for r in recordings if (r.get("score") or 0) >= 80]
    if not accepted:
        return None
    # Step 2: prefer earliest first-release-date (canonical-ness signal — Pitfall 1)
    accepted.sort(key=lambda r: r.get("first-release-date") or "9999")
    return accepted[0]
```

### Genre from MB tags (D-15)

```python
# Source: live probe of "Daft Punk - One More Time" — tags shape verified
def _genre_from_tags(recording: dict) -> str:
    tags = recording.get("tags") or []
    if not tags:
        return ""
    # Highest count wins; stable sort by name for determinism on ties
    tags_sorted = sorted(tags, key=lambda t: (-int(t.get("count", 0)), t.get("name", "")))
    return tags_sorted[0].get("name", "")
```

### Test pattern: assert User-Agent on outgoing Request

```python
# Source: tests/test_cookies.py pattern + Pitfall 6 (header case)
def test_mb_request_carries_user_agent(monkeypatch):
    from musicstreamer import cover_art_mb
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        return MagicMock(read=lambda: b'{"recordings": []}',
                         __enter__=lambda s: s, __exit__=lambda *a: None)
    monkeypatch.setattr("musicstreamer.cover_art_mb.urlopen", fake_urlopen)
    cover_art_mb._do_mb_search("Daft Punk", "One More Time")
    ua = captured["req"].get_header("User-agent")  # Pitfall 6: 'User-agent', not 'User-Agent'
    assert ua.startswith("MusicStreamer/2.")
    assert "https://github.com/lightningjim/MusicStreamer" in ua
```

### Test pattern: rate-gate deterministic clock

```python
# Source: project pattern for monotonic-clock testing (Phase 62 _BufferUnderrunTracker tests)
def test_mb_gate_serializes_with_1s_floor(monkeypatch):
    from musicstreamer import cover_art_mb
    fake_now = [0.0]
    sleeps = []
    monkeypatch.setattr(cover_art_mb.time, "monotonic", lambda: fake_now[0])
    monkeypatch.setattr(cover_art_mb.time, "sleep", lambda s: sleeps.append(s))
    gate = cover_art_mb._MbGate()
    gate.wait_then_mark()
    fake_now[0] = 0.3  # second call only 0.3s later
    gate.wait_then_mark()
    assert sleeps == [pytest.approx(0.7)]  # slept 0.7s to reach 1.0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| iTunes-only with `_last_cover_icy` dedup | Add MB+CAA fallback path; per-station preference | Phase 73 (this phase) | Coverage expands beyond iTunes' Western-pop bias |
| Per-request `threading.Thread` daemon (iTunes) | iTunes path: unchanged. MB path: persistent worker w/ gate | Phase 73 | Required to share `_next_allowed_at` across calls |
| Hardcoded User-Agent (`"MusicStreamer/2.0"` in `gbs_api.py:77`) | `importlib.metadata.version()` at construction time | Established Phase 65 (VER-02) | Auto-bumps via phase-complete hook; MB request uses live version |
| `Signal(str)` payload with `f"{token}:{path}"` | Same; consider widening (Open Question 3) | — | Path-only payload is sufficient for D-15 genre because `last_itunes_result` module dict is the genre channel |

**Deprecated / outdated knowledge to ignore:**
- "MB requires `inc=tags` to return tags": **FALSE** for search endpoint. Tags ARE returned by default on `/recording/?query=`. Live verified 2026-05-13.
- "CAA returns 200": **FALSE.** Returns 307 to archive.org. urllib follows by default.
- "Use `requests` for HTTP redirects": **N/A** here — stdlib urllib handles 307 fine.

## Assumptions Log

> All claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CAA image size 250 scales cleanly to 160×160 on DPR=1.0 Wayland | Don't Hand-Roll / CAA endpoint | If image quality is poor at upscale, switch to 500. Low risk; planner discretion per D-11. |
| A2 | `urllib.request.urlopen` default opener follows 307 redirects on GET in Python 3.10+ | Don't Hand-Roll | Verified for Python 3.14 in live test but project also runs on Python 3.10. Stdlib behavior is stable across 3.10+ per Python release notes, but not retested. |
| A3 | A `time.monotonic()`-based gate with `time.sleep()` is acceptable on a daemon thread (won't block app shutdown unreasonably) | Architecture Patterns / Pattern 1 | Sleep is at most ~1s. Daemon threads exit on interpreter shutdown. Low risk. |
| A4 | The existing `cover_art_ready = Signal(str)` is wired with auto-queued connection (so cross-thread emit works) | Pitfall 5 | Verified at `now_playing_panel.py:1180` it's emitted; connection style not directly grep-verified but the existing iTunes path provably works the same way. |
| A5 | `pyproject.toml` `version="2.1.72"` is the correct source for `importlib.metadata.version('musicstreamer')` after pip install | Stack / Versioning | True for installed packages; planner should verify behavior in PyInstaller bundle (Windows packaging). Low risk on Linux dev / Wayland deployment per current scope. |
| A6 | The planner choice between QComboBox vs three radio buttons matches edit_station_dialog's idiom — QComboBox feels right since the dialog already uses `provider_combo` (QComboBox) and similar | Recommended Project Structure / Discretion | Cosmetic only. Low risk. |

## Open Questions (RESOLVED)

1. **Should D-10 step 3 (CAA-art existence probe) ship at all, or is steps 1+2 sufficient?**
   - What we know: Live probes show "any Official release" usually has CAA art (recording rec[0] for One More Time → CAA 307 OK). Pure-fallback step 3 adds one extra HTTP call per miss and only helps for recordings where ONLY a bootleg/promo release has art.
   - What's unclear: Real-world frequency of "no Official release exists but Bootleg has CAA art".
   - RESOLVED: Deferred to a future phase per user decision 2026-05-13. D-10 step 3 (CAA art existence probe on any release) is moved to CONTEXT.md Deferred Ideas. Plan 02 implements D-10 steps 1+2 only.

2. **Does the MB User-Agent require an `email` over a `github URL`?**
   - What we know: MB docs say `( contact-url )` OR `( contact-email )` are both acceptable. CONTEXT D-18 locks the GitHub URL form: `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)`.
   - What's unclear: Nothing — the format is locked.
   - RESOLVED: Use the GitHub URL form verbatim. Privacy-preserving (memory `project_publishing_history.md`). No need to revisit.

3. **Should the Qt-thread payload widen from `Signal(str)` to `Signal(dict)` to carry source + genre?**
   - What we know: `last_itunes_result` is already the genre channel; widening the Signal isn't strictly necessary. But `last_itunes_result` is a MODULE-LEVEL singleton — racy if two stations switch rapidly.
   - What's unclear: Whether the race is observable in practice (existing iTunes path also writes module-level; no race reported).
   - RESOLVED: Keep `Signal(str)` for Phase 73 (matches existing pattern, no race regression). If favorites-star takes the wrong genre under fast switching, fix in a follow-up. Document the staleness invariant in the worker docstring.

4. **What `limit` value for MB search?**
   - What we know: D-08 says "limit=5" as default, planner's discretion. Live probe showed top-5 may not include canonical Album (Hey Jude case — canonical is rec[15] of 25).
   - What's unclear: Acceptable miss rate at limit=5 vs limit=25. Larger N = more payload but better selection.
   - RESOLVED: Start at `limit=10`. Larger than 5 to catch the canonical-release case more often; smaller than 25 to keep payload manageable. Reassess if user reports persistent misses on canonical-album lookups.

5. **Does Phase 73 need a dedicated mock-HTTP fixture set, or are JSON-string fixtures sufficient?**
   - What we know: TESTING.md doesn't currently use a mock HTTP server. The existing `test_cover_art.py` uses inline JSON dicts.
   - What's unclear: Whether monkey-patching `urlopen` is sufficient for the end-to-end "iTunes miss → MB hit shows correct image" test.
   - RESOLVED: Inline JSON fixtures + `urlopen` monkeypatch. Matches existing convention. No new test infrastructure.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ stdlib (`urllib`, `json`, `threading`, `time`) | All Phase 73 code | ✓ | 3.14.4 on dev rig | — |
| `importlib.metadata` | User-Agent construction | ✓ | stdlib | Hardcode fallback if not installed (extremely unlikely) |
| `PySide6` Signal / QPixmap | Cross-thread result + image display | ✓ | per `pyproject.toml` >=6.10 | — |
| `pytest-qt` | UI integration tests | ✓ | per `pyproject.toml` [test] >=4 | — |
| Internet access to `musicbrainz.org` | E2E manual UAT only (NOT unit tests — mocked) | Variable | — | Skip live UAT; unit tests independent |
| Internet access to `coverartarchive.org` | E2E manual UAT only | Variable | — | Skip live UAT; unit tests independent |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None — Phase 73 is pure-stdlib + existing deps.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 9 + pytest-qt >= 4 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"]) |
| Quick run command | `uv run --with pytest --with pytest-qt pytest tests/test_cover_art.py tests/test_cover_art_mb.py tests/test_now_playing_panel.py -x` |
| Full suite command | `uv run --with pytest --with pytest-qt pytest tests` |

### Phase Requirements → Test Map

Phase 73 requirement IDs (to be registered during planning, suggested `ART-MB-NN`):

| Req ID (proposed) | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ART-MB-01 | User-Agent header literal on MB API request matches `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` | unit | `pytest tests/test_cover_art_mb.py::test_mb_request_carries_user_agent -x` | ❌ Wave 0 |
| ART-MB-02 | User-Agent header literal on CAA image request | unit | `pytest tests/test_cover_art_mb.py::test_caa_request_carries_user_agent -x` | ❌ Wave 0 |
| ART-MB-03 | 1 req/sec gate: 5 sequential MB calls span ≥ 4 seconds of monotonic clock | unit (deterministic mock-clock) | `pytest tests/test_cover_art_mb.py::test_mb_gate_serializes_with_1s_floor -x` | ❌ Wave 0 |
| ART-MB-04 | Score=85 fixture accepted; score=79 fixture rejected; bare-title ICY skips MB | unit | `pytest tests/test_cover_art_mb.py::test_score_threshold -x` | ❌ Wave 0 |
| ART-MB-05 | Release selection: Official+Album+earliest wins over Bootleg with same score | unit | `pytest tests/test_cover_art_mb.py::test_release_selection_ladder -x` | ❌ Wave 0 |
| ART-MB-06 | Latest-wins queue: 5 rapid ICY arrivals → at most 1 wasted MB call (in-flight) + 1 final | unit (mocked clock + queue inspection) | `pytest tests/test_cover_art_mb.py::test_latest_wins_queue -x` | ❌ Wave 0 |
| ART-MB-07 | MB-only mode: iTunes urlopen MUST NOT be called | unit | `pytest tests/test_cover_art.py::test_mb_only_skips_itunes -x` | ❌ Wave 0 |
| ART-MB-08 | iTunes-only mode: MB urlopen MUST NOT be called | unit | `pytest tests/test_cover_art.py::test_itunes_only_skips_mb -x` | ❌ Wave 0 |
| ART-MB-09 | Auto mode: iTunes miss → MB called → image shown via cover_art_ready signal | integration (qtbot + mocked urlopen) | `pytest tests/test_cover_art_routing.py::test_auto_falls_through_to_mb -x` | ❌ Wave 0 |
| ART-MB-10 | Settings export ZIP round-trips `cover_art_source` field; old ZIPs default to 'auto' | unit | `pytest tests/test_settings_export.py::test_cover_art_source_roundtrip -x` | ❌ Wave 0 |
| ART-MB-11 | SQLite migration adds column with DEFAULT 'auto'; idempotent on re-run | unit | `pytest tests/test_repo.py::test_cover_art_source_migration_idempotent -x` | ❌ Wave 0 |
| ART-MB-12 | EditStationDialog selector reads + writes `station.cover_art_source` | qtbot | `pytest tests/test_edit_station_dialog.py::test_cover_art_source_selector -x` | ❌ Wave 0 |
| ART-MB-13 | MB tags → genre: highest-count tag wins; empty tags → genre="" | unit | `pytest tests/test_cover_art_mb.py::test_genre_from_tags -x` | ❌ Wave 0 |
| ART-MB-14 | HTTP 503 from MB → callback(None), no raise out of worker | unit | `pytest tests/test_cover_art_mb.py::test_mb_503_falls_through -x` | ❌ Wave 0 |
| ART-MB-15 | Source-grep gate: literal `MusicStreamer/` AND `https://github.com/lightningjim/MusicStreamer` appear in cover_art_mb.py source | source-grep test | `pytest tests/test_cover_art_mb.py::test_user_agent_string_literals_present -x` | ❌ Wave 0 |
| ART-MB-16 | Source-grep gate: gate has actual `time.monotonic` reference (not just a comment claiming rate-limit) | source-grep test | `pytest tests/test_cover_art_mb.py::test_rate_gate_uses_monotonic -x` | ❌ Wave 0 |

(Source-grep gates ART-MB-15/16 mirror the memory `feedback_gstreamer_mock_blind_spot.md` lesson — protocol-required strings should be tested at the source level, not just behaviorally.)

### Sampling Rate
- **Per task commit:** `pytest tests/test_cover_art.py tests/test_cover_art_mb.py -x` (~2–4 sec)
- **Per wave merge:** `pytest tests/test_cover_art.py tests/test_cover_art_mb.py tests/test_now_playing_panel.py tests/test_settings_export.py tests/test_repo.py tests/test_edit_station_dialog.py -x` (~30 sec; covers all Phase 73 touch points)
- **Phase gate:** Full suite (`pytest tests`) green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cover_art_mb.py` — covers ART-MB-01..06,13,14,15,16
- [ ] `tests/test_cover_art_routing.py` — covers ART-MB-09 (auto-mode fallthrough)
- [ ] `tests/fixtures/mb_recording_search_*.json` — mocked MB responses (at minimum: clean Official Album hit, Bootleg-only hit, score=79 reject, score=85 accept, no-tags response, 503 error body)
- [ ] Extension of `tests/test_cover_art.py` for routing — covers ART-MB-07/08
- [ ] Extension of `tests/test_repo.py` for migration — covers ART-MB-11
- [ ] Extension of `tests/test_settings_export.py` for round-trip — covers ART-MB-10
- [ ] Extension of `tests/test_edit_station_dialog.py` for selector — covers ART-MB-12
- [ ] Extension of `tests/test_now_playing_panel.py` for source-aware `_fetch_cover_art_async` — covers ART-MB-09 partial

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth on MB / CAA |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Public anonymous APIs |
| V5 Input Validation | **yes** | Lucene-escape user-derived `artist`/`title` strings before composing query; URL-encode the composed query before sending |
| V6 Cryptography | no | TLS handled by stdlib urllib + system CA store |
| V7 Error Handling | yes | Bare `except Exception` in worker → callback(None); never raise out (D-20). Log to `logging.getLogger(__name__)`. |
| V8 Data Protection | no | No PII; no secrets |
| V12 Files / Resources | yes | Temp file lifecycle for CAA image bytes — mirror existing iTunes pattern (`cover_art.py:94`); planner should consider whether tempfiles leak on long sessions (CONTEXT D-12 says no caching this phase, so each fetch creates a new temp) |
| V14 Configuration | yes | User-Agent format is policy-critical — source-grep test ART-MB-15 |

### Known Threat Patterns for stdlib urllib + JSON

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Lucene injection from ICY title (e.g., `Britney Spears - "(I Can't Get No) Satisfaction" OR *:*`) | Tampering | Lucene-escape ALL ICY-derived strings; reject empty parts; cap title length sanely |
| URL injection via crafted ICY | Tampering | `urllib.parse.quote` the entire query string; never substitute raw |
| Malicious JSON response causes parse exception → worker dies silently | Denial of Service / Information Disclosure | Bare `except Exception` per D-20; log; callback(None). MB responses come from a trusted-ish host but defense-in-depth wins. |
| Slowloris-style MB response → worker blocks for minutes | Denial of Service | `urlopen(..., timeout=5)` — matches existing iTunes pattern |
| Image bytes from CAA write to disk via `tempfile.NamedTemporaryFile(delete=False)` create orphan files | Information Disclosure (sensitive file content) / Disk Exhaustion | Existing pattern at `cover_art.py:94` is the precedent. Phase 73 mirrors. If tempfile leakage becomes a problem, the caching phase will own GC. |
| User-Agent contact URL leak (privacy) | Information Disclosure | GitHub URL (NOT email) per D-18 + memory `project_publishing_history.md` |

## Sources

### Primary (HIGH confidence — verified live or from authoritative docs)
- **[CITED: https://musicbrainz.org/doc/MusicBrainz_API]** — REST API root, JSON format selector (`fmt=json`), endpoint pattern
- **[CITED: https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting]** — *"If you impact the server by making more than one call per second, your IP address may be blocked. ... declined (http 503) until the rate drops again."* + *"Each request sent to MusicBrainz needs to include a User-Agent header"* + UA format `Application name/<version> ( contact-url )`
- **[CITED: https://musicbrainz.org/doc/MusicBrainz_API/Search]** — Lucene query syntax for `/recording/?query=`, searchable fields list, score 0-100 scale
- **[CITED: https://musicbrainz.org/doc/Cover_Art_Archive/API]** — `/release/<mbid>/front`, `/front-250`, `/front-500`, `/front-1200`; 307 redirect to archive.org; 404 = no release OR no art; GET/HEAD supported; *"There are currently no rate limiting rules in place"*
- **[CITED: https://lucene.apache.org/core/4_0_0/queryparser/org/apache/lucene/queryparser/classic/package-summary.html]** — Lucene special-char escape list: `+ - && || ! ( ) { } [ ] ^ " ~ * ? : \ /`
- **[VERIFIED: live curl probe 2026-05-13]** — MB recording search JSON shape, score=int, releases[].date heterogeneity, tags key absence pattern, CAA 307 → archive.org with `_thumb250.jpg`/`_thumb500.jpg`/`_thumb1200.jpg` suffixes
- **[VERIFIED: musicstreamer source]** — `cover_art.py`, `now_playing_panel.py:1170-1212`, `now_playing_panel.py:820-900`, `models.py`, `repo.py:79-181, 420-470`, `settings_export.py`, `migration.py`, `__main__.py:9`, `ui_qt/main_window.py:281`, `gbs_api.py:77`, `pyproject.toml:7`
- **[VERIFIED: .claude/skills/spike-findings-musicstreamer/SKILL.md + references/qt-glib-bus-threading.md]** — QTimer.singleShot drops on non-QThread; cross-thread Signal pattern
- **[VERIFIED: .planning/STATE.md]** — Phase 62 monotonic-clock cooldown precedent; Phase 65 importlib.metadata.version() VER-02 convention; Phase 999.7 cross-platform `mkstemp` precedent
- **[VERIFIED: .planning/codebase/TESTING.md]** — pytest patterns, monkeypatch urlopen pattern, FakeRepo pattern

### Secondary (MEDIUM confidence — informed by training + cross-checked against current sources)
- Python 3.10+ `urllib.request.urlopen` follows 307 redirects via default `HTTPRedirectHandler` — stable behavior across 3.10–3.14; verified live with curl that CAA returns 307.
- `tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)` is cross-platform per existing `cover_art.py:94` usage (works on Linux dev + Windows packaging per Phase 999.7 / Phase 43 UAT).

### Tertiary (LOW confidence — flagged for validation if relied upon)
- Estimated CAA image-size variant 250 is sufficient for 160×160 cover slot (assumption A1; tested only as a 307 URL probe, not as an actual decoded pixmap rendering).
- `urllib.request.Request` header normalization stores as `User-agent` (Python internal title-casing); Pitfall 6 was derived from training, not a fresh probe — planner should verify if writing a strict-equality test rather than `startswith`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pure stdlib, project-canonical patterns, version live-verified
- Architecture: HIGH — mirrors existing iTunes worker + Phase 62 monotonic gate + Phase 43.1 Signal pattern; all three precedents documented in STATE.md
- API shape (MB + CAA): HIGH — live-probed JSON shape; redirect behavior; tags-absent pattern; date heterogeneity all observed directly
- Release selection logic: HIGH — D-10 ladder verified against live probes for Hey Jude / Karma Police / Daft Punk (three representative artists; clean canonical hit, bootleg-only top-5, and DJ-mix-compilation cases all exercised)
- Pitfalls: HIGH for 1-9 (verified live or in source); MEDIUM for 10 (Lucene escape order — derived from spec, not live tested)
- Validation architecture: HIGH — every test maps to a real file path / existing test pattern

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (30 days; MB/CAA API have been stable for years, but `score` semantics and `tags` shape could shift)

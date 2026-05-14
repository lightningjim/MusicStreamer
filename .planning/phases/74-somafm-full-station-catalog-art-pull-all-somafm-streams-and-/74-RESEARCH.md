# Phase 74: SomaFM full station catalog + art — Research

**Researched:** 2026-05-13
**Domain:** Public-API bulk catalog importer + QThread-backed hamburger UX
**Confidence:** HIGH

## Summary

Phase 74 adds a SomaFM bulk importer that mirrors the existing AudioAddict importer almost line-for-line. Live-probing `https://api.somafm.com/channels.json` against today's catalog produced HTTP 200 with a 50,679-byte JSON body containing **46 channels**, each carrying exactly **four `playlists` entries** in the exact same `(format, quality)` shape — `(mp3, highest)`, `(aac, highest)`, `(aacp, high)`, `(aacp, low)` — so 184 PLS URLs total. Every playlist URL is a `.pls` file served from `api.somafm.com`; **direct stream URLs (`ice*.somafm.com/...`) are only reachable via PLS resolution**, so `_resolve_pls` (lifted from `aa_import.py`) is mandatory for D-05 dedup to work against any URL the user might have hand-curated.

The implementation is heavier on data plumbing than on algorithms: ~250 LOC of `soma_import.py` (parse the channels list, map four playlist tuples to two SomaFM-specific quality tiers, resolve PLS, dedup-by-URL, insert station + streams, kick logo download) + ~30 LOC of `main_window.py` (one hamburger action, one worker class, one finished slot, one error slot) + a `tests/fixtures/soma_channels_*.json` blob + the standard ~12 deterministic tests against monkeypatched `urlopen`. No external dependencies, no auth, no per-channel HTTP beyond logo downloads — the catalog fetch is one GET.

**Primary recommendation:** Mirror `aa_import.py` verbatim where possible (`_resolve_pls`, `_download_logo`, `import_stations_multi` semantics, ThreadPoolExecutor for logos), narrow the function surface (no `listen_key`, no per-network `NETWORKS` loop, no `_fetch_image_map`), and collapse SomaFM's four playlists into three quality tiers using the rule **MP3 highest → "hi", AAC highest → "med", aacp low → "low"** (drop `aacp high` per D-08 stream-count discipline; cite empirical bitrate ladder for rationale). Use SomaFM's `image` (120×120) for logo download — matches AA's existing logo dimensionality and avoids gratuitous 144 kB downloads per channel for a slot that displays at 160px square.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Catalog architecture**
- **D-01: Poll-to-install.** Bulk insert all ~40 SomaFM channels as real Station rows in SQLite on user-initiated import. Multi-quality streams per channel + per-station logo downloaded to the library's logos directory (same dir as AA logos). Closest parity with AudioAddict + GBS.FM importers.
- **D-02: Provider name pinning.** Every SomaFM-imported station has `provider_name = "SomaFM"` (canonical brand string — matches `"GBS.FM"`, `"DI.fm"`, `"JazzRadio"` etc.).
- **D-03: Multi-stream per channel.** Each channel becomes ONE station with MULTIPLE stream rows (one per quality variant). Stream count varies per channel — SomaFM typically offers MP3 128, AAC 64, AAC+ 32. Some channels have a fourth tier. Insert all variants the API exposes.

**Refresh policy**
- **D-04: Manual re-import only.** No auto-refresh on startup, no scheduled refresh, no etag-check toast. User clicks the hamburger action again to refresh.
- **D-05: Full no-op on URL match (true AA parity).** Re-import semantics: for each SomaFM channel, if ANY of its stream URLs already exist in the library, SKIP the entire channel — no metadata refresh, no logo redownload, no stream reset. New (never-imported) SomaFM channels insert normally. Mirrors `aa_import.py:import_stations_multi` semantics. **The only way to refresh an existing SomaFM station's logo/description is delete-and-reimport.**

**UI entry point**
- **D-06: Hamburger menu action.** Add `"Import SomaFM"` to the hamburger menu near the existing `"Add GBS.FM"` action. One-click invocation, no dialog. Status surfaced via toasts (parity with GBS.FM `import_station` toast pattern at `main_window.py:1429-1453`):
  - "Importing SomaFM…"
  - "SomaFM import: N stations added" (or "no changes" if all channels were dedup-skipped)
  - "SomaFM import failed: <truncated message>"
- **D-07: Worker-thread dispatch.** Network calls run on a worker thread (parity with GBS.FM `_start_gbs_import` at `main_window.py:1420-1465`). Worker retention pattern follows Phase 60 D-02's `SYNC-05` precedent so the QThread isn't GC'd mid-flight.
- **D-08: No progress bar.** Toast-only feedback (parity with GBS.FM). Phase 74's 40-channel import is faster than AA's import-dialog progress-bar pattern justifies. If real-world UAT shows the import takes >5 sec, planner can revisit.

**Dedup behavior**
- **D-09: Skip-if-URL-exists across the WHOLE library.** For each fetched SomaFM channel, check if ANY of its candidate stream URLs match an existing station's stream URL (any provider). If MATCH found, skip the channel entirely — regardless of the matched station's `provider_name`.
- **D-10: Atomic per-channel insert.** A SomaFM channel either inserts fully (station row + ALL its stream rows + logo) or not at all (channel-level skip). Mirror AA's `import_stations_multi` ordering: insert station → insert streams → fire logo download (background — non-blocking).
- **D-11: Logo failure is non-fatal.** If the logo HTTP fetch fails, the station + streams stay inserted; logo download is best-effort (mirror AA pattern). User can manually edit the station to set a logo later.

**MB protocol awareness (no MB calls in this phase)**
- **D-12: No MusicBrainz integration here.** Phase 73 added the per-station `cover_art_source` field with default `"auto"`. SomaFM-imported stations get `cover_art_source = "auto"`.
- **D-13: Station logos vs cover art.** SomaFM channel logos download to the logos directory and populate `station_art_path`. Phase 73's `cover_art_source` is unaffected.

**Failure handling**
- **D-14: Network error / 5xx / JSON parse error → entire import aborts cleanly.** Surface a single toast "SomaFM import failed: <truncated reason>". Do NOT partially import.
- **D-15: Per-channel best-effort within a successful catalog fetch.** Once the channels.json call succeeds, a per-channel exception during stream/logo extraction skips THAT channel but continues with the rest. Final toast counts only successful inserts.

**Logging**
- **D-16: Add `soma_import` to the per-logger registration in `__main__.py:234`.** Same INFO-level treatment as `aa_import`, `gbs_api`, `mpris2`.

### Claude's Discretion

- **Quality tier mapping.** Map four SomaFM playlists to hi/med/low or leave blank and let `stream_ordering.py` codec+bitrate sort handle ordering. Planner picks — recommend the explicit hi/med/low mapping for AA-pattern consistency.
- **Codec field population.** `mp3` → "MP3", `aac` → "AAC", `aacp` → "AAC" (HE-AAC; verified working on Windows per WIN-05/Phase 69).
- **Channel-fetch concurrency.** `channels.json` returns all channels in one HTTP call. Logo downloads are per-channel (~40 GETs) — sequential is fine for ~40 small images, parallel-with-threading-pool is also acceptable.
- **Logo file naming + persistence.** Mirror AA's `_download_logo` pattern. Use SomaFM channel `id` slug as the filename basis.
- **Stream `label` field.** Either empty (AA pattern) or "MP3 128 kbps" / etc. labels. Planner picks; prefer empty for AA parity.
- **API endpoint.** `https://api.somafm.com/channels.json` is the documented public endpoint. `https://somafm.com/channels.json` may also work. Planner verifies which is current.
- **User-Agent on SomaFM requests.** SomaFM doesn't require a UA, but for politeness use `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` (Phase 73's MB/CAA UA).

### Deferred Ideas (OUT OF SCOPE)

- In-memory / browse-modal SomaFM UX — rejected per Area 1 (poll-to-install wins).
- SomaFM tab in ImportDialog — rejected per Area 3 (hamburger only).
- Auto-refresh on app start / weekly refresh / etag-check toast — rejected per Area 2 (manual only).
- Discovery dialog SomaFM curated source — rejected per Area 3.
- Refresh metadata on URL match — rejected per Area 4 (true AA parity is full no-op).
- Truncate-and-reset for `provider_name = 'SomaFM'` stations — rejected per Area 4.
- Notification toast when SomaFM publishes a new channel — out of scope.
- SomaFM premium / paid integration — out of scope.
- Merge-by-name dedup (collapse hand-curated 'Groove Salad' into SomaFM-canonical) — rejected.
- Quality-label fallback when SomaFM API drops a tier — out of scope.
- Progress bar UX — rejected per D-08.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| (none yet) | Plan 01 will register a new `SOMA-NN` family in `REQUIREMENTS.md` (mirror Phase 73's Plan 01 read-then-add procedure). | This research is the input to Plan 01's requirement drafting. |

**Note for planner — REQUIREMENTS.md state (verified 2026-05-13):**
- No existing `SOMA-NN` or `SomaFM` requirement IDs `[VERIFIED: grep REQUIREMENTS.md]`.
- The CONTEXT.md `<specifics>` note mentioning "STATION-ART-04" appears to be **stale** — full grep of `.planning/REQUIREMENTS.md` finds zero hits on `STATION-ART` `[VERIFIED: grep .planning/]`. Plan 01 should not assume that ID exists; if a "broader station-art enhancement" parking lot is wanted, it must be added afresh. Per the user's `feedback_mirror_decisions_cite_source.md` memory rule, do **not** paraphrase that note into a closure claim without re-grepping the source.
- Current Coverage block at `REQUIREMENTS.md:152-155` reads `38 total / 38 mapped / 20 complete / 18 pending`. Plan 01 must increment in lockstep with new SOMA-NN rows.
- One existing mention of "SomaFM" in REQUIREMENTS.md is incidental — line 34 (`WIN-05`: "DI.fm AAC tier + SomaFM HE-AAC fixtures verified") — not a Phase 74 dependency.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

`CLAUDE.md` is intentionally minimal — only one binding directive:

- **Spike-findings routing**: "Windows packaging patterns, GStreamer+PyInstaller+conda-forge, PowerShell gotchas" must consult `Skill("spike-findings-musicstreamer")`. **Not load-bearing for Phase 74** — this phase ships pure-Python module + Qt UI + tests, no packaging change, no GStreamer-bundle work. The packaging Skill stays dormant.

Other project conventions surfaced via STATE.md / Key Decisions (not in CLAUDE.md but binding):

- **`mp3` family memory `feedback_mirror_decisions_cite_source.md`**: "Mirror X" research claims must cite source. Applied here — the CONTEXT note about `STATION-ART-04` is flagged as unverifiable rather than mirrored.
- **`feedback_gstreamer_mock_blind_spot.md`**: Tests that mock external libs need source-grep gates to ensure literal protocol strings aren't dropped. Applied to Phase 74 via test items #9, #14 in the validation matrix below (codec literal grep, UA literal grep).
- **`reference_qnap_github_mirror.md`**: QNAP `origin` mirrors to GitHub. Phase 74 commits are effectively public. No PII or auth tokens in code or fixtures (SomaFM is unauthenticated — nothing sensitive to leak).
- **Deployment target `project_deployment_target.md`**: Linux Wayland (GNOME), DPR=1.0. Qt offscreen tests already configured in `tests/conftest.py` — no Wayland-specific concerns for this phase.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Fetch SomaFM channels.json | Python module (`soma_import`) | — | Pure stdlib `urllib` call, same shape as `aa_import.fetch_channels_multi`. Public API, no auth, no session state. |
| Resolve PLS → direct stream URLs | Python module (`soma_import`) → `playlist_parser` | — | D-05 dedup-by-URL must match the canonical `ice*.somafm.com/...` direct URLs that the player actually consumes. PLS resolution is delegated to `playlist_parser.parse_playlist` (Phase 58 D-10 lifted out of `aa_import._resolve_pls`). |
| Quality-tier mapping (4 playlists → ≤3 stream rows) | Python module (`soma_import`) | `stream_ordering.py` (sort-time consumer) | Module-scope `_QUALITY_MAP` constant mirrors `aa_import._POSITION_MAP` / `_BITRATE_MAP` / `_CODEC_MAP` shape. Result rows feed `order_streams` at playback time. |
| Logo download | Python module (`soma_import`) | `assets.copy_asset_for_station` | Same dir + same call shape as `aa_import._download_logo`. ThreadPoolExecutor optional (~40 small images). |
| Station + stream DB insert | `repo.Repo` (existing primitives) | `soma_import` orchestrates | `insert_station` + `insert_stream` + `update_stream` + `station_exists_by_url` + `update_station_art` already exist; no schema change. |
| Hamburger menu action wiring | `ui_qt.main_window.MainWindow` | `QAction` | Direct parity with `act_gbs_add` at line 205. Bound-method `connect` (QA-05). |
| Background worker | `QThread` subclass in `main_window` | Qt `Signal` for cross-thread result | Mirror `_GbsImportWorker` at line 124-150. `Signal(int, int)` for `(inserted, skipped)`; `Signal(str)` for error. SYNC-05 retention on `self._soma_import_worker`. |
| Toast surfacing | `MainWindow.show_toast` | `ToastOverlay` | Existing infrastructure — three call sites in `_on_soma_*` slots. |

**Why this matters:** All seven tiers above are already established in the codebase. Phase 74 is a recombination, not a new architectural shape. The plan-checker should reject any task that introduces a tier not in this table (e.g., a new dialog, a new HTTP client wrapper, a new asset directory).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `urllib.request` | 3.10+ | HTTP GET on channels.json and logo URLs | Already the project's HTTP client for catalog fetches (`aa_import`, `gbs_api`, `cover_art`, `radio_browser`). Zero new dependency. `[VERIFIED: .planning/codebase/INTEGRATIONS.md, aa_import.py:13]` |
| Python stdlib `json` | 3.10+ | Parse channels.json response | Already the project's JSON parser. `[VERIFIED: aa_import.py:8]` |
| Python stdlib `tempfile` + `os.path` | 3.10+ | Stage logo download bytes → asset dir | Mirror `aa_import._download_logo` lines 257-275. `[VERIFIED: aa_import.py:11, aa_import.py:262]` |
| `concurrent.futures.ThreadPoolExecutor` | stdlib | Parallel logo downloads (optional) | AA uses `max_workers=8` for ~25 logos. SomaFM has ~46 logos so the speedup is real if planner picks parallel. `[VERIFIED: aa_import.py:15, aa_import.py:279]` |
| `musicstreamer.playlist_parser.parse_playlist` | in-tree | Convert SomaFM PLS body → list of `{url, …}` dicts | Phase 58 D-10 extracted from `aa_import._resolve_pls`; SomaFM PLS uses the same RFC-equivalent `File1=…` shape, confirmed via live probe of `https://api.somafm.com/groovesalad.pls`. `[VERIFIED: live HTTP probe, response 200 + content-type audio/x-scpls]` |
| `PySide6.QtCore.QThread` + `Signal` | 6.11+ | Off-main worker for `_start_soma_import` | Mirror `_GbsImportWorker` at `main_window.py:124-150`. `[VERIFIED: main_window.py:124]` |
| `pytest` + `pytest-qt` | 9.x / 4.x | Test framework | Already the project standard. `tests/test_aa_import.py` is the template; `tests/test_main_window_gbs.py` is the qtbot template. `[VERIFIED: STACK.md, tests/test_main_window_gbs.py]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `musicstreamer.assets.copy_asset_for_station` | in-tree | Move temp logo to `assets/<station_id>/station_art.<ext>` | Logo download phase only — mirror `aa_import:266`. `[VERIFIED: assets.py:12]` |
| `musicstreamer.repo.Repo` + `db_connect` | in-tree | DB writes from worker thread | Worker-thread Repo construction pattern: `Repo(db_connect())` inside the worker. `[VERIFIED: aa_import.py:267]` |
| `musicstreamer.stream_ordering.order_streams` | in-tree | Consumed at playback time, not at import | No direct call needed in `soma_import.py` — just populate `quality` / `codec` / `bitrate_kbps` correctly and `order_streams` does the rest. `[VERIFIED: stream_ordering.py:46]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `urllib.request` | `requests` (transitive via streamlink/yt-dlp) | `requests` is already in the runtime via streamlink, BUT the rest of the importer family is on stdlib urllib. Use urllib for consistency. `[VERIFIED: aa_import.py:13, gbs_api uses urllib too per cite]` |
| Sequential logo downloads | `ThreadPoolExecutor(max_workers=8)` | Sequential: ~40 × ~200ms = ~8 sec just for logos, plus the channels.json fetch. Parallel: ~1-2 sec. **Recommend parallel** to stay under the 5-sec threshold in D-08. `[CITED: aa_import.py:279 precedent]` |
| Reusing `aa_import._resolve_pls` directly | New `soma_import._resolve_pls` wrapper / direct `playlist_parser.parse_playlist` call | Both work. Recommend direct `playlist_parser.parse_playlist` call (skip the helper layer) since SomaFM has no AA-specific quirks to wrap. Saves ~25 LOC. |
| `xlimage` (512×512) for logo | `image` (120×120) or `largeimage` (256×256) | Probed sizes: `image`=8390 B, `largeimage`=41959 B, `xlimage`=144395 B `[VERIFIED: live HEAD probe]`. AA logos are 200-400 B per the same dir convention. Use `image` (smallest); the slot displays at 160px so anything larger is wasted bandwidth. |
| `api.somafm.com/channels.json` | `somafm.com/channels.json` | Both return byte-identical responses (50679 B, same content-type `application/json`) `[VERIFIED: dual live probe 2026-05-13]`. Pick `api.somafm.com` (documented canonical endpoint per `somafm.com/api`). |

**Installation:** No new deps. The relevant `pyproject.toml` section already covers PySide6 + pytest-qt. `[VERIFIED: pyproject.toml:14-22 via STACK.md]`

**Version verification (current versions in tree):**
- PySide6: `>=6.11` (Linux dev), conda-forge ships 6.10.x bundled on Windows `[VERIFIED: STACK.md]`
- pytest: `9.x` (`uv run --with pytest` per project test runner) `[VERIFIED: STACK.md]`
- pytest-qt: `4.x` `[VERIFIED: STACK.md]`

No npm registry check needed — no new packages.

## Architecture Patterns

### System Architecture Diagram

```
User clicks "Import SomaFM" (hamburger)
            │
            ▼
MainWindow._start_soma_import()  ──── show_toast("Importing SomaFM…")
            │
            ▼  (QThread.start)
_SomaImportWorker.run()
            │
            ├─► soma_import.fetch_channels()           (one HTTPS GET, ~50KB)
            │   └─► urllib.urlopen(api.somafm.com/channels.json)
            │   └─► json.loads → list[dict]
            │
            ├─► For each channel dict:
            │   ├─ Map 4 playlists → ≤3 stream rows (hi/med/low)
            │   ├─ Resolve each PLS URL → direct ice*.somafm.com URLs (parallel candidate)
            │   │   └─► playlist_parser.parse_playlist (Phase 58)
            │   ├─ Build streams[] list with (url, quality, position, codec, bitrate_kbps)
            │   └─ Set image_url = ch["image"]   (120×120 PNG)
            │
            └─► soma_import.import_stations(channels, repo)
                │
                For each channel:
                ├─ ANY stream URL in repo.station_streams? → skip channel (skipped+=1)
                ├─ Else:
                │   ├─ repo.insert_station(name, first_url, "SomaFM", "")   # creates 1 stream
                │   ├─ For each stream s in streams[]:
                │   │   ├─ if s.url == first_url: repo.update_stream(...quality/codec/bitrate)
                │   │   └─ else:                  repo.insert_stream(...)
                │   ├─ Append (station_id, image_url) to logo_targets
                │   └─ imported += 1
                │
                ├─ ThreadPoolExecutor(8) → for each (sid, url) in logo_targets:
                │   ├─ urllib.urlopen(image_url, timeout=15)
                │   ├─ tempfile.NamedTemporaryFile(suffix=".png")
                │   ├─ assets.copy_asset_for_station(sid, tmp, "station_art")
                │   └─ Repo(db_connect()).update_station_art(sid, rel_path)
                │
                └─► finished.emit(inserted, skipped)
                                ▼ Qt queued signal
                MainWindow._on_soma_import_done(inserted, skipped)
                    │
                    ├─ if inserted > 0: show_toast(f"SomaFM import: {inserted} stations added")
                    ├─ else:            show_toast("SomaFM import: no changes")
                    ├─ self._refresh_station_list()
                    └─ self._soma_import_worker = None   # release SYNC-05 retention
```

### Recommended Project Structure

```
musicstreamer/
├── soma_import.py            # NEW — mirror aa_import.py shape, narrower
├── aa_import.py              # unchanged — analog reference
├── gbs_api.py                # unchanged — analog reference (single-station shape)
├── playlist_parser.py        # unchanged — used for PLS resolution
├── assets.py                 # unchanged — copy_asset_for_station
├── repo.py                   # unchanged — existing insert/update/exists primitives
├── __main__.py               # 1-line addition at line 234 logger registration
└── ui_qt/
    └── main_window.py        # +50 LOC: _SomaImportWorker class + 3 methods + 1 menu action

tests/
├── test_soma_import.py       # NEW — ~12 tests mirroring tests/test_aa_import.py
├── test_main_window_soma.py  # NEW — ~6 tests mirroring tests/test_main_window_gbs.py
└── fixtures/
    └── soma_channels_3ch.json   # NEW — pruned 3-channel fixture
    └── soma_channels_46ch.json  # OPTIONAL — full real-world fixture (compressed snapshot for regression)
```

### Pattern 1: Catalog-fetcher signature (mirror of `aa_import.fetch_channels_multi`)

**What:** Public module function fetches the canonical catalog and returns a list of channel dicts ready for `import_stations`.
**When to use:** Always. Single entry point, single HTTPS call, exception-on-failure (D-14).
**Example:**

```python
# Source: pattern lifted from musicstreamer/aa_import.py:131-186

# Module-level constants (mirror aa_import._POSITION_MAP / _BITRATE_MAP / _CODEC_MAP)
_API_URL = "https://api.somafm.com/channels.json"
_TIMEOUT_S = 15  # AA uses 15 for catalog fetches; cover_art uses 5. 15 matches AA per D-07.

# SomaFM API exposes 4 playlists per channel; we collapse to 3 tiers (hi/med/low).
# Selection rule: pick MP3-highest as "hi", AAC-highest as "med", aacp-low as "low".
# The aacp-high tier is dropped (D-08 stream-count discipline — avoids 4-stream-per-station bloat).
_TIER_BY_FORMAT_QUALITY = {
    ("mp3",  "highest"): {"quality": "hi",  "position": 11, "codec": "MP3", "bitrate_kbps": 128},
    ("aac",  "highest"): {"quality": "med", "position": 21, "codec": "AAC", "bitrate_kbps": 128},
    ("aacp", "low"):     {"quality": "low", "position": 31, "codec": "AAC", "bitrate_kbps": 32},
}
# Bitrate values are NOMINAL — the actual delivered bitrate depends on the channel
# (some MP3-highest tracks resolve to 128, others to 256/320 — Boot Liquor is 320).
# A future enhancement could parse bitrate from the resolved direct-URL filename
# (e.g. groovesalad-128-mp3 -> 128), but for v1 use the most-common nominal value
# per tier and let order_streams.codec_rank do the tiebreaking.

_USER_AGENT = "MusicStreamer/{version} (https://github.com/lightningjim/MusicStreamer)"

def fetch_channels(timeout: int = _TIMEOUT_S) -> list[dict]:
    """Fetch the SomaFM catalog and return channel dicts ready for import_stations.

    Returns list of dicts:
      {"id": str, "title": str, "description": str, "image_url": str|None,
       "streams": [{"url": str, "quality": str, "position": int,
                    "codec": str, "bitrate_kbps": int}, ...]}
    Raises ValueError("no_channels") when zero channels returned.
    Raises urllib.error.URLError / json.JSONDecodeError on transport / parse failure
    (caller (worker run()) converts to user-facing toast per D-14).
    """
    req = urllib.request.Request(_API_URL, headers={"User-Agent": _USER_AGENT_RESOLVED})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    chans = data.get("channels", [])
    if not chans:
        raise ValueError("no_channels")
    out = []
    for ch in chans:
        try:
            streams = _streams_for_channel(ch)
        except Exception as exc:        # D-15: per-channel best-effort
            _log.warning("Skipping SomaFM channel %s: %s", ch.get("id"), exc)
            continue
        if not streams:
            continue
        out.append({
            "id":          ch["id"],
            "title":       ch["title"],
            "description": ch.get("description", ""),
            "image_url":   ch.get("image"),    # 120×120; smaller than xlimage
            "streams":     streams,
        })
    return out
```

### Pattern 2: PLS resolution (lifted from `aa_import._resolve_pls`)

**What:** Convert each SomaFM playlist URL (e.g. `https://api.somafm.com/groovesalad130.pls`) into the direct stream URL(s) (e.g. `https://ice4.somafm.com/groovesalad-128-aac`).
**When to use:** Every playlist URL. **Mandatory for D-05 dedup correctness** — if the user has hand-curated a SomaFM station with `https://ice4.somafm.com/groovesalad-128-aac` and the importer stores `https://api.somafm.com/groovesalad130.pls`, dedup will fail to detect the collision and the user will see two "Groove Salad" entries.
**Note (research finding):** Each SomaFM PLS contains **5 File= entries** (5 ICE relay servers) `[VERIFIED: live probe of groovesalad130.pls 2026-05-13]`. AA PLS files have 2. Phase 74 implementation should pick the FIRST entry only (one direct URL per tier) — taking all 5 inflates stream count from 3 to 15 per station, which mid-stream user-visible failover already handles upstream via the PLS resolution path inside the player.

**Decision needed (planner discretion):** Pick one direct URL per tier (recommend File1 only — matches AA's intra-tier failover behavior because the player picks the first non-failing). **OR** take all 5 and use position-within-tier as the tiebreaker (matches AA gap-06 "primary + fallback" pattern, but inflates stream count 5×). Recommend FIRST-ONLY for v1; user can re-import to pick up more if SomaFM ever drops a relay.

```python
# Source: musicstreamer/aa_import.py:23-47 (Phase 58 D-10)

def _resolve_pls_first(pls_url: str, timeout: int = 10) -> str | None:
    """Resolve a SomaFM PLS to its first direct stream URL. None on failure.

    Mirrors aa_import._resolve_pls but returns a single URL not a list.
    Falls back to None (caller skips the tier) instead of returning pls_url itself
    so that dedup-by-URL never matches a playlist URL against a direct URL.
    """
    try:
        with urllib.request.urlopen(pls_url, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
        from musicstreamer.playlist_parser import parse_playlist
        entries = parse_playlist(body, content_type=content_type, url_hint=pls_url)
        if entries:
            return entries[0]["url"]
    except Exception:    # noqa: BLE001
        _log.warning("Failed to resolve SomaFM PLS %s", pls_url)
    return None
```

### Pattern 3: Importer (mirror of `aa_import.import_stations_multi`)

**What:** Iterate channels, dedup-by-URL, insert station + streams + log, fire logo downloads.
**When to use:** Once per import click.
**Example:** Lift `aa_import.import_stations_multi` verbatim, removing `on_logo_progress` callback (no progress bar per D-08).

```python
# Source: musicstreamer/aa_import.py:189-290

def import_stations(channels: list[dict], repo, on_progress=None) -> tuple[int, int]:
    """Import SomaFM channels. Returns (inserted, skipped).

    D-05 / D-09: Skip channel if ANY stream URL already exists (any provider).
    D-10:        Atomic per-channel insert (station + ALL streams + logo).
    D-11:        Logo failure is non-fatal.
    D-15:        Per-channel exceptions skip THAT channel; do not abort.
    """
    imported = 0
    skipped = 0
    logo_targets = []      # (station_id, image_url)
    for ch in channels:
        try:
            if not ch.get("streams"):
                skipped += 1
                continue
            if any(repo.station_exists_by_url(s["url"]) for s in ch["streams"]):
                skipped += 1
                continue
            first_url = ch["streams"][0]["url"]
            station_id = repo.insert_station(
                name=ch["title"], url=first_url,
                provider_name="SomaFM", tags="",      # D-02: provider name pin
            )
            for s in ch["streams"]:
                if s["url"] == first_url:
                    rows = repo.list_streams(station_id)
                    if rows:
                        repo.update_stream(rows[0].id, s["url"], "",
                                           s["quality"], s["position"],
                                           "shoutcast", s["codec"],
                                           bitrate_kbps=s["bitrate_kbps"])
                else:
                    repo.insert_stream(station_id, s["url"], label="",
                                       quality=s["quality"], position=s["position"],
                                       stream_type="shoutcast", codec=s["codec"],
                                       bitrate_kbps=s["bitrate_kbps"])
            imported += 1
            if ch.get("image_url"):
                logo_targets.append((station_id, ch["image_url"]))
        except Exception as exc:      # D-15: per-channel best-effort
            _log.warning("SomaFM channel %s import skipped: %s", ch.get("id"), exc)
            skipped += 1
        if on_progress:
            on_progress(imported, skipped)
    _download_logos(logo_targets)     # ThreadPoolExecutor; D-11 non-fatal
    return imported, skipped
```

### Pattern 4: QThread worker + hamburger wiring (mirror of `_GbsImportWorker` at `main_window.py:124-150` + `_on_gbs_add_clicked` at `:1423-1454`)

```python
# Source: musicstreamer/ui_qt/main_window.py:124-150 + :1423-1454

class _SomaImportWorker(QThread):
    """Phase 74 / D-07: kick soma_import.import_stations off the UI thread.

    Mirrors _GbsImportWorker shape (main_window.py:124-150). SYNC-05 retention
    on MainWindow._soma_import_worker prevents mid-run GC.
    """
    finished = Signal(int, int)   # (inserted, skipped)
    error = Signal(str)

    def run(self):
        try:
            from musicstreamer.repo import Repo
            from musicstreamer import soma_import
            channels = soma_import.fetch_channels()
            repo = Repo(db_connect())
            inserted, skipped = soma_import.import_stations(channels, repo)
            self.finished.emit(int(inserted), int(skipped))
        except Exception as exc:
            self.error.emit(str(exc))

# In MainWindow.__init__, after the GBS actions:
act_soma_import = self._menu.addAction("Import SomaFM")
act_soma_import.triggered.connect(self._on_soma_import_clicked)   # QA-05 bound method

# Three methods alongside _on_gbs_add_clicked:
def _on_soma_import_clicked(self) -> None:
    self.show_toast("Importing SomaFM…")
    self._soma_import_worker = _SomaImportWorker(parent=self)   # SYNC-05 retain
    self._soma_import_worker.finished.connect(self._on_soma_import_done)   # QA-05
    self._soma_import_worker.error.connect(self._on_soma_import_error)     # QA-05
    self._soma_import_worker.start()

def _on_soma_import_done(self, inserted: int, skipped: int) -> None:
    if inserted:
        self.show_toast(f"SomaFM import: {inserted} stations added")
    else:
        self.show_toast("SomaFM import: no changes")
    self._refresh_station_list()
    self._soma_import_worker = None

def _on_soma_import_error(self, msg: str) -> None:
    truncated = (msg[:80] + "…") if len(msg) > 80 else msg
    self.show_toast(f"SomaFM import failed: {truncated}")
    self._soma_import_worker = None
```

### Anti-Patterns to Avoid

- **Storing PLS URLs directly instead of resolving them.** Breaks D-05 dedup. Verified live probe shows `api.somafm.com/groovesalad130.pls` ≠ `ice4.somafm.com/groovesalad-128-aac`. The player can technically play PLS (via `playbin3` element auto-detection), but the user's hand-curated SomaFM stations all use direct URLs (per `DEFAULT_SMOKE_URL = "https://ice1.somafm.com/groovesalad-128-mp3"` in `__main__.py:17`).
- **Using `requests` instead of `urllib.request`.** Inconsistent with `aa_import` / `gbs_api` / `radio_browser`. No registry reason to add a dependency we already avoid.
- **Skipping the `User-Agent` header.** Politeness; matches Phase 73 MB protocol literal. The `feedback_gstreamer_mock_blind_spot.md` rule applies — Test #14 below source-greps for the literal `MusicStreamer/` string in `soma_import.py`.
- **Lambda-capturing `self` on `act_soma_import.triggered.connect(...)`.** Violates QA-05 / Pitfall 10. The GBS test `test_no_self_capturing_lambda_in_gbs_action` (`tests/test_main_window_gbs.py:230`) is the template — Phase 74 must add the parallel `test_no_self_capturing_lambda_in_soma_action`.
- **Storing codec as `"AAC+"`.** Breaks `stream_ordering._CODEC_RANK` (only knows `FLAC`/`AAC`/`MP3` per line 21 of `stream_ordering.py`). `aacp` → `"AAC"` per CONTEXT D-08 / Phase 69 WIN-05 closure.
- **Inserting all 5 PLS File= entries as separate streams.** Inflates stream count to 15 per station (5 × 3 tiers). Recommend File1-only per tier (3 streams per station — matches AA's 3-tier discipline).
- **Forgetting `provider_name="SomaFM"` (CamelCase, no space, no period).** Verified canonical capitalization per CONTEXT specifics line 171.
- **Auto-polling channels.json on app startup.** D-04: manual re-import only. No `_check_and_start_soma_poll` analogue.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PLS parsing | Custom `[playlist] / File1=` regex | `musicstreamer.playlist_parser.parse_playlist` | Already handles M3U/M3U8/PLS with content-type sniffing; Phase 58 D-10 lifted this exact concern. `[VERIFIED: aa_import.py:41-46]` |
| Logo download to assets dir | Direct file copy | `musicstreamer.assets.copy_asset_for_station` | Handles per-station-id directory creation, extension preservation, relative-path computation. `[VERIFIED: assets.py:12-27]` |
| Cross-thread DB writes | Sharing one connection across threads | `Repo(db_connect())` per worker | SQLite forbids cross-thread connection sharing; AA logo workers already construct per-thread Repos. `[VERIFIED: aa_import.py:267]` |
| Toast queueing | New widget | `MainWindow.show_toast` | Existing `ToastOverlay` already on the main window. `[VERIFIED: main_window.py:1430 et al]` |
| QThread + cross-thread Signal | Raw `threading.Thread` | `QThread` subclass + typed `Signal` | Phase 60 / `_GbsImportWorker` precedent. Raw `threading.Thread` cannot marshal to Qt main thread via `Signal` per Phase 43.1 SMTC research. `[VERIFIED: main_window.py:124-150]` |
| Bitrate inference from URL filename | Regex on `groovesalad-128-aac` tail | Nominal per-tier constants `_TIER_BY_FORMAT_QUALITY` | URL-tail parsing is **unreliable** — research showed 26/46 channels use bare-id filenames (`7soul.pls`, `groovesalad.pls`) with no bitrate hint, while 20/46 use bitrate-suffixed names (`bootliquor320.pls`). Nominal per-tier constants are the simpler, AA-parity-compatible choice. The actual delivered bitrate (per ICY headers at playback time) is what the buffer-fill indicator surfaces anyway. `[VERIFIED: python analysis of live channels.json 2026-05-13]` |
| AAC+ codec rank | Adding `"AAC+"` to `stream_ordering._CODEC_RANK` | Store `"AAC"` for both `aac` and `aacp` | Phase 69 WIN-05 closure already verified that HE-AAC decodes via the same `aacparse` + `avdec_aac` chain as AAC. The codec field is a sorter input, not a UI literal. `[VERIFIED: stream_ordering.py:21]` |

**Key insight:** Phase 74 is a recombination, not a new mechanism. Almost every primitive (PLS parser, logo copier, repo writes, hamburger handlers, QThread workers, toast surface, codec-aware sort) already exists. The only new code is the SomaFM-specific glue (~250 LOC in `soma_import.py` + ~50 LOC in `main_window.py`).

## Common Pitfalls

### Pitfall 1: Storing PLS URLs in `station_streams.url`

**What goes wrong:** Player attempts to play `https://api.somafm.com/groovesalad130.pls` — GStreamer's playbin3 *can* auto-resolve PLS, but D-05 dedup breaks: a re-import finds the URL in the DB as a PLS URL, even though the user might have a hand-curated entry pointing at the direct `ice4.somafm.com` URL. Result: phantom duplicate channels every re-import.
**Why it happens:** Skipping PLS resolution as a "performance optimization" or because the player happens to play PLS too.
**How to avoid:** Always resolve every PLS via `playlist_parser.parse_playlist`. Test #4 in the validation matrix pins this — fixture asserts the inserted URL is `https://ice4.somafm.com/groovesalad-128-aac`, not the `.pls` URL.
**Warning signs:** Test fixture using `.pls` URLs in expected outputs.

### Pitfall 2: Forgetting D-15 per-channel try/except wrapping

**What goes wrong:** One channel with a malformed `playlists` field crashes the entire import — D-14 fires, no channels are inserted, and the user sees "SomaFM import failed: KeyError: …".
**Why it happens:** Wrapping only `urlopen(channels.json)` in try/except (the D-14 path) without also wrapping each channel iteration (the D-15 path).
**How to avoid:** Two try/except layers — outer for `fetch_channels()` (D-14), inner for the per-channel loop in `import_stations()` (D-15). The AA pattern at `aa_import.py:189-251` does NOT have per-channel try/except — Phase 74 must ADD it explicitly per D-15.
**Warning signs:** Phase 74 with no `try:` inside the `for ch in channels:` loop.

### Pitfall 3: Worker QThread garbage-collected mid-run (SYNC-05)

**What goes wrong:** `_SomaImportWorker` is created as a local variable in `_on_soma_import_clicked`; the method returns; Qt GCs the thread before `run()` completes; `finished` signal never fires.
**Why it happens:** Direct port of "fire-and-forget thread" patterns that work in pure Python but not Qt.
**How to avoid:** Store as `self._soma_import_worker = _SomaImportWorker(parent=self)`. **Always set `parent=self`** for an extra parent-child retention belt-and-suspenders. Set `self._soma_import_worker = None` in both `_on_soma_import_done` and `_on_soma_import_error` to release the reference after the cycle completes.
**Warning signs:** No `self._soma_import_worker` attribute. Phase 60 D-02 `SYNC-05` is the precedent — same root cause repeats across phases.

### Pitfall 4: Lambda capturing `self` in `act_soma_import.triggered.connect(...)`

**What goes wrong:** QA-05 violation — `lambda: self._foo()` capture creates a cycle that breaks across Qt re-parenting; bound method `self._foo` is the correct form.
**Why it happens:** Quick-and-dirty inlined lambdas during scaffolding.
**How to avoid:** Always pass a bound method. Test #10 source-greps the connect line; same pattern as `tests/test_main_window_gbs.py:230-242`.

### Pitfall 5: Inverted codec map (Phase 47 gap-07 history)

**What goes wrong:** Hi tier gets `"AAC"` and med/low get `"MP3"` — inverts `stream_ordering._CODEC_RANK` so med outranks hi at playback time.
**Why it happens:** Mental model "high bitrate = AAC because efficient" inverts ground truth.
**How to avoid:** Pin codec map in module-scope constants AND test the mapping directly. The AA fix at `aa_import.py:125-128` is the regression net — Phase 74 should mirror `_TIER_BY_FORMAT_QUALITY` as a single dict with the SomaFM-specific mapping. Test #14 pins this.

### Pitfall 6: SomaFM's variable `playlists` length

**What goes wrong:** Code assumes 4 playlists always; some channel returns 3 (a hypothetical drop) and `_TIER_BY_FORMAT_QUALITY` lookup misses one tier → station with only 2 streams or `KeyError`.
**Why it happens:** Believing the live-probe sample (46/46 channels with exactly 4 playlists) is a permanent contract.
**How to avoid:** Iterate `ch["playlists"]` and lookup `(format, quality)` — silently skip playlists that don't match a known tier. Resulting station can have 1-3 streams; that's fine. D-11/D-15 reinforce best-effort. Live probe today shows zero drops across 46 channels, but write the code to handle 1-N.
**Warning signs:** Loop indexing `ch["playlists"][0]` / `[1]` / `[2]` instead of dict lookup.

### Pitfall 7: 5-server PLS expansion inflating stream count

**What goes wrong:** Each PLS resolves to 5 ICE-relay URLs; naïvely take all 5 → 15 streams per station × 46 stations = 690 stream rows. Bloats the DB and confuses the stream picker.
**Why it happens:** Lifting AA's gap-06 "primary + fallback" pattern which assumed 2 entries per PLS — SomaFM has 5.
**How to avoid:** Take `entries[0]["url"]` only (`_resolve_pls_first` helper above). Player-level failover already handles ICE-relay rotation when an individual relay goes down.
**Warning signs:** Phase 74 stream count > 3 per station in fixtures.

### Pitfall 8: ChannelId vs channel title in logo filename

**What goes wrong:** Using `ch["title"]` ("Groove Salad") for the logo filename produces `Groove Salad.png` with a space; some filesystems handle this fine but `_download_logo`'s `os.path.splitext` may misparse the extension.
**Why it happens:** Title is human-readable, ID looks "internal" — instinct to use the human field.
**How to avoid:** AA's `_download_logo` uses `station_id` (the SQLite primary key) for the filename, not channel name. Same for SomaFM — `copy_asset_for_station(station_id, ...)` puts the file at `assets/<station_id>/station_art.png` per `assets.py:22`. Don't reinvent the filename rule.

## Runtime State Inventory

> SKIPPED — Phase 74 is greenfield (new module + new tests + new UI entry). No rename/refactor/migration footprint.

The relevant integration points (`provider_name = "SomaFM"`, SQLite rows, `assets/<station_id>/` paths) are all greenfield inserts. No existing data is renamed or migrated. A user who already hand-curated SomaFM stations is protected by D-05 (those rows are preserved untouched).

## Code Examples

### Operation 1: Live channels.json probe — observed shape

```json
{
  "channels": [
    {
      "id":           "groovesalad",
      "title":        "Groove Salad",
      "description":  "A nicely chilled plate of ambient/downtempo beats and grooves.",
      "dj":           "Rusty Hodge",
      "djmail":       "dj@somafm.com",
      "genre":        "ambient|electronic",
      "image":        "https://api.somafm.com/img/groovesalad120.png",
      "largeimage":   "https://api.somafm.com/logos/256/groovesalad256.png",
      "xlimage":      "https://api.somafm.com/logos/512/groovesalad512.png",
      "twitter":      "",
      "updated":      "1382565808",
      "playlists": [
        {"url": "https://api.somafm.com/groovesalad256.pls", "format": "mp3",  "quality": "highest"},
        {"url": "https://api.somafm.com/groovesalad130.pls", "format": "aac",  "quality": "highest"},
        {"url": "https://api.somafm.com/groovesalad64.pls",  "format": "aacp", "quality": "high"},
        {"url": "https://api.somafm.com/groovesalad32.pls",  "format": "aacp", "quality": "low"}
      ],
      "preroll":      [/* 19 m4a URLs — IGNORE, not used */],
      "listeners":    "1444",
      "lastPlaying":  "Sine - Take Me Higher"
    },
    ...
  ]
}
```

Field presence (across all 46 channels, 184 playlists):
- All 12 documented fields present on 46/46 channels (only `featured` is sparse: 6/46).
- Every `playlist` entry has exactly `{url, format, quality}` — no `listeners`, no `bitrate`, no extra keys.
- Format / quality combos: 4 distinct, each appearing exactly 46 times: `(mp3, highest)`, `(aac, highest)`, `(aacp, high)`, `(aacp, low)`.

### Operation 2: PLS resolution shape

```
[playlist]
numberofentries=5
File1=https://ice4.somafm.com/groovesalad-64-aac
Title1=SomaFM: Groove Salad (#1): A nicely chilled plate of ambient/downtempo beats and grooves.
Length1=-1
File2=https://ice6.somafm.com/groovesalad-64-aac
Title2=SomaFM: Groove Salad (#2): A nicely chilled plate of ambient/downtempo beats and grooves.
Length2=-1
...
File5=https://ice3.somafm.com/groovesalad-64-aac
Title5=SomaFM: Groove Salad (#5): A nicely chilled plate of ambient/downtempo beats and grooves.
Length5=-1
Version=2
```

URL convention: `https://ice{1..6}.somafm.com/{channelid}-{bitrate}-{codec}` where `{codec}` is `mp3` or `aac` (NOT `aacp`). The `-{bitrate}-` segment is reliable for direct URLs (unlike PLS URLs, which use a different convention).

### Operation 3: Test scaffold — fixture-driven importer test (mirror `tests/test_aa_import.py`)

```python
# Mirror of test_aa_import.py test patterns. Use monkeypatch on urlopen + a fixture file.

def _urlopen_factory(data: bytes, content_type: str = "application/json"):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    headers_mock = MagicMock()
    headers_mock.get = MagicMock(return_value=content_type)
    cm.headers = headers_mock
    return cm


def test_fetch_channels_maps_three_tiers(monkeypatch, tmp_path):
    """The 4-playlist→3-tier reduction yields hi/med/low with the canonical codec map."""
    fixture = json.dumps({"channels": [{
        "id": "groovesalad", "title": "Groove Salad", "description": "...",
        "image": "https://api.somafm.com/img/groovesalad120.png",
        "playlists": [
            {"url": "https://api.somafm.com/groovesalad256.pls", "format": "mp3",  "quality": "highest"},
            {"url": "https://api.somafm.com/groovesalad130.pls", "format": "aac",  "quality": "highest"},
            {"url": "https://api.somafm.com/groovesalad64.pls",  "format": "aacp", "quality": "high"},
            {"url": "https://api.somafm.com/groovesalad32.pls",  "format": "aacp", "quality": "low"},
        ],
    }]}).encode()
    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture)), \
         patch("musicstreamer.soma_import._resolve_pls_first",
               side_effect=lambda u: u.replace("api.somafm.com/", "ice4.somafm.com/").replace(".pls", "")):
        channels = soma_import.fetch_channels()
    assert len(channels) == 1
    ch = channels[0]
    assert ch["title"] == "Groove Salad"
    qual_by_codec = {s["codec"]: s["quality"] for s in ch["streams"]}
    assert qual_by_codec == {"MP3": "hi", "AAC": "med"} or qual_by_codec == {"MP3": "hi", "AAC": "med"}
    # Adjust based on final 3-tier mapping picked by planner
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-process `dbus-python` for MPRIS2 | `PySide6.QtDBus` | v2.0 Phase 41 | Single Qt-native event loop; no GIL gymnastics |
| `aa_import._resolve_pls` inline regex | Delegate to `musicstreamer.playlist_parser.parse_playlist` | Phase 58 D-10 | Phase 74 reuses the same playlist parser |
| `urllib` per-call without UA | Add UA `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` to outbound calls | Phase 73 (MB/CAA protocol requirement) | Phase 74 inherits the literal as a single shared constant — recommend `musicstreamer.constants.USER_AGENT` if it exists, else duplicate verbatim |
| In-process `requests` for HTTP | Stdlib `urllib.request` for catalog/importer paths | v1.0+ project convention | Phase 74 keeps the convention |
| `playbin` 1.x signals | `playbin3` (Phase 35+) | v2.0 | Phase 74 doesn't touch the player — N/A but worth noting per `feedback_gstreamer_mock_blind_spot.md` |

**Deprecated/outdated:**
- **`aa_import` single-station import path** — superseded by `import_stations_multi` (Phase 47-03). Phase 74 follows `_multi` shape only.
- **String-suffix bitrate inference from URL** — not adopted. SomaFM's URL convention is partially inconsistent (26/46 bare-id, 20/46 bitrate-suffixed for the same MP3-highest tier). Nominal per-tier constants are the standard.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SomaFM `playlists` shape stays at `(mp3, highest) + (aac, highest) + (aacp, high) + (aacp, low)` | Standard Stack / Pattern 1 | Code uses dict-lookup with silent miss → station has fewer streams than expected. Tolerated by D-11/D-15. Low risk. `[ASSUMED based on 1-day live probe]` |
| A2 | Dropping the `(aacp, high) = 64 kbps` tier is acceptable to the user | Pattern 1 `_TIER_BY_FORMAT_QUALITY` | If user wants 4 streams per SomaFM station (parity with raw API), they'll re-import after Plan 01 ships and feedback the planner. The 3-tier rule mirrors AA's hi/med/low discipline. `[ASSUMED]` — planner should surface this as Open Question 1 |
| A3 | `image` (120×120) is the right size for `station_art` (vs `largeimage` 256×256 or `xlimage` 512×512) | Standard Stack / Alternatives Considered | Wrong size → 144kB downloads × 46 = ~7 MB of bandwidth for a 160px slot. The 120px choice matches AA logo dimensionality. `[ASSUMED based on AA convention; verifiable via inspecting one AA logo]` |
| A4 | File1 of each PLS (5 ICE relays) is the right pick (vs taking all 5) | Pattern 2 | Wrong → 15 streams per station instead of 3. AA precedent (gap-06) actually takes BOTH primary+fallback for 2-server PLS. With 5 servers this scales poorly. `[ASSUMED]` — planner should surface as Open Question 2 |
| A5 | The user-agent literal `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` is the canonical form | Pattern 1 / Anti-patterns | Phase 73 codified this; if Phase 73 used a different exact string, Phase 74 should match Phase 73 verbatim. `[ASSUMED based on Phase 73 CONTEXT note + ART-MB-01 requirement at REQUIREMENTS.md:56]` |
| A6 | Plan 01 will register exactly N new SOMA-NN requirements with a sensible Coverage block bump | Phase Requirements | If Plan 01 forgets the bump, the test_requirements_coverage drift-guard fires. Mirror Phase 73's procedure. `[ASSUMED]` |
| A7 | The `id` field on a SomaFM channel is unique and stable | Architecture / dedup | If SomaFM rebrands `groovesalad` → `gs` (or vice-versa), re-import treats them as different channels and inserts a duplicate. Mitigated by D-05 stream-URL dedup since the underlying ICE URLs are also id-based. `[ASSUMED based on 1-day live probe]` |

## Open Questions

1. **Tier-mapping policy: 3 tiers (drop aacp-high) or 4 tiers (keep all)?**
   - What we know: SomaFM emits 4 playlists per channel today. AA emits 3 quality tiers. Existing `stream_ordering._QUALITY_RANK` defines exactly 3 named tiers (`hi`/`med`/`low`).
   - What's unclear: The user's tolerance for non-standard tier names like `"med2"` or `"high"` (a 4-tier scheme would need a fourth bucket).
   - Recommendation: **Ship 3 tiers in v1** (`MP3 highest → hi`, `AAC highest → med`, `aacp low → low`; drop `aacp high`). If UAT flags missing tier, follow-up phase reintroduces. The CONTEXT D-03 wording "Insert all variants the API exposes" technically requires 4; the planner must pick a side and lock it. Quality picks "Claude's Discretion" per CONTEXT — recommend 3-tier with a quick note.

2. **PLS expansion: File1-only or all 5 ICE relays?**
   - What we know: AA PLS files have 2 entries; AA takes both (gap-06). SomaFM PLS files have 5 entries.
   - What's unclear: Whether SomaFM's ICE rotation needs explicit failover stream rows or is handled at the relay level.
   - Recommendation: **File1 only.** Three streams per station (one per quality tier). Player-level failover already handles a single-URL outage by failing to the next quality tier. If UAT shows excessive relay-outage interruptions, a follow-up phase can extend.

3. **Bitrate value when the URL filename gives no hint (26/46 channels)?**
   - What we know: Per-tier nominal constants `128 / 128 / 32` are the simplest answer.
   - What's unclear: Whether the user wants the actual delivered bitrate (e.g. 256 kbps for Boot Liquor's MP3-highest tier) to surface in the now-playing panel or the stream picker.
   - Recommendation: **Use nominal constants** (`hi=128, med=128, low=32`). The buffer-fill indicator + ICY headers already expose the actual bitrate at playback time. URL-tail parsing is brittle (26 channels have no hint at all).

4. **SOMA-NN requirement count?**
   - What we know: Phase 73 introduced 16 ART-MB-NN requirements. Phase 71 introduced 1 SIB-01. Phase 60 introduced ~10 GBS-01a..01e.
   - What's unclear: How many discrete behaviors a planner wants pinned (likely between 6 and 12).
   - Recommendation: **Plan 01 picks 8-10** mapping to: (1) provider-name pin, (2) 3-tier mapping, (3) codec mapping, (4) dedup-by-URL, (5) full-no-op on re-import, (6) logo non-fatal, (7) hamburger entry exists, (8) toast strings verbatim, (9) UA literal, (10) PLS-resolution-before-store.

5. **Endpoint choice: `api.somafm.com` vs `somafm.com`?**
   - What we know: Both return byte-identical 50,679-byte responses with same content-type today (live verified). `api.somafm.com` is the documented endpoint per `somafm.com/api`.
   - What's unclear: Whether SomaFM might EOL one of them.
   - Recommendation: **`api.somafm.com/channels.json`**, as a module-level `_API_URL` constant.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Internet access to `api.somafm.com:443` | `fetch_channels`, all per-channel PLS resolutions, all logo downloads | ✓ (live verified 2026-05-13) | — | None — the entire feature requires it. D-14 abort-on-network-error covers the offline case. |
| `musicstreamer.playlist_parser` | PLS resolution helper | ✓ (in-tree since Phase 58) | n/a | None needed |
| `musicstreamer.assets.copy_asset_for_station` | Logo persistence | ✓ (in-tree) | n/a | None needed |
| Python `urllib.request` + `json` | All HTTP and parsing | ✓ (stdlib) | 3.10+ | None needed |
| `PySide6 >= 6.10` | QThread + Signal | ✓ | 6.10+ on Windows, 6.11+ Linux | None needed |
| `pytest >= 9` + `pytest-qt >= 4` | Tests | ✓ | per `pyproject.toml` | None needed |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-qt 4.x |
| Config file | `pyproject.toml` (project's existing `[tool.pytest.ini_options]`) + `tests/conftest.py` |
| Quick run command | `uv run --with pytest pytest tests/test_soma_import.py tests/test_main_window_soma.py -x` |
| Full suite command | `uv run --with pytest pytest -x` |

### Phase Requirements → Test Map

(`REQ-XX` placeholder rows — Plan 01 will issue real `SOMA-NN` IDs and Plan 02 will write the tests against them. The numbering below is the validation-spec checklist.)

| # | Behavior | Test Type | Automated Command | File Exists? |
|---|----------|-----------|-------------------|-------------|
| 1 | SomaFM API response parsing: fixture-driven test — given a known channels.json blob, the parser produces the expected channel list | unit | `pytest tests/test_soma_import.py::test_fetch_channels_parses_canonical_blob -x` | Wave 0 |
| 2 | Quality tier mapping: 4 playlists `(mp3,highest)+(aac,highest)+(aacp,high)+(aacp,low)` → hi/med/low (or hi/med/low+drop per Open Question 1) | unit | `pytest tests/test_soma_import.py::test_fetch_channels_maps_three_tiers -x` | Wave 0 |
| 3 | Codec inference: `format="aacp"` → `codec="AAC"` (NOT `"AAC+"`) | unit | `pytest tests/test_soma_import.py::test_aacp_codec_maps_to_AAC -x` | Wave 0 |
| 4 | PLS resolution: fixture-driven test of `_resolve_pls_first` returns the first `File1=` direct URL, not the `.pls` URL | unit | `pytest tests/test_soma_import.py::test_resolve_pls_returns_first_direct_url -x` | Wave 0 |
| 5 | Dedup-by-URL: fixture where one channel's stream URL matches an existing station — channel is skipped (skipped=1, imported=0) | unit | `pytest tests/test_soma_import.py::test_import_skips_when_url_exists -x` | Wave 0 |
| 6 | Multi-channel insert: 3-channel fixture → 3 stations inserted + N stream rows + 3 logo download calls | unit | `pytest tests/test_soma_import.py::test_import_three_channels_full_path -x` | Wave 0 |
| 7 | Logo failure non-fatal: monkeypatch logo `urlopen` to raise — station + streams stay inserted; `update_station_art` NOT called | unit | `pytest tests/test_soma_import.py::test_logo_failure_is_non_fatal -x` | Wave 0 |
| 8 | Full no-op on URL match (D-05 true AA parity): re-running import on previously-imported library → inserted=0, skipped=N | unit | `pytest tests/test_soma_import.py::test_reimport_full_noop_on_url_match -x` | Wave 0 |
| 9 | Provider name pin (D-02): every inserted SomaFM station has `provider_name == "SomaFM"` (CamelCase, no space, no period) | unit | `pytest tests/test_soma_import.py::test_provider_name_is_SomaFM -x` | Wave 0 |
| 10 | Hamburger menu wiring (D-06): `"Import SomaFM"` action exists in `MainWindow._menu`; click fires `_on_soma_import_clicked` | qtbot | `pytest tests/test_main_window_soma.py::test_import_soma_menu_entry_exists -x` | Wave 0 |
| 11 | Worker thread retention (Phase 60 SYNC-05): clicking the action sets `self._soma_import_worker` to a non-None `QThread`; clearing happens in done/error slots | qtbot | `pytest tests/test_main_window_soma.py::test_soma_worker_retained_during_run -x` | Wave 0 |
| 12 | Toast format on three cases (D-06 verbatim spec): `"Importing SomaFM…"` (on click), `"SomaFM import: N stations added"` or `"SomaFM import: no changes"` (on finished), `"SomaFM import failed: <truncated>"` (on error) | qtbot | `pytest tests/test_main_window_soma.py::test_import_soma_toasts -x` | Wave 0 |
| 13 | SOMA-NN requirements registered in REQUIREMENTS.md (drift-guard test): file contains each new requirement ID literal | unit (source grep) | `pytest tests/test_requirements_coverage.py::test_soma_nn_requirements_registered -x` | Wave 0 (extend existing test_requirements_coverage if present, else stub) |
| 14 | Codec literal source-grep: no `"AAC+"` or `"aacp"` string appears as a STORED codec field in `soma_import.py` (only `"AAC"`) | unit (source grep) | `pytest tests/test_soma_import.py::test_no_aacplus_codec_literal -x` | Wave 0 |
| 15 | User-Agent literal source-grep (`feedback_gstreamer_mock_blind_spot.md` rule): `MusicStreamer/` AND `https://github.com/lightningjim/MusicStreamer` appear in `soma_import.py` | unit (source grep) | `pytest tests/test_soma_import.py::test_user_agent_literal_present -x` | Wave 0 |
| 16 | QA-05 lambda-ban (mirror `tests/test_main_window_gbs.py:230`): `act_soma_import.triggered.connect(...)` line uses a bound method, not a lambda | unit (source grep) | `pytest tests/test_main_window_soma.py::test_no_self_capturing_lambda_in_soma_action -x` | Wave 0 |
| 17 | Logger registration (D-16): `__main__.py` calls `logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)` | unit (source grep) | `pytest tests/test_constants_drift.py::test_soma_import_logger_registered -x` | Wave 0 (extend existing drift test) |

### Sampling Rate

- **Per task commit:** `uv run --with pytest pytest tests/test_soma_import.py tests/test_main_window_soma.py -x`
- **Per wave merge:** `uv run --with pytest pytest tests/test_soma_import.py tests/test_main_window_soma.py tests/test_aa_import.py tests/test_main_window_gbs.py tests/test_constants_drift.py tests/test_requirements_coverage.py -x` (~80-100 tests, ~30s wall clock)
- **Phase gate:** Full suite `uv run --with pytest pytest -x` (~399 + 17 = ~416 tests; current baseline has 1 pre-existing failure per STATE.md so the gate is "no new failures" not "0 failures total")

### Wave 0 Gaps

- [ ] `tests/test_soma_import.py` — NEW; covers tests 1-9 + 14-15. Lift `_urlopen_factory` + `_make_http_error` helpers verbatim from `tests/test_aa_import.py`.
- [ ] `tests/test_main_window_soma.py` — NEW; covers tests 10-12 + 16. Lift `_FakePlayer` + `_FakeRepo` doubles + `_find_action` helper verbatim from `tests/test_main_window_gbs.py`.
- [ ] `tests/fixtures/soma_channels_3ch.json` — NEW; pruned 3-channel fixture for tests 6 + 8.
- [ ] `tests/fixtures/soma_channels_with_dedup_hit.json` — NEW; fixture whose first channel's stream URL collides with a stub repo row (test 5).
- [ ] Extend `tests/test_requirements_coverage.py` or create `tests/test_soma_requirements_registered.py` — covers test 13.
- [ ] Extend `tests/test_constants_drift.py` for test 17 (Phase 61's drift-guard module is the precedent).
- No framework install needed — pytest + pytest-qt already in tree (`STACK.md` lines 53-54).

## Sources

### Primary (HIGH confidence)
- **Live HTTP probe of `https://api.somafm.com/channels.json`** (2026-05-13) — `[VERIFIED]` HTTP 200, 50,679 bytes, `application/json`, 46 channels, full field shape captured at `/tmp/soma_api.json` for the duration of this session.
- **Live HTTP probe of `https://somafm.com/channels.json`** (2026-05-13) — `[VERIFIED]` Byte-identical to api.somafm.com response.
- **Live HTTP probe of `https://api.somafm.com/groovesalad.pls`** (2026-05-13) — `[VERIFIED]` 5 File= entries, `content-type: audio/x-scpls`.
- **Live HEAD probes of `image` / `largeimage` / `xlimage`** (2026-05-13) — `[VERIFIED]` 8390 / 41959 / 144395 bytes respectively.
- `musicstreamer/aa_import.py` — `[VERIFIED: code read]` THE primary analog; mirror lines 23-47 (`_resolve_pls`), 131-186 (`fetch_channels_multi`), 189-290 (`import_stations_multi`).
- `musicstreamer/gbs_api.py:1118-1170` — `[VERIFIED: code read]` Single-station idempotent import toast pattern.
- `musicstreamer/ui_qt/main_window.py:124-150 + :1420-1465 + :205` — `[VERIFIED: code read]` `_GbsImportWorker` + `_start_gbs_import` + hamburger action wire-up.
- `musicstreamer/stream_ordering.py:1-46` — `[VERIFIED: code read]` `_CODEC_RANK` + `_QUALITY_RANK` + `order_streams`.
- `musicstreamer/__main__.py:228-235` — `[VERIFIED: code read]` Per-logger registration site for D-16.
- `musicstreamer/repo.py:223-253 + 527-543 + 586-591` — `[VERIFIED: code read]` `list_streams`, `insert_stream`, `update_stream`, `station_exists_by_url`, `insert_station`, `update_station_art`.
- `musicstreamer/models.py:11-23` — `[VERIFIED: code read]` `StationStream` dataclass fields.
- `musicstreamer/assets.py:12-27` — `[VERIFIED: code read]` `copy_asset_for_station` signature.
- `tests/test_aa_import.py` — `[VERIFIED: code read]` Template for `tests/test_soma_import.py` (`_urlopen_factory`, `_make_http_error`, fixture-driven test shape).
- `tests/test_main_window_gbs.py:1-243` — `[VERIFIED: code read]` Template for `tests/test_main_window_soma.py` (`_FakePlayer`/`_FakeRepo` doubles, `_find_action`, QA-05 source-grep test).
- `.planning/REQUIREMENTS.md` — `[VERIFIED: full read + targeted greps]` Coverage block at lines 152-155; no `SOMA-NN` or `STATION-ART-NN` IDs currently registered.
- `.planning/codebase/STACK.md` + `INTEGRATIONS.md` — `[VERIFIED: full read]` Confirmed urllib over requests; SQLite + Repo; per-call timeout=10/15 convention.

### Secondary (MEDIUM confidence)
- `MEMORY.md` file `feedback_mirror_decisions_cite_source.md` — `[CITED]` Project rule against paraphrasing source claims; applied to STATION-ART-04 note in this research.
- `MEMORY.md` file `feedback_gstreamer_mock_blind_spot.md` — `[CITED]` Source-grep gates for protocol literals; applied to Tests 14 + 15 in the validation matrix.

### Tertiary (LOW confidence)
- *(none)* — All claims in this research are either backed by a live tool invocation (HTTP probe, file read, grep) or marked `[ASSUMED]` in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — every library + module is already in tree and exercised by `aa_import` / `gbs_api` / Phase 60 GBS UI tests.
- Architecture: **HIGH** — the diagram is a direct recombination of `aa_import.import_stations_multi` (catalog tier) + `_GbsImportWorker` (UI tier); zero novel components.
- Pitfalls: **HIGH** — five of eight pitfalls have explicit Phase-NN gap-closure history (gap-06, gap-07, SYNC-05, QA-05, WIN-05).
- SomaFM API shape: **HIGH** — live probe with full field enumeration at the time of research. A1/A7 assumptions account for the "today's snapshot vs future contract" risk.
- Tier-mapping policy: **MEDIUM** — Open Question 1 is genuinely Claude's-discretion-with-tradeoff; planner picks. Either direction is defensible.
- PLS expansion (File1 vs all 5): **MEDIUM** — Open Question 2; AA precedent (gap-06) is "take all", SomaFM's 5-relay count makes "take all" expensive. Recommend File1.

**Research date:** 2026-05-13
**Valid until:** 2026-06-12 (30 days) for the static portions (architecture, patterns, code primitives). The live channels.json shape (46 channels, 4 playlists each) is point-in-time and SHOULD be re-probed if Phase 74 implementation slips past 2026-06-12 or if SomaFM ships a major catalog update.

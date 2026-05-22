# Phase 83: SomaFM Station Prerolls — Research

**Researched:** 2026-05-22
**Domain:** GStreamer playbin3 gapless preroll → stream transition; SQLite additive schema; SomaFM `/channels.json` extension; Qt+GLib cross-thread marshaling
**Confidence:** HIGH

## Summary

This phase wires a gapless `~5–8s` SomaFM station-ID preroll in front of the actual station stream when the user presses Play on a SomaFM station and the 10-minute global throttle window has elapsed. The decisions in CONTEXT.md (D-01..D-15) lock the shape entirely; the open questions are mechanical (which property to set, which thread fires the signal, how to suppress the preroll's metadata).

All confirmed today against live sources: SomaFM's `api.somafm.com/channels.json` returns **46 channels, 21 with a `preroll[]` array** (45.7% coverage), 100% of preroll URLs are direct `https://somafm.com/prerolls/...` `.m4a` files (no PLS/M3U indirection), the reference Beat Blender clip is **7.99s @ 64kbps stereo 44.1kHz AAC-LC**, and Linux GStreamer 1.28.2 + `souphttpsrc` + `aacparse` + `avdec_aac` already plays SomaFM prerolls cleanly via `gst-launch-1.0`. The PyInstaller Windows bundle ships these same plugins post-Phase 69 (gst-libav).

The CONTEXT.md decision tree leaves three implementation cuts:
1. **About-to-finish marshaling.** Per `qt-glib-bus-threading.md` Rule 2, the signal fires on a GStreamer streaming thread — the handler MUST emit a queued Qt `Signal`, never call `pipeline.set_property("uri", ...)` directly from the callback. The codebase already has this exact pattern (`_try_next_stream_requested` at player.py:263). Reuse a new, narrowly-scoped `_preroll_about_to_finish_requested` Signal that triggers a main-thread method which sets the stream URI through the existing `_set_uri` / `_try_next_stream` path.
2. **Metadata suppression.** `Player._on_gst_tag` (player.py:713) emits `title_changed` for any ICY/m4a TAG message. A boolean `self._preroll_in_flight` flag gated inside `_on_gst_tag` (read-only — flag is set/cleared on the main thread inside `Player.play` and the about-to-finish slot) prevents the preroll's m4a title tag from flickering Now Playing.
3. **Background fetch.** Match the existing `threading.Thread(daemon=True)` pattern used by `_youtube_resolve_worker` and `_twitch_resolve_worker` (Player layer). DB write happens on the worker thread via `Repo(db_connect())` (the same idiom used by `cover_art_mb.py` and `soma_import._download_logos`).

**Primary recommendation:** Build a small `_preroll_*` cluster (one class-level Signal, one in-flight bool, one selection helper) inside `Player`. Reuse `_set_uri` for the actual URI swap. Touch `_on_gst_tag` exactly once to gate the early-return. Touch `_on_youtube_resolved` / `_on_twitch_resolved` zero times — the about-to-finish slot routes through `_try_next_stream()` which already handles YT/Twitch resolution.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `station_prerolls` table — `(id INTEGER PK, station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE, url TEXT NOT NULL, position INTEGER NOT NULL)`. Additive table, mirrors `station_streams` shape.
- **D-02:** `soma_import.fetch_channels()` extended to capture each channel's `preroll[]`. `soma_import.import_stations()` extended to insert one `station_prerolls` row per preroll URL after the station/streams insert succeeds.
- **D-03:** Lazy on-demand backfill for pre-existing SomaFM stations — schema migration leaves `station_prerolls` empty; first play of a SomaFM station with zero stored prerolls AND `prerolls_fetched_at IS NULL` triggers a background fetch. Play does NOT block on the fetch (D-13).
- **D-04:** `stations.prerolls_fetched_at INTEGER NULL` epoch-seconds column distinguishes "fetched, 0 prerolls" from "never fetched" — prevents API hammering for SomaFM stations that genuinely have no prerolls.
- **D-05:** Use playbin3's `about-to-finish` signal for gapless transition. Build `_streams_queue` exactly as today; if preroll gate passes (D-11/D-12), set playbin3 URI to a randomly-selected preroll URL, connect a one-shot `about-to-finish` handler that sets next URI to `_streams_queue[0]`. Disconnect after handoff. Pipeline is then playing the station stream as if `_try_next_stream()` had selected `_streams_queue[0]` directly.
- **D-06:** `_streams_queue` is NOT modified by preroll logic. Preroll URLs never enter the failover queue.
- **D-07:** Now Playing shows station name during preroll. Suppress m4a's title tag. Hook: gate `_on_gst_tag` emissions when `_preroll_in_flight = True`.
- **D-08:** User controls behave normally during preroll. Pause / Stop / Resume work as today; re-pressing Play after Stop re-evaluates the throttle gate.
- **D-09:** Preroll failure → silent skip → `_try_next_stream()` immediately. No retry of a different preroll.
- **D-10:** Station-stream failover after preroll handoff advances normally through `_streams_queue[1..N]`. Preroll never replays during failover recovery.
- **D-11:** Provider gate — `Player.play` consults `station_prerolls` ONLY when `station.provider_name == "SomaFM"` (EXACT literal — CamelCase, no space, no period; matches `soma_import.py:303`).
- **D-12:** Throttle gate — in-memory `self._last_preroll_played_at: float | None = None` on Player. 10-minute window. Timestamp updated when the preroll **starts playing**, not when about-to-finish fires. Resets on app restart.
- **D-13:** Background fetch race — Player.play sees SomaFM station with 0 prerolls + `prerolls_fetched_at IS NULL` → kicks off background fetch, does NOT wait. Current play goes straight to stream.
- **D-14:** 7 behavioral tests + 1 source-grep drift-guard pinning `"SomaFM"` literal AND a preroll-selection token. Drift-guard asserts on URI / `_streams_queue` state, NOT on `pipeline.emit` (per MEMORY: `feedback_gstreamer_mock_blind_spot.md`).
- **D-15:** Schema migration — SQLite `user_version` bump style (idempotent CREATE TABLE + ALTER TABLE) in `musicstreamer/repo.py` `db_init()`. Forward-only, no data rewrite.

### Claude's Discretion

- **Stream-URL extraction inside about-to-finish handler.** Route via marshaled signal → main-thread slot → call `_try_next_stream()` (treating preroll end as synthetic queue-head completion). Mirrors `_try_next_stream_requested` precedent.
- **Random selection algorithm.** `random.choice(list_of_preroll_urls)` from stdlib. No seeding, weighted selection, or "avoid recent repeat" tracking.
- **Preroll URL fetch path.** Direct HTTPS via `souphttpsrc` (playbin3 default); no special source-element selection.
- **Drift-guard literals.** Pin `"SomaFM"` and `_last_preroll_played_at` (and/or `station_prerolls` table name).

### Deferred Ideas (OUT OF SCOPE)

- "Skip preroll" UX affordance — explicitly rejected (D-08).
- Per-station throttle (instead of global) — explicitly rejected (D-12).
- Persisted last-preroll timestamp — explicitly rejected (D-12).
- Weighted / no-repeat random selection — explicitly rejected.
- Replay preroll on first-stream failover — explicitly rejected (D-10).
- Toast / UI surface for preroll fetch failures — explicitly rejected (D-04).
- Generic preroll support for non-SomaFM providers — explicitly rejected (D-11).
- Eager backfill at migration time — explicitly rejected (D-03).
- Periodic background refresh of prerolls — explicitly rejected.
- Integration test that exercises about-to-finish end-to-end with a real m4a — explicitly deferred (GStreamer mock blind spot).
</user_constraints>

<phase_requirements>
## Phase Requirements

Phase 83 was opened via `/gsd:add-phase` rather than from a pre-existing REQ-NN in `REQUIREMENTS.md`. The phase's behavioral truth set is the CONTEXT.md decision matrix (D-01..D-15). No REQ-ID mapping table applies — every locked decision in the User Constraints block above is itself the requirement.

The planner should treat each `D-NN` as a requirement of equal authority to a REQ-NN ID, with the same `must_haves.truths` discipline used in Phase 81 and Phase 82.
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Preroll URL storage | Database (`station_prerolls`) | — | Offline-clean — no network at play time (D-01). |
| `stations.prerolls_fetched_at` epoch marker | Database | Migration | Schema bump, additive nullable column (D-04, D-15). |
| Capture preroll URLs at import time | `soma_import.fetch_channels` + `import_stations` | Repo write methods | Mirror existing per-stream insert pattern with per-channel try/except wrapper (D-02). |
| Random preroll selection | Player layer (`random.choice`) | — | Pure stdlib; seedable for testing if needed (Claude's discretion). |
| Provider gate (`"SomaFM"` literal check) | Player layer | — | Inside `Player.play`; same chokepoint as Phase 82's `preferred_stream_id` lookup (D-11). |
| Throttle gate (in-memory 10-min window) | Player layer (`self._last_preroll_played_at`) | — | Global, instance-state, resets on app restart (D-12). |
| Preroll → stream gapless handoff | playbin3 `about-to-finish` signal | Queued Qt Signal → main thread → `_try_next_stream()` | GStreamer streaming-thread handler MUST marshal to main per qt-glib-bus-threading.md Rule 2 (D-05). |
| Suppress preroll's title-tag emission | `Player._on_gst_tag` early-return on `self._preroll_in_flight` | `title_changed` signal | Single read site; flag set/cleared on main thread (D-07). |
| On-demand SomaFM backfill | `threading.Thread(daemon=True)` worker (matches `_youtube_resolve_worker` precedent) | `Repo(db_connect())` thread-local connection (matches `_download_logos` precedent) | Player layer kicks fetch; fetch writes to a fresh sqlite3 connection it owns (D-13). |
| Failover after preroll | Existing `_try_next_stream` path (unchanged) | — | Preroll is consumed for this `Player.play()` call; failover recovery state machine sees only station streams (D-10). |
| MPRIS / SMTC metadata during preroll | `MainWindow._on_title_changed_for_media_keys` (no change required) | Indirect via D-07 title suppression | The bridge already reads from `Player.title_changed`; suppressing the title emit at source means MPRIS/SMTC inherit the station-name fallback automatically. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GStreamer | 1.28.2 (Linux apt); 1.28+ (Windows conda-forge) | playbin3 pipeline, `about-to-finish` signal, gapless URI switching | Already the project's audio pipeline (player.py:297); `about-to-finish` is the canonical signal for gapless playback per official docs. |
| Python stdlib `random` | (built-in) | `random.choice` for preroll URL selection | CONTEXT.md Claude's Discretion: "No need for seeding, weighted selection, or avoid-recent-repeat." |
| Python stdlib `threading` | (built-in) | Daemon worker for on-demand SomaFM backfill | Matches `_youtube_resolve_worker` / `_twitch_resolve_worker` precedent. |
| Python stdlib `time` | (built-in) | `time.monotonic()` for the throttle window | Monotonic clock immune to wall-clock skew; same idiom as existing `_failover_timer` cadence. |
| SQLite (via stdlib `sqlite3`) | 3.x | New `station_prerolls` table + `prerolls_fetched_at` column | Same DB as everything else; ON DELETE CASCADE mirrors `station_streams` (Phase 47). |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `urllib.request` | stdlib | SomaFM API fetch for lazy backfill | Already used by `soma_import.fetch_channels` — reuse the existing `fetch_channels` function. |
| PySide6 `QObject` / `Signal` | 6.10+ | Queued cross-thread marshaling from streaming thread → main | Already in use throughout `Player` (`_try_next_stream_requested`, `_cancel_timers_requested`, etc.). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `random.choice` | `ORDER BY RANDOM() LIMIT 1` (SQL-side) | SQL-side is one less round trip but harder to seed in tests. CONTEXT.md Discretion explicitly endorses `random.choice`. Recommendation: **`random.choice` on Python side**, after `repo.list_prerolls(station_id) -> list[str]` returns URLs in `position` order. Tests can `monkeypatch.setattr("musicstreamer.player.random.choice", lambda urls: urls[0])` to pin a deterministic pick. |
| `threading.Thread` for backfill | `QThread`, `QThreadPool.globalInstance()` | Existing Player resolver workers (`_youtube_resolve_worker`, `_twitch_resolve_worker`) use `threading.Thread(daemon=True)` — same lifetime requirements (kick and forget; result drives a queued Qt Signal). `QThread` is reserved for the UI layer (ImportDialog workers, DiscoveryDialog workers). **Use `threading.Thread`** for parity with Player precedent. |
| New `_preroll_about_to_finish_requested` signal | Reuse `_try_next_stream_requested` | Reusing the existing signal is tempting but conflates two distinct semantic events ("preroll handed off cleanly" vs "stream failed, advance queue"). Failover and the about-to-finish path have different state-machine implications for `_is_first_attempt` and the elapsed timer. **Add a dedicated signal** — three lines of code, zero semantic ambiguity. |
| `playbin3.set_property("next-uri", ...)` | `playbin3.set_property("uri", ...)` from about-to-finish handler | The `next-uri` property exists on playbin3 but is **not** the canonical pattern for the `about-to-finish` signal handler. The canonical pattern (per GStreamer docs and the `eurion.net` playbin2 example carried forward to playbin3) is `player.set_property("uri", next_uri)` inside the handler. The newer `instant-uri` property is for **mid-track switching without state changes** — not the preroll → EOS → stream transition we want. **Use `uri`** from a main-thread slot after the queued signal marshals. |
| New `station_prerolls.position` column | Skip the position column | Position column lets us return URLs in stable order even if `random.choice` is replaced or seeded. Cost: 4 bytes per row × ~60 rows. **Keep `position`** per D-01. |

**Installation:** No new pip / npm / system packages. All deps already present.

### Package Legitimacy Audit

**Not applicable.** Phase 83 adds zero new third-party packages. All work uses already-installed `gstreamer1.0`, PySide6, and Python stdlib (`random`, `threading`, `time`, `urllib`, `sqlite3`). The `gstreamer1.0` decoder/plugin set required for m4a playback (`aacparse`, `avdec_aac`, `souphttpsrc`) was already audited and bundled in Phase 69 (Windows) and is the OS-default on Linux.

slopcheck was not run because there are no packages to vet. [VERIFIED: codebase audit — `grep -rn 'import ' musicstreamer/` shows no new dependencies needed]

## Architecture Patterns

### System Architecture Diagram

```
                              User presses Play on a SomaFM station
                                              │
                                              ▼
                              ┌──────────────────────────────────┐
                              │  Player.play(station)            │
                              │  (musicstreamer/player.py:505)   │
                              └─────────────┬────────────────────┘
                                            │
                            ┌───────────────┴──────────────────────┐
                            │ 1) Provider gate: station.provider_  │
                            │    name == "SomaFM"?  (D-11)         │
                            │ 2) Throttle gate: now - _last_pre-   │
                            │    roll_played_at > 600s?  (D-12)    │
                            │ 3) Has prerolls in DB?               │
                            │    -- yes  → branch A                │
                            │    -- no, prerolls_fetched_at NULL   │
                            │            → branch B                │
                            │    -- no, prerolls_fetched_at set    │
                            │            → branch C                │
                            └───────────────┬──────────────────────┘
                                            │
                ┌───────────────────────────┼────────────────────────────────┐
                │ Branch A (preroll plays)  │ Branches B & C                 │
                │                           │ (no preroll this time)         │
                ▼                           ▼                                ▼
   ┌─────────────────────────┐   ┌───────────────────────────┐   ┌────────────────────────┐
   │ random.choice(urls)     │   │ Branch B: kick background │   │ Branch C: do nothing   │
   │ ↓                       │   │ threading.Thread(daemon)  │   │ extra; proceed to      │
   │ _preroll_in_flight=True │   │ → fetch_channels() →      │   │ existing _try_next_    │
   │ _last_preroll_played_at │   │ list_prerolls writes via  │   │ stream() path.         │
   │   = time.monotonic()    │   │ Repo(db_connect()).       │   └────────────────────────┘
   │ ↓                       │   │ Set prerolls_fetched_at   │
   │ build _streams_queue    │   │ = now() AFTER fetch       │
   │ (unchanged; D-06)       │   │ regardless of count.      │
   │ ↓                       │   └────────────┬──────────────┘
   │ _set_uri(preroll_url)   │                │
   │ ↓                       │                ▼
   │ connect handler_id =    │   ┌────────────────────────────┐
   │   _pipeline.connect(    │   │ Proceed to existing _try_  │
   │   "about-to-finish",    │   │ next_stream() path.        │
   │   _on_preroll_atf)      │   └────────────────────────────┘
   └─────────────┬───────────┘
                 │
                 │  ~8s later, playbin3 fires about-to-finish on STREAMING thread
                 ▼
   ┌─────────────────────────────┐
   │ _on_preroll_atf(pipeline)   │   ← runs on GStreamer streaming thread (NOT main)
   │ self._preroll_about_to_     │     -- must only emit a queued Signal
   │   finish_requested.emit()   │
   └─────────────┬───────────────┘
                 │
                 │  QueuedConnection marshals to main thread
                 ▼
   ┌─────────────────────────────────┐
   │ _on_preroll_about_to_finish     │   ← main thread
   │ (slot)                          │
   │ ─ disconnect handler_id         │
   │ ─ _preroll_in_flight = False    │
   │ ─ _try_next_stream()            │   ← existing path; handles YT/Twitch resolve too
   └─────────────────────────────────┘
                 │
                 ▼
            station stream plays (gapless — playbin3 has pre-rolled it via uridecodebin3)
```

Failure paths:
- Preroll bus error → `_on_gst_error` → existing `_error_recovery_requested.emit()` → `_handle_gst_error_recovery` → state guard: if `_preroll_in_flight`, disconnect handler + clear flag + call `_try_next_stream()` directly (D-09).
- Preroll EOS arrives before about-to-finish (e.g. malformed clip with no padding) → playbin3 emits EOS via bus; handle in `_on_gst_error` or a new `_on_gst_eos` (need to verify whether the project already handles EOS — see Open Q3 below).

### Recommended Project Structure

No new modules. Edits land in:
```
musicstreamer/
├── player.py            # ~50-line block inside Player.play + 3 new methods + 1 new Signal
├── repo.py              # 3 new methods (insert_preroll, list_prerolls, set_prerolls_fetched_at);
│                        # extend Station dataclass build at list_stations/list_favorite_stations/
│                        # get_station/list_recently_played; bump db_init with the new table
│                        # + ALTER TABLE for prerolls_fetched_at
├── models.py            # Add prerolls_fetched_at: Optional[int] = None to Station
├── soma_import.py       # Extend fetch_channels to capture preroll[]; extend import_stations
│                        # to insert station_prerolls rows + set prerolls_fetched_at=now()
└── (no UI changes)
tests/
├── test_player.py       # +7 behavioral tests, +1 source-grep drift-guard (D-14)
├── test_soma_import.py  # +tests for import-time preroll capture
└── test_repo.py         # +tests for migration + new methods
```

### Pattern 1: Queued Cross-Thread Signal for Streaming-Thread Callback (qt-glib-bus-threading Rule 2)

**What:** GStreamer signal handlers fire on the streaming thread. Bus handlers fire on the GstBusLoopThread. Both are non-QThread contexts. They MUST NOT call Qt methods or set playbin3 properties directly — they MUST emit a Qt `Signal` that has a `QueuedConnection` to a main-thread slot.

**When to use:** Every callback connected to a GStreamer signal or bus message handler.

**Example (verbatim from player.py:251-263 — existing precedent):**

```python
# Worker threads (twitch/youtube resolve) have no Qt event loop, so
# QTimer.singleShot(0, ...) from those threads posts to a nonexistent loop
# and the callback never runs. Queued signal marshals _try_next_stream
# onto the main thread -- same pattern as _cancel_timers_requested.
_try_next_stream_requested = Signal()        # worker → main: advance failover queue
```

And the wiring (player.py:404-405):

```python
self._try_next_stream_requested.connect(
    self._try_next_stream, Qt.ConnectionType.QueuedConnection
)
```

**For Phase 83**, add a sibling Signal:

```python
# Phase 83 / D-05: playbin3 about-to-finish fires on the GStreamer streaming
# thread. Cannot set playbin3 properties directly from that callback (per
# qt-glib-bus-threading.md Rule 2). Marshal to main via queued Signal, then
# route through _try_next_stream() to play _streams_queue[0].
_preroll_about_to_finish_requested = Signal()
```

And in `__init__`:

```python
self._preroll_about_to_finish_requested.connect(
    self._on_preroll_about_to_finish, Qt.ConnectionType.QueuedConnection
)
```

### Pattern 2: Per-Phase Boolean State Flag Read at a Single Choke-Point

**What:** A single `self._preroll_in_flight: bool = False` field, set on the main thread inside `Player.play` and cleared in the main-thread `_on_preroll_about_to_finish` slot. Read once inside `_on_gst_tag` to early-return when True.

**When to use:** D-07 metadata suppression.

**Example (the new gate to add at player.py:713):**

```python
def _on_gst_tag(self, bus, msg) -> None:
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    # Audio arrived -- cancel failover timer on the main thread via queued
    # signal. Bus-loop thread has no Qt event loop, so singleShot vanishes.
    self._cancel_timers_requested.emit()
    if not found:
        return
    # Phase 83 / D-07: suppress preroll's m4a title tag so Now Playing
    # keeps showing the station name through the ~5-8s ID. The flag is
    # set on the main thread in Player.play (before set_uri to the
    # preroll URL) and cleared in _on_preroll_about_to_finish (also
    # main thread). This read is a "cross-thread plain read" — Python
    # bool read is atomic; the worst case is a one-frame race where the
    # flag flips between read and emit, which is acceptable since the
    # only consequence is one suppressed/leaked title tick.
    if self._preroll_in_flight:
        return
    title = _fix_icy_encoding(value)
    self.title_changed.emit(title)  # auto-queued cross-thread to main
```

### Pattern 3: Source-Grep Drift-Guard (Phase 51/55/61/63/81/82 precedent)

**What:** A pytest test that reads a source file, strips comment lines, and asserts a literal substring is present. Pins critical magic strings so they can't disappear in a silent refactor.

**Example template (mirror Phase 82's `test_preferred_stream_id_drift_guard`):**

```python
def test_phase_83_preroll_drift_guard():
    """Phase 83 D-11 / D-14 drift-guard. Pins:
      - the provider-gate literal '"SomaFM"' in Player.play
      - the preroll-selection state token '_last_preroll_played_at'
    Mirrors Phase 51/55/61/63/81/82 idiom.  Non-comment filter is
    REQUIRED so a comment line cannot satisfy the assertion.
    """
    from pathlib import Path
    source = (
        Path(__file__).resolve().parent.parent / "musicstreamer" / "player.py"
    ).read_text()
    non_comments = "\n".join(
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    )
    assert '"SomaFM"' in non_comments, (
        "Phase 83 D-11: provider gate literal must remain in Player.play. "
        "Do not remove silently."
    )
    assert "_last_preroll_played_at" in non_comments, (
        "Phase 83 D-12: throttle-state token must remain in Player. "
        "Do not remove silently."
    )
```

### Pattern 4: Thread-local Repo for DB Writes from Worker Threads

**What:** SQLite connections cannot be shared across threads. Worker threads must open their own `sqlite3.Connection` via `db_connect()` and wrap it in `Repo(con)` for the duration of the write, then `con.close()` it.

**When to use:** D-13's on-demand backfill writes to `station_prerolls` from a non-main thread.

**Example (verbatim from `soma_import._download_logo` at soma_import.py:398-402 — existing precedent):**

```python
con = db_connect()
try:
    Repo(con).update_station_art(station_id, art_path)
finally:
    con.close()
```

For Phase 83 backfill worker:

```python
def _preroll_backfill_worker(self, station_id: int, slug: str) -> None:
    """Daemon worker (D-13): fetch SomaFM channels.json, locate the channel
    by SomaFM id == station-slug, insert station_prerolls rows + set
    prerolls_fetched_at = epoch_now. Silent on all failures (D-04).
    """
    from musicstreamer.soma_import import fetch_channels
    import time
    try:
        channels = fetch_channels()  # already used in soma_import path
        match = next((c for c in channels if c["id"] == slug), None)
        prerolls = match.get("preroll", []) if match else []
        con = db_connect()
        try:
            repo = Repo(con)
            for pos, url in enumerate(prerolls, start=1):
                repo.insert_preroll(station_id, url, pos)
            repo.set_prerolls_fetched_at(station_id, int(time.time()))
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001 — D-04 silent failure path
        _log.warning("Preroll backfill failed for station %d: %s", station_id, exc)
```

### Anti-Patterns to Avoid

- **Setting `_pipeline.set_property("uri", ...)` directly inside the about-to-finish callback.** This crashes / silently corrupts state because the callback runs on a GStreamer streaming thread that has no Qt event loop. ALWAYS marshal via queued Signal. (per qt-glib-bus-threading.md Rule 2; player.py file-level comment at line 248-263)
- **Asserting on `pipeline.emit(...)` invocations in tests.** Per MEMORY `feedback_gstreamer_mock_blind_spot.md`: pipeline mocks pass through any `emit()` call without ever firing the connected handlers. Tests MUST assert on `_streams_queue` / `_current_stream` / observable URI-set call args.
- **Reusing `_try_next_stream_requested` instead of adding `_preroll_about_to_finish_requested`.** Conflates failover with successful gapless handoff — different state implications for `_is_first_attempt`, `_recovery_in_flight`, and the elapsed timer.
- **Adding a fresh boolean for every flag instead of one `_preroll_in_flight`.** A second `_preroll_finished` or `_preroll_started` field invites state-machine bugs. One bool. Set in `Player.play` (main thread), cleared in `_on_preroll_about_to_finish` (main thread), read in `_on_gst_tag` (bus-loop thread; atomic Python bool read).
- **Setting `prerolls_fetched_at` only when ≥1 preroll was found.** D-04 explicitly says: set the timestamp on EVERY successful fetch, even one that returned 0 prerolls. Otherwise the throttle gate hammers the API on every Play press for SomaFM stations that genuinely have no prerolls (the MAJORITY — 25 of 46 channels per live audit).
- **Updating `_last_preroll_played_at` from the about-to-finish slot instead of when the preroll starts.** D-12 explicitly says: update at preroll START, not handoff. Otherwise a rapid replay press inside the window during preroll playback could let a second preroll start before the first finishes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gapless audio crossover | Custom GStreamer pipeline graph with a concat or audiomixer element | playbin3's built-in `about-to-finish` signal | playbin3 pre-rolls a second `uridecodebin3` and switches inputs to `playsink` at EOS automatically. This is the project's existing pipeline and the canonical pattern across GStreamer apps. |
| Cross-thread marshaling from GStreamer to Qt | `QTimer.singleShot(0, fn)` from streaming thread | Class-level `Signal()` + `Qt.ConnectionType.QueuedConnection` | `QTimer.singleShot` from a non-QThread silently drops (qt-glib-bus-threading.md Rule 2; Phase 43.1 fix commit `f1333ed`). |
| Random list selection | Hand-rolled `int(time.time()) % len(urls)` or hash-based pick | `random.choice(urls)` | stdlib, ~30+ years of distribution-uniformity testing. CONTEXT.md Discretion endorses. |
| SomaFM channel fetch | New HTTP client + JSON parser | Existing `soma_import.fetch_channels` (extend to include `preroll[]`) | Already has UA, timeout, SSRF-safe scheme check (`_safe_urlopen_request`), per-channel try/except, and 500/4xx distinction. |
| Schema migration tooling | Custom version-table + step-runner | Existing `db_init()` idempotent CREATE TABLE IF NOT EXISTS + try/except sqlite3.OperationalError on ALTER | Project's established pattern (repo.py:148-282); Phase 73 (cover_art_source) and Phase 82 (preferred_stream_id) used this exact shape and shipped clean. |
| Repo write from a worker thread | Pass the main-thread `Repo` instance into the thread | Thread-local `Repo(db_connect())` opened inside the worker, closed in `finally` | `sqlite3.Connection` is thread-bound; sharing across threads silently corrupts WAL state (cover_art_mb.py / soma_import._download_logos / aa_import precedent). |

**Key insight:** This phase has zero greenfield surface. Every required mechanism — gapless transition, cross-thread marshaling, schema migration, daemon HTTP worker, drift-guard — already has a load-bearing project precedent. The work is wiring, not invention.

## Runtime State Inventory

This phase **is not a rename / refactor / migration**. It introduces new state (a new table + a new column) but does not change any existing string, identifier, or registration.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — phase only ADDS rows/columns; no existing rows are renamed or deleted. The new `station_prerolls` table is created empty (D-15); the new `stations.prerolls_fetched_at` column is added nullable. | None. |
| Live service config | None — no OS / daemon / external service config changes. | None. |
| OS-registered state | None — no Task Scheduler, systemd, pm2, launchd, MPRIS registration changes. The MPRIS service name and bus interface (`musicstreamer/media_keys/mpris2.py`) are unchanged. | None. |
| Secrets/env vars | None — no new secrets, no env-var name changes. | None. |
| Build artifacts | None — no `pyproject.toml` version bump beyond the standard per-phase auto-bump; no installed-package rename. The conda-forge Windows bundle continues to ship the same gstreamer plugin set (Phase 69 audit) which already supports the m4a/AAC preroll codec path. | None. |

**Re-import edge case (CONTEXT.md research Q6):** Phase 74's full SomaFM wipe-and-reimport DOES affect prerolls. When `Repo.delete_station(station_id)` fires for a SomaFM station, the new `station_prerolls.station_id FK ... ON DELETE CASCADE` clause (D-01) automatically drops all preroll rows for that station. The re-import then inserts fresh rows via `soma_import.import_stations` (D-02). The `prerolls_fetched_at` column is on `stations`, not `station_prerolls` — so when the old `stations` row is dropped, the column value is dropped with it. The re-import path (now extended per D-02) MUST set `prerolls_fetched_at = int(time.time())` on every newly-inserted SomaFM station, regardless of whether `preroll[]` was empty or had entries. **Confirmation requirement for plan:** the `soma_import.import_stations` extension must include a `repo.set_prerolls_fetched_at(station_id, int(time.time()))` call inside the per-channel try block, after the preroll INSERTs (or after the streams INSERT if `preroll[]` was empty).

## Common Pitfalls

### Pitfall 1: about-to-finish handler fires on streaming thread, not main thread
**What goes wrong:** Calling `self._pipeline.set_property("uri", next_url)` directly inside the `about-to-finish` callback can succeed superficially but leaves the GLib MainContext in an inconsistent state. On Linux the symptom may be subtle (occasional pad linking failure); on Windows the symptom is worse (the bus-loop thread's MainContext is the one playbin3 uses, and calling into Qt or GLib from the wrong thread silently no-ops).
**Why it happens:** GStreamer signal handlers run on whatever thread the element scheduling chose — for `about-to-finish` that's almost always a streaming thread that the application has no QEventLoop / GMainLoop attached to.
**How to avoid:** Class-level `Signal` + QueuedConnection (Pattern 1 above). Reference fix: Phase 43.1 commit `f1333ed`. Reference file-level comment: player.py:248-263.
**Warning signs:** GStreamer log shows `unlock() → stop() → dispose()` cleanup with no error message at the exact moment the preroll ends — that's the silent-drop fingerprint.

### Pitfall 2: m4a TAG message fires AFTER playbin3 has transitioned to the new URI
**What goes wrong:** If `_preroll_in_flight` is cleared BEFORE the m4a's residual tag message is delivered, the preroll's title can briefly leak to Now Playing.
**Why it happens:** GStreamer's tag messages are asynchronous and can lag the actual audio output by hundreds of ms. The bus-loop thread is single-threaded but its queue is FIFO with no relationship to streaming-thread events.
**How to avoid:** Clear `_preroll_in_flight = False` ONLY after the about-to-finish handler fires (i.e. in `_on_preroll_about_to_finish` on the main thread). Then on the about-to-finish slot, also gate on a fresh stream's first ICY tag — which already works correctly because `_set_uri` resets the bus and a new tag message from the station stream is for the new URL anyway. The remaining edge case (m4a tag message arrives after about-to-finish but before the new URI is set) is empirically rare and silently dropped without a regression — the worst case is one frame of the preroll's title showing for ~30ms. Acceptable per D-07's "no UI flicker" intent (not "zero leak").
**Warning signs:** Manual UAT — start Beat Blender → verify title bar shows "Beat Blender" not "BeatBlenderID1" during the preroll.

### Pitfall 3: SomaFM channel slug ≠ station name
**What goes wrong:** The lazy backfill (D-03) looks up the SomaFM channel by `id` — e.g. `"beatblender"`, `"7soul"`, `"brfm"`. The station's `name` field stores the human title — e.g. `"Beat Blender"`, `"Seven Inch Soul"`, `"Black Rock FM"`. There's no stored `slug` column on `stations`.
**Why it happens:** Phase 74 imports use `ch["title"]` for `stations.name` and don't persist `ch["id"]`. The backfill worker needs to recover the slug from the station — but the easiest path is to fetch the full `channels.json` and match by title.
**How to avoid:** Two options:
  1. **Match by title** in the backfill worker: `match = next((c for c in channels if c["title"] == station.name), None)`. Risk: a renamed station can't be matched. Mitigation: D-04 silent failure path covers this — `prerolls_fetched_at` gets set anyway, so we don't keep hammering.
  2. **Derive slug from stream URL slug** — SomaFM stream URLs include the channel slug: `https://ice2.somafm.com/beatblender-128-mp3`. A regex `re.search(r"somafm\.com/([a-z0-9]+)-\d+-(?:mp3|aac|aacp)", url)` recovers it. More robust but adds parsing.
  3. **Recommendation:** Use option 1 (match by title) for simplicity; option 2 as a fallback inside the same try block. The two-step approach keeps the happy path simple while handling renames.
**Warning signs:** A renamed SomaFM station (user manually changed its name in EditStationDialog) never gets a preroll. Detected via the live UAT script in CONTEXT.md "specifics" section — if Beat Blender silently never plays a preroll after the throttle window resets, check whether the user renamed it.

### Pitfall 4: `prerolls_fetched_at` set inside the import per-channel try block can be missed on rollback
**What goes wrong:** Phase 74 wraps the per-channel import in try/except with rollback (delete_station on exception mid-loop). If `set_prerolls_fetched_at` is called BEFORE all preroll INSERTs succeed and a preroll INSERT raises, the rollback deletes the station — but only because of the CASCADE on `station_prerolls.station_id`. The `prerolls_fetched_at` column is on `stations` so it goes away with the station row. So far, fine. BUT if `set_prerolls_fetched_at` is called AFTER the preroll loop and a later step (e.g. logo download enqueue) raises, the column gets set despite the rollback — leaving an orphaned timestamp on the (about-to-be-deleted) station row.
**Why it happens:** Phase 74 `import_stations` per-channel try block currently rolls back via `repo.delete_station(inserted_station_id)`, which CASCADEs to `station_streams` (and now `station_prerolls`). The `inserted_station_id` sentinel is cleared (set to None) BEFORE the logo target append at soma_import.py:339 — which is the boundary marker for "rollback no longer needed."
**How to avoid:** Insert prerolls AND call `set_prerolls_fetched_at` BEFORE the `inserted_station_id = None` sentinel clear at soma_import.py:339. That keeps both writes inside the rollback window.
**Warning signs:** Re-import the SomaFM catalog → check that no `stations.prerolls_fetched_at IS NOT NULL` rows exist with zero matching `station_prerolls` rows where the upstream channel had a non-empty `preroll[]` array. (Empty `preroll[]` channels having `prerolls_fetched_at` set and zero rows is CORRECT and desired.)

### Pitfall 5: random.choice from an empty list raises IndexError
**What goes wrong:** `repo.list_prerolls(station_id)` returns `[]` for the (most common!) case where a SomaFM station has no prerolls. If `Player.play` reaches `random.choice(urls)` without an emptiness check, it raises IndexError mid-play — user sees a crash dialog or silent stall.
**Why it happens:** D-12 throttle gate covers "skip preroll if too recent" but D-03 backfill flow has TWO branches that return empty:
  - Station fetched, channel genuinely has no preroll (Seven Inch Soul, Covers, Deep Space One, etc. — 25 of 46 today)
  - Station never fetched and is now mid-backfill (Branch B)
Both branches return `urls == []`.
**How to avoid:** Guard with `if not urls: return None` BEFORE `random.choice`. The Player.play gate becomes:
```python
if station.provider_name == "SomaFM" and \
   (self._last_preroll_played_at is None or
    time.monotonic() - self._last_preroll_played_at > 600):
    urls = self._repo.list_prerolls(station.id)  # always returns a list
    if urls:
        preroll_url = random.choice(urls)
        self._start_preroll(preroll_url, station)
    elif station.prerolls_fetched_at is None:
        # Lazy backfill (D-03/D-13) — kick worker, do NOT block
        threading.Thread(
            target=self._preroll_backfill_worker,
            args=(station.id, station.name),
            daemon=True,
        ).start()
    # Else: fetched, genuinely empty (D-04 marker) — skip silently
```
**Warning signs:** Behavioral test #4 in D-14 covers this exactly — "SomaFM station with 0 prerolls and `prerolls_fetched_at IS NOT NULL` → no fetch scheduled, play proceeds to stream." Make sure that test asserts NO IndexError is raised.

### Pitfall 6: Player needs a Repo handle (it doesn't have one today)
**What goes wrong:** Phase 70 comment at player.py:422 explicitly says: *"Player does NOT self-connect (no repo handle — Pitfall 9)."* The current Player constructor takes `node_runtime` but no `repo`. To call `repo.list_prerolls(station_id)` and `repo.set_prerolls_fetched_at(...)` and to access the lazy-backfill writer, Player needs DB access.
**Why it happens:** Current architecture pushes DB reads to the caller (MainWindow / EditStationDialog) and passes already-built `Station` dataclasses into `Player.play`. The Station dataclass holds `streams` (eagerly loaded via `list_streams`) but does NOT hold prerolls.
**How to avoid:** Three options:
  1. **Add `prerolls: list[str]` to the Station dataclass** and load them eagerly in `list_stations` / `get_station` etc. — mirrors how `streams` is loaded. CON: every station list query now does an extra DB hit per row even when prerolls aren't needed.
  2. **Inject `Repo` into `Player.__init__`** as a constructor kwarg — opens the door to all repo APIs (BUG-09's persistent underrun-event-counter would benefit too). CON: increases Player's surface area and breaks the current "Player is pipeline-only" boundary.
  3. **Add `prerolls: list[str]` AND `prerolls_fetched_at: Optional[int]` to Station** eagerly loaded. Player needs the timestamp anyway (D-03 gate condition). Backfill worker still gets a fresh Repo via `db_connect()` (Pattern 4) inside the worker — no Player.repo needed for writes.
  3a. **Hybrid (RECOMMENDED):** Option 3 for reads (eager-load via Station dataclass — matches `streams` precedent); Pattern 4 for writes (backfill worker opens its own connection). Player never holds a Repo reference. CON: trivial — extra single-statement query per station fetch (sub-ms on a 100-station library).
**Warning signs:** If the plan introduces `Player.__init__(..., repo: Repo)`, it's enlarging Player beyond its current contract. Hybrid is cleaner.

### Pitfall 7: SomaFM preroll URLs contain URL-encoded spaces in some paths
**What goes wrong:** Some preroll URLs contain literal `%20` (URL-encoded spaces): e.g. `https://somafm.com/prerolls/bootliquor/Boot%20Liquor%20on%20SomaFM.m4a`. Live audit found these on Boot Liquor (`bootliquor`), cliqhop, DEF CON, and other channels.
**Why it happens:** SomaFM stores filenames with spaces; their CDN serves them URL-encoded.
**How to avoid:** Store URLs verbatim from `channels.json` — do NOT decode or normalize. playbin3 + souphttpsrc handles `%20` correctly out of the box. Behavioral test fixture should include at least one `%20`-bearing URL to lock this.
**Warning signs:** A failing playback URL with the `%20` in the URL — likely indicates downstream double-encoding or path normalization.

### Pitfall 8: Source-grep drift-guard test passes trivially when literal is in a comment
**What goes wrong:** `assert '"SomaFM"' in player.read_text()` passes if `"SomaFM"` appears in a comment but has been removed from the Player.play gate.
**Why it happens:** Comments are source-grep-visible.
**How to avoid:** Use Phase 81's idiom — strip comment-only lines before grep:
```python
non_comments = "\n".join(
    ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
)
assert '"SomaFM"' in non_comments
```
**Warning signs:** A drift-guard test that "passes" without the actual code path present.

## Code Examples

### Operation 1: about-to-finish signal connection (one-shot pattern)

```python
# Source: GStreamer canonical pattern (eurion.net snippet for playbin/playbin2/playbin3
# is identical for audio: set_property("uri", next)); MusicStreamer player.py threading rules
# (qt-glib-bus-threading.md Rule 2)
def _start_preroll(self, preroll_url: str, station: Station) -> None:
    """Main-thread call. Wires playbin3 to play `preroll_url`, attaches a
    one-shot about-to-finish handler that schedules the station-stream
    handoff."""
    self._preroll_in_flight = True
    self._last_preroll_played_at = time.monotonic()  # D-12: at preroll START
    # Connect the one-shot handler. handler_id is stored so the slot can
    # disconnect it after firing (otherwise it'd fire again on each subsequent
    # about-to-finish in the station stream's life — playbin3 emits the signal
    # whenever any URI in the queue is about to finish).
    self._preroll_handler_id = self._pipeline.connect(
        "about-to-finish", self._on_preroll_about_to_finish_callback
    )
    self._set_uri(preroll_url)

def _on_preroll_about_to_finish_callback(self, pipeline) -> None:
    """GStreamer streaming-thread callback.  Emit a queued Signal — DO NOT
    touch playbin3 properties directly here (qt-glib-bus-threading.md Rule 2;
    Phase 43.1 Pitfall 2)."""
    self._preroll_about_to_finish_requested.emit()

def _on_preroll_about_to_finish(self) -> None:
    """Main-thread slot. Disconnect the one-shot handler, clear in-flight
    flag, route to _try_next_stream which plays _streams_queue[0] through
    the existing YT/Twitch resolution path if needed."""
    if self._preroll_handler_id:
        try:
            self._pipeline.disconnect(self._preroll_handler_id)
        except (TypeError, RuntimeError):
            pass  # already disconnected (e.g. preroll bus error path)
        self._preroll_handler_id = 0
    self._preroll_in_flight = False
    self._try_next_stream()
```

### Operation 2: Repo additions

```python
# Source: pattern mirrors station_streams insert/list (player.py:351-371)
def insert_preroll(self, station_id: int, url: str, position: int) -> int:
    cur = self.con.execute(
        "INSERT INTO station_prerolls(station_id, url, position) VALUES (?, ?, ?)",
        (station_id, url, position),
    )
    self.con.commit()
    return int(cur.lastrowid)

def list_prerolls(self, station_id: int) -> list[str]:
    """Return preroll URLs for the station in `position` order. Empty list
    if the station has no prerolls (the most common case)."""
    rows = self.con.execute(
        "SELECT url FROM station_prerolls WHERE station_id = ? ORDER BY position",
        (station_id,),
    ).fetchall()
    return [r["url"] for r in rows]

def set_prerolls_fetched_at(self, station_id: int, epoch_seconds: int) -> None:
    """Phase 83 D-04: marks a SomaFM station as 'fetched' so the lazy backfill
    gate doesn't re-fetch. Set on both happy path (>=1 preroll) and 0-preroll
    path so legitimately-empty channels (Seven Inch Soul etc.) don't hammer
    the API on every Play press."""
    self.con.execute(
        "UPDATE stations SET prerolls_fetched_at = ? WHERE id = ?",
        (epoch_seconds, station_id),
    )
    self.con.commit()
```

### Operation 3: migration in db_init

```python
# Source: pattern mirrors Phase 82 D-01/D-08 ALTER block at repo.py:269-282
# Phase 83 D-15 — additive schema for SomaFM prerolls.
try:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS station_prerolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        )
        """
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # table already exists — idempotent

try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN prerolls_fetched_at INTEGER"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent
```

### Operation 4: soma_import.fetch_channels extension (one line)

```python
# Source: soma_import.py:234 — current channel-dict build at the end of the
# per-channel try block.
out.append({
    "id": ch["id"],
    "title": ch["title"],
    "description": ch.get("description", ""),
    "image_url": ch.get("image"),
    "streams": streams,
    "preroll_urls": ch.get("preroll", []),  # Phase 83 D-02
})
```

### Operation 5: soma_import.import_stations extension (inside the per-channel try block, before `inserted_station_id = None`)

```python
# Source: soma_import.py:336-339 — extend BEFORE the inserted_station_id
# rollback sentinel is cleared, so a mid-step exception still triggers
# delete_station + CASCADE on station_prerolls.
imported += 1
# Phase 83 D-02 / D-04: capture prerolls inside the rollback window.
for pos, preroll_url in enumerate(ch.get("preroll_urls", []), start=1):
    repo.insert_preroll(station_id, preroll_url, pos)
# Phase 83 D-04: mark fetched even if preroll_urls was empty.
repo.set_prerolls_fetched_at(station_id, int(time.time()))
# All streams + prerolls inserted — clear the rollback sentinel.
inserted_station_id = None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| playbin (1.x) | playbin3 | GStreamer 1.18+ (stable 2020); MusicStreamer adopted in v2.0 Phase 35–48 (2026-04) | `about-to-finish` API contract is identical between playbin and playbin3 from the application's perspective — the underlying mechanism (pre-rolling a second `uridecodebin3`) is improved but the signal usage is unchanged. |
| Bus signal handlers on Qt main thread by accident | `GstBusLoopThread` + queued Signals (Phase 43.1) | 2026-04-19 (Phase 43.1) | Bus messages now reliably dispatch cross-OS (Windows-specific Qt+GLib MainContext silently-not-iterated bug was the trigger). |
| `QTimer.singleShot(0, fn)` from bus handlers | Class-level `Signal` + `Qt.ConnectionType.QueuedConnection` (Phase 43.1) | 2026-04-19 (Phase 43.1, commit `f1333ed`) | Bus-loop → main marshaling must use Signals, never bare singleShot. **Applies directly to Phase 83's about-to-finish handler.** |

**Deprecated / outdated:**
- ICY-only ad insertion at the stream-server side (the model SomaFM used pre-2010) — not relevant; current SomaFM streams emit only track metadata, station IDs are pre-recorded m4a files. Confirmed via 2026-05-22 live API sample.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The SomaFM `id` field (e.g. `"beatblender"`) is stable enough to use for lazy-backfill channel matching. | Pitfall 3 | If the user renamed a station, the slug-from-URL fallback may also miss. Mitigation: silent failure path (D-04) caps the damage at "no preroll." |
| A2 | playbin3's `about-to-finish` signal fires reliably for short clips (~5-8s). | Architecture / D-05 | If signal doesn't fire on a 5-8s clip, the preroll would EOS without handoff and the user would hear silence until the failover timer or manual intervention. The 7.99s Beat Blender clip was tested with `gst-discoverer-1.0` and reported clean duration metadata, which is a leading indicator that playbin3 will handle it correctly. **NOT yet end-to-end tested with playbin3 in MusicStreamer's actual pipeline** — recommend the plan include a manual UAT step playing Beat Blender on Linux. |
| A3 | The 10-minute throttle window matches user expectations. | D-12 (locked by user) | Locked decision — no risk. |
| A4 | Suppressing the m4a title tag at `_on_gst_tag` is sufficient for D-07 — no other code paths emit the preroll's title. | D-07 / Architecture | Verified: `title_changed` is only emitted from `_on_gst_tag` (player.py:722) and from `_play_youtube` (player.py:1046, station-name fallback). The YT fallback path is unreachable from a SomaFM preroll. MPRIS/SMTC inherits the suppressed signal automatically. **Verified by grep — no other emit sites.** |
| A5 | The Phase 69 / Phase 43 Windows GStreamer bundle includes `aacparse` and `avdec_aac` (gst-libav). | Standard Stack | Phase 69 `tools/check_bundle_plugins.py` explicitly enumerates `REQUIRED_PLUGIN_DLLS = {"gstlibav.dll": ("avdec_aac", "gst-libav"), "gstaudioparsers.dll": ("aacparse", "gst-plugins-good")}`. **Verified via PROJECT.md "Phase 69 complete" entry.** |
| A6 | SomaFM's preroll URLs do not require authentication or special headers. | Architecture | Verified: `gst-launch-1.0 -q souphttpsrc location='https://somafm.com/prerolls/beatblender/BeatBlenderID1.m4a' ! decodebin ! fakesink` exited 0 on Linux 2026-05-22 with no Auth header. SomaFM's same-host (`somafm.com`) policy is well-documented. |
| A7 | `random.choice` is acceptable for selection (uniform distribution; no need for `secrets.choice` since this is not security-sensitive). | Standard Stack / D-Discretion | Locked by user discretion — no risk. |
| A8 | The eager-load Station dataclass extension (Pitfall 6 option 3a) imposes negligible cost. | Pitfall 6 | A library of 200 stations adds 200 single-row lookups (~1ms total) per `list_stations` call. Acceptable. If the cost matters later, switch to JOIN-based aggregate query. |

## Open Questions

1. **Does playbin3 reliably fire `about-to-finish` for ~5-8s clips in MusicStreamer's specific configuration (buffer-duration=10s, buffer-size=10MB, GST_PLAY_FLAG_BUFFERING=0x100)?**
   - What we know: GStreamer's `about-to-finish` is designed to fire just before EOS regardless of clip duration; `gst-discoverer-1.0` reports clean 7.99s duration for the Beat Blender clip.
   - What's unclear: MusicStreamer's pipeline sets `flags |= 0x100` (GST_PLAY_FLAG_BUFFERING) which forces queue2 buffering on. For a small clip (≤ buffer-duration of 10s), the whole clip may fit in the buffer before about-to-finish would normally fire. There's a non-zero chance about-to-finish fires immediately on URI set (right after the buffer fills) rather than near EOS.
   - Recommendation: include in the manual UAT a careful listen for a "jump cut" at the preroll→stream transition; if cleanly gapless, the signal fired correctly. If there's a noticeable pause, investigate dropping the buffer flag for the preroll URI only.

2. **What does playbin3 do if the about-to-finish handler sets `uri` to a YouTube/Twitch URL that requires async resolution?**
   - What we know: D-05's design routes the about-to-finish through `_try_next_stream()`, which already calls `_play_youtube()` / `_play_twitch()` for those URL families — those are non-blocking and emit `youtube_resolved` / `twitch_resolved` queued signals when ready. The new station-stream URI is set via `_set_uri` on the main thread some milliseconds later, NOT inside the about-to-finish handler.
   - What's unclear: playbin3 expects the next URI to be available "right now" when about-to-finish fires (so it can pre-roll). If we don't set it until the resolver returns, playbin3 may stop after EOS rather than continuing gaplessly.
   - Recommendation: this is acceptable per CONTEXT.md D-05's "Claude's discretion" — the worst case is "preroll ends, then a brief silence, then the YT stream starts." That's still better than the current "skip preroll entirely" baseline. Note in plan / VALIDATION as a manual UAT check: SomaFM stations with YouTube secondary streams (rare but possible if user manually edited) — verify behavior matches expectations.

3. **Does the project's bus handler set already cover EOS, or only `error`, `tag`, `buffering`, `state-changed`?**
   - What we know: player.py:334-337 connects `message::error`, `message::tag`, `message::buffering`, `message::state-changed`. No `message::eos` handler.
   - What's unclear: if the preroll URL is malformed (e.g. 0-byte response) and triggers immediate EOS WITHOUT firing about-to-finish first, the pipeline hits EOS and just stops — there's no `_on_gst_eos` handler.
   - Recommendation: this is largely captured by D-09 (preroll bus error → silent skip → `_try_next_stream`). For pure EOS-without-error (which would be very unusual for an HTTP m4a), the same fallback should apply. The plan should ADD a `message::eos` handler if not already present, and gate the EOS path on `_preroll_in_flight` to ensure it routes through `_try_next_stream` rather than just falling silent. **Or:** verify via test that a malformed preroll URL (e.g. `http://localhost:9/nonexistent.m4a`) does in fact trigger `message::error` not `message::eos`. The former is the safer assumption.

4. **Is the `random.choice` selection seed-able for deterministic tests?**
   - What we know: `random.choice` uses the module-level singleton `random.Random()` instance. Tests can do `monkeypatch.setattr(random, "choice", lambda urls: urls[0])` to pin a specific pick.
   - What's unclear: nothing — covered by `monkeypatch`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| GStreamer 1.x | playbin3 pipeline | ✓ | 1.28.2 (Linux apt); 1.28+ (Windows conda-forge) | none — pipeline is core |
| `aacparse` plugin | m4a/AAC preroll demux | ✓ | gst-plugins-good (Linux apt); bundled in PyInstaller (Phase 69) | none — required for D-05 |
| `avdec_aac` plugin | AAC decoding | ✓ | gst-libav (Linux apt); bundled in PyInstaller (Phase 69) | none — required for D-05 |
| `souphttpsrc` plugin | HTTPS preroll fetch | ✓ | gst-plugins-good | none — required for D-05 |
| Python 3.11+ | stdlib `random`, `threading`, `time` | ✓ | 3.13 / 3.14 (per `__pycache__` artifacts) | none |
| SomaFM API (`api.somafm.com`) | D-02 import-time capture + D-03 lazy backfill | ✓ (verified live 2026-05-22) | n/a | D-04 silent-failure path covers downtime |

No missing dependencies. No fallback paths required.

## Validation Architecture

Nyquist validation is `true` in `.planning/config.json`. This section is REQUIRED.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-qt (project standard) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (inline) |
| Quick run command | `uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py -q` |
| Full suite command | `uv run pytest -q --tb=short` |
| Estimated runtime | ~1.5s (quick) · ~22s (full, ~1500+ tests) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-01 | `station_prerolls` table + `prerolls_fetched_at` column exist after migration; idempotent re-init | unit | `uv run pytest tests/test_repo.py -k 'station_prerolls or prerolls_fetched_at' -q` | ✅ |
| D-02 | `fetch_channels` returns `preroll_urls` per channel; `import_stations` inserts `station_prerolls` rows | unit | `uv run pytest tests/test_soma_import.py -k 'preroll' -q` | ✅ |
| D-03 | Background fetch scheduled when `prerolls_fetched_at IS NULL` and 0 prerolls in DB | behavioral | `uv run pytest tests/test_player.py::test_preroll_backfill_scheduled_when_unfetched -q` | ✅ |
| D-04 | `prerolls_fetched_at` set after fetch even when 0 prerolls returned | unit + behavioral | `uv run pytest tests/test_soma_import.py::test_import_sets_prerolls_fetched_at_for_empty_preroll -q` | ✅ |
| D-05 | preroll URI set on playbin3; about-to-finish handler connected; queue built but not yet played | behavioral | `uv run pytest tests/test_player.py::test_preroll_sets_uri_and_connects_handler -q` | ✅ |
| D-06 | `_streams_queue` unchanged by preroll path (no preroll URLs in queue) | behavioral | `uv run pytest tests/test_player.py::test_preroll_does_not_pollute_streams_queue -q` | ✅ |
| D-07 | `title_changed` is NOT emitted while `_preroll_in_flight` (m4a TAG suppressed) | behavioral | `uv run pytest tests/test_player.py::test_title_tag_suppressed_during_preroll -q` | ✅ |
| D-09 | Preroll bus error → `_try_next_stream` invoked; queue advances to `_streams_queue[0]` | behavioral | `uv run pytest tests/test_player.py::test_preroll_bus_error_advances_to_stream -q` | ✅ |
| D-11 | Non-SomaFM station with synthetic preroll rows → preroll path NOT taken | behavioral | `uv run pytest tests/test_player.py::test_non_somafm_provider_bypasses_preroll -q` | ✅ |
| D-12 | Throttle window NOT expired → preroll path NOT taken | behavioral | `uv run pytest tests/test_player.py::test_throttle_window_suppresses_preroll -q` | ✅ |
| D-12 | `_last_preroll_played_at` updated at preroll START (not handoff) | behavioral | `uv run pytest tests/test_player.py::test_throttle_timestamp_set_on_start -q` | ✅ |
| D-13 | Background fetch is non-blocking — play proceeds to stream without waiting | behavioral | `uv run pytest tests/test_player.py::test_backfill_non_blocking -q` | ✅ |
| D-14 (8) | Source-grep drift-guard pins `"SomaFM"` literal AND `_last_preroll_played_at` in non-comment lines of `musicstreamer/player.py` | source-grep | `uv run pytest tests/test_player.py::test_phase_83_preroll_drift_guard -q` | ✅ |
| Manual UAT | Live SomaFM Beat Blender preroll plays then transitions cleanly to deep-house stream; Seven Inch Soul plays without preroll; throttle: replay Beat Blender within 10 min → no preroll; replay after 10 min → preroll again | manual | (Linux Wayland live audio test) | n/a |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py -q` (target: < 2s)
- **Per wave merge:** `uv run pytest -q --tb=short` (full suite ~22s)
- **Phase gate:** Full suite green before `/gsd:verify-work`; manual UAT recorded in HUMAN-UAT.md per Phase 82 precedent.

### Wave 0 Gaps
- [x] `tests/test_player.py` — exists; phase appends 7 behavioral tests + 1 drift-guard
- [x] `tests/test_soma_import.py` — exists; phase appends preroll-capture tests (likely 3-4: preroll_urls in returned dict, insert_preroll called per URL, set_prerolls_fetched_at called for both populated and empty preroll lists, per-channel rollback CASCADEs station_prerolls)
- [x] `tests/test_repo.py` — exists; phase appends migration + new-method tests (insert_preroll, list_prerolls ordering, set_prerolls_fetched_at, CASCADE on delete_station, list_stations carries prerolls_fetched_at and prerolls list)
- [x] Existing pytest-qt fixture infrastructure (conftest.py:13 `QT_QPA_PLATFORM=offscreen`; autouse `_stub_bus_bridge`) — covers all Player tests
- No new test framework, plugin, or fixture file required.

*All test infrastructure exists. No Wave 0 setup needed.*

## Security Domain

`security_enforcement` is not explicitly disabled in `.planning/config.json`, so this section is included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface introduced — SomaFM API is public unauthenticated; preroll URLs are public CDN. |
| V3 Session Management | no | No sessions introduced. |
| V4 Access Control | no | No access-control surface. |
| V5 Input Validation | yes | The SomaFM API response's `preroll[]` array is user-trusted-but-third-party. Validate each URL before INSERT — reject non-HTTP(S) schemes (SSRF mitigation, same as `_safe_urlopen_request` at soma_import.py:96-101). |
| V6 Cryptography | no | No cryptographic operations. |
| V12 File Handling | no | No file uploads, paths, or filesystem operations beyond the existing SQLite DB. |
| V13 API | partial | The SomaFM API consumer code reuses Phase 74's hardened path: HTTPS enforcement, 15s timeout, UA literal, 4xx vs 5xx distinction, per-channel try/except, JSON parsing via stdlib. |

### Known Threat Patterns for {Python + SQLite + GStreamer + HTTPS to public API}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious preroll URL (e.g. `file:///etc/passwd` injected by a MitM that survived TLS) | Tampering | Validate scheme in HTTP(S) via `_safe_urlopen_request` BEFORE persistence; refuse non-HTTP(S) schemes at the insert boundary (mirrors soma_import.py CR-02). The Phase 83 `Repo.insert_preroll` SHOULD also validate the URL scheme — defense in depth. |
| SQL injection via preroll URL | Tampering | Parameterized queries throughout `Repo.insert_preroll` / `list_prerolls` — same as every existing repo method. Verified by code-pattern review. |
| DoS via giant `preroll[]` array (1M entries from a hostile / compromised SomaFM response) | Denial of Service | Cap the per-channel preroll list at 50 entries before INSERT (live API shows max 5 per channel today; 50 is 10× headroom). This is **NEW** for Phase 83 — recommend adding to the plan. |
| Resource exhaustion from background backfill workers (a user rapidly clicking Play on many SomaFM stations with `prerolls_fetched_at IS NULL`) | Denial of Service | The throttle gate (D-12) only fires for the PREROLL itself, not the backfill. A bounded backfill mechanism (e.g. "only one backfill in flight at a time" via a class-level `_backfill_in_flight: set[int]` of station_ids) prevents N concurrent threads hitting `api.somafm.com`. Recommend adding a single-flight guard to the plan. |
| Stale-while-network-error backfill (the worker fails mid-fetch and `prerolls_fetched_at` is never set, leading to repeated backfill attempts on every play) | Information / Availability | D-04 says "set `prerolls_fetched_at = now` on EVERY successful fetch (including 0 returned)." Implementer must take care that `prerolls_fetched_at` is set in the `try` block but only AFTER fetch succeeds — not in `finally`. A network error should leave `prerolls_fetched_at` NULL so the next play retries. This is correct (matches D-04 semantics). |
| Untrusted m4a content triggering a decoder bug | Information / DoS | Limited surface — Linux apt + Windows conda-forge gstreamer plugins are widely-audited. SomaFM is a trusted source. If hostile, the worst case is GStreamer pipeline crash, which the existing `_on_gst_error` / `_handle_gst_error_recovery` path covers (D-09 silent skip). |

**Add to plan:** the per-channel preroll cap (50) and the single-flight backfill guard are new defensive items for Phase 83.

## Sources

### Primary (HIGH confidence)
- `https://api.somafm.com/channels.json` — Live response sampled 2026-05-22; 46 channels, 21 with preroll arrays, all `.m4a` on `somafm.com`. Channel keys: `['description', 'dj', 'djmail', 'genre', 'id', 'image', 'largeimage', 'lastPlaying', 'listeners', 'playlists', 'preroll', 'title', 'twitter', 'updated', 'xlimage']`.
- `gst-discoverer-1.0 https://somafm.com/prerolls/beatblender/BeatBlenderID1.m4a` 2026-05-22 — Duration 0:00:07.994, MPEG-4 AAC, 44.1kHz, 64kbps stereo, 8s clip. Container plays cleanly.
- `gst-launch-1.0 souphttpsrc ! decodebin ! fakesink` 2026-05-22 — exit 0, no errors. Confirms SomaFM preroll plays on Linux GStreamer 1.28.2.
- `gst-inspect-1.0 aacparse / avdec_aac / souphttpsrc` 2026-05-22 — All present on Linux apt; Phase 69 confirms same on Windows conda-forge bundle.
- `musicstreamer/player.py` lines 240-460 — Player class structure, all queued-signal patterns, `_streams_queue` lifecycle, `_set_uri` behavior, bus handler thread rules.
- `musicstreamer/player.py` lines 505-547, 713-722, 972-1145 — `Player.play`, `_on_gst_tag`, `_try_next_stream`, `_play_youtube`, `_play_twitch` — exact lines the phase modifies or works alongside.
- `musicstreamer/soma_import.py` lines 174-368 — `fetch_channels`, `import_stations`, per-channel try/except rollback pattern.
- `musicstreamer/repo.py` lines 88-282, 351-371, 450-580 — schema, `insert_stream`/`list_streams` precedent, `Station` build sites (4: `list_stations`, `get_station`, `list_recently_played`, `list_favorite_stations`).
- `musicstreamer/models.py` lines 26-40 — `Station` dataclass for Phase 83's `prerolls_fetched_at` (and possibly `prerolls`) field addition.
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Definitive project rules for Qt+GLib cross-thread marshaling. Phase 43.1 fix commits `5827062` and `f1333ed`.
- `.planning/phases/82-twitch-only-station-still-tries-to-play-youtube-stream-first/82-02-PLAN.md` — Latest in-project plan precedent for Player.play modification + behavioral tests + source-grep drift-guard. Phase 83 mirrors this structure.
- `.planning/phases/81-station-list-alphabetical-sorting-is-case-sensitive-a-z-then/81-01-PLAN.md` — Earlier source-grep drift-guard idiom (non-comment line filter; verbatim template).

### Secondary (MEDIUM confidence)
- `https://gstreamer.freedesktop.org/documentation/playback/playbin3.html` — Official `about-to-finish` signal docs. Quoted: "This signal is emitted from the context of a GStreamer streaming thread."
- `https://gstreamer.freedesktop.org/documentation/additional/design/playback-gapless.html` — Gapless design doc. Quoted: "Users are still expected to listen to about-to-finish and set the next URI to play back."
- `https://discourse.gstreamer.org/t/gapless-playback-with-playbin3/385` — Community discussion; confirmed audio-only gapless via `about-to-finish + set_property("uri", next)` works reliably (video has format-pair caveats that don't apply to us).
- `https://eurion.net/python-snippets/snippet/Gapless%20playback.html` — Canonical PyGObject example showing `set_property("uri", filename)` from the handler (playbin2; pattern carries to playbin3 unchanged for audio).

### Tertiary (LOW confidence)
- WebSearch results for "playbin3 instant-uri" — newer property exists but is for mid-track switching, NOT for the EOS-driven about-to-finish flow we want. Not used.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every component verified against running system (gst-inspect, live HTTP probe).
- Architecture: HIGH — Player.play modification mirrors Phase 82 exactly; about-to-finish is the canonical GStreamer pattern; cross-thread marshaling has Phase 43.1 precedent + skill anchor.
- Pitfalls: HIGH — every pitfall is anchored to a specific file:line precedent or MEMORY anchor.
- about-to-finish reliability on short m4a clips in MusicStreamer's specific buffer-flagged pipeline: MEDIUM — designed to work; not yet end-to-end tested. Recommended manual UAT step covers it.

**Research date:** 2026-05-22
**Valid until:** 2026-06-22 (30 days — fast-moving project; SomaFM catalog is stable but always verify the `id` of the reference channels at UAT time)

---

## RESEARCH COMPLETE

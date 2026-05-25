# Phase 87: GBS.FM Marquee + Themed-Day Detection — Research

**Researched:** 2026-05-25
**Domain:** GBS.FM marquee polling + themed-day logo detection (QThread + urllib + cookies)
**Confidence:** HIGH for codebase reuse paths; LOW for marquee endpoint (deferred to Plan 87-01 live harvest per D-01/D-10)

## Summary

Phase 87 builds a `GbsMarqueeWorker` that reuses Phase 76's cookies-jar auth (`gbs_api.load_auth_context()` + `gbs_api._open_with_cookies`) to poll a still-to-be-identified gbs.fm endpoint for marquee text and, once per app launch, fetch `logo_3.png` for SHA-256 themed-day detection. The threading shape mirrors `_AaLiveWorker` (now_playing_panel.py:114-139) exactly — `QThread` subclass, typed `Signal` payloads, `QueuedConnection` to main, single-shot `QTimer` owned by the panel rescheduled per cycle.

The roadmap's "QtWebEngine cookie-persistence pattern" framing is wrong (caught in CONTEXT D-07/D-08): Phase 76 shipped a Netscape cookies file at `paths.gbs_cookies_path()` consumed by pure-urllib `_open_with_cookies` — there is NO `gbs_auth.py` module, NO `QWebEngineProfile` in main-process code (verified by `76-VERIFICATION.md` Goal Achievement table + `gbs_api.py:92-113,158-172`). Phase 87 mirrors that pure-urllib shape; the source-grep drift-guard enforces it.

**Primary recommendation:** Sequence plans as (87-01 harvest live fixtures TODAY) → (87-02 parser-lock with researcher-back-from-harvest endpoint constants) → (87-03 GbsMarqueeWorker + cadence) → (87-04 themed-day correlator + logo swap) → (87-05 banner widget + dismissal) → (87-06 source-grep drift-guards + REQUIREMENTS/ROADMAP edits). Module split (a) from CONTEXT discretion: new `musicstreamer/gbs_marquee.py` + new `musicstreamer/ui_qt/announcement_banner.py`.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Plan 87-01 is the harvest plan, fires FIRST today, captures live "da troops" Memorial Day fixtures (logo + raw marquee bytes + canonical logo if available)
- **D-02:** Inline-only harvest, no `/gsd:spike` ceremony — Plan 87-01 directly produces fixtures
- **D-03:** Researcher (this run) consumes harvested fixtures; live gbs.fm probing is deferred to 87-01
- **D-04:** GBS-THEME-06 "3+/5+" literal RELAXED to "structure ships today; entries accrete." `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` with `resolves_phase: 87` + `next_window: 2026-10-31` required at phase close
- **D-05:** Themed logo runtime = in-memory QPixmap only, NEVER to disk. Source-grep drift-guard asserts no `repo.set_setting`, no `open(..., 'w'/'wb')` on logo path, no `pixmap.save`
- **D-06:** Fixture layout `tests/fixtures/gbs_themed_logos/<YYYY-MM-DD>_<slug>.png` + `tests/fixtures/gbs_themed_logos/canonical-<seq>.png` + `tests/fixtures/gbs_marquee/<YYYY-MM-DD>_<seq>.{txt,json}` + MANIFEST.md per directory
- **D-07:** GBS-MARQ-06 rewrite in REQUIREMENTS.md REQUIRED — locks the Phase 76 cookies-jar reuse path (paths.gbs_cookies_path + gbs_api.load_auth_context), NOT a phantom `gbs_auth.py` / `QWebEngineProfile`
- **D-08:** ROADMAP.md Phase 87 Success Criterion #4 edit REQUIRED — drop `GBS_WEB_PROFILE_NAME` / `gbs_auth.py` wording; replace with cookies-jar reuse wording + source-grep drift-guard mention
- **D-09:** Themed-day detection fires ONCE per app session; cached in worker state; unbind→rebind reuses cached result; next app launch re-evaluates from scratch
- **D-10:** Marquee endpoint = researcher-locked. CONTEXT specifies the researcher probes live, but D-01/D-03 redirect this to Plan 87-01 harvest output. Researcher (this run) reports what Phase 60 RESEARCH already documented — Plan 87-01 captures the real bytes; Plan 87-02 locks constants
- **D-11:** Implementation tries `gbs_api.load_auth_context()` first; falls back to anonymous `urllib.request.urlopen` if `load_auth_context()` returns None
- **D-12:** `GBS_THEMED_DAY_KEYWORDS` in `musicstreamer/constants.py` (frozenset literal); detection rule = hash drift AND keyword in FULL marquee text (case-insensitive substring); fallback = hash drift WITHOUT keyword still applies logo + emits `gbs.themed_day.unknown_theme_observed` INFO log via buffer_log
- **D-13:** Marquee parse = split on `|`, first segment is announcement, perpetual segments ignored for banner; FULL marquee text still searched for themed-day keywords (D-12)
- **D-14:** Banner widget = QLabel + `Qt.TextFormat.PlainText` + `wordWrap=True` + first-segment text with internal pipes → `\n`; inline `QPushButton("×")` dismiss; `self._dismissed_announcement_hashes: set[str]` on NowPlayingPanel; in-memory only, NO persistence
- **D-15:** `GbsMarqueeWorker(QThread)` owns its own `QTimer`; started lazily on first GBS bind; torn down only on app exit; urllib calls on worker thread; results via PyQt signals + `Qt.QueuedConnection`
- **D-16:** Cadence state machine — A: GBS bound + playing = 60s; B: GBS bound + not playing = 5min; C: GBS unbound = idle (timer paused). Transitions wired via existing `NowPlayingPanel.bind_station` / `NowPlayingPanel.on_playing_state_changed` paths (see Pitfall #2 below — CONTEXT references `Player.state_changed` / `Player.station_bound` which DO NOT EXIST as signals; the real wiring goes via the panel method surface)
- **D-17:** `self._themed_day_detected_this_session: bool` on worker; first State C→A/B transition fires logo fetch + hash + correlation once; subsequent transitions reuse cached result
- **D-18:** Failures quiet: `gbs.marquee.fetch_failed`, `gbs.marquee.auth_expired`, `gbs.themed_day.logo_fetch_failed` — all WARN to `buffer_log.py` named-logger sink; no toast, no AccountsDialog open; structured key=value, no PII, no marquee body
- **D-19:** No exponential backoff. 60s / 5min cadence regardless of consecutive failures

### Claude's Discretion

- **Module split** — default (a): new `musicstreamer/gbs_marquee.py` + new `musicstreamer/ui_qt/announcement_banner.py`. Researcher concurs — option (a) is mandatory for the source-grep drift-guard cleanliness (one module to audit per `gbs_marquee.py` ban-list)
- **Banner placement** — default: above station name in NowPlayingPanel
- **Dismiss button** — default: `×` Unicode U+00D7
- **Hash function** — default: `hashlib.sha256(...).hexdigest()` (consistent for logo baseline AND announcement-dismissal)
- **Marquee bytes vs str** — default: decode UTF-8 errors=replace at fetch time
- **Fixture metadata** — default: single MANIFEST.md per fixture directory (markdown table)
- **`force_poll()` test affordance** — default: yes, exposes a public method bypassing the timer
- **Banner parenting** — planner's call based on NowPlayingPanel layout shape

### Deferred Ideas (OUT OF SCOPE)

- Themed accent re-tint (GBS-THEME-RETINT — already deferred to v2.3+ in REQUIREMENTS.md)
- Exponential backoff on marquee errors (D-19)
- Persistent banner dismissal in SQLite (D-14)
- Per-session re-detection of themed day on unbind→rebind (D-09/D-17)
- "Force refresh" UI affordance (auto-poll covers it)
- Themed-day hash baseline auto-grow via runtime observation
- Multi-language marquee
- WebSocket / SSE marquee push (Phase 87-02 researcher reports if such a channel exists in harvest)
- Zero-token single-song add (Phase 87b consumes the cookie-persistence pattern)
- YouTube / Twitch channel-avatar work (Phase 89 family)
- Live re-detection on unbind→rebind during one app session

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GBS-THEME-01 | Fetch `logo_3.png` at session start; SHA-256 hash vs baseline | `gbs_api.GBS_STATION_METADATA["logo_url"]` already = `f"{GBS_BASE}/images/logo_3.png"` (gbs_api.py:54); reuse — no new constant. `_open_with_cookies` for fetch (gbs_api.py:158-172). `hashlib.sha256(...).hexdigest()` — stdlib, no existing usage in codebase (verified: grep returned empty), no precedent file to mirror — first use is fine, isolated to gbs_marquee.py |
| GBS-THEME-02 | Hash differs AND marquee keyword match → apply themed logo for session | D-12 keyword set + D-13 full-marquee-text search; D-12 fallback path covers unknown themes |
| GBS-THEME-03 | Themed logo replaces canonical logo in NowPlayingPanel logo slot ONLY (never cover slot, never list row) | Logo slot identifier = `self.logo_label: QLabel` in NowPlayingPanel (now_playing_panel.py:356-360 — `QLabel(self)` + `setFixedSize(180, 180)` + `setAlignment(Qt.AlignCenter)`). Swap path = call existing `_show_station_logo()` precedent (now_playing_panel.py:859) with QPixmap override; OR add a dedicated `set_themed_logo_override(pixmap)` slot. Drift-guard ban-list MUST forbid `self.cover_label` / `cover_slot` references in gbs_marquee.py |
| GBS-THEME-04 | Session-scoped only; no SQLite persistence; reset on next launch | D-05 source-grep drift-guard enforces. Mirrors Phase 84 buffer-events in-memory cache + Phase 67 similar-cache patterns |
| GBS-THEME-05 | No libnotify toast / banner for themed-day detection itself | Verified — no `show_toast` call from the themed-day path. Researcher confirms: the `D-12 unknown_theme_observed` log goes to `buffer_log` sink (file only), NOT MainWindow.show_toast |
| GBS-THEME-06 | Baseline 3+ themed / 5+ non-themed harvested | RELAXED per D-04 — structure ships, entries accrete. `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` required |
| GBS-MARQ-01 | Poll cadence 60s (playing) / 5min (bound but not playing) | D-16 state machine; mirrors `_aa_poll_timer` single-shot rescheduling pattern (now_playing_panel.py:2412-2477) |
| GBS-MARQ-02 | Split on `|`; first segment = changeable announcement; rest ignored | D-13. Researcher will verify the EXACT delimiter from Plan 87-01 fixtures — gbs.fm may use ` | ` (spaces-padded) per PITFALLS.md §Integration Gotchas, not bare `|`. Plan 87-02 locks. |
| GBS-MARQ-03 | Top-of-NowPlayingPanel banner; visible only when GBS bound AND non-empty AND hash differs from dismissed | D-14 widget + visibility predicate; integrated above station name (CONTEXT discretion default) |
| GBS-MARQ-04 | Pipe boundaries preserved as wrap hints; multi-line wrap | D-14 — first-segment text with internal `|` → `\n` + `wordWrap=True` |
| GBS-MARQ-05 | Inline × dismiss; store hash so same banner doesn't reappear until marquee changes | D-14 `self._dismissed_announcement_hashes: set[str]` on NowPlayingPanel; in-memory only |
| GBS-MARQ-06 | Reuse Phase 76 GBS auth via `paths.gbs_cookies_path()` + `gbs_api.load_auth_context()`; NO parallel QtWebEngine session, NO parallel cookies file | **REWRITE REQUIRED PER D-07.** Current REQUIREMENTS.md text (lines 62) cites the phantom `gbs_auth.py` / `QWebEngineProfile` — this Plan-phase MUST rewrite. Researcher provides the verbatim replacement text in §"Pitfall #1" below |
| GBS-MARQ-07 | 10+ marquee samples committed under `tests/fixtures/gbs_marquee/` | Plan 87-01 harvests today + accretes opportunistically; literal "10+" may not hit on day-one (only Memorial Day window is live); RELAXED in spirit alongside GBS-THEME-06 — sample count grows as future polls fire. Researcher notes: synthetic samples (variations on the harvested template) acceptable to reach 10+ for parser robustness testing |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Marquee HTTP fetch | gbs_marquee.py (worker thread) | gbs_api.py (helpers reused) | Pure urllib path, off main thread; mirrors aa_live.py + _AaLiveWorker split |
| Marquee parse (split-on-pipe) | gbs_marquee.py (`parse_marquee`) | — | Pure function, testable without Qt — mirrors aa_live._parse_live_map shape (aa_live.py:68-108) |
| Themed-day SHA-256 + correlate | gbs_marquee.py (`compute_logo_theme`) | constants.py (keyword set) | Pure function on (logo_bytes, marquee_text) — testable |
| Themed-day baseline table | gbs_marquee.py (`GBS_LOGO_BASELINE_HASHES: dict`) | — | Module-level constant; entries from Plan 87-01 harvest |
| QTimer + cadence state machine | gbs_marquee.GbsMarqueeWorker (QThread) | NowPlayingPanel (state transition hooks) | Worker owns timer (D-15); panel calls start/stop on bind transitions, mirroring _aa_poll_timer + start_aa_poll_loop pattern (now_playing_panel.py:2412-2477) |
| Banner widget construction | announcement_banner.py (QWidget) | now_playing_panel.py (parents it) | Separate file for source-grep cleanliness; consistent with edit_station_dialog/discovery_dialog split |
| Banner dismissal-hash set | now_playing_panel.py (`self._dismissed_announcement_hashes`) | — | Instance state on NowPlayingPanel — survives bind/unbind, dies on app exit |
| Themed-logo override in logo slot | now_playing_panel.py (logo_label QPixmap setter) | gbs_marquee.GbsMarqueeWorker emits QPixmap-ready signal | Panel owns logo_label widget; worker provides bytes-decoded QPixmap via Signal(object) |
| Worker thread lifecycle (construct + start + stop) | main_window.py | now_playing_panel.py (cadence hooks) | Mirrors `_aa_live_worker` ownership pattern; MainWindow constructs at app start, NowPlayingPanel drives cadence transitions through worker.set_cadence(state) calls |
| Quiet failure logging | buffer_log.py (existing handler) | gbs_marquee.py (logger=`musicstreamer.gbs_marquee` named) | Per D-18; structured `gbs.marquee.*` / `gbs.themed_day.*` event names |

## Standard Stack

### Core (all stdlib — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` | stdlib | HTTP fetch (marquee + logo) | Project convention — pure urllib, NO requests/httpx [VERIFIED: gbs_api.py:158-172, aa_live.py:124] |
| `http.cookiejar.MozillaCookieJar` | stdlib | Phase 76 cookies-jar loader | `gbs_api.load_auth_context()` returns this exactly [VERIFIED: gbs_api.py:92-113] |
| `hashlib` | stdlib | SHA-256 for logo baseline + announcement dismissal | D-12, GBS-THEME-01. Stdlib. No existing codebase usage (verified — grep returned empty); first use is fine, isolated to gbs_marquee.py |
| `PySide6.QtCore.QThread` | 6.x | Worker thread for blocking urllib | [VERIFIED: now_playing_panel.py:85, 114, 142 — three precedent classes; aa_live equivalent is `_AaLiveWorker` at line 114] |
| `PySide6.QtCore.QTimer` | 6.x | Cadence timer (single-shot rescheduled) | [VERIFIED: now_playing_panel.py:2432-2434 — single-shot rescheduling pattern] |
| `PySide6.QtCore.Signal` | 6.x | Cross-thread payloads | [VERIFIED: now_playing_panel.py:124-125 — `finished = Signal(object)` for dict payload] |
| `PySide6.QtGui.QPixmap` | 6.x | In-memory themed-logo decode | Standard Qt image type; existing usage `_load_scaled_pixmap` at now_playing_panel.py:202 |

### Supporting (existing project modules)

| Module | Purpose | Reuse Site |
|--------|---------|-----------|
| `musicstreamer.gbs_api` | `load_auth_context()` + `_open_with_cookies()` + `GbsAuthExpiredError` | gbs_api.py:92-172 — drop-in for marquee fetch |
| `musicstreamer.paths` | `gbs_cookies_path()` | paths.py:54-60 — sole authoritative path |
| `musicstreamer.buffer_log` | Structured WARN sink (named-logger RotatingFileHandler) | buffer_log.py — pattern reused; install a parallel `gbs_marquee_log.py` OR reuse same handler with named logger `musicstreamer.gbs_marquee` |
| `musicstreamer.constants` | Home for `GBS_THEMED_DAY_KEYWORDS` (D-12) | constants.py — add frozenset constant |

### Alternatives Considered

| Instead of | Could Use | Why Rejected |
|------------|-----------|---------------|
| `QThread` subclass | Qt async HTTP (`QNetworkAccessManager`) | Project-wide convention is urllib + worker thread (aa_live.py, gbs_api.py); a second HTTP idiom would create maintenance debt — see CONTEXT "Specifics" §Worker thread |
| `QtWebEngineProfile` cookie reuse | n/a — DOES NOT EXIST in this codebase | Phase 76 D-04 ladder #3 LOCKED the cookies-file path; the roadmap's framing of a "QtWebEngine cookie-persistence pattern" was based on misreading Phase 76. CONTEXT D-07/D-08 corrects this. PITFALLS.md §Pitfall 14 is REDIRECTED to enforce the cookies-jar reuse, not a non-existent QWebEngineProfile reuse |
| Per-poll re-fetch of `logo_3.png` | Themed-day re-detection on every poll | D-09/D-17 lock once-per-session; rejected because (a) gbs.fm doesn't push mid-day theme changes in any documented case, (b) re-fetching wastes bandwidth, (c) mid-session swap surprises user |
| BeautifulSoup for HTML marquee parse | Plain `html.parser.HTMLParser` (stdlib) | `gbs_api.py` already uses `html.parser.HTMLParser` (gbs_api.py:38, 376, 453, 565, 649) — no bs4 dependency exists. If marquee is JSON, just `json.loads`. Researcher recommends string split first; HTML parsing only if Plan 87-01 reveals embedded marquee in `<marquee>` / data attributes |
| `requests` library | `urllib.request` | NO `requests` in project — `urllib` everywhere |

**Installation:** None — all dependencies already present.

**Version verification:** N/A (stdlib-only + existing PySide6 6.x).

## Package Legitimacy Audit

**Not applicable** — Phase 87 introduces zero new external packages. All dependencies are Python stdlib (`urllib.request`, `http.cookiejar`, `hashlib`, `re`, `json`) or already-installed PySide6 6.x. Skip slopcheck.

## Architecture Patterns

### System Architecture Diagram

```
                ┌────────────────────────────────────────────────────────┐
                │                    Main Thread (Qt)                    │
                │                                                        │
  station bind ─┤  NowPlayingPanel.bind_station(station)                 │
                │       │                                                │
                │       ▼                                                │
                │  if station.provider_name == "GBS.FM":                 │
                │       worker.set_cadence(playing? 60s : 5min)          │
                │       (idempotent; no-op if already in that state)     │
                │                                                        │
                │  else: worker.set_cadence(idle)  ── timer pauses       │
                │                                                        │
                │  ┌─────────── Signals (QueuedConnection) ──────────┐   │
                │  │ themed_logo_ready(QPixmap)  →  set logo_label   │   │
                │  │ marquee_ready(str)           →  banner update   │   │
                │  └──────────────────────────────────────────────────┘   │
                └────────┬─────────────────────────────────────▲─────────┘
                         │                                     │
                         │ worker.set_cadence(...)             │
                         ▼                                     │
                ┌────────────────────────────────────────────────────────┐
                │              gbs_marquee.GbsMarqueeWorker              │
                │                  (QThread, owns QTimer)                │
                │                                                        │
                │  state machine: idle / playing-60s / not-playing-5min  │
                │                                                        │
                │  on first State C→A/B (per-session-once):              │
                │      ┌─ fetch logo_3.png via _open_with_cookies        │
                │      ├─ sha256 → look up GBS_LOGO_BASELINE_HASHES      │
                │      ├─ if drift: correlate with last marquee text     │
                │      └─ emit themed_logo_ready(QPixmap) if themed      │
                │                                                        │
                │  every timer tick:                                     │
                │      ┌─ fetch <marquee endpoint — Plan 87-02 locks>    │
                │      ├─ parse_marquee() → first-segment + full-text    │
                │      └─ emit marquee_ready(first_segment, full_text)   │
                │                                                        │
                │  failures → buffer_log WARN (D-18), no UI surface      │
                └────────┬───────────────────────────────────────────────┘
                         │ urllib.request.urlopen (off main thread)
                         ▼
                ┌────────────────────────────────────────────────────────┐
                │              gbs.fm (vintage Django)                   │
                │                                                        │
                │  GET /images/logo_3.png   (no cookies needed; public)  │
                │  GET <marquee endpoint>   (cookies may matter — TBD)   │
                └────────────────────────────────────────────────────────┘
```

**File-to-implementation mapping** (component responsibilities):

| File | Responsibility |
|------|----------------|
| `musicstreamer/gbs_marquee.py` (NEW) | `GbsMarqueeWorker(QThread)`; `parse_marquee(text) -> (first_seg, full_text)`; `compute_logo_theme(logo_bytes, full_marquee_text) -> ThemeResult`; `GBS_LOGO_BASELINE_HASHES: dict[str, str]` (hash → label) |
| `musicstreamer/ui_qt/announcement_banner.py` (NEW) | `AnnouncementBanner(QWidget)` — QLabel + `×` QPushButton; emits `dismissed(str)` carrying the announcement hash |
| `musicstreamer/constants.py` (EDIT) | Add `GBS_THEMED_DAY_KEYWORDS: frozenset[str]` per D-12 literal |
| `musicstreamer/ui_qt/now_playing_panel.py` (EDIT) | Instantiate `AnnouncementBanner` at top of layout; add `self._dismissed_announcement_hashes: set[str]`; add `set_themed_logo_override(QPixmap)` slot; wire worker signals into the panel |
| `musicstreamer/ui_qt/main_window.py` (EDIT) | Construct `GbsMarqueeWorker`; pass to NowPlayingPanel; tear down on closeEvent (mirror `stop_aa_poll_loop` pattern at main_window.py:754-759) |
| `tests/fixtures/gbs_themed_logos/` (NEW dir) | PNG files + MANIFEST.md |
| `tests/fixtures/gbs_marquee/` (NEW dir) | TXT/JSON snapshots + MANIFEST.md |
| `tests/test_gbs_marquee.py` (NEW) | Unit tests — parser, theme correlator, hash baseline, cadence state machine (no Qt event loop required for pure functions; QTest for cadence) |
| `tests/test_gbs_marquee_drift_guard.py` (NEW) | Source-grep gates: phase-76-auth reuse + themed-logo-never-persists |
| `tests/test_announcement_banner.py` (NEW) | Widget tests: PlainText format, dismiss button emits hash, multi-line pipe wrap |

### Recommended Project Structure (delta)

```
musicstreamer/
├── gbs_marquee.py                          # NEW: worker + parser + correlator + baseline dict
├── ui_qt/
│   ├── announcement_banner.py              # NEW: banner widget
│   ├── now_playing_panel.py                # EDIT: parent banner + wire worker signals
│   └── main_window.py                      # EDIT: construct worker + tear down
└── constants.py                            # EDIT: add GBS_THEMED_DAY_KEYWORDS

tests/
├── fixtures/
│   ├── gbs_themed_logos/                   # NEW dir: harvested PNGs + MANIFEST.md
│   │   ├── 2026-05-25_memorial-day_da-troops.png  # Plan 87-01 harvest
│   │   ├── canonical-001.png                       # Plan 87-01 if available
│   │   └── MANIFEST.md
│   └── gbs_marquee/                        # NEW dir: harvested marquee + MANIFEST.md
│       ├── 2026-05-25_memorial-day_001.{txt|json} # Plan 87-01 harvest
│       └── MANIFEST.md
├── test_gbs_marquee.py                     # NEW
├── test_gbs_marquee_drift_guard.py         # NEW: source-grep enforcement
└── test_announcement_banner.py             # NEW
```

### Pattern 1: QThread worker + typed Signals (closest precedent: `_AaLiveWorker`)

**What:** `QThread` subclass with typed `Signal` payloads; `run()` does the blocking I/O; emissions are queued back to main thread.

**When to use:** Any HTTP poll that must not block the Qt event loop.

**Example** (mirrors aa_live.py / now_playing_panel.py:114-139 directly):

```python
# Source: musicstreamer/ui_qt/now_playing_panel.py:114-139 (verified)
class _AaLiveWorker(QThread):
    """Mirrors _GbsPollWorker shape: typed signals, single-attempt run(), no
    retries (A-04 / A-05 — caller re-attempts on next poll cycle).

    Cross-thread contract: results emit via Signal with QueuedConnection; the
    worker NEVER calls QTimer.singleShot or touches Qt event-loop objects.
    """
    finished = Signal(object)  # dict[str, str] — {channel_key: show_name}
    error = Signal(str)

    def __init__(self, network_slug: str = "di", parent=None):
        super().__init__(parent)
        self._slug = network_slug

    def run(self):
        try:
            from musicstreamer.aa_live import fetch_live_map as _fetch
            live_map = _fetch(self._slug)
            self.finished.emit(live_map)
        except Exception as exc:
            self.error.emit(str(exc))
```

**Phase 87 GbsMarqueeWorker note:** Unlike `_AaLiveWorker` (single-shot per cycle), `GbsMarqueeWorker` is a long-lived QThread that OWNS its QTimer for D-15. This is a key difference — the AA pattern spawns/destroys per poll; Phase 87 keeps one worker alive for the app lifetime. The worker's `run()` is `self.exec_()` (Qt event loop on the thread) so the QTimer signals are delivered to slots on the worker thread. The actual urllib calls happen in `_on_timer_tick()` slots ON the worker thread.

### Pattern 2: Single-shot QTimer with rescheduling (cadence state machine)

**What:** `QTimer(parent).setSingleShot(True)`; `timeout.connect(...)`; in the slot, call `start(interval_ms)` again with the new interval.

**Why not interval-based:** Single-shot lets cadence change mid-cycle without missing/overlapping ticks; mirrors `_aa_poll_timer` semantics (now_playing_panel.py:2432-2434).

**Example** (verified — now_playing_panel.py:2432-2477):

```python
# Source: musicstreamer/ui_qt/now_playing_panel.py:2412-2477 (verified)
def start_aa_poll_loop(self) -> None:
    if not bool(self._repo.get_setting("audioaddict_listen_key", "")):
        return  # B-03: silent skip
    if self._aa_poll_timer is None:
        self._aa_poll_timer = QTimer(self)
        self._aa_poll_timer.setSingleShot(True)
        self._aa_poll_timer.timeout.connect(self._on_aa_poll_tick)  # QA-05
    worker_running = (self._aa_live_worker is not None
                      and self._aa_live_worker.isRunning())
    if self._aa_poll_timer.isActive() or worker_running:
        return  # BL-04: already in a poll cycle
    self._aa_poll_timer.start(0)  # immediate first tick
```

**Phase 87 mapping:** State transitions call `worker.set_cadence(new_state)`; the worker's slot (running on worker thread) reschedules its timer to (60000 / 300000 / paused).

### Pattern 3: urllib + cookie-handler opener (Phase 76 reuse)

**Example** (verified — gbs_api.py:158-172):

```python
# Source: musicstreamer/gbs_api.py:158-172 (verified)
def _open_with_cookies(url: str, cookies: http.cookiejar.MozillaCookieJar,
                      timeout: int = _TIMEOUT_READ):
    """Send GET with cookies; return urlopen response (caller closes via with).

    Raises GbsAuthExpiredError on 302 → /accounts/login/.
    """
    handler = urllib.request.HTTPCookieProcessor(cookies)
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        return opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302) and "/accounts/login/" in (e.headers.get("Location") or ""):
            raise GbsAuthExpiredError(f"Session expired (302→login from {url})") from e
        raise
```

**Phase 87 usage** (sketch — Plan 87-02 will finalize per harvested endpoint):

```python
# In gbs_marquee.py
def _fetch_marquee(cookies) -> str | None:
    """Returns raw marquee text/JSON; None on quiet failure (D-18)."""
    auth = gbs_api.load_auth_context()  # may return None per D-11
    url = MARQUEE_URL  # locked by Plan 87-02 from harvest
    try:
        if auth is not None:
            with gbs_api._open_with_cookies(url, auth, timeout=_TIMEOUT_READ) as resp:
                return resp.read().decode("utf-8", errors="replace")
        else:
            # D-11: anonymous fallback
            with urllib.request.urlopen(url, timeout=_TIMEOUT_READ) as resp:
                return resp.read().decode("utf-8", errors="replace")
    except gbs_api.GbsAuthExpiredError:
        _log.warning("gbs.marquee.auth_expired url=%s", url)
        return None
    except (urllib.error.URLError, OSError) as exc:
        _log.warning("gbs.marquee.fetch_failed url=%s error=%s", url, exc.__class__.__name__)
        return None
```

### Pattern 4: Source-grep drift-guard (closest precedent: `tests/test_fake_player_no_inline.py`)

**Example** (verified — test_fake_player_no_inline.py:17-53):

```python
# Source: tests/test_fake_player_no_inline.py (verified)
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent / "tests"
FAKE_PLAYER_RE = re.compile(r'^\s*class\s+_?FakePlayer\s*\(QObject\)', re.M)
ALLOWED = {"_fake_player.py"}

def test_no_inline_fake_player_subclass_in_tests():
    offenders = []
    for py in sorted(ROOT.rglob("*.py")):
        if py.name in ALLOWED:
            continue
        text = py.read_text(encoding="utf-8")
        if FAKE_PLAYER_RE.search(text):
            offenders.append(str(py.relative_to(ROOT.parent)))
    assert not offenders, ...
```

Also `tests/test_constants_drift.py:48-60` for the rglob + ban-list shape (verified — search for placeholder `org.example.MusicStreamer` across `musicstreamer/`).

**Phase 87 application** (drift-guard sketch):

```python
# tests/test_gbs_marquee_drift_guard.py (NEW)
from pathlib import Path

GBS_MARQUEE_SRC = Path(__file__).parent.parent / "musicstreamer" / "gbs_marquee.py"

def test_marquee_module_reuses_phase76_auth_only():
    """D-07: gbs_marquee.py MUST import from musicstreamer.gbs_api +
    musicstreamer.paths. MUST NOT instantiate QWebEngineProfile, write a
    parallel cookies file, or import oauth_helper.
    """
    src = GBS_MARQUEE_SRC.read_text(encoding="utf-8")
    # Required imports
    assert "from musicstreamer import" in src and "gbs_api" in src, \
        "gbs_marquee.py must import gbs_api (Phase 76 auth reuse)"
    assert "paths" in src, \
        "gbs_marquee.py must reference paths (gbs_cookies_path)"
    # Banned identifiers
    banned = [
        "QWebEngineProfile",          # No parallel WebEngine session
        "QWebEnginePage",
        "GBS_WEB_PROFILE_NAME",       # phantom constant from the old roadmap framing
        "GBS_WEB_STORAGE_PATH",
        "oauth_helper",               # subprocess login is not the marquee fetch path
        "_GbsLoginWindow",
    ]
    for b in banned:
        assert b not in src, f"gbs_marquee.py must not reference {b!r}"

def test_themed_logo_never_persists():
    """D-05: themed-logo path NEVER writes to disk / NEVER hits SQLite."""
    src = GBS_MARQUEE_SRC.read_text(encoding="utf-8")
    banned = [
        "repo.set_setting",           # No SQLite persistence
        "set_station_art",            # Not a station-art write
        ".save(",                     # No pixmap.save / open().save
        "open(",                      # No file open in gbs_marquee.py at all
        # NOTE: if open() proves necessary for fixture loading in tests, restrict
        # this assertion to mode-contains-'w' patterns instead
    ]
    for b in banned:
        assert b not in src, f"gbs_marquee.py must not call {b!r} (themed logo is in-memory only)"
```

**Refinement note for Plan 87-06:** The `"open("` ban is aggressive. If gbs_marquee.py needs to load committed test-baseline-PNG bytes at module-import time (to compute their hashes), that becomes a violation. Recommended: hash the canonical PNGs at test-fixture-commit time and hardcode the SHA-256 strings into `GBS_LOGO_BASELINE_HASHES`. Then `gbs_marquee.py` truly never opens a file.

### Anti-Patterns to Avoid

- **Constructing `QWebEngineProfile` anywhere in `gbs_marquee.py`** — there is NO such object in main-process gbs.fm code; the cookies-jar path is the entire auth surface (Phase 76 D-04/D-06; gbs_api.py:92-113)
- **Writing themed-logo bytes to disk** — D-05 hard-locks this; drift-guard enforces
- **Persisting banner dismissal in SQLite** — D-14 hard-locks this
- **Hammering gbs.fm with retries on transient failure** — D-19 forbids backoff; next-tick cadence IS the retry
- **Emitting `show_toast` from the themed-day path** — D-18 + GBS-THEME-05 lock this
- **Re-fetching `logo_3.png` on every rebind** — D-09/D-17 lock once-per-session
- **Calling `QTimer.singleShot` or `QTimer(parent=self)` FROM the worker's `run()`** — per CONTEXT D-15 + aa_live precedent comment (now_playing_panel.py:121-122): "worker NEVER calls QTimer.singleShot or touches Qt event-loop objects." If the worker needs an event loop for its own timer, use `self.exec_()` in `run()` and construct the timer in a slot that runs on the worker thread
- **Substring-only domain check for cookie file** — the existing `_validate_gbs_cookies` (gbs_api.py:116-153) already uses label-boundary match (`domain == "gbs.fm" or domain.endswith(".gbs.fm")`); Phase 87 reuses this validator if it touches cookies at all (it shouldn't — auth load goes through `load_auth_context()` only)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GBS cookies loading | New `MozillaCookieJar` instantiation | `gbs_api.load_auth_context()` | Already handles corruption check (Phase 999.7), 0o600 perms, label-boundary domain match (gbs_api.py:92-113) |
| GBS authenticated GET | New `urllib.request.build_opener(...)` cookie chain | `gbs_api._open_with_cookies(url, cookies)` | Already raises `GbsAuthExpiredError` on 302→login (gbs_api.py:158-172) |
| Auth-expired exception type | New custom exception | `gbs_api.GbsAuthExpiredError` | Already exists at gbs_api.py:86-87; consistency keeps the catch-and-WARN site uniform |
| Cookies file path | Construct via `os.path.join(...)` | `paths.gbs_cookies_path()` | Single source of truth; survives test monkeypatching via `paths._root_override` (paths.py:54-60) |
| Structured WARN sink | New file handler in gbs_marquee.py | Reuse buffer_log's RotatingFileHandler pattern (or extend buffer_log.py to also cover the marquee logger; planner's call) | buffer_log.py's idempotent install pattern is the convention; second sink with a different filename is acceptable IF planner picks that route |
| QPixmap from PNG bytes | Manual decode | `QPixmap.loadFromData(bytes)` | Stdlib Qt; no extra deps |
| HTML marquee parse (if Plan 87-02 finds HTML, not JSON) | bs4 | `html.parser.HTMLParser` (stdlib) | gbs_api.py:38, 376, 453, 565, 649 already use this pattern — six precedents |
| First-segment hash for dismissal tracking | MD5 / custom hash | `hashlib.sha256(text.encode("utf-8")).hexdigest()` | D-12 + Discretion: SAME function as logo baseline keeps a single hash idiom in gbs_marquee.py |

**Key insight:** Phase 87 is almost entirely about composing existing primitives. The only genuinely new code is (a) the marquee parser (~10 LOC once the delimiter is locked from harvest), (b) the cadence state machine on the worker (~30 LOC), (c) the banner widget (~50 LOC), (d) the themed-day correlator (~20 LOC). Everything else is reuse.

## Runtime State Inventory

**Skip rationale:** Phase 87 is a greenfield feature addition (banner + worker + themed-logo override). No rename, refactor, or migration. No old runtime state to retire. **None — verified greenfield.**

## Common Pitfalls

### Pitfall #1: REQUIREMENTS.md GBS-MARQ-06 cites a phantom `gbs_auth.py` / `QWebEngineProfile` (CONTEXT D-07 mandates rewrite)

**What goes wrong:** Implementer reads GBS-MARQ-06 (REQUIREMENTS.md:62) literally, looks for `musicstreamer/gbs_auth.py`, doesn't find it, gets stuck — OR creates a parallel `QWebEngineProfile` to satisfy the literal text, triggering Pitfall 14 (re-login storm).

**Why it happens:** The roadmap framing was authored before Phase 76 finalized its auth shape. Phase 76 D-04 (ladder #3) actually shipped the cookies-jar path; the `gbs_auth.py` module / `QWebEngineProfile` constants never existed. 76-VERIFICATION.md Goal Achievement table confirms only `paths.gbs_cookies_path()` + `gbs_api.load_auth_context()` shipped.

**How to avoid:** Plan-phase MUST execute D-07 + D-08 in its FIRST plan (or D-08 in 87-06 cleanup plan). The verbatim REQUIREMENTS.md rewrite text (per CONTEXT D-07):

> **GBS-MARQ-06**: The marquee fetcher reuses Phase 76 GBS authenticated session via `paths.gbs_cookies_path()` (cookies-jar file) and `musicstreamer.gbs_api.load_auth_context()` (loader). The marquee module imports these — does NOT construct a `QWebEngineProfile`, does NOT write a parallel cookies file, and does NOT instantiate `oauth_helper`. A source-grep drift-guard test (`test_marquee_module_reuses_phase76_auth_only`) confirms.

ROADMAP.md Phase 87 Success Criterion #4 rewrite (per CONTEXT D-08):

> Marquee fetcher imports `paths.gbs_cookies_path()` + `musicstreamer.gbs_api.load_auth_context()`; source-grep drift-guard confirms no parallel cookie file is written and no QtWebEngine session is instantiated.

**Warning signs:** `grep -rn "QWebEngineProfile" musicstreamer/` returns ANY hit outside `oauth_helper.py` (which is subprocess-only).

### Pitfall #2: CONTEXT D-16 references `Player.state_changed` and `Player.station_bound` signals — neither exists

**What goes wrong:** Planner takes CONTEXT D-16 literally, wires `self._player.state_changed.connect(...)` — Player has no such Signal; AttributeError at app start.

**Why it happens:** D-16 was written aspirationally based on Phase 87's needs, not verified against `musicstreamer/player.py`. Verified via `grep "= Signal" musicstreamer/player.py | head -40`: Player exposes `title_changed`, `failover`, `offline`, `playback_error`, `elapsed_updated`, `buffer_percent`, `buffer_duration_changed`, `audio_caps_detected`, `underrun_count_changed`, etc. There is **no** `state_changed` or `station_bound`.

**How to avoid:** Wire the cadence state machine through the EXISTING MainWindow → NowPlayingPanel surface that already handles AA poll lifecycle (verified — main_window.py:492-499, 682-703, 754-759):

| State transition trigger | Existing call site | Phase 87 hook |
|---------------------------|-------------------|---------------|
| Station bound | `NowPlayingPanel.bind_station(station)` (now_playing_panel.py:837) | Add: if `station.provider_name == "GBS.FM"` → call `worker.set_cadence(...)` based on `self._is_playing` |
| Play / pause / stop | `NowPlayingPanel.on_playing_state_changed(bool)` (now_playing_panel.py:977) | Add: if bound station is GBS.FM → call `worker.set_cadence(playing=is_playing)` |
| Station unbound (different provider bound) | Same `bind_station` call with non-GBS station | Add: call `worker.set_cadence(idle)` |
| App close | `MainWindow.closeEvent` (mirrors main_window.py:754-759 `stop_aa_poll_loop`) | Add: `worker.stop_and_wait()` parallel to `stop_aa_poll_loop` |

The `worker.set_cadence(state)` API is the right abstraction. Internally on the worker thread it pauses/restarts the QTimer with the new interval.

**Warning signs:** First plan reads "wire Player.state_changed" and creates a TODO to find that signal — STOP and reread D-16 with this pitfall.

### Pitfall #3: Marquee endpoint never identified in Phase 60 RESEARCH — Plan 87-01 harvest is the discovery moment

**What goes wrong:** Researcher (this run) is expected to provide a definitive `MARQUEE_URL` constant; Phase 60 RESEARCH (2026-05-04) did NOT probe marquee/announcement/banner/news endpoints (verified: comprehensive grep for `marquee|announce|banner|news|notice|motd|alert|notification` returned only `messages` cookie hits — unrelated to marquee; the Django messages framework is for inline POST-success feedback).

**Why it happens:** Phase 60 scope didn't include marquee — that work was deferred to Phase 87. The DEBUG=True 404 page captured at `/tmp/gbs/django404.html` (per 60-RESEARCH.md:155) exposed ~70 URL patterns but the URLconf snapshot quoted in 60-RESEARCH.md:155-180 contains NO marquee-specific URL. The marquee text might live in:
- (a) **Embedded in the gbs.fm homepage HTML** (`GET /` returns the page that includes the marquee text in a `<marquee>` element or a `<div class="...">` block); 60-RESEARCH.md mentions `home_playlist_table.html` fixture but no marquee snippet was captured
- (b) **A key under `/api/<resource>`** — the URLconf line `^api/(?P<resource>.+)$` is a generic key-value endpoint with verified keys `nowplaying`, `metadata`, `listeners`, `users` (60-RESEARCH.md:474-477). Possible undocumented keys: `/api/marquee`, `/api/announcement`, `/api/news`
- (c) **A separate page like `/news`, `/stats`, `/announcements`** — `/stats` exists per URLconf
- (d) **AJAX endpoint** — `/ajax` event stream might include a `marquee` event name (similar to `now_playing`, `metadata`, `linkedMetadata`); 60-RESEARCH.md event taxonomy at lines 197-219 lists 11 events, none called marquee/announcement

**How to avoid:** Plan 87-01 captures BOTH `GET https://gbs.fm/` (homepage) AND `GET https://gbs.fm/ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0` (cold-start /ajax) as raw bytes. The researcher's follow-up (post-harvest, before 87-02 starts) dissects:

1. `grep -i "da troops\|memorial\|marquee\|announcement"` across the captured bytes
2. Identify the element type (marquee tag, div + class, JSON field, ajax event-name) holding the text
3. If found in homepage HTML: define `MARQUEE_URL = GBS_BASE + "/"` and add a parser (CSS selector or regex)
4. If found via `/ajax`: define `MARQUEE_AJAX_EVENT = "marquee"` (or whatever the event name is) and reuse `_fold_ajax_events` shape from gbs_api.py:262-300
5. If found at a new `/api/<key>` route: define `MARQUEE_URL = GBS_BASE + "/api/<key>"`

**Researcher's pragmatic order of probability** (NOT verified — for harvest sequencing only):

1. **Most likely (~60%):** `/ajax` event stream — Django's `<marquee>` JS variable is typically loaded once at page render but periodically refreshed via the same /ajax cursor that already drives playlist. The marquee being in /ajax explains why it's "live updating" per CONTEXT.
2. **Likely (~25%):** Homepage HTML — embedded in a `<marquee>` HTML element or `<div id="marquee">`. Phase 60 fixture `home_playlist_table.html` captured the playlist table but may have omitted the marquee region.
3. **Possible (~10%):** `/api/<key>` key — gbs.fm exposes plain-text key-value via `/api/<resource>`; an undocumented `marquee` key is plausible.
4. **Unlikely (~5%):** WebSocket / SSE push — gbs.fm is a vintage Django + jQuery 1.3 stack (60-RESEARCH.md:13); modern push channels are out of character.

**Plan 87-01 fixture capture script sketch** (not committed code; for the harvest plan to reference):

```python
# Run TODAY with dev cookies (~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt)
# Captures snapshot for the researcher to dissect post-harvest
import http.cookiejar, urllib.request, datetime

jar = http.cookiejar.MozillaCookieJar(DEV_COOKIES_PATH)
jar.load(ignore_discard=True, ignore_expires=True)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# Capture 1: homepage
with opener.open("https://gbs.fm/", timeout=15) as r:
    Path("tests/fixtures/gbs_marquee/2026-05-25_homepage.html").write_bytes(r.read())

# Capture 2: /ajax cold start
with opener.open("https://gbs.fm/ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0",
                 timeout=15) as r:
    Path("tests/fixtures/gbs_marquee/2026-05-25_ajax_cold.json").write_bytes(r.read())

# Capture 3: logo
with urllib.request.urlopen("https://gbs.fm/images/logo_3.png", timeout=15) as r:
    Path("tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png").write_bytes(r.read())

# Capture 4: SHA-256 of harvested logo
import hashlib
img = Path("tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png").read_bytes()
print(hashlib.sha256(img).hexdigest())
```

**Warning signs:** Plan 87-02 cannot start without Plan 87-01 fixtures committed (D-03 dependency).

### Pitfall #4: GStreamer mock blind spot pattern transfer — source-grep gate is the only credible enforcer of D-05/D-07

**What goes wrong:** A pipeline mock test (or in our case, a unit test that imports `gbs_marquee` and asserts behavior) passes because the bad path silently swallows the call. Per `memory/feedback_gstreamer_mock_blind_spot.md`: behavioral mocks can pass through any call; only source-level grep catches construction-time pollution.

**Why it happens:** A test like `test_gbs_marquee_does_not_use_webengine` that mocks `QWebEngineProfile` and asserts the mock was NOT called gives a false sense of security — if the real code does `from PySide6.QtWebEngineCore import QWebEngineProfile` and never calls it, the mock-not-called assertion passes but the import has already failed at runtime (or worse, silently dragged 130MB of QtWebEngine into the main process).

**How to avoid:** Per `feedback_gstreamer_mock_blind_spot.md` + CONTEXT D-05/D-07: use the **source-grep gate** (`tests/test_gbs_marquee_drift_guard.py` sketched above) as the PRIMARY enforcer; behavioral tests are secondary. Two gates per CONTEXT:

1. `test_marquee_module_reuses_phase76_auth_only` — asserts cookies-jar path is reused, banned identifiers absent
2. `test_themed_logo_never_persists` — asserts no disk-write paths

**Warning signs:** A drift-guard test passes but `grep -rn "QWebEngineProfile" musicstreamer/gbs_marquee.py` shows a hit — the gate's ban list is missing the new pattern.

### Pitfall #5: Banner widget triggers Phase 71 sibling-line rendering drift

**What goes wrong:** Inserting an `AnnouncementBanner` widget at the TOP of NowPlayingPanel's layout shifts every other widget down by N pixels, which could trip the Phase 71 baseline test (`test_richtext_baseline_unchanged_by_phase_71` — verified to exist per PITFALLS.md §Pitfall 13).

**Why it happens:** Phase 71's source-introspection drift-guard locks the RichText literal count (`EXPECTED_RICHTEXT_COUNT = 3` per test_constants_drift.py:21). The banner is `Qt.TextFormat.PlainText` (D-14) — adds ZERO RichText labels — so the literal-count check should remain GREEN. But planner should verify by running `tests/test_constants_drift.py` after the banner widget lands.

**How to avoid:** Confirm at Plan 87-05 close:
- `grep -c "setTextFormat(Qt.RichText)" musicstreamer/` returns 3 (unchanged from baseline)
- `grep -c "setTextFormat(Qt.PlainText)" musicstreamer/` increased by exactly the count of new QLabels in AnnouncementBanner

**Warning signs:** `tests/test_constants_drift.py::test_richtext_count_unchanged` (or similar — find the actual test name in test_constants_drift.py) goes RED after Plan 87-05.

### Pitfall #6: Marquee delimiter is ambiguous — `|` vs ` | ` vs newline

**What goes wrong:** Implementation uses `text.split('|')[0]` but gbs.fm marquee delimiter is actually ` | ` (space-padded). Result: first segment includes leading/trailing whitespace; hash differs every time even when text is identical.

**Why it happens:** Per PITFALLS.md §Integration Gotchas (table line 414): "GBS.FM marquee parse | `text.split('|')[0]` | Inspect 10 real samples, define delimiter as `' | '` (spaces required), fall back to newline / max-length."

**How to avoid:** Plan 87-02 (after Plan 87-01 fixtures land) inspects the harvested raw bytes and locks the delimiter. The parser shape:

```python
def parse_marquee(raw_text: str) -> tuple[str, str]:
    """Returns (first_segment, full_text).

    Whitespace-trim each segment after split. Delimiter locked by Plan 87-02.
    """
    full = (raw_text or "").strip()
    if not full:
        return ("", "")
    segments = [s.strip() for s in full.split("|") if s.strip()]
    first = segments[0] if segments else ""
    return (first, full)
```

The `.strip()` per segment defends against both `|` and ` | ` delimiter conventions. Plan 87-02 may also add a max-length cap if gbs.fm sometimes serves the marquee on a single line without `|` (graceful degradation).

**Warning signs:** Two consecutive marquee polls produce different first-segment hashes for identical-looking text. → Strip whitespace before hashing.

### Pitfall #7: Worker thread + QTimer requires the worker to RUN a Qt event loop

**What goes wrong:** `GbsMarqueeWorker.run()` is `pass` or contains a busy `while True: time.sleep(60)` loop. The QTimer constructed on the worker thread NEVER fires because there's no event loop on the worker thread.

**Why it happens:** A common QThread misuse — `QThread.start()` runs `run()`, which by default does `self.exec_()` (event loop). If you override `run()` and don't call `exec_()`, timer signals never get delivered to slots on this thread.

**How to avoid:** `GbsMarqueeWorker.run()` should be:

```python
def run(self):
    # The timer is constructed in a slot that fires from set_cadence(),
    # which queues across thread boundaries to a slot running on this thread.
    # exec_() drives the event loop so the timer's timeout signal fires our
    # _on_tick slot on this thread, where urllib.urlopen can block safely.
    self.exec_()
```

The cadence state machine works like:

```python
class GbsMarqueeWorker(QThread):
    themed_logo_ready = Signal(object)   # QPixmap or None
    marquee_ready = Signal(str, str)     # (first_segment, full_text)
    cadence_changed_internal = Signal(int)  # ms — for cross-thread cadence change

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer: QTimer | None = None
        self._themed_day_detected_this_session: bool = False
        self._last_full_marquee_text: str = ""
        # cross-thread bridge: external set_cadence() emits this signal,
        # connected (in start()) to a slot on the worker thread that
        # actually reschedules the timer
        self.cadence_changed_internal.connect(
            self._apply_cadence_on_worker_thread, Qt.QueuedConnection
        )

    def set_cadence(self, ms: int) -> None:
        """Public: callable from main thread. 0 = pause; >0 = restart interval."""
        self.cadence_changed_internal.emit(int(ms))

    def _apply_cadence_on_worker_thread(self, ms: int) -> None:
        """Runs on worker thread (via QueuedConnection)."""
        if self._timer is None:
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_tick)
        if ms == 0:
            self._timer.stop()
        else:
            self._interval_ms = ms
            self._timer.start(0)  # immediate first tick after cadence change

    def _on_tick(self) -> None:
        """Runs on worker thread. urllib.urlopen blocks here safely."""
        # ... fetch + parse + emit themed_logo_ready / marquee_ready ...
        # reschedule:
        if self._timer is not None and self._interval_ms > 0:
            self._timer.start(self._interval_ms)

    def run(self):
        self.exec_()
```

**Warning signs:** Setting cadence to 60s, but no marquee ever arrives, no errors logged. → Worker isn't running an event loop.

### Pitfall #8: GBS-MARQ-07 literal "10+ marquee samples" is impossible to satisfy on day-one

**What goes wrong:** Plan 87-01 only captures Memorial Day fixtures (one window — likely 1–3 marquee snapshots harvestable in a single afternoon). GBS-MARQ-07 literal says "10+ real GBS marquee samples committed under `tests/fixtures/gbs_marquee/`." Plan-phase cannot satisfy this on day-one without synthetic samples.

**Why it happens:** Same pragma as GBS-THEME-06 D-04 relaxation. CONTEXT D-04 explicitly relaxes the themed-day "3+/5+" literal but does NOT explicitly relax GBS-MARQ-07's "10+" literal. Researcher recommends extending D-04 spirit to GBS-MARQ-07 — ship the directory + MANIFEST.md + as many real-captured samples as Plan 87-01 yields, plus 5–10 synthetic samples (variations on the harvested template: short/medium/long marquee, single pipe, multiple pipes, unicode in announcement, empty announcement after a pipe, leading/trailing whitespace) for parser robustness.

**How to avoid:** Plan-phase amends GBS-MARQ-07 alongside D-07's GBS-MARQ-06 rewrite — add a note: "Sample count grows opportunistically; initial commit ≥3 real-captured + ≥7 synthetic; 10+ real-captured is the long-term target." Or rephrase to "≥10 samples (real or synthetic)" with a `todos/` followup for accretion.

**Warning signs:** Verification rejects Phase 87 closure because `ls tests/fixtures/gbs_marquee/ | wc -l < 10`.

## Code Examples

### Example 1: Load Phase 76 cookies (verified)

```python
# Source: musicstreamer/gbs_api.py:92-113 (verified)
def load_auth_context() -> Optional[http.cookiejar.MozillaCookieJar]:
    """Return a loaded MozillaCookieJar from paths.gbs_cookies_path() or None."""
    path = paths.gbs_cookies_path()
    if not os.path.exists(path):
        return None
    try:
        from musicstreamer import cookie_utils
        if cookie_utils.is_cookie_file_corrupted(path):
            return None
    except ImportError:
        pass
    jar = http.cookiejar.MozillaCookieJar(path)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception:
        return None
    return jar
```

### Example 2: SHA-256 of bytes (stdlib pattern — no existing codebase usage)

```python
import hashlib

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

### Example 3: QPixmap from bytes (verified Qt 6 API)

```python
from PySide6.QtGui import QPixmap

def _pixmap_from_png_bytes(data: bytes) -> QPixmap | None:
    pix = QPixmap()
    ok = pix.loadFromData(data, "PNG")
    return pix if ok and not pix.isNull() else None
```

### Example 4: Cadence state machine call sites (in NowPlayingPanel)

```python
# In NowPlayingPanel — additions to existing methods

# At end of bind_station():
if self._gbs_marquee_worker is not None:
    if station.provider_name == "GBS.FM":
        self._refresh_gbs_marquee_cadence()
    else:
        self._gbs_marquee_worker.set_cadence(0)  # idle

# At end of on_playing_state_changed():
if self._gbs_marquee_worker is not None and self._station is not None:
    if self._station.provider_name == "GBS.FM":
        self._refresh_gbs_marquee_cadence()

def _refresh_gbs_marquee_cadence(self) -> None:
    """Pick 60s (playing) vs 5min (not playing) for the current bound state."""
    if self._is_playing:
        self._gbs_marquee_worker.set_cadence(60_000)
    else:
        self._gbs_marquee_worker.set_cadence(300_000)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Roadmap framing: `gbs_auth.py` + `QWebEngineProfile` constants reused | Phase 76 cookies-jar + `gbs_api.load_auth_context()` reused | Phase 76 closure (2026-05-23) | GBS-MARQ-06 + ROADMAP Success #4 require rewrite (CONTEXT D-07/D-08) |
| AA-style per-poll QThread spawn (`_AaLiveWorker` lives one cycle then dies) | Long-lived `GbsMarqueeWorker` with internal QTimer (D-15) | Phase 87 design | Different thread-lifecycle pattern; explicit `set_cadence(ms)` API replaces external timer rescheduling |
| Hand-rolled cookies validator (substring `"gbs.fm" in domain`) | Label-boundary match (`domain == "gbs.fm" or domain.endswith(".gbs.fm")`) | Phase 76 WR-04 | Phase 87 reuses `_validate_gbs_cookies` if it touches cookies; rejected lookalike domains |
| Themed-day persisted to SQLite | Session-only QPixmap in worker memory | Phase 87 D-05 | No DB churn; restart re-evaluates |

**Deprecated/outdated:**
- Roadmap line "QtWebEngine cookie persistence cross-process pattern" — never existed in main-process gbs.fm code. PITFALLS §Pitfall 14 mitigation REDIRECTED to enforce cookies-jar reuse.
- The `gbs_auth.py` module name in PITFALLS.md §Pitfall 14 line 328 — that file does not exist; the constants must NOT be added under that name. The drift-guard ban list explicitly forbids `GBS_WEB_PROFILE_NAME` and `GBS_WEB_STORAGE_PATH` identifiers.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Marquee endpoint is most likely embedded in `/ajax` event stream OR in homepage HTML; researcher does NOT lock this | Pitfall #3 | Plan 87-02 may need a brief re-probe before parser-lock; harvest fixture covers both surfaces so the cost is dissection time only |
| A2 | Pitfall #6 delimiter recommendation (`.split("|")` + per-segment `.strip()`) covers both `|` and ` | ` conventions | Code Examples §parse_marquee | Wrong → empty announcement detected as non-empty; banner shows whitespace. Mitigated by `if not segment.strip()` guard |
| A3 | GBS-MARQ-07's "10+ real samples" is impossible day-one; synthetic samples are acceptable filler | Pitfall #8 | If verification interprets literally, Phase 87 closure blocks until 10 real polls accrete (weeks) — Plan-phase should pre-empt with explicit relaxation note |
| A4 | `hashlib.sha256` is the right hash for both logo baseline AND announcement dismissal | Discretion default + CONTEXT D-12 | None — stdlib, no existing precedent to mirror, deterministic across runs |
| A5 | The themed-day correlation rule (hash drift AND keyword in full marquee) fires correctly when the themed logo is on a known day (Memorial Day "da troops") | D-12 + Plan 87-04 | Plan 87-01 harvest validates immediately: today's logo SHA-256 must differ from a canonical and today's marquee must contain "da troops" — if either fails, the rule needs revision before 87-04 |
| A6 | Phase 76 cookies will still be valid by the time Plan 87-01 runs | CANONICAL REF dev fixture | Per 76-VERIFICATION.md sessionid expires 2026-05-17 (already past); the dev fixture may need refresh BEFORE harvest. CONTEXT notes this. If cookies are stale, the harvest can use anonymous GET first (D-11 fallback) since gbs.fm marquee may be anonymously visible — researcher cannot confirm without probing |
| A7 | The drift-guard `"open("` ban (proposed) doesn't break legitimate file IO needs in `gbs_marquee.py` | Pattern 4 refinement note | Likely safe — `gbs_marquee.py` is pure logic + urllib + Qt signals; no file IO required if `GBS_LOGO_BASELINE_HASHES` is a hardcoded dict |
| A8 | `gbs_marquee_log.py` parallel sink to `buffer_log.py` is acceptable, OR extending buffer_log to install on the gbs_marquee logger is acceptable | Don't Hand-Roll table | Both shapes work; planner picks. Recommended: extend `buffer_log.py` rather than create a parallel module, to keep one rotation policy |
| A9 | The marquee endpoint accepts the same Phase 76 cookies as `/ajax` / `/api/vote` / `/search` | D-11 fallback note + Phase 60 RESEARCH | Phase 60 RESEARCH §141 verified cookies authenticate against "every endpoint Phase 60 needs" — likely extends to marquee. If marquee endpoint is ONLY anonymous (most public read-only marquees are), D-11 fallback uses anonymous urlopen and we're fine |

**Per-claim resolution path:** A1, A2, A5, A6, A9 resolved by Plan 87-01 + 87-02 (harvest + parser-lock). A3, A8 resolved by Plan-phase decision. A4, A7 are low-risk defaults.

## Open Questions

1. **Marquee endpoint identity (URL + response shape)**
   - What we know: It's not in the 60-RESEARCH URLconf snapshot under any marquee/announcement name; most likely path is `/ajax` event stream (60% confidence) or homepage HTML (25%)
   - What's unclear: The exact URL constant and parse path
   - Recommendation: Plan 87-01 harvests homepage + cold /ajax + logo; researcher post-harvest dissects within the day; Plan 87-02 locks the constant. DO NOT block plan-phase on this — sequence as Plan 87-01 → 87-02 → 87-03+

2. **Dev fixture cookies freshness**
   - What we know: 76-VERIFICATION confirms cookies file shipped; CANONICAL REF notes sessionid was set to expire 2026-05-17 (already past)
   - What's unclear: Whether the dev fixture has been refreshed since 2026-05-17
   - Recommendation: Plan 87-01 first step = check expiry; if stale, log into gbs.fm and refresh BEFORE harvesting. Alternatively, harvest with anonymous GET (D-11 fallback) — many marquees are publicly visible. Researcher cannot test without probing.

3. **Module file naming for the structured WARN sink**
   - What we know: `buffer_log.py` is the established pattern (Phase 78)
   - What's unclear: Should Phase 87 add a parallel `gbs_marquee_log.py` (separate file), OR extend `buffer_log.py` to install on the `musicstreamer.gbs_marquee` logger ALSO?
   - Recommendation: Extend `buffer_log.py` — one rotation policy, one sink config. Add a function `install_gbs_marquee_handler()` parallel to `install_buffer_events_handler()`. Saves a module + keeps the file-rotation knobs in one place.

4. **AnnouncementBanner parenting model**
   - What we know: NowPlayingPanel uses a complex outer/center HBox/VBox layout (now_playing_panel.py:348-622)
   - What's unclear: Whether the banner should be (a) a sibling at the top of the OUTER QHBoxLayout (taking full width), (b) a sibling at the top of the CENTER QVBoxLayout (taking only center column width), or (c) a separate child above the entire panel layout
   - Recommendation: Option (c) — wrap NowPlayingPanel's existing layout in a new outer QVBoxLayout where row 0 = banner, row 1 = the existing layout. Banner takes full panel width. Plan 87-05 verifies via UI screenshot at narrow/medium/wide panel widths (memory `feedback_ui_bug_verify_with_extremes.md`).

## Environment Availability

**Skip rationale:** Phase 87 is pure Python stdlib + already-installed PySide6 6.x + already-installed urllib (stdlib). No external CLI tools or services. No database changes. No new runtime dependencies.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing — `tests/` dir with `tests/test_*.py` naming) |
| Config file | `pyproject.toml` (test settings) — verified via existing tests like `tests/test_constants_drift.py` |
| Quick run command | `uv run --with pytest pytest tests/test_gbs_marquee.py tests/test_gbs_marquee_drift_guard.py tests/test_announcement_banner.py -x` |
| Full suite command | `uv run --with pytest pytest` |

### Phase Requirements → Test Map

| REQ ID | Behavior (Invariant) | Oracle | Test Type | Automated Command | File Exists? |
|--------|----------------------|--------|-----------|-------------------|-------------|
| GBS-THEME-01 | logo_3.png fetched + SHA-256 hashed against baseline | `compute_logo_theme(harvested_logo_bytes, "")` returns ThemeResult with hash matching the harvested PNG's literal SHA-256 | unit | `pytest tests/test_gbs_marquee.py::test_compute_logo_theme_hashes_logo_bytes -x` | ❌ Wave 0 |
| GBS-THEME-02 | Hash drift + keyword match → themed_logo_applied | `compute_logo_theme(themed_png_bytes, "Memorial Day - da troops!")` returns themed=True; `compute_logo_theme(canonical_png_bytes, "Memorial Day - da troops!")` returns themed=False; `compute_logo_theme(themed_png_bytes, "ordinary marquee")` triggers D-12 fallback (themed=True + unknown_theme_observed log line) | unit + log capture | `pytest tests/test_gbs_marquee.py::test_themed_detection_keyword_match -x` | ❌ Wave 0 |
| GBS-THEME-03 | Logo override hits `logo_label` only (never cover_label) | Drift-guard greps `gbs_marquee.py` source for `cover_label` / `set_station_art` — must be absent | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_themed_logo_targets_logo_slot_only -x` | ❌ Wave 0 |
| GBS-THEME-04 | No SQLite write / no disk write | Drift-guard greps for `repo.set_setting`, `.save(`, `open(` in gbs_marquee.py | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_themed_logo_never_persists -x` | ❌ Wave 0 |
| GBS-THEME-05 | No toast on themed-day detection | Drift-guard greps for `show_toast`, `livenotify`, `QSystemTrayIcon` in `gbs_marquee.py` themed-day path | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_no_toast_in_themed_day_path -x` | ❌ Wave 0 |
| GBS-THEME-06 | Baseline table structure ships | `GBS_LOGO_BASELINE_HASHES` is `dict[str, str]` with at least the Plan 87-01 harvested entries | unit | `pytest tests/test_gbs_marquee.py::test_baseline_table_has_harvest_entries -x` + manual: `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` exists with `resolves_phase: 87` | unit + manual |
| GBS-MARQ-01 | Cadence = 60s (playing) / 5min (not playing) / idle (unbound) | Test calls `worker.set_cadence(state)` and asserts the internal interval state matches expected ms (via worker.intervalMs() introspection accessor exposed for testing) | unit (using QTest event loop) | `pytest tests/test_gbs_marquee.py::test_cadence_state_machine -x` | ❌ Wave 0 |
| GBS-MARQ-02 | Parse: split on `|`, first segment, perpetual ignored | `parse_marquee("aaa | bbb | ccc")` returns `("aaa", "aaa | bbb | ccc")`; `parse_marquee("only")` returns `("only", "only")`; `parse_marquee("")` returns `("", "")` | unit | `pytest tests/test_gbs_marquee.py::test_parse_marquee_pipe_split -x` | ❌ Wave 0 |
| GBS-MARQ-03 | Banner visible iff GBS-bound AND non-empty AND hash differs | NowPlayingPanel + AnnouncementBanner integration test: bind GBS station → first marquee_ready → banner shown; same marquee_ready again → banner stays at same content (no re-show); user dismisses → hash added to set → same marquee_ready → banner hidden | integration (QTest) | `pytest tests/test_announcement_banner.py::test_banner_visibility_predicate -x` | ❌ Wave 0 |
| GBS-MARQ-04 | Pipe boundaries → `\n` wrap hints | Banner widget given `"first | second"` displays as multi-line; QLabel `text()` contains `\n` | unit (QTest, no event loop required) | `pytest tests/test_announcement_banner.py::test_pipe_to_newline_wrap -x` | ❌ Wave 0 |
| GBS-MARQ-05 | × dismiss stores hash; same banner doesn't reappear | Same as GBS-MARQ-03 — dismissal-set assertion | integration (QTest) | `pytest tests/test_announcement_banner.py::test_dismiss_stores_hash -x` | ❌ Wave 0 |
| GBS-MARQ-06 | Phase 76 cookies-jar reuse; no QWebEngineProfile / parallel cookies file | Drift-guard greps `gbs_marquee.py` source for `gbs_api` + `paths` imports; bans `QWebEngineProfile`, `GBS_WEB_PROFILE_NAME`, `oauth_helper`, parallel `open(<cookies-path>, "w")` | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_marquee_module_reuses_phase76_auth_only -x` | ❌ Wave 0 |
| GBS-MARQ-07 | ≥10 marquee samples committed (real or synthetic per Pitfall #8) | `len(list(Path("tests/fixtures/gbs_marquee/").glob("*.txt")) + list(Path("tests/fixtures/gbs_marquee/").glob("*.json"))) >= 10` | fixture-count | `pytest tests/test_gbs_marquee.py::test_fixture_count_ten_or_more -x` (asserts dir count) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run --with pytest pytest tests/test_gbs_marquee.py tests/test_gbs_marquee_drift_guard.py tests/test_announcement_banner.py -x` (typical <5s)
- **Per wave merge:** `uv run --with pytest pytest` (full suite — typical ~90s based on Phase 76 baseline of 1780+ tests)
- **Phase gate:** Full suite green before `/gsd:verify-work` PLUS `grep -rn "QWebEngineProfile\|GBS_WEB_PROFILE_NAME\|GBS_WEB_STORAGE_PATH" musicstreamer/gbs_marquee.py musicstreamer/ui_qt/announcement_banner.py` returns empty

### Wave 0 Gaps (all NEW — none exist today)

- [ ] `tests/test_gbs_marquee.py` — covers GBS-THEME-01/02/06 + GBS-MARQ-01/02/07 (unit + fixture-count)
- [ ] `tests/test_gbs_marquee_drift_guard.py` — covers GBS-THEME-03/04/05 + GBS-MARQ-06 (source-grep)
- [ ] `tests/test_announcement_banner.py` — covers GBS-MARQ-03/04/05 (integration + widget)
- [ ] `tests/fixtures/gbs_themed_logos/MANIFEST.md` — fixture metadata schema (Plan 87-01 establishes)
- [ ] `tests/fixtures/gbs_marquee/MANIFEST.md` — fixture metadata schema (Plan 87-01 establishes)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (read-only path) | Phase 76 cookies-jar reuse — Django sessionid + csrftoken; no new credential surface in Phase 87 |
| V3 Session Management | yes (read-only) | Reuses Phase 76 session; no new session creation. `GbsAuthExpiredError` propagation logs to WARN, doesn't auto-reopen AccountsDialog (D-18) |
| V4 Access Control | partial | Cookies file 0o600 (Phase 999.7 / Phase 76 D-19); already enforced — Phase 87 only reads, never writes |
| V5 Input Validation | yes | Marquee body is gbs.fm operator-controlled untrusted text. `Qt.TextFormat.PlainText` on AnnouncementBanner QLabel (D-14) — defeats HTML/JS injection in the banner. Themed-day keyword match is case-insensitive substring on stripped text (no regex of user input). Hash inputs are bytes (image) or UTF-8 text — no injection vector |
| V6 Cryptography | yes (non-secret use) | `hashlib.sha256` for content-identity hashing — not credential storage, not signature verification. Stdlib only. Not a credential hash; no salt needed |
| V13 API / Web Service | yes | HTTPS-only (`https://gbs.fm/...` constants); 10–15s timeouts (reuse `gbs_api._TIMEOUT_READ`/`_TIMEOUT_WRITE`); bound-method signal connections (QA-05); URL constants in module (no SSRF risk); reuses pure urllib pattern, no eval / no subprocess |
| V14 Configuration | partial | No new env vars, no new config files. Banned config-channel = SQLite settings table (D-05) |

### Known Threat Patterns for PySide6 + urllib + Django backend stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| HTML/JS injection in marquee body (gbs.fm operator-controlled) | Tampering | `Qt.TextFormat.PlainText` on the banner QLabel (D-14); already a project convention (T-40-04) |
| URL string built from operator-controlled data → SSRF | Tampering | All URLs are module-level constants (`GBS_BASE + "/images/logo_3.png"`, marquee URL locked by Plan 87-02); no user input in the URL chain |
| Cookies file read by another local user | Information Disclosure | 0o600 (Phase 76 / paths.py:54-60 docstring); Phase 87 never writes the file |
| Re-login storm via parallel QtWebEngine session | DoS (UX) + Tampering | Drift-guard `test_marquee_module_reuses_phase76_auth_only` bans `QWebEngineProfile`; PITFALLS.md §Pitfall 14 redirected to enforce cookies-jar reuse (CONTEXT D-07) |
| Themed-day cache poisoning (gbs.fm changes canonical logo) | Tampering | D-12 fallback "unknown_theme_observed" — false-positive is acceptable per CONTEXT specifics; logged at INFO; no data loss |
| Worker thread crash on transient network failure | DoS | Top-level try/except in `_on_tick` (project convention — see aa_live.py:128-139 belt-and-suspenders `except Exception:`); WARN log; next tick reschedules |
| QtWebEngine subprocess sandbox-in-sandbox crash | DoS | NOT applicable to Phase 87 — no QtWebEngine usage; this risk is Pitfall 4 (Flatpak) for Phase 86 |
| GET-with-side-effects on marquee fetch | Tampering | Marquee fetch is read-only; gbs.fm marquee endpoint is observed-not-yet-locked; researcher confirms via Plan 87-01 the endpoint is idempotent |

## Project Constraints (from CLAUDE.md)

CLAUDE.md routes to `Skill("spike-findings-musicstreamer")` for Windows-packaging spike findings — NOT phase 87 relevant. Deployment target per memory `project_deployment_target.md` is **Linux Wayland DPR=1.0**; visual UAT for the banner widget at Wayland DPR=1.0 (NOT HiDPI / not X11).

Project conventions from `.planning/codebase/CONVENTIONS.md` that gate Phase 87 code:

- **snake_case** for files, functions, variables; PascalCase for classes (GbsMarqueeWorker, AnnouncementBanner)
- **Type hints throughout** (PEP 484; modern `X | None` over `Optional[X]` per Python 3.10+)
- **`Qt.TextFormat.PlainText`** on every new QLabel content (T-40-04 — locked invariant). Banner widget MUST use this
- **0o600** for sensitive file mode (already enforced for cookies file by Phase 76; Phase 87 never writes cookies)
- **Pure urllib** for HTTP (no requests/httpx) — Phase 87 honors
- **Bound-method signal connections** (no self-capturing lambdas; QA-05) — Phase 87 honors throughout
- **Docstring on every public function + module-level file header** explaining purpose

## Sources

### Primary (HIGH confidence)

- `musicstreamer/gbs_api.py` (entire file read) — auth helpers, exception types, URL constants
- `musicstreamer/aa_live.py` (entire file read) — closest pure-data-layer precedent
- `musicstreamer/ui_qt/now_playing_panel.py:80-180, 280-630, 800-1000, 2400-2500` — worker classes, panel layout, AA poll lifecycle
- `musicstreamer/paths.py` (entire file read) — path constants
- `musicstreamer/buffer_log.py` (entire file read) — structured WARN sink pattern
- `musicstreamer/constants.py` (entire file read) — home for GBS_THEMED_DAY_KEYWORDS
- `musicstreamer/player.py:240-330` — actual Player signal surface (confirmed `state_changed` / `station_bound` absence)
- `tests/test_fake_player_no_inline.py` (entire file read) — source-grep drift-guard precedent
- `tests/test_constants_drift.py:1-80` — additional source-grep precedent
- `tests/fixtures/gbs/` directory listing — Phase 60 fixture conventions
- `.planning/milestones/v2.1-phases/60-gbs-fm-integration/60-RESEARCH.md` — gbs.fm Django URLconf snapshot, /ajax event taxonomy, cookies auth verification (lines 13-15, 153-330, 446-480, 1066-1287)
- `.planning/milestones/v2.1-phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-CONTEXT.md` — Phase 76 cookies-jar LOCKED auth model
- `.planning/milestones/v2.1-phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-VERIFICATION.md` — what Phase 76 actually shipped
- `.planning/research/PITFALLS.md` §Pitfall 14 — original framing redirected to cookies-jar reuse
- `.planning/codebase/CONVENTIONS.md` — snake_case, PlainText, urllib, 0o600
- `.planning/phases/87-gbs-fm-marquee-themed-day-detection/87-CONTEXT.md` — D-01..D-19 locked decisions

### Secondary (MEDIUM confidence)

- Inferred marquee endpoint probability ordering (§Pitfall #3) — based on Django URLconf surface and standard vintage-Django patterns; NOT verified live (deferred to Plan 87-01 harvest)
- AA poll cadence pattern as canonical precedent (now_playing_panel.py:2412-2477) — verified, but the cadence semantics differ (AA = adaptive; Phase 87 = state machine) and `GbsMarqueeWorker` shape uses long-lived QThread with internal QTimer vs AA's per-cycle worker — design choice, not verified pattern

### Tertiary (LOW confidence)

- Pitfall #6 delimiter recommendation (` | ` space-padded vs `|`) is per PITFALLS.md §Integration Gotchas line 414 — author's recommendation, not live-verified; Plan 87-01 fixture resolves
- Pitfall #8 GBS-MARQ-07 literal-relaxation recommendation — interpretive, requires Plan-phase concurrence
- Worker thread + QTimer architecture (Pitfall #7 sketch) — believed correct per Qt 6 documentation conventions; Plan 87-03 implementation will verify via test harness

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all stdlib + already-installed Qt/PySide6 6.x; no new deps
- Architecture (worker + cadence + signals): HIGH — three precedent worker classes already in the codebase (_GbsPollWorker, _AaLiveWorker, _GbsVoteWorker); single divergence is long-lived vs per-cycle worker
- Marquee endpoint identity: LOW — deferred to Plan 87-01 (harvest) + Plan 87-02 (parser-lock). Researcher provides probability-ordered guesses (§Pitfall #3) and a fixture-capture script sketch
- Pitfalls: HIGH — most pitfalls are already documented in `.planning/research/PITFALLS.md` (§Pitfall 14) + CONTEXT.md (D-07/D-08); researcher added Pitfall #2 (Player signal mismatch — verified empirically), #3 (endpoint discovery), #6 (delimiter ambiguity reinforced), #7 (worker event loop), #8 (10+ literal pragmatic)
- REQUIREMENTS / ROADMAP rewrite (D-07/D-08): HIGH — verbatim replacement text provided in §Pitfall #1
- Drift-guard structure: HIGH — direct mirror of `tests/test_fake_player_no_inline.py` + `tests/test_constants_drift.py:48-60`
- Validation map: HIGH for greenfield tests; the cadence/integration tests (GBS-MARQ-01, GBS-MARQ-03/05) will need QTest scaffolding that's already proven in the project

**Research date:** 2026-05-25
**Valid until:** Plan 87-02 commits (parser-lock) — at that point this RESEARCH.md's "marquee endpoint" guesses are superseded by Plan 87-01 harvest data. Other sections remain valid until v2.3+ planning revisits the GBS family.

## RESEARCH COMPLETE

**Phase:** 87 - GBS.FM Marquee + Themed-Day Detection
**Confidence:** HIGH for codebase reuse paths + drift-guard structure; LOW for marquee endpoint constants (intentionally deferred per CONTEXT D-01/D-03/D-10 to Plan 87-01 harvest + Plan 87-02 parser-lock)

### Key Findings

1. **`Player.state_changed` and `Player.station_bound` do NOT exist** (CONTEXT D-16 references are aspirational). Wire cadence transitions through existing `NowPlayingPanel.bind_station` + `NowPlayingPanel.on_playing_state_changed` (now_playing_panel.py:837, 977) — same shape MainWindow already uses for AA poll lifecycle (main_window.py:492-499, 682-703). This is Pitfall #2 — planner MUST honor.

2. **Phase 60 RESEARCH never probed marquee** — verified via comprehensive grep. The marquee endpoint is most likely embedded in the `/ajax` event stream (60% confidence) or homepage HTML (25%); Plan 87-01 captures both as raw bytes for post-harvest dissection. Pitfall #3 documents the probability ordering and provides a fixture-capture script sketch.

3. **GBS-MARQ-06 rewrite + ROADMAP Success Criterion #4 rewrite are MANDATORY** (CONTEXT D-07/D-08). Verbatim replacement text is provided in Pitfall #1. The roadmap framing of a `gbs_auth.py` module / `QWebEngineProfile` reuse pattern is phantom — Phase 76 shipped the cookies-jar path (paths.gbs_cookies_path + gbs_api.load_auth_context, gbs_api.py:92-113); 76-VERIFICATION confirms.

4. **All dependencies are stdlib + already-installed PySide6 6.x** — no new packages, no slopcheck needed. SHA-256 via `hashlib.sha256(...).hexdigest()` is a first-use in the codebase but is stdlib + isolated to `gbs_marquee.py`.

5. **Drift-guard structure is high-confidence** — direct mirror of `tests/test_fake_player_no_inline.py` (17-53) + `tests/test_constants_drift.py:48-60`. Two drift-guards needed: `test_marquee_module_reuses_phase76_auth_only` (D-07 enforcer) + `test_themed_logo_never_persists` (D-05 enforcer). Sketches provided in §Pattern 4.

6. **Module split = option (a)** from CONTEXT discretion — new `musicstreamer/gbs_marquee.py` (worker + parser + correlator + baseline dict) + new `musicstreamer/ui_qt/announcement_banner.py` (widget). This split keeps the source-grep drift-guard target file (`gbs_marquee.py`) auditable in isolation. The themed-logo override path goes through a new `NowPlayingPanel.set_themed_logo_override(QPixmap)` slot.

7. **Worker thread architecture has a quirk** — `GbsMarqueeWorker.run()` must call `self.exec_()` so the worker-thread QTimer's `timeout` signal can fire its slot ON the worker thread (Pitfall #7). The cadence change happens via a Signal-Queued-Connection bridge: external `set_cadence(ms)` emits a signal that's slot-connected on the worker thread, which reschedules the timer. Sketch provided.

8. **GBS-THEME-06 (3+/5+) is RELAXED per D-04**; **GBS-MARQ-07 (10+) is implicitly relaxed** per Pitfall #8 — Plan-phase should pre-empt by extending the spirit of D-04 to MARQ-07. Synthetic samples are acceptable filler to reach the literal count alongside real-captured Plan 87-01 fixtures.

### File Created

`.planning/phases/87-gbs-fm-marquee-themed-day-detection/87-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | Stdlib + already-installed Qt 6.x; no new deps |
| Architecture | HIGH | Three QThread precedents in now_playing_panel.py; cadence pattern mirrors AA poll; cookies reuse mirrors Phase 76 |
| Pitfalls | HIGH | Pitfall #2 (Player signal mismatch) caught empirically; Pitfalls #1, #3, #4, #5, #6, #8 are direct extensions of documented PITFALLS.md / memory entries |
| Marquee endpoint identity | LOW | Phase 60 never probed; researcher correctly defers to Plan 87-01 + 87-02 per CONTEXT D-01/D-03 |
| Drift-guard structure | HIGH | Direct mirror of two shipped patterns (test_fake_player_no_inline.py + test_constants_drift.py) |
| REQUIREMENTS/ROADMAP rewrite text | HIGH | Verbatim per CONTEXT D-07/D-08; researcher provides quoted text in §Pitfall #1 |
| Validation map | HIGH for greenfield; MEDIUM for cadence integration tests (QTest scaffolding) |

### Open Questions (Resolved by Plan 87-01 / 87-02 sequencing)

1. Marquee endpoint URL + response shape (Plan 87-01 harvest, Plan 87-02 parser-lock)
2. Dev fixture cookies freshness (Plan 87-01 first step)
3. Anonymous vs cookies-required for marquee fetch (Plan 87-01 reports; D-11 fallback covers either outcome)

### Open Questions (Decisional, Plan-phase resolves)

4. `gbs_marquee_log.py` parallel file vs extending `buffer_log.py` (researcher recommends extending — one rotation policy)
5. AnnouncementBanner parenting (option c — wrap existing NowPlayingPanel layout in a new outer QVBoxLayout — recommended)
6. GBS-MARQ-07 10+ literal relaxation (extend D-04 spirit; pre-empt verification block)

### Ready for Planning

Research complete. The planner has:
- Verbatim REQUIREMENTS.md GBS-MARQ-06 rewrite text (Pitfall #1)
- Verbatim ROADMAP.md Success Criterion #4 rewrite text (Pitfall #1)
- Eight pitfalls catalogued with mitigations
- Three pattern examples drawn from verified codebase precedents
- A REQ→test mapping table for the Validation Architecture section
- Two drift-guard sketches (source-grep)
- A worker thread architecture sketch with the event-loop quirk handled (Pitfall #7)
- Explicit module split recommendation (option a)
- Wire-cadence-via-existing-bind_station path (Pitfall #2 correction to CONTEXT D-16)

Recommend Plan structure: 87-01 (harvest fixtures + REQUIREMENTS/ROADMAP edits — small, time-sensitive, fires TODAY) → 87-02 (parser-lock + endpoint constants from harvest) → 87-03 (GbsMarqueeWorker + cadence) → 87-04 (themed-day correlator + logo swap) → 87-05 (AnnouncementBanner + dismissal) → 87-06 (drift-guards + todos entry + verification gates).

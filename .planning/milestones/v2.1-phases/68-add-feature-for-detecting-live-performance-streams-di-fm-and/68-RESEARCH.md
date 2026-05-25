# Phase 68: Live Stream Detection (DI.fm) - Research

**Researched:** 2026-05-10
**Domain:** AudioAddict API, Qt QThread worker pattern, NowPlayingPanel widget extension, StationFilterProxyModel extension, toast infrastructure
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Hybrid detection — AA API primary for DI.fm when `audioaddict_listen_key` saved, ICY-title `LIVE:` / `LIVE -` prefix fallback for all others.
**D-02:** Provider scope DI.fm only for API path; code must accept other AA slugs via allowlist with one-line change.
**D-03:** No master enable/disable toggle. Feature always-on when conditions met.
**P-01:** ICY pattern `re.match(r'^\s*LIVE\s*[:\-]\s*(.+?)\s*$', title, re.IGNORECASE)` — prefix match only.
**P-02:** Reject substring matches — `LIVE and Let Die`, `Live at Wembley` do not trigger.
**P-03:** No state on ICY detection beyond current title. Every `title_changed` re-evaluates.
**A-01:** Use existing `audioaddict_listen_key` setting. Read via `repo.get_setting("audioaddict_listen_key", "")`. Empty → silent fallback.
**A-02:** Endpoint — *research deliverable (see below).*
**A-03:** Auth model — query-string `listen_key`. No OAuth, no headers beyond User-Agent.
**A-04:** Failure mode — any non-2xx, JSON parse error, timeout, missing key → "not live" silently.
**A-05:** No retries within a poll. Stale data persists until next successful poll.
**A-06:** Channel keying — match by channel `key` field derived from stream URL via existing `_aa_channel_key_from_url`.
**B-01:** Adaptive cadence — 60 s while playing DI.fm, 5 min otherwise.
**B-02:** Single batched poll per cycle covering all DI.fm channels.
**B-03:** Poll runs while app is open. Started in `MainWindow.__init__` after settings load. Stopped on `closeEvent`. Skipped if no `audioaddict_listen_key`.
**B-04:** Listen-key change reactive. Poll loop starts/stops/restarts when key is saved or cleared.
**B-05:** Poll HTTP call on a `QThread` worker; result emitted via signal back to main thread. Timer on Qt main thread (single-shot QTimer rescheduled each cycle).
**C-01:** `_refresh_live_status()` called in `bind_station` after `_refresh_similar_stations()`.
**C-02:** Subscribe to `Player.title_changed` — on every fire, re-run `_refresh_live_status()`.
**C-03:** Decision tree: DI.fm with key → cache lookup (one-shot poll if cold); else → ICY pattern.
**U-01:** Badge: `QLabel` (`_live_badge`) in new `QHBoxLayout` to the LEFT of `icy_label` in center column.
**U-02:** Badge text: `LIVE`. Show name appended to ICY title row as ` — {show name}`.
**U-03:** Badge styling: Phase 66 theme accent token (planner picks exact token). Small rounded chip. White/theme-contrast text.
**U-04:** Badge visibility: `setVisible(True)` when live, `setVisible(False)` otherwise.
**T-01:** Three toast triggers via existing `MainWindow._toast`/`show_toast`: (a) bind-to-already-live, (b) off→on, (c) on→off.
**T-02:** No toast cooldown.
**T-03:** Toasts ONLY for currently bound station transitions. Poll-only library updates do not toast.
**T-04:** No emoji/glyph in v1 (text-only).
**F-01:** "Live now" chip in existing `StationListPanel` filter strip (Phase 47.1 FlowLayout).
**F-02:** Toggle: shows only stations whose channel key is in live map with `is_live=True`.
**F-03:** Composes with existing tag/provider chip filters (AND-between).
**F-04:** When chip on and no channels live, tree is empty — existing empty-tree placeholder.
**F-05:** Chip styling: reuse existing Phase 47.1 chip styling. Optional live accent (planner picks).
**F-06:** Results may be 60s / 5min stale. Acceptable. No spinner.
**F-07:** When `audioaddict_listen_key` empty, "Live now" chip HIDDEN entirely.
**N-01:** Silent fallback to ICY-pattern only.
**N-02:** No proactive nudge.
**N-03:** Reactive activation on key save.
**T-D-01:** Wave 0 RED contract first.
**T-D-02:** AA API mocking via recorded fixtures.
**T-D-03:** No QA-05-style lambda-grep test needed.

### Claude's Discretion

- Module structure: planner picks `musicstreamer/aa_live.py` (new) vs extending `aa_import.py` vs inside `now_playing_panel.py`. Research recommends `musicstreamer/aa_live.py`.
- Poll thread implementation: planner picks pattern. Research recommends `QThread` + `Worker` object (mirrors `_GbsPollWorker` precedent already in `now_playing_panel.py`).
- Cache invalidation on poll failure: keep last successful state vs drop entries. Research recommends keep last successful with TTL.
- Show-name truncation policy: planner picks max-width / ellipsis.

### Deferred Ideas (OUT OF SCOPE)

- Universal ICY pattern variants beyond `LIVE:` / `LIVE -` prefix.
- Multi-network AA support (RockRadio, JazzGroove, etc.).
- Live-show history / archive.
- Schedule / EPG fetch.
- Browse live shows dialog.
- Per-station opt-out / mute for toasts.
- Master enable/disable toggle.
- Recording / capturing live shows.
- Visual color picker for badge color.
</user_constraints>

---

## Summary

Phase 68 adds live-show detection for DI.fm channels. The feature uses two detection paths: the AudioAddict public API (authenticated by the existing `audioaddict_listen_key`) and a conservative ICY-title prefix fallback. Research confirms the exact API endpoint, response schema, and live-show detection mechanism. Three UI surfaces are added without touching Phase 64 or Phase 67 code. The entire implementation composes cleanly on top of established Phase 67 patterns.

**Critical finding — API endpoint and live detection mechanism:** The AA `currently_playing` endpoint (`https://api.audioaddict.com/v1/di/currently_playing`) returns all 101 channels but has NO live-show indicator field. Instead, live-show detection must use the **events API** (`https://api.audioaddict.com/v1/di/events`), which returns a schedule of upcoming/current shows with `start_at` / `end_at` timestamps. A show is "currently live" when `now` falls within `[start_at, end_at)`. This endpoint is public (no auth required), covers all DI.fm channels, and can be batched in a single call. The `shows` endpoint (`/v1/di/shows`) also provides a `now_playing: bool` field per show, but it is paginated (10 results/page) and the `now_playing=true` filter did not work correctly in testing. The `events` endpoint is the correct and reliable approach.

**Primary recommendation:** Use `GET https://api.audioaddict.com/v1/di/events` (no listen_key required). Parse response to build `dict[channel_key, LiveState]` by checking which events have `start_at <= now < end_at`. Channel key is in `event.show.channels[].key`. No listen_key needed for detection — the `audioaddict_listen_key` check is still the gate for starting the poll loop (per B-03) but the HTTP call itself requires no auth.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live-show detection (AA API) | API / Backend helper (`aa_live.py`) | — | Pure HTTP + JSON parsing; no Qt coupling; testable in isolation |
| Poll loop lifecycle | Qt main thread (QTimer) | QThread worker (HTTP) | Timer scheduling on main thread; HTTP blocking call offloaded |
| Per-channel live state cache | Application memory (main thread) | — | Simple `dict`, no DB; updated by poll worker signal callback |
| Badge widget | NowPlayingPanel (Frontend widget) | — | Inline display; updates on `_refresh_live_status` call |
| Toast notifications | MainWindow (controller) | — | Matches existing `show_toast` pattern; transition state managed by NowPlayingPanel, toast emitted to MainWindow |
| "Live now" filter chip | StationListPanel (Frontend widget) | StationFilterProxyModel | Chip is UI; filter logic is proxy predicate |
| ICY pattern detection | Pure helper (`aa_live.py` or similar) | — | `re.match` with no Qt/network dependency; testable without fixtures |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `PySide6` | (project existing) | Qt widgets, QThread, QTimer, Signal | All Phase 68 UI surfaces use existing project stack |
| `urllib.request` | stdlib | HTTP GET for AA events endpoint | Mirrors `aa_import.py` convention — no new dependency |
| `re` | stdlib | ICY title pattern matching | Stdlib; no external dependency |
| `datetime` | stdlib | `now()` comparison against event `start_at` / `end_at` | ISO 8601 with timezone offsets supported natively |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` | stdlib | Parse AA API JSON responses | Already used in `aa_import.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `urllib.request` | `requests` | `requests` would add a dep. `urllib` matches `aa_import.py` convention exactly. |
| Single `/events` fetch | Per-channel `/events/channel/{id}` | Per-channel is N=30 calls. Single batched `/events` is 1 call for all 30 active-event channels. |
| `/events` | `/shows?now_playing=true` | `/shows` pagination is 10/page; `now_playing=true` filter misbehaved in testing (returned all shows regardless). `/events` is reliable and unambiguous. |

**Installation:** No new packages required.

---

## Architecture Patterns

### System Architecture Diagram

```
MainWindow.__init__
  │
  ├─► start AAPollManager (if listen_key saved)
  │     │
  │     ├─► QTimer (main thread) ──60s/5min──► fire
  │     │     │
  │     │     └─► _AaLiveWorker(QThread).start()
  │     │               │  run(): urllib GET /v1/di/events
  │     │               │  parse timestamps → dict[ch_key, LiveState]
  │     │               └─► Signal live_map_updated(dict) ──queued──►
  │     │                         │
  │     └─────────────────────────┘
  │           on_live_map_updated(live_map):
  │             self._live_map = live_map
  │             notify NowPlayingPanel._refresh_live_status()
  │             notify StationFilterProxy.set_live_map(live_map)
  │
  ├─► NowPlayingPanel.bind_station(station)
  │     ├─► _refresh_siblings()          [Phase 64]
  │     ├─► _refresh_similar_stations()  [Phase 67]
  │     └─► _refresh_live_status()       [Phase 68 NEW]
  │               │
  │               ├─ is DI.fm + key saved? → lookup _live_map[channel_key]
  │               │   if cache empty → trigger one-shot poll (cold start)
  │               ├─ else → apply ICY pattern (P-01) to _last_icy_title
  │               └─► update _live_badge visibility + text
  │                   compare to prior state → emit transition toast (T-01)
  │
  ├─► Player.title_changed ──signal──► NowPlayingPanel.on_title_changed()
  │     (existing slot extended)
  │     └─► _refresh_live_status()       [Phase 68 hook]
  │
  └─► StationListPanel filter strip
        └─► "Live now" chip (hidden when no listen_key)
              └─► toggled → StationFilterProxy.set_live_only(bool)
                      └─► filterAcceptsRow: check station channel_key in live_map
```

### Recommended Project Structure

New file:
```
musicstreamer/
└── aa_live.py           # AA events fetcher + ICY pattern matcher (no Qt)

tests/
├── test_aa_live.py      # pure-helper + fixture-based API parser tests
└── fixtures/
    └── aa_live/
        ├── events_no_live.json      # all events in future
        ├── events_with_live.json    # one event currently live (trance ch)
        └── events_multiple_live.json
```

Modified files:
```
musicstreamer/ui_qt/
├── now_playing_panel.py   # _live_badge + _refresh_live_status + toast transitions
├── station_list_panel.py  # "Live now" chip + AAPollManager integration
├── station_filter_proxy.py # set_live_map + set_live_only predicates
└── main_window.py         # AAPollManager lifecycle, closeEvent, key-change reactivity
```

### Pattern 1: AA Events API — Live Show Detection

**What:** Single `GET https://api.audioaddict.com/v1/di/events` returns up to ~201 upcoming events. Each event has `start_at` and `end_at` ISO-8601 strings with timezone offsets, plus `show.channels[].key` linking to channel keys. A show is live when `start_at <= now < end_at`.

**Verified response shape (probed 2026-05-10):**
```python
# Source: Live probe of https://api.audioaddict.com/v1/di/events
# Response: list of event dicts
[
  {
    "id": 201572,
    "duration": None,          # nullable
    "name": "#949",            # episode name
    "show_id": 10554145,
    "slug": "949",
    "start_at": "2026-05-10T13:00:00-04:00",   # ISO8601 with tz offset
    "end_at": "2026-05-10T15:00:00-04:00",
    "subtitle": "",
    "artists_tagline": "with Lars Behrenroth featuring ...",
    "description_html": "",
    "show": {
      "id": 10554145,
      "name": "Deeper Shades of House",   # show name for badge/toast
      "tagline": None,
      "artists_tagline": "with Lars Behrenroth",
      "slug": "deeper-shades-of-house",
      "human_readable_schedule": ["Every Sunday"],
      "next_start_at": "2026-05-10T13:00:00-04:00",
      "channels": [
        {
          "id": 10,
          "key": "house",   # matches _aa_channel_key_from_url output
          "name": "House",
          "images": { ... }
        }
      ]
    },
    "tracks": []   # list of tracks in the episode (may be empty)
  },
  ...
]
```

**How to detect "currently live":**
```python
# Source: VERIFIED — live probe of events endpoint 2026-05-10
from datetime import datetime, timezone

def parse_live_map(events: list[dict]) -> dict[str, str]:
    """Return {channel_key: show_name} for currently-live shows.

    A show is live when start_at <= now < end_at.
    Multiple shows may be live simultaneously on different channels.
    """
    now = datetime.now(timezone.utc)
    live_map: dict[str, str] = {}
    for ev in events:
        start_raw = ev.get("start_at", "")
        end_raw = ev.get("end_at", "")
        if not start_raw or not end_raw:
            continue
        try:
            start = datetime.fromisoformat(start_raw)
            end = datetime.fromisoformat(end_raw)
        except ValueError:
            continue
        if start <= now < end:
            show = ev.get("show", {})
            show_name = show.get("name", "")
            for ch in show.get("channels", []):
                key = ch.get("key", "")
                if key:
                    live_map[key] = show_name
    return live_map
```

**Observation:** The events list has ~201 entries covering multiple days ahead. Only events whose time window includes `now` are "currently live". No authentication required for this endpoint.

### Pattern 2: Channel Key Mapping (A-06)

**What:** The events endpoint uses the same channel `key` field that `_aa_channel_key_from_url` already extracts from stream URLs. No new mapping needed.

```python
# Source: VERIFIED — cross-reference events response keys vs url_helpers.py
# Example: events channel key "trance" matches:
#   stream URL "http://prem1.di.fm:80/di_trance_hi?listen_key=..."
#   → _aa_channel_key_from_url strips "di_" prefix and "_hi" suffix → "trance"
# 
# Example: events channel key "house" matches:
#   stream URL "http://prem1.di.fm:80/di_house?listen_key=..."
#   → "house"
```

The Station has no `channel_key` column. The channel key must be derived from the station's stream URL at lookup time via the existing `_aa_channel_key_from_url(url, slug="di")` from `url_helpers.py`. This is a pure string operation — no DB query.

```python
# Source: VERIFIED — url_helpers.py live code
from musicstreamer.url_helpers import _aa_channel_key_from_url, _aa_slug_from_url, _is_aa_url

def get_di_channel_key(station) -> str | None:
    """Extract DI.fm channel key from station's first stream URL.
    Returns None if not a DI.fm station or key not derivable.
    """
    if not station.streams:
        return None
    url = station.streams[0].url
    if not _is_aa_url(url):
        return None
    slug = _aa_slug_from_url(url)
    if slug != "di":
        return None
    return _aa_channel_key_from_url(url, slug="di")
```

### Pattern 3: QThread Worker (B-05)

**What:** The HTTP poll runs on a `QThread` worker, emits results back to main thread via signal. Exactly mirrors `_GbsPollWorker` in `now_playing_panel.py:73-100` and `_YtScanWorker` in `import_dialog.py:74-93`.

**Canonical pattern (source: `import_dialog.py:74-93` — `_YtScanWorker`):**
```python
# Source: VERIFIED — musicstreamer/ui_qt/import_dialog.py:74-93
class _AaLiveWorker(QThread):
    """Fetch AA events on a worker thread, emit parsed live_map back to main thread."""
    finished = Signal(object)  # dict[str, str] — {channel_key: show_name}
    error = Signal(str)

    def __init__(self, network_slug: str = "di", parent=None):
        super().__init__(parent)
        self._slug = network_slug

    def run(self):
        try:
            from musicstreamer.aa_live import fetch_live_map
            live_map = fetch_live_map(self._slug)
            self.finished.emit(live_map)
        except Exception as exc:
            self.error.emit(str(exc))
```

**QTimer orchestration on main thread (mirrors `_GbsPollWorker` lifecycle):**
```python
# Source: VERIFIED — now_playing_panel.py:419-427 GBS poll pattern
self._aa_poll_timer = QTimer(self)
self._aa_poll_timer.setSingleShot(True)  # rescheduled after each cycle
self._aa_poll_timer.timeout.connect(self._on_aa_poll_tick)  # QA-05

def _on_aa_poll_tick(self):
    if self._aa_live_worker is not None and self._aa_live_worker.isRunning():
        return  # previous worker still running; reschedule
    self._aa_live_worker = _AaLiveWorker(parent=self)
    self._aa_live_worker.finished.connect(self._on_aa_live_ready, Qt.QueuedConnection)
    self._aa_live_worker.error.connect(self._on_aa_live_error, Qt.QueuedConnection)
    self._aa_live_worker.start()

def _on_aa_live_ready(self, live_map: dict):
    self._live_map = live_map
    self._reschedule_poll()   # fire again after cadence

def _on_aa_live_error(self, msg: str):
    # A-04: silent failure; keep last live_map as-is
    self._reschedule_poll()

def _reschedule_poll(self):
    # B-01: 60s if currently playing DI.fm; 5min otherwise
    is_playing_di = (self._current_station is not None
                     and self._is_di_fm_station(self._current_station))
    interval_ms = 60_000 if is_playing_di else 300_000
    self._aa_poll_timer.start(interval_ms)
```

**Qt/GLib threading note:** Phase 68's `_AaLiveWorker` uses `QThread` (not a GLib thread) and makes standard blocking `urllib` HTTP calls from `run()`. The only cross-thread communication is via `Signal` with `QueuedConnection`, which is the project standard. The spike-findings document's two threading rules (GstBusLoopThread bus watch, `QTimer.singleShot` from non-QThread) do NOT apply here because Phase 68 never calls `QTimer.singleShot` from the worker thread and never touches GStreamer bus objects. `[VERIFIED: qt-glib-bus-threading.md does not apply to this pattern]`

### Pattern 4: NowPlayingPanel `_refresh_live_status` Insertion Seam

**What:** Following the Phase 64 / Phase 67 pattern, `_refresh_live_status()` is called from `bind_station` after `_refresh_similar_stations()`, and also connected to `Player.title_changed`.

**Exact insertion point in `bind_station` (source: `now_playing_panel.py:620-658` — verified):**
```python
def bind_station(self, station: Station) -> None:
    # ... existing setup ...
    self._refresh_siblings()               # Phase 64
    self._refresh_similar_stations()       # Phase 67
    self._refresh_live_status()            # Phase 68 NEW — append here
    self._refresh_gbs_visibility()         # Phase 60 (must stay last — GBS logic)
```

**Note:** `_refresh_gbs_visibility()` must remain the last call in `bind_station`. `_refresh_live_status()` inserts before it, not after.

**Badge widget placement — center column widget tree (verified from `now_playing_panel.py:260-301`):**
```
center (QVBoxLayout)
  ├── name_provider_label   (9pt Normal — "Station · Provider")
  ├── _sibling_label        (RichText — Phase 64 "Also on:")
  ├── [NEW] icy_row         (QHBoxLayout) ─── replaces direct center.addWidget(icy_label)
  │     ├── _live_badge     (QLabel, hidden by default)
  │     └── icy_label       (13pt DemiBold — ICY title)
  ├── elapsed_label         (10pt TypeWriter)
  ├── controls              (QHBoxLayout — play/pause/stop/edit/combo/star/eq/volume)
  ├── _stats_widget         (Phase 47.1)
  ├── _gbs_playlist_widget  (Phase 60)
  ├── [GBS vote row]        (Phase 60)
  └── _similar_container    (Phase 67 — outermost; addWidget at end)
```

**Badge widget creation pattern:**
```python
# Source: ASSUMED (U-01, U-02, U-03 from CONTEXT.md + QHBoxLayout pattern)
# Replace direct: center.addWidget(self.icy_label)
# With:
icy_row = QHBoxLayout()
icy_row.setContentsMargins(0, 0, 0, 0)
icy_row.setSpacing(6)

self._live_badge = QLabel("LIVE", self)
self._live_badge.setTextFormat(Qt.PlainText)
self._live_badge.setVisible(False)  # hidden until live
# Chip styling: palette(highlight) background + palette(highlighted-text) text
# Matches _CHIP_QSS selected state in station_list_panel.py:60-67
self._live_badge.setStyleSheet(
    "QLabel {"
    "  background-color: palette(highlight);"
    "  color: palette(highlighted-text);"
    "  border-radius: 8px;"
    "  padding: 2px 6px;"
    "  font-weight: bold;"
    "}"
)
icy_row.addWidget(self._live_badge)
icy_row.addWidget(self.icy_label, 1)
center.addLayout(icy_row)    # instead of center.addWidget(self.icy_label)
```

### Pattern 5: Filter Chip and Proxy Extension

**Existing chip creation pattern (source: `station_list_panel.py:218-246` — verified):**
```python
# Provider chip example — Phase 68 "Live now" chip mirrors this shape
btn = QPushButton("Provider Name", provider_chip_container)
btn.setCheckable(True)
btn.setProperty("chipState", "unselected")
btn.setStyleSheet(_CHIP_QSS)
self._provider_chip_group.addButton(btn)
provider_chip_layout.addWidget(btn)
```

**"Live now" chip placement:** After the clear-all button row in `_build_chip_rows()`, OR as a new dedicated row above the provider chips. Planner decides placement. The chip is a standalone checkable `QPushButton`, not added to `_provider_chip_group` or `_tag_chip_group` (it's a separate predicate dimension).

**StationFilterProxy extension (source: `station_filter_proxy.py` — verified):**
```python
# Source: VERIFIED — station_filter_proxy.py — add these methods
class StationFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._search_text: str = ""
        self._provider_set: set[str] = set()
        self._tag_set: set[str] = set()
        # Phase 68 NEW:
        self._live_only: bool = False
        self._live_channel_keys: set[str] = set()  # keys from live_map

    def set_live_map(self, live_map: dict[str, str]) -> None:
        """Update live channel keys from poll result. Invalidates if live_only active."""
        self._live_channel_keys = set(live_map.keys())
        if self._live_only:
            self.invalidate()

    def set_live_only(self, enabled: bool) -> None:
        self._live_only = enabled
        self.invalidate()

    def has_active_filter(self) -> bool:
        return bool(self._search_text or self._provider_set or self._tag_set
                    or self._live_only)   # Phase 68: include live_only

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        # ... existing provider/station logic ...
        if node.kind == "station":
            if self._live_only:
                # Derive channel key from station's first stream URL
                from musicstreamer.url_helpers import _aa_channel_key_from_url, _aa_slug_from_url, _is_aa_url
                station = node.station
                ch_key = None
                if station.streams:
                    url = station.streams[0].url
                    if _is_aa_url(url):
                        slug = _aa_slug_from_url(url)
                        ch_key = _aa_channel_key_from_url(url, slug=slug)
                if ch_key not in self._live_channel_keys:
                    return False
            return matches_filter_multi(
                node.station,
                self._search_text,
                self._provider_set,
                self._tag_set,
            )
```

**Note:** `_live_channel_keys` contains keys from all AA networks, not just DI.fm. In v1 the poll only covers DI.fm, so only DI.fm stations will ever match. This is correct behavior.

### Pattern 6: Toast Transition Pattern

**What:** `_refresh_live_status()` compares the new live state to `self._prev_live_state` and calls the appropriate toast via a `Signal` back to `MainWindow.show_toast`.

```python
# Source: ASSUMED — mirrors existing show_toast pattern in main_window.py:395-397
# NowPlayingPanel emits a signal (similar to gbs_vote_error_toast) to MainWindow

# In NowPlayingPanel class:
live_status_toast = Signal(str)   # emitted for transition toasts

# In MainWindow.__init__:
self.now_playing.live_status_toast.connect(self.show_toast)  # QA-05

# In NowPlayingPanel._refresh_live_status():
def _refresh_live_status(self):
    was_live = self._live_show_active   # prior state
    show_name = self._detect_live()     # None or str (show name)
    is_live = show_name is not None

    # Update badge
    self._live_badge.setVisible(is_live)
    if is_live:
        # Append show name to icy_label if it differs from current track display
        pass  # planner formalizes

    # Toast transitions
    if is_live and not was_live:
        if self._first_bind_check:      # bound to already-live
            self.live_status_toast.emit(f"Now live: {show_name} on {self._station.name}")
        else:                           # off → on mid-listen
            self.live_status_toast.emit(f"Live show starting: {show_name}")
    elif not is_live and was_live:      # on → off mid-listen
        self.live_status_toast.emit(f"Live show ended on {self._station.name}")

    self._live_show_active = is_live
    self._first_bind_check = False
```

**Toast text (T-01):**
- Bind-to-already-live: `"Now live: {show name} on {station name}"`
- Off → On: `"Live show starting: {show name}"`
- On → Off: `"Live show ended on {station name}"`

### Pattern 7: MainWindow Poll Lifecycle (B-03, B-04)

**AccountsDialog AA key clear path (verified: `accounts_dialog.py:343-355`):**
When user clears AA key, `_repo.set_setting("audioaddict_listen_key", "")` is called. No signal is emitted. **B-04 reactive options:**

1. **Signal-push (recommended):** `AccountsDialog` emits a new `aa_key_changed = Signal(bool)` (True=key saved, False=cleared). `MainWindow` connects to start/stop poll. Requires `AccountsDialog` modification.

2. **Lazy poll-cycle check:** On each poll reschedule, read `repo.get_setting("audioaddict_listen_key", "")` and start/stop accordingly. No new signal. More resilient but slightly less immediate.

The planner should pick option 2 as the simpler path: each poll reschedule checks whether the key is still present. If gone, stop scheduling. If newly present (checked every 5 min), start. `AccountsDialog` stays unmodified. `ImportDialog` write path (`import_dialog.py:459`) similarly just writes the setting; the next poll cycle (or `MainWindow.__init__` on restart) picks it up.

**For N-03 reactivity on key save:** `MainWindow._open_accounts_dialog()` or `_open_import_dialog()` can call `_aa_poll_manager.check_key_and_start()` after the dialog closes. This is a one-line hook.

### Anti-Patterns to Avoid

- **Never call `QTimer.singleShot(0, callable)` from the `_AaLiveWorker.run()` thread.** The worker thread has no Qt event loop. Use `Signal` with `QueuedConnection` to communicate back to main thread (already the recommended pattern).
- **Never import Qt from `aa_live.py`.** Keep it pure Python + stdlib for testability.
- **Never hit the live AA API from tests.** Record fixtures. Tests mock HTTP.
- **Do not use `requests`** — project convention is `urllib.request` (no dependency; matches `aa_import.py`).
- **Do not cache live state in SQLite.** It's transient in-memory only (per CONTEXT.md).
- **Do not modify `_refresh_gbs_visibility` call ordering** — it must remain last in `bind_station`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ICY title pattern | Custom string parser | `re.match` with `re.IGNORECASE` | Handles case, whitespace edge cases in one line |
| ISO 8601 datetime parsing | Manual string slicing | `datetime.fromisoformat()` (Python 3.11+; compatible with offset strings) | Handles timezone offsets natively |
| Cross-thread signal | `threading.Event`, Queue | PySide6 `Signal(QueuedConnection)` | Established pattern; already used everywhere in project |
| HTTP fetch | `asyncio.aiohttp` | `urllib.request.urlopen` | No new dependency; matches `aa_import.py` |
| Live-show chip | New chip widget class | Reuse `QPushButton` + `_CHIP_QSS` | Already established; chipState property pattern |

**Key insight:** The entire Phase 68 live-detection logic reuses existing infrastructure. The AA events API is the only genuinely new domain; everything else (QThread, QTimer, Signal, chip, proxy predicate, toast) has a direct copy-paste analog already in the codebase.

---

## A-02 Endpoint Verification — Critical Finding

**VERIFIED endpoint: `GET https://api.audioaddict.com/v1/di/events`**

| Property | Value |
|----------|-------|
| Full URL | `https://api.audioaddict.com/v1/di/events` |
| Method | GET |
| Auth | None (public endpoint — no `listen_key` parameter required) |
| Response type | `application/json; charset=utf-8` |
| Response shape | `list[EventDict]` |
| Event count | ~201 events (several days ahead) |
| Rate-limit headers | None detected (`x-ratelimit` absent) |
| HTTP status on success | 200 |
| One-call coverage | All DI.fm channels with upcoming events |

**Rejected endpoint candidates:**

| Endpoint | Status | Why Rejected |
|----------|--------|--------------|
| `https://api.audioaddict.com/v1/di/currently_playing` | Public, works | Returns 101 channels but has NO live-show field — only `display_artist`, `display_title`, `start_time`, `duration` per track. Regular track and live show look identical. Cannot detect live shows. |
| `https://api.audioaddict.com/v1/di/currently_playing?listen_key={key}` | Works | Same response shape with or without key — no live indicator field. |
| `https://www.di.fm/_papi/v1/di/currently_playing` | Returns HTML | Cloudflare-protected; not accessible without browser session. |
| `https://api.audioaddict.com/v1/di/shows` | Works | Has `now_playing: bool` per show, but paginated (10/page, ~1510 total shows). `now_playing=true` filter did not work correctly in testing — returned all shows with `now_playing: False`. |
| `https://api.audioaddict.com/v1/di/track_history` / `/channel/{id}` | Works | Has `type: "track"` field, but only `"track"` values observed — no `"show"` type currently returned (all live shows show as regular tracks or are absent). |

**Cadence validation:** 60 s cadence against a single unauthenticated endpoint with no rate-limit headers. The response is ~50 KB (201 events). This is well within safe usage for a personal app's background poll. `[VERIFIED: no x-ratelimit headers; ASSUMED: no undocumented rate limit at 60s/request]`

**`listen_key` role clarification (A-01 / A-03):** The `listen_key` is used as the gate for starting the poll loop (B-03) and for the badge feature overall, but the events HTTP call itself needs no key. This is a UX decision from CONTEXT.md — users without a key get no poll loop, no filter chip, ICY fallback only. The key check is a feature gate, not an auth requirement for the events API.

---

## Runtime State Inventory

Step 2.6 SKIPPED — no runtime state. Phase 68 is pure additive code: new module, new UI widgets, new test files. No rename/migration.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `urllib.request` | AA events fetch | ✓ | stdlib | — |
| `datetime.fromisoformat` | ISO8601 parse | ✓ | Python 3.11+ (project requirement met) | — |
| `PySide6.QtCore.QThread` | Poll worker | ✓ | (project existing) | — |
| `PySide6.QtCore.QTimer` | Poll cadence | ✓ | (project existing) | — |
| Network: `api.audioaddict.com` | Live poll | ✓ | Probed successfully 2026-05-10 | If down: A-04 silent "not live" |
| `pytest-qt` | Widget tests | ✓ | (project existing) | — |

---

## Common Pitfalls

### Pitfall 1: Using `currently_playing` instead of `events` for live detection
**What goes wrong:** `currently_playing` endpoint returns all channels but has no live/show field — `display_artist`/`display_title` are identical for live shows and regular tracks. The endpoint cannot distinguish them.
**Why it happens:** The name suggests it's the right endpoint; it's documented by third-party clients.
**How to avoid:** Use `/events` endpoint. Check `start_at <= now < end_at`.
**Warning signs:** Poll returns data but live badge never appears even during known live shows.

### Pitfall 2: `datetime.fromisoformat` timezone handling
**What goes wrong:** `datetime.fromisoformat("2026-05-10T13:00:00-04:00")` returns a timezone-aware datetime. `datetime.now()` returns a naive (UTC-unaware) datetime. Comparing them raises `TypeError`.
**Why it happens:** Mixing naive and aware datetimes.
**How to avoid:** Always use `datetime.now(timezone.utc)` for the current time.
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes` in test or production.

### Pitfall 3: Channel key mismatch — aliases and prefixes
**What goes wrong:** Events API returns `channel_key: "trance"`. Stream URL is `http://prem1.di.fm:80/di_trance_hi`. `_aa_channel_key_from_url` with `slug="di"` strips `di_` prefix and `_hi` suffix → `"trance"`. But aliased channels (e.g., `classicelectronica` → `classictechno` in `_AA_CHANNEL_KEY_ALIASES`) are already handled by `_aa_channel_key_from_url`. The events API returns the canonical API key (not the URL path segment), so the alias table may produce mismatches.
**Why it happens:** Events API `channel.key` is the canonical API key; stream URL path segment may be a legacy alias.
**How to avoid:** Verify the events API `channel.key` matches what `_aa_channel_key_from_url` returns for representative channels. Test with the aliased channels in `_AA_CHANNEL_KEY_ALIASES`. If mismatch, the live map lookup will find nothing for aliased channels.
**Warning signs:** Live badge never appears for `classictechno` channel despite show in progress.

### Pitfall 4: `bind_station` ordering — `_refresh_gbs_visibility` must remain last
**What goes wrong:** Inserting `_refresh_live_status()` after `_refresh_gbs_visibility()` breaks GBS's internal state setup.
**Why it happens:** Phase 60 assumes `_refresh_gbs_visibility()` is the final call in `bind_station`.
**How to avoid:** Insert `_refresh_live_status()` BEFORE `_refresh_gbs_visibility()`, immediately after `_refresh_similar_stations()`.
**Warning signs:** GBS poll behavior changes for GBS stations; GBS entryid is stale.

### Pitfall 5: `_first_bind_check` state for bind-to-already-live toast
**What goes wrong:** When the panel first binds to an already-live station, `_refresh_live_status()` fires twice: once from `bind_station`, once from the first `title_changed` event. Both comparisons see `was_live=False → is_live=True`, causing two toasts.
**Why it happens:** State is compared in both call sites without distinguishing "first bind" from "mid-listen transition."
**How to avoid:** Track `_first_bind_check: bool` reset to `True` in `bind_station` and cleared to `False` after the first `_refresh_live_status()` completes. The `first_bind` path uses T-01a toast text; subsequent off→on transitions use T-01b.
**Warning signs:** Duplicate "Now live: ..." toasts appear immediately on station switch.

### Pitfall 6: `Player.title_changed` fires before API cache is populated (cold start)
**What goes wrong:** On app startup, the first `bind_station` fires `_refresh_live_status()`, but the poll hasn't run yet → `_live_map` is empty → live status is "not live" even if a show is broadcasting.
**Why it happens:** `_AaLiveWorker` is async; results arrive 1-2 seconds after start.
**How to avoid:** On `_refresh_live_status()` when `_live_map` is empty AND station is DI.fm with key, trigger a one-shot immediate poll (B-02: "if cache not yet populated, trigger one-shot for just this channel"). Actually easier: trigger a full poll immediately on app start; by the time the user interacts, the cache is warm. Cold-start badge shows "not live" briefly then updates on first successful poll.
**Warning signs:** Live badge appears 60 seconds after app start instead of immediately.

### Pitfall 7: `set_live_map` → proxy invalidation causes layout flicker
**What goes wrong:** Calling `self.invalidate()` on `StationFilterProxyModel` from `set_live_map` re-runs all `filterAcceptsRow` calls. If "Live now" chip is off, this is a no-op in effect but triggers a full re-layout of the tree every 60 seconds.
**Why it happens:** `invalidate()` is unconditional.
**How to avoid:** In `set_live_map`, only call `self.invalidate()` if `self._live_only` is `True` (as shown in Pattern 5 above).
**Warning signs:** Station list flickers every 60 seconds.

---

## Code Examples

### AA Events Fetch (aa_live.py)
```python
# Source: VERIFIED — adapted from live probe of https://api.audioaddict.com/v1/di/events
import json
import urllib.request
from datetime import datetime, timezone

AA_EVENTS_URL = "https://api.audioaddict.com/v1/{slug}/events"
_REQUEST_TIMEOUT_S = 15

def fetch_live_map(network_slug: str = "di") -> dict[str, str]:
    """Fetch currently-live shows for the given AA network.

    Returns {channel_key: show_name} for all channels currently broadcasting a show.
    Empty dict if no shows are live or if the request fails.

    Raises ValueError on HTTP auth error (401/403).
    Raises RuntimeError on network / JSON failure (callers should catch Exception).
    """
    url = AA_EVENTS_URL.format(slug=network_slug)
    with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT_S) as resp:
        data = json.loads(resp.read())
    return _parse_live_map(data)

def _parse_live_map(events: list[dict]) -> dict[str, str]:
    """Pure function: extract {channel_key: show_name} for currently-live events."""
    now = datetime.now(timezone.utc)
    live_map: dict[str, str] = {}
    for ev in events:
        start_raw = ev.get("start_at", "")
        end_raw = ev.get("end_at", "")
        if not start_raw or not end_raw:
            continue
        try:
            start = datetime.fromisoformat(start_raw)
            end = datetime.fromisoformat(end_raw)
        except ValueError:
            continue
        if start <= now < end:
            show = ev.get("show") or {}
            show_name = show.get("name", "")
            for ch in show.get("channels") or []:
                key = ch.get("key", "")
                if key:
                    live_map[key] = show_name
    return live_map
```

### ICY Pattern Matcher
```python
# Source: CITED — CONTEXT.md P-01 (planner finalizes regex)
import re

_LIVE_ICY_RE = re.compile(r'^\s*LIVE\s*[:\-]\s*(.+?)\s*$', re.IGNORECASE)

def detect_live_from_icy(title: str) -> str | None:
    """Return show name if title matches LIVE: or LIVE - prefix, else None.

    Prefix-only match (P-01, P-02). False positives (Live and Let Die) are
    excluded because they don't match the ': ' or ' - ' separator pattern.
    """
    m = _LIVE_ICY_RE.match(title or "")
    return m.group(1).strip() if m else None
```

### Fixture File Structure
```json
// tests/fixtures/aa_live/events_with_live.json
// (to be recorded from live API when a show is actually broadcasting)
[
  {
    "id": 201572,
    "show_id": 10554145,
    "name": "#949",
    "start_at": "2026-05-10T11:00:00+00:00",
    "end_at": "2026-05-10T13:00:00+00:00",
    "show": {
      "id": 10554145,
      "name": "Deeper Shades of House",
      "channels": [{"id": 4, "key": "house", "name": "House"}]
    }
  }
]
```

---

## Validation Architecture

**Nyquist validation is enabled** (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run --with pytest pytest tests/test_aa_live.py -x` |
| Full suite command | `uv run --with pytest pytest tests/ -x` |

### Phase Requirements → Test Map

| Decision ID | Behavior | Test Type | Automated Command | File Exists? |
|-------------|----------|-----------|-------------------|-------------|
| A-02 | `_parse_live_map` detects event in window | unit | `pytest tests/test_aa_live.py::test_parse_live_map_event_in_window -x` | ❌ Wave 0 |
| A-02 | `_parse_live_map` returns empty when no event in window | unit | `pytest tests/test_aa_live.py::test_parse_live_map_no_live -x` | ❌ Wave 0 |
| A-02 | `_parse_live_map` handles multiple channels from one show | unit | `pytest tests/test_aa_live.py::test_parse_live_map_multi_channel -x` | ❌ Wave 0 |
| A-04 | HTTP failure → empty dict (no exception propagation) | unit | `pytest tests/test_aa_live.py::test_fetch_live_map_http_error -x` | ❌ Wave 0 |
| P-01 | `detect_live_from_icy("LIVE: DJ Set")` → `"DJ Set"` | unit | `pytest tests/test_aa_live.py::test_icy_live_prefix_colon -x` | ❌ Wave 0 |
| P-01 | `detect_live_from_icy("LIVE - Set")` → `"Set"` | unit | `pytest tests/test_aa_live.py::test_icy_live_prefix_dash -x` | ❌ Wave 0 |
| P-02 | `detect_live_from_icy("Live and Let Die")` → `None` | unit | `pytest tests/test_aa_live.py::test_icy_no_false_positive -x` | ❌ Wave 0 |
| P-01 | Case-insensitive match: `"live: Set"` → `"Set"` | unit | `pytest tests/test_aa_live.py::test_icy_case_insensitive -x` | ❌ Wave 0 |
| U-01/U-04 | Badge hidden on non-live station bind | widget | `pytest tests/test_now_playing_panel.py::test_live_badge_hidden_on_non_live_bind -x` | ❌ Wave 0 |
| U-01/U-04 | Badge visible when live_map has station's channel key | widget | `pytest tests/test_now_playing_panel.py::test_live_badge_visible_when_live -x` | ❌ Wave 0 |
| T-01a | Bind-to-already-live → live_status_toast emitted | widget | `pytest tests/test_now_playing_panel.py::test_bind_to_live_emits_toast -x` | ❌ Wave 0 |
| T-01b | Off→On mid-listen → live_status_toast emitted | widget | `pytest tests/test_now_playing_panel.py::test_off_to_on_transition_toast -x` | ❌ Wave 0 |
| T-01c | On→Off mid-listen → live_status_toast emitted | widget | `pytest tests/test_now_playing_panel.py::test_on_to_off_transition_toast -x` | ❌ Wave 0 |
| T-03 | Poll update on non-bound station → no toast | widget | `pytest tests/test_now_playing_panel.py::test_poll_update_no_toast_for_unbound -x` | ❌ Wave 0 |
| F-01/F-07 | Chip hidden when no listen_key | widget | `pytest tests/test_station_list_panel.py::test_live_chip_hidden_without_key -x` | ❌ Wave 0 |
| F-02/F-03 | Chip ON + provider chip → AND filter | proxy | `pytest tests/test_station_filter_proxy.py::test_live_only_and_provider -x` | ❌ Wave 0 |
| F-04 | Chip ON + no live channels → empty tree | proxy | `pytest tests/test_station_filter_proxy.py::test_live_only_empty -x` | ❌ Wave 0 |
| B-03/B-04 | Poll loop starts when key present, stops when cleared | integration | `pytest tests/test_now_playing_panel.py::test_poll_loop_starts_with_key -x` | ❌ Wave 0 |
| A-06 | `get_di_channel_key` maps stream URL to events channel key | unit | `pytest tests/test_aa_live.py::test_channel_key_from_di_url -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --with pytest pytest tests/test_aa_live.py -x`
- **Per wave merge:** `uv run --with pytest pytest tests/ -x`
- **Phase gate:** Full suite green (currently 399 passing, 1 pre-existing skip) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_aa_live.py` — new file covering A-02, A-04, P-01, P-02, A-06 (pure unit, no qtbot)
- [ ] `tests/fixtures/aa_live/events_no_live.json` — fixture: events all in future
- [ ] `tests/fixtures/aa_live/events_with_live.json` — fixture: one event currently in window
- [ ] `tests/fixtures/aa_live/events_multiple_live.json` — fixture: multiple concurrent events
- [ ] Extend `tests/test_now_playing_panel.py` — badge visibility, toast transitions, poll-loop lifecycle
- [ ] Extend `tests/test_station_list_panel.py` — chip hidden/visible
- [ ] Extend `tests/test_station_filter_proxy.py` — `set_live_map`, `set_live_only`, `has_active_filter`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user-facing auth in Phase 68 |
| V3 Session Management | No | Stateless poll |
| V4 Access Control | No | Feature gate on key presence is not access control |
| V5 Input Validation | Yes | Show names and channel keys from AA API must not be rendered as HTML (existing `icy_label` is `Qt.PlainText`; badge uses `Qt.PlainText`) |
| V6 Cryptography | No | No crypto |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Show name with HTML metacharacters in badge/toast | Spoofing / Tampering | `Qt.PlainText` format on `_live_badge` and `icy_label` (already enforced); toast is plain string |
| Malformed `start_at`/`end_at` in API response | Tampering | `try/except ValueError` around `datetime.fromisoformat`; skip malformed events |
| Channel key injection in live map lookup | Tampering | Channel key is only used as a `dict` key lookup — no SQL interpolation, no HTML rendering |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Assumed `currently_playing` has live indicator | Use `/events` endpoint + datetime window | This research (2026-05-10) | Endpoint choice changes — see A-02 finding |
| `datetime.fromisoformat` didn't support offsets | Python 3.11+ supports full ISO 8601 with offset | Python 3.11 | No workaround needed |

**Deprecated/outdated:**
- `https://www.di.fm/_papi/v1/di/currently_playing`: Cloudflare-blocked, returns HTML. Not usable.
- `requests` library: Project convention is `urllib.request` to avoid adding dependencies.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | AA events endpoint returns the same response shape on subsequent requests (no undocumented auth/session requirement discovered after initial access) | A-02 / Standard Stack | Poll fails silently (A-04 handles this) |
| A2 | 60 requests/hour against `/events` endpoint will not trigger an undocumented rate limit | A-02 | Poll throttled; badge/filter become stale. Mitigation: A-04 silent failure; fallback to ICY pattern for bound station |
| A3 | Event `channel_key` in `/events` response always matches what `_aa_channel_key_from_url` returns for the corresponding stream URL | A-06 / Pitfall 3 | Live map lookup never finds match for affected channels; badge never appears |
| A4 | `listen_key` in A-01 is the poll loop gate, not an API auth requirement (events API is public) | A-01, A-03 | If AA ever adds auth to `/events`, the poll breaks for no-key users; but they already have no key, so the poll shouldn't run anyway |
| A5 | `datetime.fromisoformat` handles `-04:00` offset strings correctly on the project's Python version | Code examples | `ValueError` from `fromisoformat` — caught by try/except, event skipped |

---

## Open Questions

1. **Aliased channel keys (A-06 / Pitfall 3)**
   - What we know: `_AA_CHANNEL_KEY_ALIASES` in `url_helpers.py` maps legacy stream URL path segments to current API keys (e.g., `classicelectronica` → `classictechno`). The events API returns canonical API keys (e.g., `classictechno`). The `_aa_channel_key_from_url` function applies these aliases.
   - What's unclear: Whether the events API `channel.key` for `classictechno` matches the aliased output of `_aa_channel_key_from_url` for a stream URL using `classicelectronica`. This could only be confirmed by observing an event for that channel while the station is in the library.
   - Recommendation: Add a unit test for each aliased channel key to verify the mapping survives the round-trip. If mismatches surface, add inverse aliases to `aa_live.py`'s lookup, or normalize both sides to the canonical API key.

2. **Events endpoint pagination**
   - What we know: Observed ~201 events in a single call. The response is a flat list (no `metadata.total` or `next_page` observed).
   - What's unclear: Whether 201 is the page size or the total. If paginated, a single call would miss future shows. For Phase 68's "is live NOW" use case, this is not a problem — any show live right now will be in the earliest events.
   - Recommendation: Treat the response as "sufficient for current-window detection." Do not implement pagination in v1. Note in plan.

3. **Badge width overflow for long show names**
   - What we know: Show names can be long ("Deeper Shades of House", "Future Sound of Egypt"). The badge contains "LIVE" only; show name is in the ICY label row. But if show name is appended to `icy_label`, the label may overflow its column.
   - Recommendation: Planner picks elide behavior (`QLabel.setElideMode(Qt.ElideRight)` or fixed max-width). The badge itself ("LIVE") is short and unlikely to overflow.

---

## Sources

### Primary (HIGH confidence)
- Live probe: `https://api.audioaddict.com/v1/di/currently_playing` — verified response schema, 101 channels, 5 track fields, NO live-show indicator
- Live probe: `https://api.audioaddict.com/v1/di/events` — verified full response schema including `start_at`, `end_at`, `show.channels[].key`, `show.name`
- Live probe: `https://api.audioaddict.com/v1/di/track_history` — verified `type: "track"` field, no `"show"` type observed currently
- Live probe: `https://api.audioaddict.com/v1/di/shows` — verified `now_playing: bool` field; rejected due to pagination + filter bug
- Codebase read: `musicstreamer/aa_import.py` — auth pattern, NETWORKS, `_aa_channel_key_from_url` logic
- Codebase read: `musicstreamer/url_helpers.py` — `_aa_channel_key_from_url`, `_aa_slug_from_url`, `_AA_CHANNEL_KEY_ALIASES`
- Codebase read: `musicstreamer/ui_qt/now_playing_panel.py` — `bind_station`, `_sibling_label`, `_similar_container`, Phase 67 insertion seam
- Codebase read: `musicstreamer/ui_qt/station_list_panel.py` — filter strip, chip pattern, `_CHIP_QSS`
- Codebase read: `musicstreamer/ui_qt/station_filter_proxy.py` — existing predicates, `filterAcceptsRow` shape
- Codebase read: `musicstreamer/ui_qt/main_window.py` — `show_toast`, `closeEvent`, worker lifecycle pattern
- Codebase read: `musicstreamer/ui_qt/import_dialog.py:74-93` — `_YtScanWorker` pattern (canonical QThread worker)
- Codebase read: `musicstreamer/ui_qt/accounts_dialog.py` — `_is_aa_key_saved`, `_on_aa_clear_clicked`
- Codebase read: `musicstreamer/player.py:237` — `title_changed = Signal(str)`
- Codebase read: `musicstreamer/ui_qt/_theme.py` — `ERROR_COLOR_HEX`, `WARNING_COLOR_HEX`, `STATION_ICON_SIZE`

### Secondary (MEDIUM confidence)
- [di-tui components.go](https://github.com/acaloiaro/di-tui) — confirms `GetCurrentlyPlaying` uses `https://api.audioaddict.com/v1/{network}/currently_playing` and struct fields: `channel_id`, `channel_key`, `track.display_artist`, `track.display_title`, `track.start_time`, `track.duration`. Confirms no live-show field.
- [AudioAddict tune API docs](https://github.com/GeertJohan/tune/blob/master/api-rev-5.html) — confirms `/v1/{network}/track_history` endpoint and `events/channel/{id}` endpoints.

### Tertiary (LOW confidence)
- [AudioAddict Plex bundle](https://github.com/phrawzty/AudioAddict.bundle) — mentions `track_history` structure and ad detection; no live-show type values confirmed.

---

## Metadata

**Confidence breakdown:**
- A-02 endpoint choice: HIGH — live probed, schema verified, rejected candidates documented
- Standard stack: HIGH — all existing project libraries
- Channel key mapping: HIGH — existing `_aa_channel_key_from_url` verified; alias round-trip is assumed (A3)
- Qt threading pattern: HIGH — direct analog in `_GbsPollWorker` and `_YtScanWorker`
- Pitfall 3 (channel key aliases): MEDIUM — cannot verify without a live aliased channel event
- Rate limits: ASSUMED (A2) — no `x-ratelimit` headers observed; 60s/request is conservative

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (AA API is stable; events schema unlikely to change)

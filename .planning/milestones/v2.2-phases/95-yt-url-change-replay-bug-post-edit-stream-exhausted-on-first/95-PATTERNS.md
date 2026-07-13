# Phase 95: YT URL-change replay bug — Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 5 (all MODIFY — no new source files; one new test file optional)
**Analogs found:** 5 / 5 (all in-codebase; every mechanism this fix needs already exists)

This is a wiring + one-guard + one-decision-method bug fix. There are NO new
capabilities. Every pattern below is copied from a proven, current site in the
same repo. Line numbers were re-verified against live code on 2026-06-18 (they
match RESEARCH.md within ±2 lines where noted).

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/player.py` (MODIFY) | service (playback engine, QObject) | event-driven + request-response | self — `_preroll_seq` guard + `play()` rebuild path | exact (in-file) |
| `musicstreamer/ui_qt/main_window.py` (MODIFY) | controller (Qt wiring) | event-driven (signal slot) | self — `_sync_now_playing_station` (panel rebind) | exact (in-file) |
| `musicstreamer/ui_qt/edit_station_dialog.py` (likely UNCHANGED) | controller (dialog) | request-response (persist + emit) | self — `_on_save` → `station_saved.emit()` | exact (in-file) — see "No Analog / No Change" |
| `tests/_fake_player.py` (MODIFY) | test double | — | self — existing Signal mirror + method stubs | exact (in-file) |
| `tests/test_player_failover.py` OR new `tests/test_player_edit_invalidation.py` (MODIFY/CREATE) | test | — | `tests/test_player_failover.py` `make_player`/`make_stream` | exact |

**Generic, not YouTube-only (D-04 / Specifics):** the queue/URI invalidation and
URL-change detection are stream-type-agnostic and live in `player.py`. Only the
resolve-generation guard (Pattern 2) is YouTube-specific, because only YouTube
has an async daemon-thread resolver.

---

## Pattern Assignments

### `musicstreamer/player.py` — new `invalidate_for_edit(station, is_playing)` + `_youtube_resolve_seq` guard (service, event-driven)

**Analog A — the proven full-rebuild path to REUSE for the D-01 restart case.**
Do NOT hand-roll a partial queue reset. Re-issue `self.play(updated_station, ...)`;
it already does the complete reset.

`musicstreamer/player.py:674-734` (`Player.play`):
```python
def play(self, station: Station, on_title=None, preferred_quality: str = "",
         on_failover=None, on_offline=None) -> None:
    # Cancel any in-progress failover from previous play
    self._cancel_timers()                       # :677
    self._streams_queue = []                    # :678  full reset
    self._recovery_in_flight = False            # :679
    # WR-02: tear down any leaked preroll handler from a prior play()/stop()
    if self._preroll_in_flight or self._preroll_handler_id:   # :690
        self._preroll_seq += 1                  # :691  (note: this idiom is the analog for Pattern 2)
        if self._preroll_handler_id:
            try:
                self._pipeline.disconnect(self._preroll_handler_id)
            except (TypeError, RuntimeError):
                pass
            self._preroll_handler_id = 0
        self._preroll_in_flight = False         # :698
    self._install_legacy_callbacks(on_title, on_failover, on_offline)
    self._current_station_name = station.name   # :700
    self._current_station_id = station.id        # :701
    self._is_first_attempt = True               # :702
    self._twitch_resolve_attempts = 0           # :703
    if not station.streams:
        self.title_changed.emit("(no streams configured)")  # :706  (Pitfall 6 no-streams guard)
        return
    streams_by_position = order_streams(station.streams)     # :714
    # ... preferred-stream-id / preferred-quality logic :715-732 ...
    self._streams_queue = queue                 # :734
    # ... preroll gate :735+ ; _try_next_stream() at the tail of play() ...
```
**Copy intent:** D-01 (URL of currently-playing stream changed AND actively
playing) → call `self.play(updated_station, ...)`. Re-using `play()` gets you
`_cancel_timers`, `_streams_queue` reset, preroll teardown (WR-02),
`_is_first_attempt = True`, `order_streams`, and the no-streams guard for free
(Pitfall 6 — deleted-playing-stream).

---

**Analog B — the generation-guard idiom to MIRROR for the in-flight YouTube race (Pattern 2, Pitfall 1).**
The YouTube resolver has NO equivalent today; the preroll path is the project's
proven idiom for "ignore a stale in-flight async result."

`musicstreamer/player.py:576-583` (declaration + rationale):
```python
# CR-01 / WR-03 (Phase 83 code review): monotonic preroll-attempt
# counter. Bumped by _start_preroll (new handoff opens) and by
# _handle_gst_error_recovery's preroll branch (in-flight handoff cancelled).
# The about-to-finish streaming-thread callback captures _preroll_seq at
# emit time; the main-thread slot ignores any delivery whose stamp !=
# _preroll_seq. Cross-thread int read is atomic in CPython (same
# justification as _preroll_in_flight).
self._preroll_seq: int = 0                       # :583  ← declare _youtube_resolve_seq: int = 0 alongside this
```

`musicstreamer/player.py:1561-1572` (capture seq at emit time, streaming/worker side):
```python
def _on_preroll_about_to_finish_callback(self, pipeline) -> None:
    # ONLY emits the queued Signal. NEVER call Qt API from this body.
    self._preroll_about_to_finish_requested.emit(self._preroll_seq)   # :1572  capture-at-emit
```

`musicstreamer/player.py:1574-1616` (main-thread slot rejects stale deliveries):
```python
def _on_preroll_about_to_finish(self, expected_seq: int = 0) -> None:
    if expected_seq != self._preroll_seq:        # :1615  ← the no-op-if-stale check to mirror
        return  # CR-01: stale slot — bus-error or new preroll superseded this one
    ...
```
Note the default `expected_seq: int = 0` so synchronous test calls (no `play()`
first) still pass the guard — mirror this defaulting in the YouTube slot.

**The YouTube path to widen (where the guard must land):**

`musicstreamer/player.py:273-274` (signal declarations — arity drift point, Pitfall 4):
```python
youtube_resolved           = Signal(str, bool)  # internal: (resolved_url, is_live)
youtube_resolution_failed  = Signal(str)        # internal: yt-dlp error message
```

`musicstreamer/player.py:1856-1870` (`_play_youtube` — spawn point; capture seq here):
```python
def _play_youtube(self, url: str) -> None:
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    if self._current_station_name:
        self.title_changed.emit(self._current_station_name)
    threading.Thread(
        target=self._youtube_resolve_worker, args=(url,), daemon=True   # :1869  ← add seq to args, OR stamp instance attr
    ).start()
```

`musicstreamer/player.py:1953` (worker emit — inside `_youtube_resolve_worker`):
```python
self.youtube_resolved.emit(resolved, is_live)   # :1953  ← carry seq if Signal-carry approach chosen
```

`musicstreamer/player.py:1957-1974` (the two main-thread slots that must no-op on stale seq):
```python
def _on_youtube_resolved(self, resolved_url: str, is_live: bool) -> None:
    # ← INSERT: if captured_seq != self._youtube_resolve_seq: return  (Pitfall 1 / V5)
    self._pending_live_dvr_seek = is_live        # :1966
    self._set_uri(resolved_url)                  # :1967  ← this is the OLD-url clobber if unguarded
    self._failover_timer.start(self._current_buffer_duration_s * 1000)  # :1968

def _on_youtube_resolution_failed(self, msg: str) -> None:
    self.playback_error.emit(f"YouTube resolve failed: {msg}")  # :1973
    self._try_next_stream()                       # :1974
```

**Two acceptable implementations (RESEARCH Open Q3 — planner picks one):**
1. **Signal-carry (mirrors preroll exactly, more auditable):** widen
   `youtube_resolved = Signal(str, bool, int)`, capture `seq = self._youtube_resolve_seq`
   in `_play_youtube`, pass through worker → emit → slot, check in slot.
   **REQUIRES updating `tests/_fake_player.py:64` in the SAME wave** (trips the
   parity guard — see that file's assignment below).
2. **Instance-attribute (no Signal arity change):** store
   `self._youtube_pending_seq` on the instance, stamp at spawn, compare in slot.
   Same CPython-atomic int justification as `_preroll_in_flight` (`:573`). No
   FakePlayer edit needed.
RESEARCH recommends #1 for auditability; either is acceptable.

---

**URL-change detection (Discretion / D-02 / Pitfall 3):** compare the STORED
`StationStream.url`, never the resolved playbin3 URI.

`musicstreamer/models.py:12-23` (`StationStream` — `.id`, `.url`, `.station_id`):
```python
@dataclass
class StationStream:
    id: int
    station_id: int
    url: str
    label: str = ""
    quality: str = ""
    ...
```
- The playing stream is `self._current_stream` (`player.py:563` decl, assigned
  in `_try_next_stream` at `:1455`). Its `.url` holds the STORED user-typed URL,
  NOT the resolved HLS URL (RESEARCH A2, HIGH confidence — `_set_uri` receives
  the resolved url separately and never mutates `_current_stream.url`).
- Match `updated_station.streams` by `stream.id`; compare
  `old_url.strip() != new_url.strip()` (RESEARCH recommends raw `.strip()`
  equality over `aa_normalize_stream_url` to avoid false "unchanged").

**State-lifecycle gotchas the new method MUST respect (Pitfall 2):**
- `pause()` (`player.py:834-862`) and `stop()` (`:864-900`) clear
  `_streams_queue` (`:853`/`:874`) but do NOT clear `_current_stream` /
  `_current_station_id`. So `_current_station_id == updated.id` alone does NOT
  prove audio is live. Gate the D-01 restart on the panel's `is_playing` flag
  passed in from the caller (see main_window assignment).
- D-04/D-05 invalidate-only path: set `_streams_queue = []` and
  `_current_stream = None`, bump `_youtube_resolve_seq`. Do NOT call
  `set_state(NULL)` when audio is live and a NON-playing stream was edited.

---

### `musicstreamer/ui_qt/main_window.py` — wire the player notification at the existing junction (controller, event-driven)

**Analog — `_sync_now_playing_station` (the panel-only rebind; the FIX adds the player call here).**

`musicstreamer/ui_qt/main_window.py:1430-1442`:
```python
def _sync_now_playing_station(self, station_id: int) -> None:
    """Re-fetch station from DB and rebind the now-playing panel."""
    updated_station = self._repo.get_station(station_id)   # :1437
    if updated_station is None:
        return
    current = getattr(self.now_playing, "_station", None)  # :1440
    if current is not None and current.id == updated_station.id:
        self.now_playing.bind_station(updated_station)     # :1442  ← PANEL ONLY (the gap)
        # FIX ADDS: notify the Player to invalidate/restart.
        # e.g. self._player.invalidate_for_edit(
        #          updated_station, is_playing=self.now_playing.is_playing)
```

**Wiring source (read-only context):** `_on_edit_requested` (`main_window.py:1332-1346`)
connects `dlg.station_saved` → `_refresh_station_list` (`:1340`) and
→ `lambda: self._sync_now_playing_station(fresh.id)` (`:1341`). The slot runs on
the main thread (Qt signal), so calling `self._player.invalidate_for_edit(...)`
directly is safe (RESEARCH A3, HIGH confidence — `play()` is already called
from `_on_station_activated` on the main thread).

**`is_playing` source** — `NowPlayingPanel.is_playing` property
(`now_playing_panel.py:961-964`), already reachable via `self.now_playing`:
```python
@property
def is_playing(self) -> bool:
    return self._is_playing
```

**Placement decision (RESEARCH note at §Code Examples):** the panel rebind is
gated on `current.id == updated_station.id`. The cleanest option is to always
pass `updated_station` to the Player and let `invalidate_for_edit` decide
(it checks `_current_station_id` itself), keeping id-match logic in ONE place.
Planner picks; "pass-and-let-player-decide" is recommended.

---

### `tests/_fake_player.py` — Signal mirror + new method stub (test double)

**Analog — the existing Signal-mirror block and method-stub convention in the same file.**

`tests/_fake_player.py:64` (the line that changes ONLY if Signal-carry approach chosen):
```python
youtube_resolved           = Signal(str, bool)  # BUG-YT-LIVE-BUFFER D-02: (resolved_url, is_live)
```
If `youtube_resolved` is widened to `Signal(str, bool, int)` in player.py, this
line MUST be updated to identical arity in the SAME wave (Rule 1 convention,
file header `:14-22`). Otherwise the parity guard goes red (see next file).

**New method stub** — mirror the existing call-recording stubs
(`tests/_fake_player.py:116-129`, e.g. `play`/`play_stream`):
```python
def play(self, station: Station, **kwargs) -> None:
    self.play_calls.append(station)         # :116-117  ← copy this call-recording shape
```
Add `invalidate_for_edit(self, station, is_playing=...)` (or `reload_station`)
recording calls into a new `self.invalidate_calls: list` initialized in
`__init__` alongside `self.play_calls` (`:98`). MainWindow integration test (V7)
asserts on it.

---

### `tests/test_player_failover.py` (extend) OR new `tests/test_player_edit_invalidation.py` — coverage V1-V6, V10 (test)

**Analog — the existing Player unit-test harness in `test_player_failover.py`.**

`tests/test_player_failover.py:16-50`:
```python
def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    player._pipeline = MagicMock()              # :26  pipeline is a MagicMock — assert set_property/set_state calls
    return player

def make_stream(id_, position, quality, url="http://stream.test/"):
    return StationStream(id=id_, station_id=1, url=f"{url}{id_}",
                         quality=quality, position=position)   # :31-37

def make_station_with_streams(streams):
    return Station(id=1, name="Test Station", provider_id=None,
                   provider_name=None, tags="", station_art_path=None,
                   album_fallback_path=None, streams=streams)   # :41-50
```
**Copy intent:** drive the new `invalidate_for_edit` directly; assert
`_streams_queue`/`_current_stream`/`_set_uri` outcomes. For V5 (race),
emit `player.youtube_resolved.emit(OLD, False, stale_seq)` (or set the stale
instance seq) AFTER an invalidate and assert `_set_uri` was NOT called with the
old url. Patch `_set_uri`/`_play_youtube` with MagicMock to assert call args
without a real pipeline.

---

## Shared Patterns

### Cross-thread marshaling — queued Signal only
**Source:** `musicstreamer/player.py:273-274` (`youtube_resolved`/`youtube_resolution_failed`),
`:304` (`_preroll_about_to_finish_requested`).
**Apply to:** any worker→main hop in the fix.
The fix runs on the MAIN thread (invoked from a Qt signal slot), so it may call
Player methods directly. Any NEW worker→main path must use a queued Signal
(qt-glib-bus-threading Rule 2 — no bare `QTimer.singleShot` from a non-Qt thread).

### Generation-guard for stale async results
**Source:** `musicstreamer/player.py:583` (decl), `:1572` (capture-at-emit), `:1615` (no-op-if-stale).
**Apply to:** the YouTube resolve path (new `_youtube_resolve_seq`). Bump on
every restart/invalidate (in `play()` and in `invalidate_for_edit`); capture at
worker spawn; reject deliveries whose captured seq != current.

### FakePlayer parity drift-guard (mandatory if Signal arity changes)
**Source:** `tests/test_fake_player_signal_parity.py` (name + arity, source-grep based).
**Apply to:** `tests/_fake_player.py` — if `youtube_resolved` arity changes,
update the mirror in the same wave or `test_fake_player_signal_arity_matches_player`
fails. The test regex `^\s*NAME = Signal(ARGS)` source-parses both files
(`:33-43`); the FakePlayer string must match the player.py string exactly.

### Re-fetch + ordering (no new SQL/sort)
**Source:** `repo.get_station` + `order_streams()` (`stream_ordering.py:46`), already
used by `play()` (`player.py:714`) and `_sync_now_playing_station` (`main_window.py:1437`).
**Apply to:** the invalidation path — receive the already-fetched
`updated_station`; do not re-query inside the Player.

---

## No Analog / No Change Expected

| File | Role | Why |
|------|------|-----|
| `musicstreamer/ui_qt/edit_station_dialog.py` `_on_save` (`:1713`) | dialog | Already correctly persists URL via `repo.update_stream` (`:1814`) and emits `station_saved` (`:1838`). The fix is DOWNSTREAM of this signal. RESEARCH: "it should NOT change." Only touch if planner moves the wiring here instead of `_sync_now_playing_station` (D-Discretion); default keeps it unchanged. V8 is a regression-only assertion. |
| `musicstreamer/repo.py` `update_stream`/`get_station` | repository | DB is the source of truth and is already correct after save (Runtime State Inventory). No change. |

There are NO files lacking an analog — every needed mechanism exists in-repo.

---

## Metadata

**Analog search scope:** `musicstreamer/player.py`, `musicstreamer/ui_qt/main_window.py`,
`musicstreamer/ui_qt/now_playing_panel.py`, `musicstreamer/ui_qt/edit_station_dialog.py`,
`musicstreamer/models.py`, `tests/_fake_player.py`, `tests/test_fake_player_signal_parity.py`,
`tests/test_player_failover.py`.
**Files scanned (read):** 8.
**Line-number verification:** re-checked against live code 2026-06-18; matches
RESEARCH.md citations (preroll seq decl `:583`, slot `:1574/1615`, `play()` `:674`,
YT path `:1856/1953/1957`, `_sync_now_playing_station` `:1430`, FakePlayer signal `:64`).
**Pattern extraction date:** 2026-06-18.
**Test runner reminder (MEMORY):** use `.venv/bin/python -m pytest`, scope tightly
(full suite >600s, 2 known unrelated failures).

# Phase 78 (Commit A only): Buffer underrun harvest infra — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 10 (2 created, 7 modified, 1 drift-guard already-passing)
**Analogs found:** 10 / 10 (every Commit A surface has a project-canonical analog)
**Scope:** Commit A only — file sink + cycle counter UI row. Commit B (behavior fix) is deferred.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/buffer_log.py` (new) | utility / helper module | install-time side effect (attach `logging.Handler`) | `musicstreamer/oauth_log.py` | exact (same primitive: `RotatingFileHandler` attached to a named logger) |
| `musicstreamer/paths.py` (mod) | path helper | pure function | `cookies_path()` / `gbs_cookies_path()` / `oauth_log_path()` in same file | exact (sibling helper) |
| `musicstreamer/player.py` (mod) | service / model — QObject state owner | event-driven (main-thread slot emits Signal) | existing `_on_underrun_cycle_closed` slot + `underrun_recovery_started = Signal()` in same file | exact (same call site, same Signal idiom) |
| `musicstreamer/__main__.py` (mod) | glue / app boot | one-shot install at startup | existing per-logger `setLevel(INFO)` block in `main()` + migration site in `_run_gui` | role-match (same boot phase; install must move to `_run_gui` post-migration per Pitfall 1) |
| `musicstreamer/ui_qt/now_playing_panel.py` (mod) | UI (QWidget) | request-response (`set_X` slot updates QLabel) | existing `_build_stats_widget` body (Buffer row) + `set_buffer_percent` slot in same file | exact (same form, same widget conventions) |
| `musicstreamer/ui_qt/main_window.py` (mod) | UI glue (wiring) | Signal → slot wiring | existing `self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)` at line 381 | exact (same precedent line, one over) |
| `tests/_fake_player.py` (mod) | test infra | INFRA-01 drift-guard mirror | existing `underrun_recovery_started = Signal()` in same file at line 69 | exact (parity mirror — required by drift-guard) |
| `tests/test_buffer_events_log.py` (new) | test | unit | `tests/test_oauth_log.py` (rotation, attribute introspection, `tmp_path` pattern) | exact (same handler shape, same fixture conventions) |
| `tests/test_player_underrun_count.py` (new) | test | unit | `tests/test_player_underrun.py` (Player-with-mocked-pipeline) + `tests/test_player_underrun_tracker.py` (pure-state) | exact (two analogs both apply) |
| `tests/test_paths.py` (mod) | test | unit | existing `test_oauth_log_path_honors_root_override` / `test_oauth_log_path_does_not_create_file` in same file | exact (sibling test cases) |
| `tests/test_now_playing_panel.py` (mod) | test (qtbot) | UI test | existing `test_buffer_bar_properties` / `test_set_buffer_percent_updates_both` in same file | exact (Stats-for-nerds row test stack) |
| `tests/test_main_window_underrun.py` (mod) | test (qtbot) | integration | existing `test_first_call_shows_toast` in same file | exact (MainWindow + FakePlayer + qtbot integration template) |

---

## Pattern Assignments

### `musicstreamer/buffer_log.py` (new — utility helper, install-time side effect)

**Analog:** `musicstreamer/oauth_log.py:55-71`
**Critical difference from analog:** `propagate=True` (default — keep stderr parity) instead of `oauth_log.py`'s `propagate=False`. NO `0o600` chmod (D-03: diagnostic data, not credentials). Module-level idempotent install function instead of a class (caller is `__main__._run_gui`, not user code).

**Imports pattern** (mirrors `oauth_log.py:6-12`):
```python
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from musicstreamer import paths
```

**Handler-shape pattern** (`oauth_log.py:55-70` — copy maxBytes/backupCount/encoding shape; change values to D-02 spec):
```python
# oauth_log.py:55-70 — project-canonical RotatingFileHandler install
self._logger = logging.getLogger(f"musicstreamer.oauth.{id(self)}")
self._logger.setLevel(logging.INFO)
self._logger.propagate = False                       # <-- DO NOT mirror this for buffer_log
handler = RotatingFileHandler(
    log_path,
    maxBytes=64 * 1024,                              # <-- buffer_log uses 1_048_576 (D-02)
    backupCount=2,                                   # <-- buffer_log uses 3 (D-02)
    encoding="utf-8",
)
handler.setFormatter(logging.Formatter("%(message)s"))  # <-- buffer_log uses "%(asctime)s %(message)s"
self._logger.addHandler(handler)
```

**Idempotency pattern** (RESEARCH.md Pitfall 7, lines 382-392 — new pattern, no exact in-tree precedent; closest is single-instance-style guard):
```python
def install_buffer_events_handler() -> None:
    path = paths.buffer_events_log_path()
    log = logging.getLogger("musicstreamer.player")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed — short-circuit (Pitfall 7)
    handler = RotatingFileHandler(
        path,
        maxBytes=1_048_576,        # D-02
        backupCount=3,             # D-02
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
```

**Why a separate module (not inline in `__main__.py`):** RESEARCH.md Open Q4 / Recommendation (b) — narrow testable helper, matches `cookie_utils.py` / `desktop_install.py` / `yt_dlp_opts.py` project shape. Test surface is clean (call function, introspect handlers).

---

### `musicstreamer/paths.py` (modified — add `buffer_events_log_path()` helper)

**Analog:** `musicstreamer/paths.py:46-65` (`cookies_path` / `oauth_log_path` / `gbs_cookies_path` siblings)

**Add helper** (line ~66, after `oauth_log_path`):
```python
# paths.py:63-65 — analog (verbatim):
def oauth_log_path() -> str:
    """Phase 999.3 D-10: path to the persistent OAuth diagnostic log."""
    return os.path.join(_root(), "oauth.log")
```

**New helper** (same shape, mirror filename + docstring + Phase tag):
```python
def buffer_events_log_path() -> str:
    """Phase 78 / BUG-09 D-03: path to the size-rotated buffer-event diagnostic log."""
    return os.path.join(_root(), "buffer-events.log")
```

**Invariant from analog (lines 11-15 of `paths.py`):** Module is pure — does NOT create directories. Caller (`install_buffer_events_handler()`) trusts `migration.run_migration()` to have created `data_dir()` first. NO `os.makedirs(...)` here.

---

### `musicstreamer/player.py` (modified — class-level Signal + `__init__` field + slot increment/emit)

**Analog 1 — class-level Signal declaration** (`player.py:271-277`):
```python
# Phase 62 / BUG-09: buffer-underrun cycle Signals.
# _underrun_cycle_opened / _underrun_cycle_closed are bus-loop → main
# queued (Pitfall 2 — bus handlers may only emit Signals).
# underrun_recovery_started is main → MainWindow (D-07 dwell elapsed).
_underrun_cycle_opened    = Signal()         # bus-loop → main: arm dwell timer
_underrun_cycle_closed    = Signal(object)   # bus-loop → main: log + cancel dwell
underrun_recovery_started = Signal()         # main → MainWindow: show_toast (D-07)
```

**Pattern to add** (immediately after `underrun_recovery_started` at line 277):
```python
# Phase 78 / BUG-09 Commit A: cumulative cycle counter for stats-for-nerds.
# Emitted from _on_underrun_cycle_closed (main-thread slot — receiver may
# default to DirectConnection because both ends are on the main thread).
underrun_count_changed    = Signal(int)      # main → MainWindow → NowPlayingPanel.set_underrun_count
```

**Analog 2 — instance field init** (`player.py:437-442`):
```python
# Phase 62 / BUG-09: cycle-tracker instance + station_id field.
# Tracker mirrors Phase 47.1 D-14 sentinel reset lifecycle (Pitfall 3 —
# bind_url is called from _try_next_stream alongside _last_buffer_percent reset).
# _current_station_id mirrors _current_station_name for log-line context.
self._tracker = _BufferUnderrunTracker()
self._current_station_id: int = 0
```

**Pattern to add** (adjacent — same physical block per Pitfall 3 of RESEARCH.md):
```python
# Phase 78 / BUG-09 Commit A: cumulative cycle count (resets per launch, D-Discretion).
self._underrun_event_count: int = 0
```

**Analog 3 — main-thread slot** (`player.py:918-934` — VERBATIM, do not regress):
```python
def _on_underrun_cycle_closed(self, record) -> None:
    """Main-thread slot (Phase 62 / D-02). Cancels in-flight dwell timer
    (silent recovery, D-07) and writes the structured log line at INFO.

    T-62-01 mitigation: station_name and url are %r-quoted, so embedded
    newlines / control chars / quotes from library data cannot inject
    spurious log lines or break grep-based diagnosis.
    """
    self._underrun_dwell_timer.stop()    # idempotent
    _log.info(
        "buffer_underrun "
        "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
        "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
        record.start_ts, record.end_ts, record.duration_ms, record.min_percent,
        record.station_id, record.station_name, record.url,
        record.outcome, record.cause_hint,
    )
```

**Pattern to add** (two lines AFTER the `_log.info(...)` call, before the function returns — preserve T-62-01 by leaving the `%r` quoting intact):
```python
    # Phase 78 / BUG-09 Commit A: increment + emit on EVERY cycle_close
    # (every outcome — recovered / failover / stop / pause / shutdown —
    # mirrors the file-sink semantics per CONTEXT <specifics>).
    self._underrun_event_count += 1
    self.underrun_count_changed.emit(self._underrun_event_count)
```

**Thread-affinity note** (RESEARCH.md A3 + Pattern 2): The slot is the receiving end of a queued cross-thread connection (`player.py:409-411`), so by the time `_on_underrun_cycle_closed` runs we are already on the main thread. Increment + emit happen on the main thread; receiver in NowPlayingPanel is also main-thread (QWidget). No `Qt.ConnectionType.QueuedConnection` needed on the new wire.

---

### `musicstreamer/__main__.py` (modified — call install_buffer_events_handler in `_run_gui` after migration)

**Analog — per-logger level escalation** (`__main__.py:230-239`):
```python
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    # Phase 62 / BUG-09 / Pitfall 5: per-logger INFO level for musicstreamer.player
    # so buffer-underrun cycle close lines surface to stderr without bumping the
    # GLOBAL level (which would surface chatter from aa_import / gbs_api / mpris2).
    logging.getLogger("musicstreamer.player").setLevel(logging.INFO)
    logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)
    # Phase 79 / BUG-11: surface scan_playlist node_path INFO line at default
    # verbosity (consumed by Plan 79-03's yt_import.scan_playlist INFO log).
    logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
```

**KEEP VERBATIM (Pitfall 2 / Pitfall 5 invariant):** `basicConfig(level=logging.WARNING)` on line 231 MUST NOT change. The drift-guard `tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info` at lines 109-133 source-greps for this. The per-logger `setLevel(INFO)` for `musicstreamer.player` MUST stay at line 235.

**Analog — migration call site** (`__main__.py:176-177`):
```python
    from musicstreamer import migration
    migration.run_migration()
```

**Pattern to add** (immediately AFTER `migration.run_migration()` in `_run_gui` — per Pitfall 1; DATA_DIR is now guaranteed to exist):
```python
    # Phase 78 / BUG-09 Commit A: install rotating file handler on
    # musicstreamer.player logger so buffer_underrun lines land at
    # ~/.local/share/musicstreamer/buffer-events.log regardless of launch
    # context (.desktop vs terminal). MUST run after migration so DATA_DIR
    # exists (RESEARCH Pitfall 1). Idempotent — safe across hot-reload tests.
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
```

**Why not co-located with `setLevel(INFO)` in `main()`:** `main()` runs before `_run_gui()`, which runs before `migration.run_migration()`. Installing the handler at the same site as `setLevel(INFO)` would try to open the file before DATA_DIR exists → `FileNotFoundError`. Per-logger level escalation has no filesystem dependency, so it stays put.

---

### `musicstreamer/ui_qt/now_playing_panel.py` (modified — add `Underruns` row + `set_underrun_count` slot)

**Analog 1 — `_build_stats_widget` extensibility** (`now_playing_panel.py:2451-2482`):
```python
def _build_stats_widget(self) -> QWidget:
    """Construct the stats-for-nerds wrapper (D-07/D-08/D-09). Phase 47.1."""
    wrapper = QWidget(self)
    form = QFormLayout(wrapper)
    form.setContentsMargins(0, 0, 0, 0)

    # Row label -- muted palette (D-10; RESEARCH §6 Option A: QPalette.Disabled).
    # _MutedLabel re-applies the muted color on palette/theme changes so
    # light<->dark flips stay readable (UAT follow-up).
    buffer_row_label = _MutedLabel("Buffer", wrapper)

    # Value side: QProgressBar + {N}% QLabel inside a QHBoxLayout
    value_row = QWidget(wrapper)
    value_layout = QHBoxLayout(value_row)
    value_layout.setContentsMargins(0, 0, 0, 0)
    value_layout.setSpacing(6)
    self.buffer_bar = QProgressBar(value_row)
    self.buffer_bar.setRange(0, 100)
    self.buffer_bar.setTextVisible(False)  # D-01: label next to it is authoritative
    self.buffer_bar.setFixedWidth(120)     # D-02
    self.buffer_pct_label = _MutedLabel("0%", value_row)
    value_layout.addWidget(self.buffer_bar)
    value_layout.addWidget(self.buffer_pct_label)
    value_layout.addStretch(1)

    form.addRow(buffer_row_label, value_row)
    # D-05: default hidden. MainWindow drives visibility from the QAction's
    # checked state after construction (WR-02: single source of truth).
    wrapper.setVisible(False)
    return wrapper
```

**Pattern to add** (between `form.addRow(buffer_row_label, value_row)` at line 2478 and `wrapper.setVisible(False)` at line 2481):
```python
    # Phase 78 / BUG-09 Commit A: cumulative cycle count, observable live.
    # Same _MutedLabel pattern as the Buffer row above (Phase 47.1 D-10 theme-flip safety).
    # Two-column shape (label + value) matches the existing Buffer row idiom
    # (RESEARCH Open Q2 recommendation).
    underrun_row_label = _MutedLabel("Underruns", wrapper)
    self._underrun_count_label = _MutedLabel("0", wrapper)
    form.addRow(underrun_row_label, self._underrun_count_label)
```

**Analog 2 — `set_buffer_percent` slot** (`now_playing_panel.py:946-949`):
```python
def set_buffer_percent(self, percent: int) -> None:
    """Update the buffer indicator bar + {N}% label atomically (D-11). Phase 47.1."""
    self.buffer_bar.setValue(int(percent))
    self.buffer_pct_label.setText(f"{int(percent)}%")
```

**Pattern to add** (sibling slot immediately after `set_buffer_percent` at line 950):
```python
def set_underrun_count(self, count: int) -> None:
    """Phase 78 / BUG-09 Commit A: update the Underruns: {N} stats row."""
    self._underrun_count_label.setText(str(int(count)))
```

---

### `musicstreamer/ui_qt/main_window.py` (modified — Signal wiring)

**Analog — buffer_percent wiring** (`main_window.py:378-393`):
```python
        # Player → now-playing panel
        self._player.title_changed.connect(self.now_playing.on_title_changed)
        self._player.elapsed_updated.connect(self.now_playing.on_elapsed_updated)
        self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)

        # Player → toast notifications (D-11)
        self._player.failover.connect(self._on_failover)
        self._player.offline.connect(self._on_offline)
        self._player.playback_error.connect(self._on_playback_error)
        self._player.cookies_cleared.connect(self.show_toast)  # Phase 999.7
        # Phase 62 / D-07-D-08 / BUG-09: dwell-elapsed → cooldown-gated toast.
        # Queued connection per file convention (Player Signals are queued to
        # MainWindow throughout this file). Bound method per QA-05 — no lambda.
        self._player.underrun_recovery_started.connect(
            self._on_underrun_recovery_started, Qt.ConnectionType.QueuedConnection
        )
```

**Pattern to add** (one line, immediately after the existing `buffer_percent` wiring at line 381 — same direct-connection idiom because both ends are on the main thread):
```python
        # Phase 78 / BUG-09 Commit A: cycle counter → stats-for-nerds row.
        # QA-05: bound method, no lambda. DirectConnection (default) is correct —
        # both emitter (Player._on_underrun_cycle_closed slot) and receiver
        # (NowPlayingPanel.set_underrun_count) are on the main thread.
        self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)
```

**Critical convention from analog:** Use the same shape as the `buffer_percent` line (no `Qt.ConnectionType.QueuedConnection` argument). The `underrun_recovery_started` connection three lines below uses QueuedConnection but that's because Player emits it from various contexts where defensiveness was wanted; the new Signal is strictly main-thread → main-thread (RESEARCH A3).

---

### `tests/_fake_player.py` (modified — drift-guard mirror)

**Analog — existing Signal declarations** (`_fake_player.py:62-69`):
```python
    # Internal cross-thread marshaling signals (7 — underscore-prefixed)
    _cancel_timers_requested       = Signal()
    _error_recovery_requested      = Signal()
    _try_next_stream_requested     = Signal()
    _playbin_playing_state_reached = Signal()
    _underrun_cycle_opened         = Signal()
    _underrun_cycle_closed         = Signal(object)
    underrun_recovery_started      = Signal()
```

**Pattern to add** (one line, immediately after `underrun_recovery_started` at line 69 — preserving the production declaration order from `player.py:271-282`):
```python
    underrun_count_changed         = Signal(int)  # Phase 78 / BUG-09 Commit A
```

**Why this must ship in the same wave as the Player edit:** INFRA-01 drift-guard `tests/test_fake_player_signal_parity.py` source-greps both files and fails the build if production has a Signal that the FakePlayer doesn't (RESEARCH.md Pitfall 4). The two edits are intentionally coupled.

**Also update the header docstring** at `_fake_player.py:6` — "**all 18 Signals**" → "**all 19 Signals**", and "(18 signals, D-16 invariant)" at line 36 → "(19 signals, D-16 invariant)". Same drift-guard logic does NOT check those strings, but Phase 77 INFRA-01 convention is to keep the docstring honest.

---

### `tests/test_buffer_events_log.py` (new — handler unit tests)

**Analog:** `tests/test_oauth_log.py:1-221` (entire file)

**Imports + fixture template** (`test_oauth_log.py:1-17`):
```python
"""Tests for musicstreamer.oauth_log — rotating OAuth diagnostic log.

Phase 999.3 D-10/D-11. Verifies:
- 0o600 permissions after first write (T-40-03 parity).
- JSON-line format with fixed schema.
- Scrub rules: URLs, access_token, state=/code=/token= prefixes, >200 chars.
- RotatingFileHandler with maxBytes=64KB, backupCount=2.
- No backup 3 ever created.
"""
from __future__ import annotations

import json
import os

import pytest

from musicstreamer.oauth_log import OAuthLogger, _scrub
```

**Attribute-introspection pattern** (RESEARCH.md Pitfall 6, lines 352-370 — the canonical "don't write real bytes to ~/.local/share/musicstreamer" approach):
```python
def test_handler_attached_to_player_logger(tmp_path, monkeypatch):
    monkeypatch.setattr("musicstreamer.paths._root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    import logging
    log = logging.getLogger("musicstreamer.player")
    rotating_handlers = [
        h for h in log.handlers
        if h.__class__.__name__ == "RotatingFileHandler"
    ]
    assert len(rotating_handlers) == 1
    h = rotating_handlers[0]
    assert h.baseFilename == str(tmp_path / "buffer-events.log")
    assert h.maxBytes == 1_048_576
    assert h.backupCount == 3
```

**Rotation assertion pattern** (`test_oauth_log.py:178-203`):
```python
def test_log_rotation_at_64kb(tmp_path):
    """After enough writes to exceed 64KB, oauth.log.1 exists."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    payload = "a" * 150
    for i in range(500):
        logger.log_event(
            {"ts": float(i), "category": "X", "detail": payload, "provider": "twitch"}
        )
    assert os.path.exists(log_path + ".1"), "rotation should have produced oauth.log.1"

def test_log_never_creates_backup_3(tmp_path):
    """backupCount=2 means oauth.log.3 never exists."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    payload = "a" * 150
    for i in range(2000):
        logger.log_event(
            {"ts": float(i), "category": "X", "detail": payload, "provider": "twitch"}
        )
    assert not os.path.exists(log_path + ".3"), "backupCount=2 must cap at .2"
```

**Adapted for buffer_log** — write directly to the logger after install (no helper class):
```python
def test_log_rotation_at_1mb(tmp_path, monkeypatch):
    monkeypatch.setattr("musicstreamer.paths._root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    import logging
    log = logging.getLogger("musicstreamer.player")
    payload = "a" * 2000  # ~2KB per line incl asctime
    for i in range(600):
        log.info("buffer_underrun bench=%d %s", i, payload)
    assert os.path.exists(str(tmp_path / "buffer-events.log.1"))

def test_log_never_creates_backup_4(tmp_path, monkeypatch):
    monkeypatch.setattr("musicstreamer.paths._root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    import logging
    log = logging.getLogger("musicstreamer.player")
    payload = "a" * 2000
    for i in range(3000):
        log.info("buffer_underrun bench=%d %s", i, payload)
    assert not os.path.exists(str(tmp_path / "buffer-events.log.4"))
```

**Idempotency test** (covers RESEARCH.md Pitfall 7 — no in-tree exact precedent; novel test, but pattern is trivial):
```python
def test_install_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("musicstreamer.paths._root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    install_buffer_events_handler()  # second call must NOT add a second handler
    import logging
    log = logging.getLogger("musicstreamer.player")
    rotating = [h for h in log.handlers if h.__class__.__name__ == "RotatingFileHandler"]
    assert len(rotating) == 1
```

**Pitfall to avoid (RESEARCH.md Pitfall 6):** Tests MUST monkeypatch `paths._root_override` so they write under `tmp_path`, never `~/.local/share/musicstreamer`. Existing `_reset_root_override` autouse fixture in `tests/test_paths.py:10-16` is the canonical reset shape — replicate per-test with `monkeypatch.setattr(...)` since this file has no autouse fixture yet.

**Handler-leak cleanup (between tests):** Adding a `RotatingFileHandler` to the `musicstreamer.player` logger has process-global effect. Tests in this file should either (a) install once, run all assertions, then `log.removeHandler(...)` in teardown, or (b) use a session-scoped fixture. Recommended: per-test fixture that resets `musicstreamer.player.handlers` to its initial state. Pattern is novel; closest precedent is the `_reset_root_override` autouse fixture in `test_paths.py`.

---

### `tests/test_player_underrun_count.py` (new — counter + Signal unit tests)

**Analog 1 — Player-with-mocked-pipeline harness** (`tests/test_player_underrun.py:16-31`):
```python
def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.

    Verbatim duplicate of tests/test_player_buffering.py:8-18 (per
    PATTERNS.md §S-7 — codebase convention is per-file helper duplication,
    not shared conftest extraction).
    """
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player
```

**Use this verbatim for the new file** — codebase convention is per-file helper duplication (PATTERNS.md §S-7 from prior phases; see Phase 62 docstring).

**Analog 2 — slot-driven assertion** (`test_player_underrun.py:61-81`):
```python
def test_buffering_recover_emits_cycle_closed(qtbot):
    """D-02: cycle close emits _underrun_cycle_closed with full record payload."""
    player = make_player(qtbot)
    _seed_url(player, url="http://prem2.di.fm/ambient", station_id=7, station_name="DI.fm Ambient")
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # arm
    player._on_gst_buffering(None, _fake_buffering_msg(70))    # open

    closed_records = []
    player._underrun_cycle_closed.connect(closed_records.append)
    player._on_gst_buffering(None, _fake_buffering_msg(100))   # close
    qtbot.wait(100)

    assert len(closed_records) == 1
    rec = closed_records[0]
    assert rec.outcome == "recovered"
```

**Pattern adapted — counter assertions:**
```python
def test_count_starts_at_zero(qtbot):
    player = make_player(qtbot)
    assert player._underrun_event_count == 0

def test_count_increments_per_close(qtbot):
    player = make_player(qtbot)
    # Build a minimal _CycleClose record (analog: test_player_underrun_tracker.py:43-60)
    from musicstreamer.player import _CycleClose
    rec = _CycleClose(
        start_ts=10.0, end_ts=11.5, duration_ms=1500, min_percent=60,
        station_id=7, station_name="Test", url="http://x/",
        outcome="recovered", cause_hint="unknown",
    )
    player._on_underrun_cycle_closed(rec)
    assert player._underrun_event_count == 1
    player._on_underrun_cycle_closed(rec)
    assert player._underrun_event_count == 2

def test_signal_emits_with_count_value(qtbot):
    player = make_player(qtbot)
    from musicstreamer.player import _CycleClose
    rec = _CycleClose(
        start_ts=10.0, end_ts=11.5, duration_ms=1500, min_percent=60,
        station_id=7, station_name="Test", url="http://x/",
        outcome="recovered", cause_hint="unknown",
    )
    received = []
    player.underrun_count_changed.connect(received.append)
    player._on_underrun_cycle_closed(rec)
    qtbot.wait(50)
    assert received == [1]
```

**Outcome-parametric test pattern** (from `test_player_underrun_tracker.py` style — build a record per outcome):
```python
import pytest

@pytest.mark.parametrize("outcome", ["recovered", "failover", "stop", "pause", "shutdown"])
def test_count_increments_for_all_outcomes(qtbot, outcome):
    player = make_player(qtbot)
    from musicstreamer.player import _CycleClose
    rec = _CycleClose(
        start_ts=10.0, end_ts=11.5, duration_ms=1500, min_percent=60,
        station_id=7, station_name="Test", url="http://x/",
        outcome=outcome, cause_hint="unknown",
    )
    player._on_underrun_cycle_closed(rec)
    assert player._underrun_event_count == 1
```

---

### `tests/test_paths.py` (modified — add `test_buffer_events_log_path`)

**Analog** (`test_paths.py:32, 59-69`):
```python
# Line 32 — in test_root_override_redirects_all_accessors:
assert paths.oauth_log_path() == os.path.join(root, "oauth.log")
```
```python
# Lines 59-69 — sibling test cases:
def test_oauth_log_path_honors_root_override(monkeypatch, tmp_path):
    """Phase 999.3 D-10: oauth.log path resolves under the override root."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.oauth_log_path() == os.path.join(str(tmp_path), "oauth.log")


def test_oauth_log_path_does_not_create_file(monkeypatch, tmp_path):
    """Purity contract: helper returns a string; does NOT touch disk."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    result = paths.oauth_log_path()
    assert os.path.exists(result) is False
```

**Pattern to add** (sibling test, same shape, ~line 70):
```python
def test_buffer_events_log_path_honors_root_override(monkeypatch, tmp_path):
    """Phase 78 / BUG-09 D-03: buffer-events.log path resolves under the override root."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.buffer_events_log_path() == os.path.join(str(tmp_path), "buffer-events.log")


def test_buffer_events_log_path_does_not_create_file(monkeypatch, tmp_path):
    """Purity contract: helper returns a string; does NOT touch disk."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    result = paths.buffer_events_log_path()
    assert os.path.exists(result) is False
```

**Also add to `test_root_override_redirects_all_accessors`** at line 32 (after the existing `oauth_log_path` assertion):
```python
    assert paths.buffer_events_log_path() == os.path.join(root, "buffer-events.log")
```

**And to `test_paths_do_no_io_on_import`** at line 52 — add a call alongside the existing batch:
```python
    paths.buffer_events_log_path()
```

---

### `tests/test_now_playing_panel.py` (modified — `Underruns` row tests)

**Analog 1 — stats widget construction** (`test_now_playing_panel.py:612-624`):
```python
def test_stats_widget_always_constructed(qtbot):
    """D-08: stats widget is always built, even when hidden."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel._stats_widget is not None
```

**Analog 2 — set_X slot assertion** (`test_now_playing_panel.py:657-663`):
```python
def test_set_buffer_percent_updates_both(qtbot):
    """D-11: single slot updates both bar and label atomically."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.set_buffer_percent(73)
    assert panel.buffer_bar.value() == 73
    assert panel.buffer_pct_label.text() == "73%"
```

**Pattern to add** (sibling tests in the Phase 47.1 stats section, ~line 676):
```python
def test_underrun_count_row_present(qtbot):
    """Phase 78 / BUG-09 Commit A: the Underruns row exists in _build_stats_widget."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    # Default value is "0" (Player counter starts at 0; row mirrors).
    assert panel._underrun_count_label.text() == "0"

def test_set_underrun_count_updates_label(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    panel.set_underrun_count(5)
    assert panel._underrun_count_label.text() == "5"
```

**Autouse fixture** (`test_now_playing_panel.py:25-36`) — already pulls in `block_real_network`, no changes needed for the new tests; they inherit the file-level fixture.

---

### `tests/test_main_window_underrun.py` (modified — count → stats row integration)

**Analog — first-call toast integration** (`test_main_window_underrun.py:32-42`):
```python
def test_first_call_shows_toast(qtbot, fake_player, fake_repo, monkeypatch, block_real_network):
    """D-06: first underrun_recovery_started emission shows Buffering toast."""
    monkeypatch.setattr(
        "musicstreamer.ui_qt.main_window.time.monotonic",
        lambda: 1000.0,
    )
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    fake_player.underrun_recovery_started.emit()
    qtbot.wait(50)
    assert "Buffering" in w._toast.label.text()
```

**Pattern to add** (sibling test, same fixture set, same FakePlayer emit pattern):
```python
def test_count_changed_updates_stats_row(qtbot, fake_player, fake_repo, block_real_network):
    """Phase 78 / BUG-09 Commit A: underrun_count_changed → NowPlayingPanel.set_underrun_count.

    MainWindow wires Player.underrun_count_changed → now_playing.set_underrun_count
    one line below the buffer_percent connection at main_window.py:381. Emitting
    the FakePlayer signal here mimics the post-cycle-close emit from Player.
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    fake_player.underrun_count_changed.emit(3)
    qtbot.wait(50)
    assert w.now_playing._underrun_count_label.text() == "3"
    fake_player.underrun_count_changed.emit(7)
    qtbot.wait(50)
    assert w.now_playing._underrun_count_label.text() == "7"
```

**Drift-guard test (already exists; must stay green)** — `test_main_module_sets_player_logger_to_info` at lines 109-133 enforces Pitfall 5 (basicConfig stays WARNING; per-logger INFO for `musicstreamer.player`). DO NOT modify; the new Commit A code preserves both invariants.

---

## Shared Patterns

### S-1: `RotatingFileHandler` install on a named logger
**Source:** `musicstreamer/oauth_log.py:63-70`
**Apply to:** `musicstreamer/buffer_log.py`
**Key delta from source:** `propagate=True` (default — keep stderr parity); no `0o600` chmod (D-03 diagnostic vs credentials); module-function install (not class).

```python
handler = RotatingFileHandler(
    log_path,
    maxBytes=64 * 1024,
    backupCount=2,
    encoding="utf-8",
)
handler.setFormatter(logging.Formatter("%(message)s"))
self._logger.addHandler(handler)
```

### S-2: Path helper purity
**Source:** `musicstreamer/paths.py:11-15, 46-65`
**Apply to:** `musicstreamer/paths.py` (`buffer_events_log_path()`) and any tests that exercise paths.
**Invariant:** Module is pure — accessors return strings, do NOT mkdir, do NOT touch disk. Directory creation is `assets.ensure_dirs` / `migration.run_migration` responsibility. Tests monkeypatch `paths._root_override` to redirect under `tmp_path`.

### S-3: Bound-method Signal.connect (QA-05)
**Source:** `musicstreamer/ui_qt/main_window.py:381` (`self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)`)
**Apply to:** New `underrun_count_changed` wire in `main_window.py`.
**Rule:** No lambdas in `.connect(...)`. Bound method or top-level function only. Two ends both on main thread → no `Qt.ConnectionType.QueuedConnection`.

### S-4: `_MutedLabel` for stats-for-nerds rows (Phase 47.1 D-10)
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:2460, 2473` (`buffer_row_label`, `buffer_pct_label`)
**Apply to:** Both new `Underruns` row widgets (label + value column).
**Rule:** Theme-flip safety — `_MutedLabel` re-applies muted color on palette change. Plain `QLabel` would go unreadable on light↔dark flip (Phase 47.1 UAT follow-up).

### S-5: FakePlayer Signal parity (INFRA-01 drift-guard)
**Source:** `tests/_fake_player.py:51-72` + `tests/test_fake_player_signal_parity.py`
**Apply to:** Every new Signal added to `musicstreamer/player.py`.
**Rule:** Add the Signal to `tests/_fake_player.py` in the SAME plan/wave as the production Signal addition. Arity must match exactly. Header docstring "18 Signals" → "19 Signals" update is a courtesy, not enforced by the grep gate.

### S-6: `tmp_path` + `monkeypatch.setattr(paths, "_root_override", ...)` for filesystem tests
**Source:** `tests/test_paths.py:59-62` + `tests/test_oauth_log.py:25-34`
**Apply to:** `tests/test_buffer_events_log.py` (every test).
**Rule:** NEVER let a test write to `~/.local/share/musicstreamer/` — redirect to `tmp_path` first. The `paths._root_override` hook is the single redirection point (line 22-31 of `paths.py`).

### S-7: Per-file Player-test helper duplication (NOT conftest extraction)
**Source:** `tests/test_player_underrun.py:16-31` (verbatim duplicate of `test_player_buffering.py:8-18`)
**Apply to:** `tests/test_player_underrun_count.py` — paste `make_player(qtbot)` verbatim.
**Rule:** Codebase convention is per-file duplication of the mocked-pipeline helper. Do NOT extract to `conftest.py` (intentional choice from prior phases — see PATTERNS.md §S-7 referenced in Phase 62 docstrings).

### S-8: Pitfall 5 invariant — `basicConfig(level=logging.WARNING)` is sacrosanct
**Source:** `musicstreamer/__main__.py:231` + drift-guard at `tests/test_main_window_underrun.py:109-133`
**Apply to:** Any plan that touches `__main__.py`.
**Rule:** The root logger stays at WARNING. New handler attaches to the **named** logger `musicstreamer.player` only (`_player_log.addHandler(...)`). Never `logging.getLogger().addHandler(...)`, never `basicConfig(level=logging.INFO)`. Drift-guard test fails the build if violated.

### S-9: Pitfall 1 invariant — file handler install must run after `migration.run_migration()`
**Source:** `musicstreamer/__main__.py:176-177` (migration call) + RESEARCH.md Pitfall 1
**Apply to:** Any plan that adds the install call in `__main__.py`.
**Rule:** DATA_DIR (`~/.local/share/musicstreamer/`) is created by `migration.run_migration()` in `_run_gui`. `RotatingFileHandler(path)` opens the file eagerly (default `delay=False`) → `FileNotFoundError` if install runs before migration. Install in `_run_gui` after line 177. The `setLevel(INFO)` in `main()` can stay where it is (no filesystem dependency).

---

## No Analog Found

None. Every Commit A surface has at least one project-canonical analog. Two surfaces are "novel-but-trivial":

| File | Concern | Why no exact analog | Mitigation |
|------|---------|---------------------|------------|
| `musicstreamer/buffer_log.py` idempotency loop | RESEARCH.md Pitfall 7 — scanning existing handlers before adding | No prior in-tree pattern for "check existing handlers first" (single-instance.py is the closest spiritual cousin but uses QLocalServer, not logger introspection). | RESEARCH.md provides the exact code (lines 382-392); pattern is six lines, trivial. Test covers it (`test_install_is_idempotent`). |
| `tests/test_buffer_events_log.py` handler-leak teardown | Adding a `RotatingFileHandler` to `musicstreamer.player` has process-global effect | `test_oauth_log.py` uses unique-per-instance logger names (`musicstreamer.oauth.{id(self)}`) — buffer_log uses the shared `musicstreamer.player` logger, so tests leak handlers between runs. | Add a per-test fixture that snapshots `musicstreamer.player.handlers` at start and restores at teardown. Pattern shape mirrors `test_paths.py:10-16` `_reset_root_override` autouse fixture. |

---

## Metadata

**Analog search scope:**
- `musicstreamer/oauth_log.py` (file-sink shape, full file 1-90)
- `musicstreamer/paths.py` (path helpers + `_root_override`, full file 1-96)
- `musicstreamer/player.py` (logger declaration 79-81, class-level Signals 240-282, `__init__` fields 437-447, queued connects 400-411, cycle-closed slot 909-940, `_try_next_stream` reset 946-979)
- `musicstreamer/__main__.py` (boot ordering 163-263 — `_run_gui` migration call at 176-177, `main()` per-logger setLevel block at 230-239)
- `musicstreamer/ui_qt/now_playing_panel.py` (`_build_stats_widget` 2451-2482, `set_buffer_percent` 946-949)
- `musicstreamer/ui_qt/main_window.py` (Player→panel wiring 378-396)
- `tests/_fake_player.py` (Signal mirror block 45-72, full file)
- `tests/test_oauth_log.py` (rotation + attribute assertions, full file 1-221)
- `tests/test_paths.py` (sibling path tests, full file 1-88)
- `tests/test_now_playing_panel.py` (Stats-for-nerds tests 605-676)
- `tests/test_main_window_underrun.py` (FakePlayer + qtbot integration template, full file 1-133)
- `tests/test_player_underrun.py` (make_player harness 16-48, slot-driven assertion 61-81)
- `tests/test_player_underrun_tracker.py` (pure-state test idioms 1-60, `_CycleClose` record construction)

**Files scanned:** 13
**Pattern extraction date:** 2026-05-17
**Scope confirmed:** Commit A only. Commit B's file edits (`constants.py` bump, `_grow_buffer_on_underrun` method, `Buffer config:` row) are NOT mapped here — they belong to a second planning pass after the ~1-week harvest week.

## PATTERN MAPPING COMPLETE

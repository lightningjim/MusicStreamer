# Phase 52: EQ Toggle Dropout Fix — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 3 (1 source modify, 2 test modify)
**Analogs found:** 3 / 3 (all in-tree, role-and-data-flow exact)

This phase introduces no new files. All patterns come from the same files being
modified — i.e., the analogs are the surrounding code in `player.py`, the test
shape established in `tests/test_player.py`, and the existing toggle-test
shape in `tests/test_now_playing_panel.py`. The closest "new pattern" is a
QTimer that ticks N times then stops itself with a tick counter — the closest
in-tree analog is `_elapsed_timer` (interval timer with handler increment),
combined with the single-shot pattern of `_failover_timer`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/player.py` (modify `set_eq_enabled` / `_apply_eq_state`; add `_eq_ramp_timer`, `_eq_ramp_state`, `_on_eq_ramp_tick`) | service / audio backend | event-driven (timer-driven, multiple writes spread over time) | `Player._elapsed_timer` (interval QTimer with handler-increment) + `Player._apply_eq_state` (the function being refactored) | exact (same class, same threading model, same GstChildProxy mutation primitive) |
| `tests/test_player.py` (extend with ramp tests) | test (unit + integration) | request-response (drive timer, assert band gain values) | existing EQ tests at `tests/test_player.py:182-296` (real-pipeline `player` fixture) and existing elapsed-tick tests at `tests/test_player.py:54-145` (manual `timer.timeout.emit()` pattern) | exact (same fixtures, same GstChildProxy property reads) |
| `tests/test_now_playing_panel.py` (defensive SC #3 test for `clicked` wiring) | test (UI) | request-response (simulate click, assert call shape) | `test_eq_toggle_click_calls_player_and_persists` at `tests/test_now_playing_panel.py:661-676` | exact (same FakePlayer/FakeRepo fixtures, same panel construction) |

## Pattern Assignments

### `musicstreamer/player.py` — ramp state + tick timer + ramp-aware `_apply_eq_state`

**Analogs:**
- Construction shape and bound-method `timeout` connection: `_failover_timer` (single-shot) at `player.py:135-137` and `_elapsed_timer` (interval, runs while playing) at `player.py:146-148`.
- Per-tick handler shape (instance method on Player, increments counter, side-effects): `_on_elapsed_tick` at `player.py:405-408`.
- Stop / state-reset on lifecycle events: `_elapsed_timer.stop()` at `player.py:275, 283` and `_failover_timer.stop()` at `player.py:399`.
- Function being refactored (preserves freq/bandwidth/type write paths verbatim, only the gain write becomes interpolated): `_apply_eq_state` at `player.py:637-659`.
- Public-API entrypoint that triggers the ramp: `set_eq_enabled` at `player.py:211-214`.

**Imports / class scope (already present, reused — DO NOT re-import):**

`player.py:34`:
```python
from PySide6.QtCore import QObject, Qt, QTimer, Signal
```

`player.py:33`:
```python
from gi.repository import Gst
```

No new imports required for the ramp itself. If the planner introduces module-level constants `_EQ_RAMP_MS = 40` and `_EQ_RAMP_TICKS = 8`, they belong near the existing `_EQ_BAND_TYPE` constant at `player.py:635`.

**QTimer construction pattern** — copy from `_failover_timer` (`player.py:135-137`) and `_elapsed_timer` (`player.py:146-148`), in `__init__`:

```python
# Existing — _failover_timer (single-shot, fires once after start(ms))
self._failover_timer = QTimer(self)
self._failover_timer.setSingleShot(True)
self._failover_timer.timeout.connect(self._on_timeout)

# Existing — _elapsed_timer (interval, runs while pipeline is intended to be PLAYING)
self._elapsed_timer = QTimer(self)
self._elapsed_timer.setInterval(1000)
self._elapsed_timer.timeout.connect(self._on_elapsed_tick)
```

**Ramp timer construction (new — adapt the interval-with-counter pattern from `_elapsed_timer`).** The ramp timer is an interval timer (5ms) with a tick counter; the handler stops the timer itself when `tick_index >= _EQ_RAMP_TICKS`. The construction line lives next to the other timers (after `player.py:148`) and follows QA-05 (bound method, no lambda):

```python
# (Phase 52 — example shape; planner picks attribute name)
self._eq_ramp_timer = QTimer(self)
self._eq_ramp_timer.setInterval(5)  # _EQ_RAMP_MS // _EQ_RAMP_TICKS
self._eq_ramp_timer.timeout.connect(self._on_eq_ramp_tick)
self._eq_ramp_state: dict | None = None
```

**Per-tick handler pattern** — copy the shape of `_on_elapsed_tick` (`player.py:405-408`):

```python
def _on_elapsed_tick(self) -> None:
    """1Hz tick: increment counter and emit elapsed_updated(seconds)."""
    self._elapsed_seconds += 1
    self.elapsed_updated.emit(self._elapsed_seconds)
```

The Phase 52 equivalent: increment `tick_index`, compute `t = tick_index / _EQ_RAMP_TICKS`, lerp each band gain from `start_gain[i]` to `target_gain[i]`, write via GstChildProxy, and on the final tick stop the timer + clear `_eq_ramp_state`.

**Band-write primitive** — copy the GstChildProxy gain write from `_apply_eq_state` at `player.py:647-648` (bypass branch) and `player.py:653-659` (profile-apply branch):

```python
# Bypass — single-property write per band (line 647-648)
for i in range(self._eq.get_children_count()):
    self._eq.get_child_by_index(i).set_property("gain", 0.0)

# Profile-apply — multi-property write per band (line 653-659)
for i, b in enumerate(self._eq_profile.bands):
    if i >= self._eq.get_children_count():
        break
    band = self._eq.get_child_by_index(i)
    band.set_property("freq", float(b.freq_hz))
    # Pitfall 4: GStreamer bandwidth is Hz, AutoEQ Q is quality factor.
    band.set_property("bandwidth", float(b.freq_hz) / max(float(b.q), 0.01))
    # Pitfall 5: ADD preamp (usually negative) -- do NOT subtract abs().
    band.set_property("gain", float(b.gain_db) + self._eq_preamp_db)
    band.set_property("type", self._EQ_BAND_TYPE.get(b.filter_type, 0))
```

**Crucial Phase-47.2 pitfalls preserved during ramp** — the planner MUST keep these contracts:

- **Pitfall 4** (`player.py:655-656`): `bandwidth = freq_hz / max(q, 0.01)`. Bandwidth is written **once at ramp start** (or once on each `_apply_eq_state` invocation under the bypass-branch pattern), not per-tick. Only `gain` interpolates per-tick.
- **Pitfall 5** (`player.py:657-658`): preamp ADDS to gain (`b.gain_db + preamp_db`), never subtracts `abs()`. The ramp's `target_gain[i]` calculation must use `+ self._eq_preamp_db`.
- **Pitfall 1** (`player.py:661-671`): band-count realloc unreliable → `_rebuild_eq_element` does a READY-state transition. Phase 52 ramp NEVER changes band count, so this pitfall does not apply per-tick.

**Early-return guards** — copy from `_apply_eq_state` at `player.py:644`:

```python
if self._eq is None:
    return
```

The graceful-degrade contract (`set_eq_*` becomes a no-op when the equalizer plugin is missing) is locked by `test_player_eq_handles_missing_plugin` at `tests/test_player.py:340-365`. The ramp must preserve it: if `self._eq is None`, `set_eq_enabled` flips `_eq_enabled` and returns — no timer started.

**Bypass semantics on enable=False** — locked by D-05 of Phase 47.2 (preserved here): the ramp's `target_gain[]` for `set_eq_enabled(False)` is `[0.0] * children_count` (matches the existing branch at `player.py:646-649`).

**Public-API entrypoint** — `set_eq_enabled` at `player.py:211-214`:

```python
def set_eq_enabled(self, enabled: bool) -> None:
    """D-05: Hot-toggle EQ by zeroing band gains (bypass) vs applying profile."""
    self._eq_enabled = bool(enabled)
    self._apply_eq_state()
```

**Phase 52 modification contract for `set_eq_enabled`** (per CONTEXT.md D-06, D-05):
1. `self._eq_enabled = bool(enabled)` — IMMEDIATE, before ramp logic (D-06).
2. Compute `target_gain[]` from new `(_eq_enabled, _eq_profile, _eq_preamp_db)`.
3. If a ramp is currently running (`self._eq_ramp_state` is not None):
   - Read each band's **current** gain from `self._eq.get_child_by_index(i).get_property("gain")` (or from the in-progress lerp tick state — both are valid; `get_property` from GstChildProxy is the authoritative read).
   - Set as new `start_gain[]`. Reset `tick_index = 0`. Replace target.
4. Else (fresh ramp):
   - `start_gain[i] = self._eq.get_child_by_index(i).get_property("gain")` for each band.
   - Write `freq`, `bandwidth`, `type` for each band ONCE here (per-tick only `gain` changes).
   - `tick_index = 0`; start the timer.
5. If `self._eq is None` → flip `_eq_enabled` and return (graceful-degrade preserved).

**Stop / cleanup pattern** — when a fresh `play()` or `stop()` cancels in-flight work, follow the precedent set by `_elapsed_timer.stop()` at `player.py:275, 283`. Phase 52 should add `self._eq_ramp_timer.stop()` to the same lifecycle points if the ramp could be in-flight at stop (planner picks; not strictly required because the ramp state is purely about audio output and the pipeline state-change to NULL already silences output).

**Lerp idiom** (recommended dB-linear per CONTEXT.md Discretion):

```python
# Pure helper — no Qt, no GStreamer
def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
```

**Final-tick exact-commit** — important: the last tick must write the **exact target** values (not `lerp(start, target, 7/8)` which would leave a tiny residual). Pattern:

```python
if tick_index >= _EQ_RAMP_TICKS:
    # Commit final state exactly (avoid lerp residual)
    for i, target in enumerate(target_gain):
        self._eq.get_child_by_index(i).set_property("gain", target)
    self._eq_ramp_timer.stop()
    self._eq_ramp_state = None
    return
```

---

### `tests/test_player.py` — ramp behavior tests

**Analog 1 (driving QTimer manually):** `test_elapsed_timer_emits_seconds_while_playing` at `tests/test_player.py:54-73` shows the canonical pattern for unit-testing a Player QTimer without waiting on real wall-clock:

```python
def test_elapsed_timer_emits_seconds_while_playing(qtbot):
    """Timer ticks emit elapsed_updated(1), (2), (3); stop() halts the timer."""
    p = make_player(qtbot)
    emissions = []
    p.elapsed_updated.connect(emissions.append)

    _seed_playback(p)

    # Manually drive the timer three times (bypass real wall clock).
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()
    p._elapsed_timer.timeout.emit()

    assert emissions == [1, 2, 3]
```

**Apply to Phase 52 ramp tests:** drive `p._eq_ramp_timer.timeout.emit()` 8 times; after each tick read `p._eq.get_child_by_index(i).get_property("gain")` and assert the value is `lerp(start, target, k/8)` to a tolerance.

**Analog 2 (real-pipeline EQ fixture):** `player` fixture at `tests/test_player.py:169-179` constructs a real `Player` with a real `playbin3` + real `equalizer-nbands`:

```python
@pytest.fixture
def player(qtbot):
    """Real Player instance (real playbin3 + real equalizer-nbands).

    The autouse ``_stub_bus_bridge`` fixture in conftest.py replaces the
    GLib.MainLoop daemon; everything else is a genuine GStreamer pipeline.
    """
    from musicstreamer.player import Player
    p = Player()
    yield p
    p.stop()
```

**Apply to Phase 52 ramp tests:** prefer the real-pipeline `player` fixture (not the `make_player` mock at `tests/test_player.py:16-33`) so band gains are genuine GstChildProxy reads — the same pattern that `test_player_eq_apply_profile` (`tests/test_player.py:196-222`) already uses.

**Analog 3 (assertion idiom for band gain):** `test_player_eq_apply_profile` at `tests/test_player.py:207-214`:

```python
b0 = player._eq.get_child_by_index(0)
b1 = player._eq.get_child_by_index(1)
assert b0.get_property("freq") == pytest.approx(1000.0)
assert b0.get_property("gain") == pytest.approx(-3.5)
```

**Apply to Phase 52:**

- **Per-tick progression test:** seed a profile with non-zero target gains, call `set_eq_enabled(True)`, then for `k in range(1, 9)` do `p._eq_ramp_timer.timeout.emit()` and assert each band's `get_property("gain")` equals `lerp(0.0, target[i], k/8)` to `pytest.approx`.
- **Final-tick exact-commit test:** after 8 ticks, assert `b0.get_property("gain") == pytest.approx(target[0])` with a tight tolerance (no lerp residual).
- **Reverse-from-current test:** start a ramp toward target T1; emit 3 ticks; capture mid-ramp gains; call `set_eq_enabled(False)` (target T2 = zeros); emit 8 more ticks; assert final gains == zeros AND mid-ramp gains were used as the new start (e.g., the ramp does not snap back to T1's pre-ramp start).
- **Graceful-degrade test:** existing `test_player_eq_handles_missing_plugin` at `tests/test_player.py:340-365` already exercises `_eq is None`; planner may extend it to assert no timer is started in that case (or trust the existing no-op contract).

**`make_player` mock fixture (alternative for fast unit tests):** `tests/test_player.py:16-33` constructs a Player with a mocked `Gst.ElementFactory.make`:

```python
def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    from musicstreamer.player import Player
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_pipeline
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    player._pipeline = MagicMock()
    return player
```

**When to use which:** the `player` fixture (real pipeline) is the right choice for ramp tests because the assertions read real `band.get_property("gain")`. `make_player` is the right choice for tests that need to assert on `_eq_ramp_state` lifecycle (start/stop/None) without real GStreamer.

**`qtbot.wait` alternative (NOT preferred):** if the planner instead chooses to let the real QTimer fire on the wall clock, the pattern would be `qtbot.wait(50)` after `set_eq_enabled` and assert final state. The manual `timeout.emit()` pattern is cheaper, deterministic, and already established by `test_elapsed_timer_*` tests — recommend that.

---

### `tests/test_now_playing_panel.py` — SC #3 defensive test

**Analog:** `test_eq_toggle_click_calls_player_and_persists` at `tests/test_now_playing_panel.py:661-676`:

```python
def test_eq_toggle_click_calls_player_and_persists(qtbot):
    """D-08: Clicking the toggle calls player.set_eq_enabled AND persists eq_enabled setting."""
    repo = FakeRepo({"volume": "80"})
    player = FakePlayer()
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    # Start unchecked
    panel.eq_toggle_btn.setChecked(False)
    # Click -> checked -> player.set_eq_enabled(True) + eq_enabled="1"
    panel.eq_toggle_btn.click()
    assert ("enabled", True) in player.calls
    assert repo.get_setting("eq_enabled") == "1"
    # Click again -> unchecked -> player.set_eq_enabled(False) + eq_enabled="0"
    panel.eq_toggle_btn.click()
    assert ("enabled", False) in player.calls
    assert repo.get_setting("eq_enabled") == "0"
```

**FakePlayer shape (already exists):** `tests/test_now_playing_panel.py:60-62`:

```python
def set_eq_enabled(self, enabled: bool) -> None:
    # Phase 47.2 D-08: mirrors Plan 03's canonical FakePlayer shape.
    self.calls.append(("enabled", bool(enabled)))
```

**Apply to Phase 52 SC #3 defensive test:** copy the fixture+click pattern, but assert call **count** — not just `in` membership — so a hypothetical double-fire would surface:

```python
def test_eq_toggle_fires_exactly_once_per_click(qtbot):
    """SC #3: each click invokes _on_eq_toggled exactly once (no double-fire from
    accidentally connecting both `clicked` and `toggled`).
    """
    repo = FakeRepo({"volume": "80"})
    player = FakePlayer()
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.eq_toggle_btn.setChecked(False)

    initial_calls = len(player.calls)
    panel.eq_toggle_btn.click()
    assert len(player.calls) - initial_calls == 1, (
        "exactly one set_eq_enabled call per click"
    )
```

**Wiring assertion (alternative or additional):** to lock the wiring choice (`clicked`, not `toggled`), planner can either (a) trust the call-count check above, or (b) introspect the receivers list. The call-count check is simpler and is the recommended approach. The construction line being verified is at `musicstreamer/ui_qt/now_playing_panel.py:261`:

```python
self.eq_toggle_btn.clicked.connect(self._on_eq_toggled)
```

**No FakePlayer change required** for SC #3 — the existing shape at `tests/test_now_playing_panel.py:60-62` already supports the test. If Phase 52 wants to assert that the panel does NOT call `set_eq_enabled` from any path other than the click (defensive), no new FakePlayer hooks are needed — the `calls` list already captures every invocation.

---

## Shared Patterns

### QA-05: Bound-method signal connections (no self-capturing lambdas)

**Source:** Project convention. Existing examples at `player.py:137, 148`:

```python
self._failover_timer.timeout.connect(self._on_timeout)
self._elapsed_timer.timeout.connect(self._on_elapsed_tick)
```

**Apply to Phase 52:** the new `_eq_ramp_timer.timeout.connect(self._on_eq_ramp_tick)` MUST be a bound method, not a lambda. Same for any per-tick helper.

### QTimer parented to `self` (Pitfall 2: main-thread construction)

**Source:** `player.py:135, 146` — every QTimer in `Player` is `QTimer(self)`. The comment at `player.py:134` calls this out explicitly:

```python
# QTimer objects -- constructed on the main thread (Pitfall 2)
```

**Apply to Phase 52:** `self._eq_ramp_timer = QTimer(self)`. Player is constructed on the main thread; the ramp timer's parent must be `self` so it lives on that thread.

### GstChildProxy band mutation (the only audio-mutation primitive)

**Source:** `player.py:647-648, 653-659`:

```python
self._eq.get_child_by_index(i).set_property("gain", float_value)
```

**Apply to Phase 52:** the ramp uses this same primitive at every tick. No new GStreamer plumbing — only the timing of the `set_property` calls changes. Reads (`get_property("gain")`) use the same access pattern.

### Phase 47.2 Pitfalls 4 and 5 (preserved during target-gain calculation)

**Source:** `player.py:655-658`. The ramp's `target_gain[i]` calculation must:
- Use `bandwidth = freq_hz / max(q, 0.01)` (Pitfall 4) — but bandwidth is written ONCE at ramp start, not per-tick.
- Use `gain = b.gain_db + self._eq_preamp_db` (Pitfall 5, ADD not subtract) — this is the per-band target the ramp interpolates toward.

### `_eq is None` graceful-degrade (locked by tests)

**Source:** `player.py:644`, `tests/test_player.py:340-365`. Every `set_eq_*` method early-returns when the plugin is absent. **Apply to Phase 52:** `set_eq_enabled` flips `_eq_enabled` and returns; `_on_eq_ramp_tick` defensively checks `if self._eq is None: return` (and stops the timer).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every Phase 52 file has a strong in-tree analog. The "QTimer with tick counter that stops itself after N ticks" pattern is novel to this phase, but is a natural composition of `_failover_timer` (single-shot) and `_elapsed_timer` (interval + handler increment). No external research needed. |

## Metadata

**Analog search scope:**
- `musicstreamer/player.py` — QTimer construction, EQ pipeline, lifecycle hooks
- `musicstreamer/ui_qt/edit_station_dialog.py` — debounce QTimer pattern (cross-checked, but Player-internal analogs are closer)
- `musicstreamer/ui_qt/now_playing_panel.py` — toggle button construction
- `tests/test_player.py` — existing EQ tests + elapsed-tick test pattern
- `tests/test_now_playing_panel.py` — existing toggle test pattern

**Files scanned:** 5 source files, 2 test files. Three additional QTimer use sites surveyed (`toast.py:74`, `edit_station_dialog.py:283-294`) — confirmed the in-Player analogs are the closest match.

**Pattern extraction date:** 2026-04-28

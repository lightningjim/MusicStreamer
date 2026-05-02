# Phase 57: Windows Audio Glitch + Test Fix — Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 4 (3 modified + 1 new)
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/player.py` (MOD: `_set_uri` and/or `pause`/`set_volume`) | service / playback-pipeline | request-response (state-machine write) | self (`_set_uri:485` for funnel; `audio-filter` slot at `:113`,`:121` for Option B; `set_volume:218` for property re-apply) | exact (in-file precedent) |
| `tests/test_player_failover.py` (MOD: add WIN-03 regression-guard test) | test | request-response (mock-pipeline assertion) | `tests/test_player_failover.py::test_set_uri_normalizes_difm_https_to_http:455` | exact (same file, sibling test using real `_set_uri`) |
| `tests/test_media_keys_smtc.py::_build_winrt_stubs` (MOD: line ~95) | test fixture | event-driven (mock object construction) | self (`_make_media_player_instance:76`); no existing `AsyncMock` precedent in the suite | role-match (same file; AsyncMock convention seeded fresh per D-08) |
| `.planning/phases/57-windows-audio-glitch-test-fix/57-DIAGNOSTIC-LOG.md` (NEW) | doc / diagnostic artifact | batch | `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` | exact |

> **No SOURCE-side modification** is required for WIN-04 (D-10). `musicstreamer/media_keys/smtc.py` is read-only this phase.

---

## Pattern Assignments

### `musicstreamer/player.py` — WIN-03 volume + glitch fix (controller of `playbin3` lifecycle)

**Analog:** SAME FILE — Phase 47.2 (audio-filter slot) and existing `set_volume`/`_set_uri` are the in-file precedents. The fix shape (Option A vs Option B) is data-driven from the diagnostic, but BOTH analogs already exist in `player.py` and the planner can copy idioms directly.

#### Imports pattern (already in place — no new imports for either Option)

`musicstreamer/player.py:32-48`:
```python
from __future__ import annotations

import os
import threading

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import QObject, Qt, QTimer, Signal

from musicstreamer import constants, cookie_utils, paths
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES
from musicstreamer.eq_profile import EqBand, EqProfile, parse_autoeq
from musicstreamer.gst_bus_bridge import GstBusLoopThread
from musicstreamer.models import Station, StationStream
from musicstreamer.stream_ordering import order_streams
from musicstreamer.url_helpers import aa_normalize_stream_url
```

`Gst` is already in scope via `from gi.repository import Gst`. No `import` change is needed for either Option A or Option B.

---

#### Option A — Re-apply volume property after NULL→PLAYING rebuild

**Pattern source 1: `set_volume` — single-line property write to keep**

`musicstreamer/player.py:218-220`:
```python
def set_volume(self, value: float) -> None:
    self._volume = max(0.0, min(1.0, value))
    self._pipeline.set_property("volume", self._volume)
```

This is the API surface; D-02 keeps its signature unchanged. `self._volume` (line 196) survives pipeline rebuilds — it lives on the player object, not on `playbin3` — so Option A re-applies the cached value at the end of `_set_uri`.

**Pattern source 2: `_set_uri` — funnel where the re-apply lands**

`musicstreamer/player.py:485-490`:
```python
def _set_uri(self, uri: str) -> None:
    uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS->HTTP at URI funnel
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
```

**D-03 INVARIANT (LOCKED):** `aa_normalize_stream_url(uri)` MUST stay as the FIRST executable line. Any Option A patch appends AFTER `set_state(PLAYING)`, never before the rewrite call.

**Option A literal patch shape** (after diagnostic confirms `playbin3.volume` resets across NULL→PLAYING):
```python
def _set_uri(self, uri: str) -> None:
    uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS->HTTP — D-03 invariant, MUST stay first
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
    # Phase 57 / WIN-03 D-06 Option A: re-apply volume; playbin3 resets it on NULL→PLAYING (Win-only)
    self._pipeline.set_property("volume", self._volume)
```

Linux behavior is preserved because Linux already retains the property; the second write is a no-op there. Single line, smallest blast radius.

---

#### Option B — Explicit `volume` GstElement in `playbin3.audio-filter` (Phase 47.2 mirror)

**Pattern source: EQ slot construction at `__init__`**

`musicstreamer/player.py:113-121`:
```python
# Phase 47.2 D-01: equalizer-nbands in playbin3.audio-filter slot.
# Constructed once; bands mutated live via GstChildProxy (D-05).
# Graceful degrade if gst-plugins-good's equalizer is missing
# (Windows Phase 43 spike will verify DLL presence): self._eq = None
# and all set_eq_* methods become no-ops.
self._eq = Gst.ElementFactory.make("equalizer-nbands", "eq")
if self._eq is not None:
    self._eq.set_property("num-bands", 10)  # placeholder; rebuilt per-profile
    self._pipeline.set_property("audio-filter", self._eq)
```

**Caveat:** `playbin3.audio-filter` is a SINGLE-element slot. EQ already occupies it (line 121). If WIN-03 ships Option B, the planner cannot set `audio-filter = volume_element`; it MUST chain volume → eq inside a `Gst.Bin` (or wrap them as a `GstBin` element). This is a meaningful blast-radius increase vs Option A, and is one reason D-06 prefers Option A when the data permits.

**Pattern source: rebuild-on-mutation idiom**

`musicstreamer/player.py:815-825` (mirrors `pause()` NULL-transition):
```python
def _rebuild_eq_element(self, num_bands: int) -> None:
    """D-04 + Pitfall 1: num-bands realloc unreliable; rebuild the whole element.

    Mirrors the pause() NULL-transition idiom at lines 199-206.
    """
    self._pipeline.set_state(Gst.State.READY)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._eq = Gst.ElementFactory.make("equalizer-nbands", "eq")
    if self._eq is not None:
        self._eq.set_property("num-bands", num_bands)
        self._pipeline.set_property("audio-filter", self._eq)
```

If Option B ships, an analogous `self._volume_element = Gst.ElementFactory.make("volume", "vol")` at `__init__` (around line 113, BEFORE the EQ block) and `set_volume()` body change to `self._volume_element.set_property("volume", v)` — but only after wrapping volume + eq into a `GstBin` so both occupy the single `audio-filter` slot. Planner picks the chaining shape.

**Graceful-degrade pattern (D-04 step 1 may name a sink without `volume` plugin):**

Lines 119-121 are the template — `if self._volume_element is not None:` guards every write. If the `volume` element factory returns None on Windows (unlikely; it's in `gst-plugins-base`), `set_volume()` falls back to `self._pipeline.set_property("volume", v)` (the Linux path). One-line fallback, mirrors the EQ `is None` guard.

---

#### Pause/resume audible-glitch fix (Claude's discretion, sink-mediated)

**Pattern source: `pause()` is the NULL-emit site**

`musicstreamer/player.py:299-311`:
```python
def pause(self) -> None:
    """Stop audio output without clearing station context (D-04)."""
    self._cancel_timers()
    self._elapsed_timer.stop()
    # Phase 52: cancel any in-flight EQ ramp; the pipeline going NULL
    # silences output anyway, but stopping the timer prevents a dangling
    # tick on a torn-down element.
    self._eq_ramp_timer.stop()
    self._eq_ramp_state = None
    self._streams_queue = []
    self._recovery_in_flight = False
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
```

**Pattern source: Phase 52 EQ gain ramp = nearest precedent for a smoothing timer wrapper**

`musicstreamer/player.py:160-163`:
```python
self._eq_ramp_timer = QTimer(self)
self._eq_ramp_timer.setInterval(self._EQ_RAMP_INTERVAL_MS)
self._eq_ramp_timer.timeout.connect(self._on_eq_ramp_tick)
self._eq_ramp_state: dict | None = None
```

`musicstreamer/player.py:683-685`:
```python
_EQ_RAMP_MS = 40
_EQ_RAMP_TICKS = 8
_EQ_RAMP_INTERVAL_MS = 5  # _EQ_RAMP_MS // _EQ_RAMP_TICKS
```

`musicstreamer/player.py:746-786` (full ramp-state idiom — fresh ramp + reverse-from-current):
- Pitfall 2: `QTimer` parented to `self` (main thread).
- Pitfall reset: `_eq_ramp_state = None` after `timeout.stop()` to avoid dangling state on a torn-down element.
- D-05: re-capture live values when reversing mid-ramp.

If the planner picks a "fade audio sink to 0 then NULL then PLAYING then fade up" smoothing wrapper, this Phase 52 ramp idiom is the in-file template. The smoothing wrapper MUST compose with the chosen volume fix (Option A or B) without double-writing the volume property — i.e., if Option B owns the volume element, the smoothing ramp writes to the element; if Option A keeps `playbin3.volume`, the ramp writes there.

**Threading invariant (Pitfall 2):** Any new `QTimer` MUST be constructed on the main thread, parented to `self`. See line 142 (`self._failover_timer = QTimer(self)`) and line 160. Never construct from a bus-loop or worker thread.

---

### `tests/test_player_failover.py` — WIN-03 D-07 Linux CI regression guard (test, request-response)

**Analog:** `tests/test_player_failover.py::test_set_uri_normalizes_difm_https_to_http` (line 455-462).

This sibling test is the **closest possible** analog: same file, same `make_player(qtbot)` fixture, same pattern (call real `_set_uri`, assert on the `_pipeline` MagicMock's `set_property` calls), and the comment block at lines 444-453 explicitly justifies the convention.

**Imports pattern** (already at top of file, lines 10-13):
```python
from unittest.mock import MagicMock, patch

from musicstreamer.models import Station, StationStream
from musicstreamer.player import Gst, Player
```

**Fixture pattern** (lines 16-27):
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
    player._pipeline = MagicMock()
    return player
```

**Critical convention** (lines 444-453, copy verbatim into the new test's docstring or section header):
```python
# NOTE: these tests deliberately do NOT patch.object(p, "_set_uri").
# All other tests in this file mock _set_uri to avoid real GStreamer state
# changes -- but that mock would intercept BEFORE the new normalization line
# runs, and a buggy helper would pass vacuously. These tests exercise the
# real _set_uri body and assert on the underlying _pipeline.set_property
# MagicMock (which make_player already replaces _pipeline with on line 26).
```

**Pattern shape for WIN-03 regression guard** (Option A flavor):
```python
def test_set_uri_reapplies_volume_after_rebuild(qtbot):
    """WIN-03 / D-07 Linux CI guard: after _set_uri rebuilds playbin3
    (NULL → PLAYING), the player's stored volume is re-applied to the
    pipeline. Regression guard for "contributor adds a new set_state(NULL)
    site and forgets to re-write volume" — catches the Windows-only bug
    on Linux without needing a Win CI runner."""
    p = make_player(qtbot)
    p.set_volume(0.5)
    # set_volume's own write is one assert_any_call; the WIN-03 guarantee is
    # that ANOTHER write of the same value happens after _set_uri's rebuild.
    p._pipeline.set_property.reset_mock()
    p._set_uri("http://example.com/stream.mp3")
    p._pipeline.set_property.assert_any_call("volume", 0.5)
```

**Pattern shape for Option B flavor** (if Option B ships, planner edits the assert target):
```python
# Replace the last two lines with:
#   assert p._volume_element is not None
#   p._volume_element.set_property.assert_any_call("volume", 0.5)
# (assuming the Option B field name; planner picks the actual attr.)
```

**Naming + grouping convention:** Add the test under a comment header following the existing pattern at line 444 (`# Phase 56 / WIN-01: _set_uri normalizes DI.fm HTTPS -> HTTP (D-01)`). New header text:
```python
# ---------------------------------------------------------------------------
# Phase 57 / WIN-03 D-07: _set_uri re-applies volume after NULL→PLAYING rebuild
# ---------------------------------------------------------------------------
```

---

### `tests/test_media_keys_smtc.py::_build_winrt_stubs` — WIN-04 AsyncMock fix (test fixture)

**Analog:** SAME FILE — `_make_media_player_instance` (lines 76-88) is the in-file MagicMock-construction precedent. There is **no existing `AsyncMock` usage anywhere in the test suite** (grep returned zero hits across `tests/`). WIN-04 introduces the convention; D-08 picks the minimal-patch shape.

**Imports pattern** (current top-of-file, lines 10-13):
```python
from __future__ import annotations

import sys
import tomllib
import types
import unittest.mock as mock  # noqa: F401
from pathlib import Path
from unittest.mock import MagicMock
```

**Required diff** (D-08 + D-09 minimal-patch shape):
```python
# Line 13: add AsyncMock to the from-import
from unittest.mock import AsyncMock, MagicMock
```

D-09 says: do NOT broaden — only the `DataWriter().store_async` attribute gets `AsyncMock`. `_await_store` is the only awaited winrt method in `smtc.py:60` (`await writer.store_async()`).

**Existing pattern at the fix site** (lines 93-96):
```python
storage_streams = types.ModuleType("winrt.windows.storage.streams")
storage_streams.InMemoryRandomAccessStream = MagicMock(name="InMemoryRandomAccessStream")
storage_streams.DataWriter = MagicMock(name="DataWriter")
storage_streams.RandomAccessStreamReference = MagicMock(name="RandomAccessStreamReference")
```

**Patch shape** — make instances of `DataWriter` carry an `AsyncMock` `store_async` attribute. The minimal D-09-respecting patch:
```python
storage_streams.DataWriter = MagicMock(name="DataWriter")
storage_streams.DataWriter.return_value.store_async = AsyncMock(name="store_async")
```

`DataWriter(stream)` returns a `MagicMock` (the class mock's `return_value`); the `_build_thumbnail_ref` body does `writer = DataWriter(stream)` then `await writer.store_async()`. Setting `return_value.store_async = AsyncMock()` makes that single await resolve. Production code (`_await_store` and the `asyncio.run(...)` driver in `smtc.py:248-258`) is untouched (D-10).

**Alternative shape** (D-08 explicitly permits): subclass-style factory mirroring `_make_media_player_instance:76-88`. NOT preferred because the WIN-04 surface is one attribute, not a multi-attribute object graph. Planner picks the minimal one-line `return_value.store_async = AsyncMock(...)` form.

**Why no broader audit (D-09):** All other winrt calls touched in this fixture are synchronous (`InMemoryRandomAccessStream()` constructor, `RandomAccessStreamReference.create_from_stream`, `writer.write_bytes(data)`). Only `writer.store_async()` is awaited in production. Future awaitable winrt methods get `AsyncMock` as they land — no anticipatory work this phase.

**No fixture cleanup change:** `mock_winrt_modules` (lines 118-129) is unchanged. The only edit is inside `_build_winrt_stubs` (~line 95) plus the import at line 13.

---

### `.planning/phases/57-windows-audio-glitch-test-fix/57-DIAGNOSTIC-LOG.md` (NEW, doc / batch artifact)

**Analog:** `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` — exact precedent. D-05 explicitly cites it.

**Section structure to copy** (from 56-03-DIAGNOSTIC-LOG.md lines 1-25, 26-55, 83-99, 101-115, 116-141):

1. **Header block** (lines 1-9):
```markdown
# Phase 57 / WIN-03 — Win11 VM Audio Diagnostic Log

**Started:** YYYY-MM-DD
**Driver:** Linux orchestrator (interactive paste-back mode); user executes PowerShell on Win11 VM
**Goal:** Capture the three D-04 readbacks (sink identity + volume property persistence + slider mid-stream effect), so Plan 57-XX knows whether to ship Option A (re-apply property), Option B (explicit volume element), or a hybrid.
```

2. **Pre-flight readiness table** (mirror lines 11-22 — `Win11 22H2+`, `Conda env active`, `Fresh installer artifact`, `Two PowerShell windows ready`).

3. **Per-step Pre/Post sections** — each D-04 step gets its own:
   ```markdown
   ## D-04 Step N: <step-name> (PRE-FIX)

   **Command (authoritative):**
   ```powershell
   <ps command>
   ```

   **Output:**
   ```
   <captured stdout>
   ```

   **Outcome classification:** **A / B / C** — <one-liner>

   **Implication for D-06:**
   - <hypothesis ruled out / confirmed with evidence>
   ```
   See 56-03-DIAGNOSTIC-LOG.md lines 26-79 for the literal template.

4. **Decision section** — mirror 56-03 lines 117-141:
   ```markdown
   ## D-06 Fix-Shape Selection + D-07 Plan Scope

   **Decision:** Option A / Option B / hybrid
   **D-06 classification:** <which evidence path picked it>
   **Rationale (one sentence):** ...

   **Cross-reference table:**

   | D-06 candidate | Hypothesis | Status | Evidence |
   |---------------|-----------|--------|----------|
   | Option A | playbin3.volume resets on NULL→PLAYING | <confirmed/ruled out> | Step 2 readback |
   | Option B | Sink ignores playbin3.volume entirely | <confirmed/ruled out> | Step 2 readback |
   ```

**Concrete readback table format** (copy from 56-03 line 33-38):
```markdown
| Check | Result | Notes |
|-------|--------|-------|
| Win11 22H2+ | assumed ✓ | Same VM used in Phase 56-03 / Phase 43-44 spike rig |
| Conda env active | ✓ | env named `<x>` |
```

**Naming convention:** `57-DIAGNOSTIC-LOG.md` (top-level, not per-plan) is proposed in CONTEXT.md (Claude's Discretion section). Mirrors `56-03-DIAGNOSTIC-LOG.md` location convention. Planner can move to per-plan name (`57-XX-DIAGNOSTIC-LOG.md`) if a multi-plan layout is chosen.

---

## Shared Patterns

### Threading rules — apply to ALL `player.py` edits

**Source:** Module docstring `musicstreamer/player.py:3-12` + `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` (auto-loaded for this project).

```
- Player lives on the thread that constructed it (the Qt main thread under
  QCoreApplication.exec()). All QTimer objects, all signal connections, and
  the pipeline state-changes happen on that thread.
- GStreamer bus signal watches (message::error, message::tag) are dispatched
  by a GstBusLoopThread daemon thread running GLib.MainLoop. Handlers run on
  THAT thread and emit Qt signals -- cross-thread emission is auto-queued.
```

**Apply to:** Any new `QTimer` for the smoothing wrapper MUST be constructed on the main thread (Pitfall 2), parented to `self`. Any new bus-handler work uses queued signals (existing pattern at `musicstreamer/player.py:89-95`, `:177-187`). The volume re-apply in Option A runs on the main thread (it's inside `_set_uri`, called from `_try_next_stream` which is itself main-thread-marshalled via `_try_next_stream_requested` — line 95).

### `Gst.State.NULL` settle-wait pattern — apply to any new state transitions

**Source:** `musicstreamer/player.py:452-458` (exemplar inside `_try_next_stream`):
```python
self._pipeline.set_state(Gst.State.NULL)
# Wait for NULL to complete so playbin3's internal streamsynchronizer
# fully resets before we reconfigure.  Without this, rapid
# teardown→replay (e.g. YouTube resolve failure → failover) can leave
# duplicate pad names in streamsynchronizer, triggering GStreamer
# CRITICAL assertions that abort the process.
self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
```

**Apply to:** Every `set_state(NULL)` MUST be followed by `get_state(Gst.CLOCK_TIME_NONE)`. Existing call sites: `_set_uri:487`, `pause:310`, `stop:322`, `_try_next_stream:452`, `_play_youtube:503`, `_play_twitch:611`, `_rebuild_eq_element:820`. If the smoothing wrapper inserts new state transitions, they keep this idiom.

### `_set_uri` D-03 invariant — apply to any `_set_uri` edit

**Source:** Phase 56 D-04 (locked by `tests/test_player_failover.py::test_set_uri_normalizes_difm_https_to_http`).

The line `uri = aa_normalize_stream_url(uri)` MUST be the **first executable line** of `_set_uri`. Any WIN-03 patch (Option A or Option B) that touches `_set_uri` keeps the rewrite call as the very first executable line. Both Phase-56 invariant tests at lines 455-482 will fail vacuously and audibly if violated.

### Test fixture convention — apply to any new player test

**Source:** `tests/test_player_volume.py:9-23` (canonical `make_player(qtbot)` fixture). Every player test file in `tests/test_player_*.py` reproduces it:

```python
def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    from musicstreamer.player import Player
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    player._pipeline = MagicMock()
    return player
```

**Apply to:** D-07 Linux CI regression-guard test reuses this fixture verbatim. No new conftest/fixture work — it's already file-local in `test_player_failover.py:16-27` (and identical copies in `_volume`, `_pause`, etc.).

### Diagnose-first cadence — apply to all WIN-03 work

**Source:** Phase 56 D-07/D-08 + 56-03-DIAGNOSTIC-LOG.md verdict (line 95: "SMTC binding is **WORKING CORRECTLY** ... The 'Unknown app' symptom does NOT reproduce on this install + launch-path combination — environmental/launch-discipline issue, not a code bug.").

Phase 56 shipped docs-only because the diagnostic disproved the assumed code-bug hypothesis. WIN-03 follows the same cadence: read back actual state on the VM, then choose Option A vs Option B vs no-code-change. The planner does NOT pre-commit to an Option in PLAN.md — only enumerates both with patch shapes.

---

## No Analog Found

None. All four touched files have strong in-codebase analogs (three same-file precedents + one sibling-phase doc precedent).

---

## Metadata

**Analog search scope:**
- `musicstreamer/player.py` (entire file — 854 lines, single Read)
- `musicstreamer/media_keys/smtc.py` (`_await_store:52`, `_build_thumbnail_ref:210` regions)
- `musicstreamer/ui_qt/now_playing_panel.py` (volume slider region 320-340)
- `tests/test_player_*.py` (six files: `_buffer`, `_buffering`, `_failover`, `_pause`, `_tag`, `_volume`)
- `tests/test_player.py` (audio-filter assertion at line 191)
- `tests/test_media_keys_smtc.py` (`_build_winrt_stubs:40-115`, failing test at `:438`)
- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md`
- `grep` across `tests/` for `AsyncMock` (zero hits — confirms WIN-04 introduces convention)
- `grep` across `musicstreamer/` and `tests/` for `store_async`, `_await_store`, `asyncio.run`, `audio-filter`

**Files scanned:** ~15 source/test files + 1 sibling-phase doc.

**Pattern extraction date:** 2026-05-02

---

## PATTERN MAPPING COMPLETE

**Phase:** 57 — windows-audio-glitch-test-fix
**Files classified:** 4
**Analogs found:** 4 / 4

### Coverage
- Files with exact analog: 3 (player.py same-file; test_player_failover.py same-file sibling test; 56-03-DIAGNOSTIC-LOG.md exact format precedent)
- Files with role-match analog: 1 (test_media_keys_smtc.py — same file fixture-builder convention; AsyncMock convention introduced fresh per D-08)
- Files with no analog: 0

### Key Patterns Identified
- **D-03 invariant** is locked: `aa_normalize_stream_url(uri)` stays first line of `_set_uri` regardless of which Option ships.
- **Option A** is a one-liner copy of `set_volume`'s own write at the end of `_set_uri` (after `set_state(PLAYING)`); Linux is no-op.
- **Option B** mirrors Phase 47.2's `audio-filter` slot idiom (`musicstreamer/player.py:113-121`), with the **single-slot caveat** — EQ already occupies it, so volume + EQ must chain inside a `Gst.Bin`.
- **Pause/resume smoothing** has Phase 52's EQ gain ramp (`_eq_ramp_*` family at lines 160-163, 683-685, 746-813) as the in-file precedent for a `QTimer`-driven fade.
- **WIN-04** is a one-attribute test-only patch: `storage_streams.DataWriter.return_value.store_async = AsyncMock(name="store_async")` plus `AsyncMock` in the from-import. No production touch (D-10).
- **Diagnostic log** copies 56-03-DIAGNOSTIC-LOG.md's section structure (pre-flight table, per-step PRE/POST blocks, decision cross-reference table).
- **Threading invariants** (Pitfall 2 — main-thread `QTimer` parented to `self`) and **NULL settle-wait** (`get_state(Gst.CLOCK_TIME_NONE)` after every `set_state(NULL)`) apply to every `player.py` edit.

### File Created
`.planning/phases/57-windows-audio-glitch-test-fix/57-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns + concrete excerpts in the WIN-03 (Option A/B), WIN-04, and diagnostic-log plan actions.

# Phase 56: Windows DI.fm + SMTC Start Menu - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 4 (1 modified helper module, 1 modified player, 2 modified test files, 1 new optional test file)
**Analogs found:** 4 / 4 (all in-tree, exact role + data flow matches)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/url_helpers.py` (MODIFY: add `aa_normalize_stream_url`) | utility (pure URL classifier/transformer) | transform (sync, stateless) | Same file: `_aa_slug_from_url` (line 123), `_aa_channel_key_from_url` (line 85), `_is_aa_url` (line 79) | exact (same module, same shape) |
| `musicstreamer/player.py` (MODIFY: prepend helper call in `_set_uri`) | controller (URI funnel for `playbin3`) | request-response (one-shot synchronous URL transform at boundary) | Same file: `_set_uri` (line 484) is its own analog — minimal-diff one-line wrap | exact (in-place wrap) |
| `tests/test_aa_url_detection.py` (MODIFY: add 6-8 unit tests) | test (pure-function unit tests) | transform (input → expected output assertion) | Same file: existing 30+ assert-style tests for `_is_aa_url`, `_aa_channel_key_from_url` (lines 4-116) | exact (extend in place) |
| `tests/test_player_failover.py` (MODIFY: add 2 player-level tests) | test (Player + MagicMock pipeline integration) | request-response (call `_set_uri` directly, observe `_pipeline.set_property` MagicMock calls) | Same file: `make_player` harness (line 16) + existing tests using `patch.object(p, "_set_uri")` (lines 66, 83, etc.) — but new tests must NOT mock `_set_uri` | role-match (existing harness, inverted mock strategy) |
| `tests/test_aumid_string_parity.py` (NEW, optional D-09 #3 guard) | test (file-text regex parity assertion) | transform (read both files, assert literal match) | No exact analog — closest is `tests/test_aa_url_detection.py` for the assert-style file-isolation convention | role-match (test convention only; the file-read pattern is novel for this repo) |

## Pattern Assignments

### `musicstreamer/url_helpers.py` — add `aa_normalize_stream_url` (utility, transform)

**Analog:** `musicstreamer/url_helpers.py` itself — `_aa_slug_from_url`, `_aa_channel_key_from_url`, `_is_aa_url` are the established convention.

**Module docstring sets the constraint** (lines 1-7):
```python
"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests (test_aa_url_detection, test_yt_thumbnail) survive the
deletion of the ui/ tree. These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
```
**Implication:** new helper MUST be pure stdlib (no Qt, no GLib, no GStreamer, no DB). The new helper inherits this constraint by living in this module.

**Imports already present** (lines 8-13):
```python
from __future__ import annotations

import html
import urllib.parse

from musicstreamer.aa_import import NETWORKS
```
**Implication:** the helper does NOT need to add any new imports beyond `import logging` (which is required by D-05 silent-rewrite directive). `_aa_slug_from_url` is in-module; reference it directly.

**Closest existing function — `_aa_slug_from_url`** (lines 123-134):
```python
def _aa_slug_from_url(url: str) -> str | None:
    """Determine the AA network slug from a stream URL domain.

    e.g. 'http://prem2.di.fm:80/di_house' -> 'di'
    """
    url_lower = url.lower()
    for net in NETWORKS:
        # Match the domain part (e.g. di.fm matches prem2.di.fm)
        domain_base = net["domain"].replace("listen.", "")  # "di.fm"
        if domain_base in url_lower:
            return net["slug"]
    return None
```
**Pattern to copy:** terse single-purpose function, type-hinted (`str` → `str | None`), one-line docstring + example, reads from in-module `NETWORKS` constant. The new `aa_normalize_stream_url` mirrors this shape but composes `_aa_slug_from_url` rather than re-iterating `NETWORKS`.

**Composition pattern from `find_aa_siblings`** (lines 158-165) — early-return guard ladder over `_aa_slug_from_url`:
```python
# Gate: current station must itself be a parseable AA URL (D-04).
if not _is_aa_url(current_first_url):
    return []
current_slug = _aa_slug_from_url(current_first_url)
if not current_slug:
    return []
current_key = _aa_channel_key_from_url(current_first_url, slug=current_slug)
if not current_key:
    return []
```
**Pattern to copy:** sequential `if not <predicate>: return <pass-through>` guards, cheapest check first. New helper applies the same idiom: empty check → prefix check → slug check → rewrite.

**Logging pattern** (NOT in `url_helpers.py` today — borrowed from `aa_import.py`):
```python
import logging
_log = logging.getLogger(__name__)
# ...
_log.warning("AA image map HTTP error for %s: %s", slug, e)  # aa_import.py:81
```
**Pattern to copy:** module-level `_log = logging.getLogger(__name__)` at top, then `_log.debug("...: %s -> %s", url, rewritten)` at the rewrite site (D-05 silent-rewrite, single debug line). Import `logging` near `urllib.parse`.

**Idempotency / pass-through convention** (from `_aa_channel_key_from_url` lines 98-120):
```python
try:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lstrip("/")
    if not path:
        return None
    # ... transformations ...
    return key or None
except Exception:
    return None
```
**Pattern to copy:** defensive — never raises on malformed input; D-06 mandates pass-through for empty/None/non-DI.fm/already-http. The new helper is even simpler (no urlparse needed; cheap `startswith` is enough).

---

### `musicstreamer/player.py::_set_uri` — one-line helper call (controller, request-response)

**Analog:** the function as it stands today is the analog — minimal-diff transform at the boundary.

**Current implementation** (`musicstreamer/player.py` lines 484-488):
```python
def _set_uri(self, uri: str) -> None:
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
```

**Imports section pattern** (`musicstreamer/player.py` lines 32-47):
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
```
**Pattern to copy:** intra-`musicstreamer.*` imports come AFTER stdlib + third-party imports, alphabetically. New import line:
```python
from musicstreamer.url_helpers import aa_normalize_stream_url
```
Place between `from musicstreamer.stream_ordering import order_streams` and the next blank line (alphabetical insertion after `stream_ordering`).

**Wire-in pattern** (proposed minimal diff):
```python
def _set_uri(self, uri: str) -> None:
    uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS→HTTP at URI funnel
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
```
**Pattern reference:** Phase 47-01 "transform once at the boundary" pattern — applied here exactly per CONTEXT.md D-01.

**Caller sites that converge on `_set_uri`** (audited per RESEARCH.md A1):
- `play()` line 480: `self._set_uri(url)` (direct streams)
- YouTube resolved signal handler (around line 590): `self._set_uri(<hls-url>)`
- Twitch resolved signal handler (around line 669): `self._set_uri(<hls-url>)`
- `_try_next_stream` (failover): also funnels through `_set_uri`

**Pattern to copy:** the helper call goes inside `_set_uri` (single funnel) — NOT at any caller. Any future direct `pipeline.set_property("uri", ...)` outside `_set_uri` would bypass normalization (Pitfall not in current code; new player-level tests guard the wired path).

---

### `tests/test_aa_url_detection.py` — extend with `aa_normalize_stream_url` unit tests (test, transform)

**Analog:** the file itself is the analog — 30+ assertion-style unit tests with the exact convention to extend.

**Import pattern** (line 1):
```python
from musicstreamer.url_helpers import _is_aa_url, _aa_channel_key_from_url
```
**Pattern to copy:** add `aa_normalize_stream_url` to this import (or a new line if planner prefers grouping public vs. underscore-prefixed names).

**Test convention — function-per-case, single assert** (lines 4-26):
```python
def test_is_aa_url_di():
    assert _is_aa_url("http://prem2.di.fm:80/di_house?listen_key=abc") is True

def test_is_aa_url_radiotunes():
    assert _is_aa_url("http://prem1.radiotunes.com:80/ambient?listen_key=x") is True

def test_is_aa_url_false_youtube():
    assert _is_aa_url("https://www.youtube.com/watch?v=abc") is False

def test_is_aa_url_false_generic():
    assert _is_aa_url("http://example.com/stream") is False
```
**Pattern to copy:** each test does one thing, one assertion, descriptive snake-case name encoding the case (e.g., `test_aa_normalize_difm_https_to_http`, `test_aa_normalize_difm_http_passthrough`, `test_aa_normalize_non_difm_passthrough`, `test_aa_normalize_empty`, `test_aa_normalize_none_passthrough`, `test_aa_normalize_idempotent`). No fixtures, no parametrize — RESEARCH.md confirms repo convention is verbose-but-clear individual functions.

**Comment-as-section divider pattern** (lines 52, 66, 101 — used to group related tests):
```python
# --- DI.fm di_ prefix stripping (bug fix: di_ prefix was not stripped) ---

# --- DI.fm channel key aliases (renamed channels whose URL path != API key) ---

# --- RadioTunes 'rt' prefix stripping (parallel to DI 'di_' and ZenRadio 'zr') ---
```
**Pattern to copy:** add a `# --- DI.fm HTTPS→HTTP normalization (Phase 56 / WIN-01) ---` divider above the new tests.

**No fixtures, no qtbot, no MagicMock** — these are pure-function tests. The new `aa_normalize_stream_url` tests follow the same shape (no autouse `_stub_bus_bridge` impact because Player is not constructed).

---

### `tests/test_player_failover.py` — extend with `_set_uri` integration tests (test, request-response)

**Analog:** `make_player` harness in same file (lines 16-27) + the `patch.object(p, "_set_uri")` mock pattern used by 14+ existing tests.

**Critical inversion:** existing tests MOCK `_set_uri` to avoid real GStreamer calls. The new tests must NOT mock `_set_uri` — they exercise the real method body so the new normalization line runs, then assert on the underlying `_pipeline.set_property` MagicMock (which is captured by `make_player`).

**Existing harness pattern — `make_player`** (lines 16-27):
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
**Pattern to copy:** reuse `make_player(qtbot)` directly. The `player._pipeline = MagicMock()` reassignment on line 26 is what makes `_pipeline.set_property("uri", ...)` calls observable via `assert_any_call`. No new fixture needed.

**Existing test that mocks `_set_uri` — DO NOT replicate this mock for the new tests** (line 66):
```python
def test_preferred_stream_first(qtbot):
    p = make_player(qtbot)
    streams = [...]
    station = make_station_with_streams(streams)
    with patch.object(p, "_set_uri"):     # <-- intercepts BEFORE normalization runs
        p.play(station, preferred_quality="hi")
    assert p._current_stream.quality == "hi"
```
**Anti-pattern alert (RESEARCH.md Pitfall #1):** if the new normalization test wraps `_set_uri` in `patch.object(p, "_set_uri")`, the new line `uri = aa_normalize_stream_url(uri)` never executes and the test passes vacuously even with a buggy helper.

**Recommended new-test pattern** (RESEARCH.md Example 3):
```python
def test_set_uri_normalizes_difm_https_to_http(qtbot):
    """WIN-01: _set_uri rewrites DI.fm https:// to http:// before
    handing the URL to playbin3 (D-01)."""
    p = make_player(qtbot)
    # NOTE: deliberately do NOT patch.object(p, "_set_uri") — must exercise
    # the real method body so the normalization line runs.
    p._set_uri("https://prem1.di.fm/lounge?listen_key=abc")
    p._pipeline.set_property.assert_any_call(
        "uri", "http://prem1.di.fm/lounge?listen_key=abc"
    )

def test_set_uri_passes_through_non_difm(qtbot):
    """Non-DI.fm URLs must reach playbin3 unchanged (D-06 idempotency)."""
    p = make_player(qtbot)
    p._set_uri("https://ice4.somafm.com/dronezone-256-mp3")
    p._pipeline.set_property.assert_any_call(
        "uri", "https://ice4.somafm.com/dronezone-256-mp3"
    )
```

**Section-divider comment convention** (lines 53-55, 101-103, 186-188, 222-224, 238-240, 334-336, 383-386):
```python
# ---------------------------------------------------------------------------
# Phase 47-02: failover queue uses order_streams (PB-18)
# ---------------------------------------------------------------------------
```
**Pattern to copy:** add a new divider above the new tests:
```python
# ---------------------------------------------------------------------------
# Phase 56 / WIN-01: _set_uri normalizes DI.fm HTTPS → HTTP (D-01)
# ---------------------------------------------------------------------------
```
Place these tests near the bottom, after the existing Phase 47-02 / gap-closure block (after line 442).

**Imports section** (lines 10-13):
```python
from unittest.mock import MagicMock, patch

from musicstreamer.models import Station, StationStream
from musicstreamer.player import Gst, Player
```
**Pattern to copy:** no new imports needed — `MagicMock`, `Player`, `make_player` already in scope.

---

### `tests/test_aumid_string_parity.py` (NEW, optional D-09 #3 guard) — file-text regex parity (test, transform)

**Analog:** no exact in-tree analog (this is the only test that reads source files as text for cross-file consistency). Closest stylistic match is `tests/test_aa_url_detection.py` for the assert-style convention.

**Recommended pattern** (RESEARCH.md Pitfall #6, verbatim):
```python
"""Phase 56 / D-09 #3: AUMID literal parity between __main__.py and the Inno Setup .iss.

A typo in either file silently breaks the SMTC overlay binding without
any runtime error or Linux-CI test failure. This guard catches drift
at unit-test time (Linux CI safe — no Windows dependency)."""
import re
from pathlib import Path


def test_aumid_string_parity():
    main_py = Path("musicstreamer/__main__.py").read_text()
    iss = Path("packaging/windows/MusicStreamer.iss").read_text()
    main_match = re.search(r'app_id:\s*str\s*=\s*"([^"]+)"', main_py)
    iss_match = re.search(r'AppUserModelID:\s*"([^"]+)"', iss)
    assert main_match is not None, "AUMID default arg not found in __main__.py"
    assert iss_match is not None, "AppUserModelID directive not found in MusicStreamer.iss"
    assert main_match.group(1) == iss_match.group(1), (
        f"AUMID drift: __main__.py='{main_match.group(1)}' "
        f"iss='{iss_match.group(1)}'"
    )
```

**Source-of-truth references for the regexes:**
- `musicstreamer/__main__.py` line 99: `def _set_windows_aumid(app_id: str = "org.lightningjim.MusicStreamer") -> None:`
- `packaging/windows/MusicStreamer.iss` line 71: `    AppUserModelID: "org.lightningjim.MusicStreamer"`

**Pattern reuse — assertion style and module-level test function** matches `test_aa_url_detection.py`. Path resolution uses `Path(...)` relative to repo root (pytest's `testpaths = ["tests"]` runs from project root, so relative paths work; if the planner prefers, anchor to `Path(__file__).parent.parent` for robustness).

**Status:** OPTIONAL per CONTEXT.md D-09 #3 / Claude's discretion. RESEARCH.md Open Question #1 recommends shipping it. Planner decides.

## Shared Patterns

### Pure free functions in `url_helpers.py`
**Source:** `musicstreamer/url_helpers.py` (entire module)
**Apply to:** any new URL classifier or transformer in this phase or later
**Constraint:** zero Qt/GLib/GStreamer coupling, stdlib + in-module-`NETWORKS` only, must be importable from a non-Qt unit test
```python
# Module docstring locks the convention:
"""Pure URL classification helpers for stream sources.
...
These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
```

### Module-level logger via `logging.getLogger(__name__)`
**Source:** `musicstreamer/aa_import.py` (and many other modules)
**Apply to:** any new code path that needs forensic visibility (D-05 silent debug log)
```python
import logging
_log = logging.getLogger(__name__)
# ...
_log.debug("aa_normalize_stream_url: DI.fm https→http: %s -> %s", url, rewritten)
```
Note: use `%s` lazy formatting, NOT f-strings — matches established convention and avoids string interpolation when log level filters the message out.

### Single-funnel transform at the URI boundary
**Source:** `musicstreamer/player.py::_set_uri` (line 484)
**Apply to:** WIN-01 helper wire-in
**Reference:** Phase 47-01 stream-ordering precedent — transform once at the boundary, never at every call site. CONTEXT.md D-01 locks this for WIN-01.

### Test convention: assertion-per-function, descriptive snake-case names
**Source:** `tests/test_aa_url_detection.py`
**Apply to:** all new pure-function unit tests in this phase
```python
def test_aa_normalize_difm_https_to_http():
    assert aa_normalize_stream_url("https://prem1.di.fm/lounge") == "http://prem1.di.fm/lounge"
```
No `pytest.parametrize`, no fixtures (for pure functions), no shared setup. Each test is self-contained and reads top-to-bottom as a spec.

### Test convention: `make_player(qtbot)` MagicMock-pipeline harness
**Source:** `tests/test_player_failover.py:16-27`
**Apply to:** new `_set_uri` integration tests (without `patch.object(p, "_set_uri")`)
**Critical:** `make_player` already replaces `_pipeline` with a fresh `MagicMock()` (line 26), so `_pipeline.set_property("uri", ...)` calls are captured and assertable via `assert_any_call`.

### Test convention: section-divider comment blocks
**Source:** `tests/test_player_failover.py` (lines 53-55, 101-103, 186-188, etc.)
**Apply to:** new test groupings in either `test_aa_url_detection.py` or `test_player_failover.py`
```python
# ---------------------------------------------------------------------------
# Phase 56 / WIN-01: <one-line description>
# ---------------------------------------------------------------------------
```

### Conftest autouse `_stub_bus_bridge` (background context)
**Source:** `tests/conftest.py:20-30`
**Apply to:** automatically applies to any test that constructs `Player()` — no action required by new tests, but the planner should know that real `GstBusLoopThread` never spins up under pytest, which is what makes `make_player` safe.

## No Analog Found

No files in this phase have zero analog. The optional `tests/test_aumid_string_parity.py` is the only file whose data flow (cross-file text-regex parity check) is novel, but it follows the standard pytest assertion convention so it's a partial role-match, not a no-analog case.

## Metadata

**Analog search scope:**
- `musicstreamer/url_helpers.py` (full file, 232 lines)
- `musicstreamer/player.py` (lines 1-60 imports + lines 470-520 `_set_uri` and surrounding context)
- `musicstreamer/__main__.py` (lines 90-150 AUMID + run_gui surroundings)
- `musicstreamer/aa_import.py` (lines 80-100 NETWORKS + logger pattern)
- `packaging/windows/MusicStreamer.iss` (full file, 87 lines)
- `tests/test_aa_url_detection.py` (full file, 122 lines)
- `tests/test_player_failover.py` (full file, 442 lines)
- `tests/conftest.py` (lines 1-30, autouse fixture)

**Files scanned:** 8 (each read once with non-overlapping ranges)
**Pattern extraction date:** 2026-05-02
**Phase:** 56-windows-di-fm-smtc-start-menu

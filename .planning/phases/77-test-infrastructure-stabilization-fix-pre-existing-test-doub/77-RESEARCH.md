# Phase 77: Test infrastructure stabilization — Research

**Researched:** 2026-05-17
**Domain:** pytest / pytest-qt test infrastructure; PySide6 introspection; QtDBus session-bus lifecycle; streamlink session API
**Confidence:** HIGH

## Summary

Phase 77 closes six discrete failure clusters that have been carried across 10+ phases' `deferred-items.md` audits. The CONTEXT.md decisions D-00 through D-18 are mostly locked, but **two of them require correction** based on direct API and codebase verification done during research:

1. **D-05 must be inverted.** Streamlink removed `Streamlink.set_plugin_option()` entirely in **streamlink 6.0.0 (2023-07-20)**, PR #5033 [CITED: streamlink/streamlink#5033]. The project pins `streamlink>=8.3` in `pyproject.toml:20` and the installed copy is `streamlink 8.3.0`. The Phase 31 docstring at `tests/test_twitch_auth.py:1-9` is **stale 2-year-old documentation referring to a deleted API**. Production at `musicstreamer/player.py:1156` already uses the correct migrated API: `session.set_option("twitch-api-header", ...)`. The fix is therefore **test follows impl** (delete/rewrite the `set_plugin_option` assertion and update the stale docstring), NOT impl follows test. Verified by direct CPython probe: `'Streamlink' object has no attribute 'set_plugin_option'`.

2. **FakePlayer drift is wider than CONTEXT.md D-09 describes.** Production `Player.audio_caps_detected = Signal(int, int, int)` (3 args, per `musicstreamer/player.py:282`), but `tests/test_main_window_gbs.py:34` and `tests/test_main_window_soma.py:42` both declare it as `Signal(object)` (1 arg) — wrong arity. The drift-guard test (D-16) must compare not just signal *names* but also *argument arity* against the canonical Player class, or it will silently miss arity drift. Additionally, four other FakePlayer sites are missing `audio_caps_detected` entirely. Full inventory below.

Beyond the corrections, the recommendations are: introspect `Player.__dict__` (NOT `dir(Player)`) filtering by `isinstance(v, Signal)` to enumerate the canonical signal set — this naturally excludes inherited QObject signals (verified empirically); monkeypatch `musicstreamer.media_keys.mpris2.SERVICE_NAME` at the module level via pytest's `monkeypatch.setattr` (the function reads the name dynamically, verified); use option (b) `panel._stack.currentIndex() == 0` for D-15 because `isVisibleTo()` returns False on any widget whose top-level was never shown (which is what's actually happening, NOT an offscreen-platform quirk); fix the EditStationDialog logo-fetch crash by patching `urllib.request.urlretrieve` at the test sites that construct EditStationDialog rather than adopting pytest-socket project-wide.

**Primary recommendation:** Plan the work in this order — (1) write the canonical `tests/_fake_player.py` module + signal-parity drift-guard, (2) ship the drift-guards FIRST (so the planner's own subsequent FakePlayer-site migrations are guard-rail-protected), (3) migrate the 11 FakePlayer sites (CONTEXT.md says 12 but actual grep count is 11), (4) fix the MPRIS2 unique-name fixture, (5) close the six test↔impl drift items, (6) end with a phase-gate `uv run pytest tests/` clean run.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Player Signal canonicalization | tests/_fake_player.py | tests/test_fake_player_signal_parity.py | Test infrastructure; production Player is single source of truth |
| Drift-guard against inline FakePlayer | tests/test_fake_player_no_inline.py | — | Test infrastructure; source-grep convention (precedent: tests/test_yt_dlp_opts_drift.py) |
| MPRIS2 unique service name | tests/test_media_keys_mpris2.py fixture | — | Test infrastructure only — production `mpris2.py` unchanged per D-10 |
| Twitch streamlink API call | musicstreamer/player.py (already correct) | tests/test_twitch_auth.py (rewrite) | Production is correct; test references deleted API |
| AudioAddict quality dropdown | (removed in Phase 56) | tests/test_import_dialog_qt.py (delete orphans) | Production already correct; tests orphaned |
| Recent-played row limit (5) | musicstreamer/ui_qt/station_list_panel.py:492 (unchanged) | tests/test_station_list_panel.py:517 (update to 5) | Production correct per BROWSE-04 |
| QStackedWidget page-0 visibility | tests/test_station_list_panel.py:326,332 (rewrite) | — | Test uses `isVisibleTo` against an unshown widget; replace with `_stack.currentIndex()` |
| Network call sandbox in tests | tests/test_main_window_underrun.py (monkeypatch) | — | Local urllib.request.urlretrieve patch per test, not project-wide pytest-socket |
| Cover-art worker teardown | musicstreamer/cover_art.py (threading.Thread daemon) | musicstreamer/ui_qt/now_playing_panel.py token guard already exists | Daemon thread + token guard is the existing pattern; no production-code refactor in Phase 77 |
| `_YtScanWorker` teardown | tests/test_import_dialog_qt.py:234 (worker join) | musicstreamer/ui_qt/import_dialog.py (worker class) | Test-side `qtbot.waitSignal` + explicit worker.wait() is the surgical fix |

## Standard Stack

### Core (already pinned; no new deps required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=9 | Test runner | Already pinned in `pyproject.toml` `[project.optional-dependencies] test` (line 31) [VERIFIED: file:./pyproject.toml] |
| pytest-qt | >=4 | qtbot fixture, Qt event-loop integration | Already pinned in `pyproject.toml` (line 32); used throughout `tests/` [VERIFIED: file:./pyproject.toml] |
| PySide6 | >=6.10 | QObject, Signal, QtDBus | Already pinned; runtime is 6.11.0 [VERIFIED: pytest output `PySide6 6.11.0`] |
| streamlink | >=8.3 | Twitch HLS resolution | Already pinned; runtime is 8.3.0 [VERIFIED: `python -c "import streamlink; print(streamlink.__version__)"` → `8.3.0`] |

### Supporting (no new packages — all stdlib)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock` (stdlib) | — | `monkeypatch`, `MagicMock`, `patch` | Existing pattern throughout tests/ — used for SERVICE_NAME monkeypatch and urlretrieve patch |
| `uuid` (stdlib) | — | Per-test unique MPRIS2 service-name suffix | D-10 fixture body uses `uuid4().hex[:8]` |
| `os` (stdlib) | — | `os.getpid()` for debuggable suffix | D-10 working form `test_{pid}_{uuid8}` |
| `inspect` / `pathlib` (stdlib) | — | Drift-guard source-grep (D-17) | Existing precedent at `tests/test_yt_dlp_opts_drift.py:16,35`; `tests/test_constants_drift.py:55,99` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-test `monkeypatch.setattr(urllib.request, "urlretrieve", ...)` | `pytest-socket` (project-wide network block) | `pytest-socket` is legitimate ([VERIFIED: pypistats.org — 11.3M downloads/month, version 0.7.0, miketheman/pytest-socket on GitHub]) but adds a new dev-only dependency and introduces a global gate that integration tests under `tests/integration/` would have to opt out of. Per-test monkeypatch is the surgical fix consistent with the project's "tests bias toward minimum-diff" pattern. Recommendation: **stay with monkeypatch**. |
| Module-level monkeypatch of `SERVICE_NAME` | Add a new constructor kwarg `service_name: str \| None = None` to `LinuxMprisBackend` | Constructor-kwarg is wider blast radius (changes the production API for a test-only concern, and the existing `mpris2.py:256` TODO already documents this as a future production feature). Monkeypatch is the canonical project pattern (precedent: `tests/test_cookies.py` `paths._root_override`). [CITED: CONTEXT.md D-10] |
| Walk `dir(Player)` filtering by `isinstance(v, Signal)` | Walk `Player.__dict__` filtering by `isinstance(v, Signal)` | `dir(Player)` includes inherited `QObject` Signals (`destroyed`, `objectNameChanged`) [VERIFIED: direct probe; both appear in `dir()` output, count 20 vs 18]. `Player.__dict__` excludes inherited Signals naturally because `__dict__` only contains class-level attributes declared on `Player` itself. Use `__dict__`. |

**No installation needed** — all dependencies are already in `pyproject.toml`. Phase 77 ships **zero** new third-party deps.

**Version verification:**
```bash
uv run --no-sync python -c "import streamlink; print(streamlink.__version__)"  # 8.3.0
uv run --no-sync python -c "import PySide6; from PySide6 import __version__; print(__version__)"  # 6.11.0
```

## Package Legitimacy Audit

Phase 77 ships **no new third-party packages**. The Standard Stack section above only references already-pinned dependencies from `pyproject.toml`. The slopcheck gate therefore does not apply.

The one *alternative* that was researched and rejected:

| Package | Registry | Age | Downloads | Source Repo | Disposition |
|---------|----------|-----|-----------|-------------|-------------|
| pytest-socket | PyPI | 7+ years (initial 2018; v0.7.0 current) | 11.3M/month | github.com/miketheman/pytest-socket | NOT ADOPTED — surgical monkeypatch preferred over project-wide network gate per CONTEXT.md `<discretion>` |

[VERIFIED: `curl -s https://pypi.org/pypi/pytest-socket/json` returned name=pytest-socket, version=0.7.0, project URLs include Bug Tracker, Change Log, Funding, Repository pointing at github.com/miketheman/pytest-socket] [VERIFIED: pypistats.org/api/packages/pytest-socket/recent returned last_month=11284445]

## Architecture Patterns

### System Architecture Diagram (test-infrastructure scope)

```
                        ┌──────────────────────────────┐
                        │  musicstreamer/player.py     │
                        │  Player(QObject) — canonical │
                        │  Signal block lines 241–282  │
                        └──────────────┬───────────────┘
                                       │ (source of truth)
                                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  tests/_fake_player.py — shared FakePlayer(QObject)  │
        │  Mirrors EVERY Signal from Player.__dict__           │
        │  Method stubs: play/pause/stop/set_volume/eq/        │
        │  shutdown_underrun_tracker/restore_eq_from_settings  │
        └──────────────┬───────────────┬───────────────────────┘
                       │               │
        ┌──────────────▼─────┐  ┌──────▼───────────────────────┐
        │ 11 test-file       │  │ tests/                       │
        │ imports (D-09)     │  │ test_fake_player_signal_     │
        │ Single line:       │  │ parity.py (D-16)             │
        │ from tests._fake_  │  │ — walks Player.__dict__      │
        │ player import      │  │ for Signal-typed attrs       │
        │ FakePlayer         │  │ tests/                       │
        └────────────────────┘  │ test_fake_player_no_inline.py│
                                │ (D-17) — source-grep all     │
                                │ tests/ for class definitions │
                                └──────────────────────────────┘

        ┌──────────────────────────────────────────────────────┐
        │  Cluster 2: MPRIS2 DBus name collision               │
        │  tests/test_media_keys_mpris2.py fixture →           │
        │  monkeypatch musicstreamer.media_keys.mpris2.        │
        │  SERVICE_NAME = "org.mpris.MediaPlayer2.             │
        │     musicstreamer.test_{pid}_{uuid8}"                │
        │  → LinuxMprisBackend.__init__ reads it dynamically   │
        │  → teardown: bus.unregisterService(SERVICE_NAME)     │
        └──────────────────────────────────────────────────────┘
```

### Recommended Project Structure (additions only)

```
tests/
├── _fake_player.py        # NEW: shared FakePlayer(QObject)
│                          #      (D-07 — mirrors tests/conftest.py _FakeRepo/_FakeStation
│                          #       module-level class shape, lines 102-207)
├── test_fake_player_signal_parity.py   # NEW: D-16 introspection drift-guard
├── test_fake_player_no_inline.py       # NEW: D-17 source-grep drift-guard
├── conftest.py            # UNCHANGED (Phase 77 does NOT add a fake_player fixture
│                          #            per recommendation: direct-import-only
│                          #            mirrors _FakeRepo's class-level export)
└── test_*.py              # 11 sites updated to import from _fake_player
```

### Pattern 1: Source-introspection drift-guard (D-16 canonical shape)

**What:** Walk the source-of-truth class's `__dict__` for `Signal`-typed attributes; assert each appears on the test double with matching argument arity.

**When to use:** Whenever a test double mirrors a production QObject; protects against the Phase 62 → Phase 77 recurrence shape (10+ phases logged the same drift).

**Verified canonical predicate (probed live):**
```python
# Source: live probe against musicstreamer.player.Player on 2026-05-17
from PySide6.QtCore import Signal
from musicstreamer.player import Player

player_signals = {
    name for name, value in Player.__dict__.items()
    if isinstance(value, Signal)
}
# Probe returned 18 signals (excludes inherited QObject.destroyed / objectNameChanged
# because __dict__ only contains class-level attributes declared on Player itself)
```

**Why `__dict__` and not `dir(Player)`:** `dir(Player)` returned 20 Signals (added inherited `destroyed`, `objectNameChanged`). `__dict__` returned exactly the 18 Signals declared in `player.py:241-282`. Inherited signals don't need parity on the FakePlayer; only Player-specific ones do.

**Arity check (catches the `audio_caps_detected = Signal(object)` vs `Signal(int, int, int)` drift):**

PySide6's `Signal.__init__` records argument types in the C++ metaobject, not in a clean Python attribute. The most portable arity check is via `QMetaObject` (slower, requires an instance) or — simpler and adequate — comparing the *source line* `Signal(...)` declaration in both files via grep. Recommended approach: drift-guard test asserts (a) every Player signal name exists on FakePlayer, AND (b) reads both source files and asserts the `= Signal(...)` argument lists match line-for-line for each named signal. This catches the gbs/soma `Signal(object)` arity drift.

Alternative arity probe via Shiboken (fragile, version-dependent; not recommended):
```python
# Source: PySide6 6.11 — Shiboken signal metaobject inspection
# This relies on private C++ metadata; brittle. Don't use.
import shiboken6
# ... not recommended ...
```

### Pattern 2: Module-level monkeypatch for test-time constant override (D-10)

**What:** Pytest's `monkeypatch.setattr(module, "CONSTANT_NAME", new_value)` rebinds the name at the module level. Functions inside the same module that reference the constant by bare name resolve it dynamically at call time (Python name resolution looks up the module's `__dict__` on every reference, not at function-def time).

**When to use:** Test-time override of a module-level constant. Whenever the production code looks up the constant by bare name inside a function body, monkeypatch sees the override.

**Verified empirically:**
```python
# Source: live probe on 2026-05-17
import musicstreamer.media_keys.mpris2 as m
m.SERVICE_NAME = 'org.test.foo'  # simulates monkeypatch.setattr
# Subsequent calls to LinuxMprisBackend.__init__ → bus.registerService(SERVICE_NAME)
# at line 254 will see 'org.test.foo' because the function reads the name from
# the module-level binding, not a captured closure.
```

The function reference at `mpris2.py:254` is `bus.registerService(SERVICE_NAME)` — bare name lookup, monkeypatch-visible.

**Recommended fixture shape:**
```python
# Source: tests/conftest.py existing _FakeRepo pattern + new mpris helper
import os, uuid
from unittest.mock import patch
import pytest

@pytest.fixture
def unique_mpris_service_name(monkeypatch):
    """Per-test unique MPRIS2 bus name (D-10 / D-18).

    Patches musicstreamer.media_keys.mpris2.SERVICE_NAME at the module level
    so LinuxMprisBackend.__init__ reads the unique name on registerService.
    Teardown unregisters explicitly (D-11) to avoid leaking bus name binds.
    """
    suffix = f"test_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    unique = f"org.mpris.MediaPlayer2.musicstreamer.{suffix}"
    from musicstreamer.media_keys import mpris2 as _m
    monkeypatch.setattr(_m, "SERVICE_NAME", unique)
    yield unique
    # Best-effort cleanup (D-11): production shutdown() already unregisters,
    # but cover the case where the test never calls shutdown explicitly.
    try:
        from PySide6.QtDBus import QDBusConnection
        bus = QDBusConnection.sessionBus()
        if bus.isConnected():
            bus.unregisterService(unique)
    except Exception:
        pass  # bus already torn down or service already released
```

**Why `os.getpid()` in the suffix:** Aids debugging if a leaked name shows up in `qdbus`; `uuid4().hex[:8]` alone would also work, but pid gives a hook back to the test process.

### Pattern 3: Per-test `monkeypatch.setattr(urllib.request, "urlretrieve", ...)` (D-12 option a)

**What:** Replace `urllib.request.urlretrieve` with a no-op or a tmp-file-writer at the test fixture level, so a worker thread spawned during the test cannot make a real network call.

**When to use:** Whenever a test indirectly constructs a widget that owns a `_LogoFetchWorker` (or any worker that calls `urllib.request.urlretrieve`/`urlopen` on a background thread). The two `urlretrieve` call sites are at `musicstreamer/ui_qt/edit_station_dialog.py:94` (YouTube thumbnail) and `:125` (AudioAddict logo). Plus `urlopen` is in `musicstreamer/cover_art.py:111,119` (iTunes) and `musicstreamer/cover_art_mb.py:290,312` (MusicBrainz).

**Example:**
```python
# Source: tests/test_main_window_underrun.py — proposed fixture extension
@pytest.fixture
def block_real_network(monkeypatch):
    """Replace network primitives the dialog workers might call with stubs.
    Phase 77 D-12 option (a): surgical local fix, no pytest-socket dep.
    """
    def _stub_urlretrieve(url, filename=None, *a, **kw):
        if filename:
            with open(filename, "wb") as fh:
                fh.write(b"")
        return (filename or "/tmp/stub", {})

    monkeypatch.setattr("urllib.request.urlretrieve", _stub_urlretrieve)
    # urlopen used by cover_art.py and cover_art_mb.py — block those too if a
    # test ends up triggering icy_title→cover_art flow
    from unittest.mock import MagicMock
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(side_effect=OSError("blocked in test")))
```

### Anti-Patterns to Avoid

- **`dir(Player)` instead of `Player.__dict__`** in the drift-guard. `dir()` returns inherited QObject signals (`destroyed`, `objectNameChanged`) which the FakePlayer doesn't need; the test would either over-require parity (failing) or under-filter and silently break later.
- **Fixture-scoped `panel.show()` workaround for D-15** without also removing the `isVisibleTo` semantic mismatch. `show()` fixes the symptom; replacing `isVisibleTo(panel)` with `panel._stack.currentIndex() == 0` removes the offscreen-platform fragility entirely.
- **`pytest-forked` or `pytest-xdist` to "isolate" the Qt-teardown crashes.** Listed in CONTEXT.md `<deferred>` for a reason — masks the underlying worker-leak race instead of fixing it. Per D-12/D-13, fix at the leak source.
- **`session.set_plugin_option("twitch", "api-header", ...)` rewrite of production code.** The API doesn't exist in streamlink ≥6.0. Verified via direct probe.
- **Re-introducing `_aa_quality`** to satisfy the orphan test. Phase 56 deliberately removed it; D-04 locks deletion of the orphan assertions.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| QObject Signal enumeration | Custom reflection via `__dataclass_fields__` or hand-maintained list | `isinstance(v, Signal)` over `Player.__dict__.items()` | PySide6 already exposes `Signal` as the class-level descriptor type; `isinstance` works against the imported `Signal` class. Hand-maintained lists become drift sources themselves. |
| Per-test DBus session bus | Hand-rolled DBus mock or stub | `monkeypatch.setattr(mpris2, "SERVICE_NAME", unique_name)` on the real session bus | The real session bus accepts unique names, and per-test register/unregister cycles complete in microseconds. A mock would lose coverage of the actual `registerService` failure mode. |
| Network call sandbox | A new "TestNetworkProvider" abstraction | `monkeypatch.setattr(urllib.request, "urlretrieve", stub)` | `urlretrieve`/`urlopen` are the only two network primitives Phase 77 sees in test-relevant code paths. A provider abstraction is overkill for two-call-site coverage. |
| Worker-thread lifecycle | New per-test "worker pool" abstraction | Existing `worker.wait(2000)` pattern already in `edit_station_dialog.py:1342` and `_aa_live_worker.wait(16000)` at `now_playing_panel.py:1979` | Project already has the pattern; reuse it via existing methods. |

**Key insight:** every Phase 77 fix has an established same-project precedent. Phase 77 is harvesting existing patterns, not introducing new ones. The drift-guards (D-16, D-17) are the only genuinely new test files; both follow the `tests/test_yt_dlp_opts_drift.py` (Phase 79) and `tests/test_constants_drift.py` (Phase 61) source-grep convention exactly.

## Runtime State Inventory

**Skipped — not a rename/refactor/migration phase.** Phase 77 changes Python source files (tests and one production-code call site) plus adds two new test files. There are no stored data, OS-registered tasks, secrets, build artifacts, or live service configs to migrate.

## Common Pitfalls

### Pitfall 1: streamlink API drift — `set_plugin_option` was removed in streamlink 6.0

**What goes wrong:** Test asserts `session.set_plugin_option.assert_called_once_with("twitch", "api-header", ...)` against a streamlink ≥6.0 session object that has no such method. Test fails with `AttributeError: 'Streamlink' object has no attribute 'set_plugin_option'` OR `MagicMock` happily accepts the assertion because it auto-creates attributes — making the test silently pass while production behavior diverges.

**Why it happens:** The Phase 31 commit (2023-ish) authored the test against streamlink 5.x's plugin-scoped API. PR #5033 [CITED: github.com/streamlink/streamlink/pull/5033] removed `Streamlink.set_plugin_option()` and `Streamlink.get_plugin_option()` from the session class in **6.0.0 (2023-07-20)** [CITED: streamlink/changelog]. Migration path per the PR description: `session.set_option("twitch-api-header", ...)` (already what production does).

**How to avoid:** Direct API probe of the pinned dependency BEFORE writing API-signature tests. The drift-guard pattern from `tests/test_yt_dlp_opts_drift.py` (asserting on call-site presence in source) is the project's standard mitigation for this exact failure class.

**Warning signs:** Tests using `MagicMock()` for a real library API + `.assert_called_once_with()`. MagicMock returns a Mock for any attribute access, so the missing-method failure mode is invisible unless `spec=Streamlink` is used. **Recommendation for the rewritten test (cluster 6):** use `MagicMock(spec=Streamlink)` so calling `session.set_plugin_option(...)` would raise AttributeError immediately — catching any future rewrite that tries to bring back the deleted API.

[VERIFIED: live probe `uv run --no-sync python -c "from streamlink.session import Streamlink; s=Streamlink(); print(hasattr(s, 'set_plugin_option'))"` returned `False`. Method signature for `set_option` reads `def set_option(self, key: str, value: Any) -> None:` per `streamlink/session/session.py` source inspection.]

### Pitfall 2: `isVisibleTo()` returns False on widgets whose ancestor was never `show()`-n

**What goes wrong:** Test reads `panel._search_box.isVisibleTo(panel)` and expects True; gets False; assertion fails. The original test author assumed `isVisibleTo` is independent of the top-level window's show-state. It isn't.

**Why it happens:** Qt's `QWidget::isVisibleTo(QWidget *ancestor)` walks up the parent chain and returns True only if every widget between `this` and `ancestor` is visible. If `panel` was never `show()`-n, `panel.isVisible()` is False, so `panel._search_box.isVisibleTo(panel)` is False even though `_search_box` is on the active stack page.

**How to avoid:** Either (a) call `panel.show(); qtbot.waitExposed(panel)` before the assertions, OR (b) replace `isVisibleTo(panel)` with `panel._stack.currentIndex() == 0` (semantic equivalent: the search box is on page 0, so page-0-active == search-box-visible-when-shown). **Recommendation: (b)** per D-15 — smaller diff, no Qt event-loop dependency, doesn't introduce `waitExposed` flake risk under offscreen.

**Warning signs:** Tests calling `qtbot.addWidget(panel)` but not `panel.show()` and then asserting on visibility. `addWidget` registers for cleanup; `show()` makes the widget actually visible.

[VERIFIED: live probe under `QT_QPA_PLATFORM=offscreen` — `parent.show()` then `search.isVisibleTo(parent)` returned True. Test reproducer at `tests/test_station_list_panel.py:326` fails with `AssertionError: assert False` because `panel.show()` is never called.]

### Pitfall 3: `Player.__dict__` excludes inherited QObject Signals — by design

**What goes wrong:** A naïve `for name in dir(Player)` walk picks up `destroyed = Signal()` and `objectNameChanged = Signal(str)` from QObject's class hierarchy. The drift-guard would then require FakePlayer to mirror these — but they're inherited, not declared on Player.

**Why it happens:** `dir()` traverses the MRO; `__dict__` returns only attributes declared on the specific class.

**How to avoid:** Use `Player.__dict__.items()`. Verified probe count: 18 Player-specific signals via `__dict__`, 20 via `dir()` (the extra 2 are inherited).

**Warning signs:** Drift-guard fails on a brand-new FakePlayer that mirrors all 18 expected Player signals but doesn't declare `destroyed` or `objectNameChanged` (which would be wrong to mirror anyway — those come from QObject).

[VERIFIED: live probe — `Player.__dict__` returned 18 Signal-typed attrs, `dir(Player)` returned 20; the 2 extras were `destroyed` and `objectNameChanged`.]

### Pitfall 4: Signal arity drift — `Signal(object)` vs `Signal(int, int, int)`

**What goes wrong:** FakePlayer declares `audio_caps_detected = Signal(object)` (one positional arg). Production emits `self.audio_caps_detected.emit(sid, rate, depth)` (three positional args). On the FakePlayer the emit raises `TypeError: audio_caps_detected.emit() takes 1 argument but 3 were given` or — worse — silently coerces depending on PySide6 version.

**Why it happens:** Test-double author saw `audio_caps_detected = Signal(int, int, int)` and wrote `Signal(object)` as a shortcut, not realizing the arity matters.

**How to avoid:** Drift-guard test must check both signal *name* AND *signature*. Recommended check: read both `musicstreamer/player.py` and `tests/_fake_player.py` as text; extract the `= Signal(...)` declarations for every Player signal; assert the argument lists match string-for-string. This catches arity drift without needing PySide6 metaobject introspection.

**Warning signs:** Sites at `tests/test_main_window_gbs.py:34` and `tests/test_main_window_soma.py:42` both declare `audio_caps_detected = Signal(object)` — wrong arity. These are CURRENTLY undetected by Phase 77's grep audit because the signal *name* is present.

[VERIFIED: `musicstreamer/player.py:282` declares `audio_caps_detected = Signal(int, int, int)`. The two test files declare `Signal(object)`.]

### Pitfall 5: pytest-qt fixture order across files — qtbot tear-down vs daemon-thread network workers

**What goes wrong:** Test A constructs a widget that spawns `threading.Thread(daemon=True)` for cover-art fetch (`musicstreamer/cover_art.py:128`). Test A finishes; qtbot tears down its widgets. The daemon thread keeps running because Python doesn't join it. Test B starts, constructs a NEW QApplication / widgets. The orphan daemon thread completes its `urllib.request.urlopen` after Test A's QObjects are gone but maybe in Test B's QApplication scope — the thread invokes `on_done(temp_path)` which is a closure over a deleted parent's slot. Crash.

**Why it happens:** `cover_art._itunes_attempt` (cover_art.py:91-128) uses `threading.Thread(daemon=True)` not QThread. No `wait()` exists. The token-guard at `now_playing_panel.py:1445` (`if token != self._cover_fetch_token: return`) helps but ONLY if `self._cover_fetch_token` is still a valid reference — if the panel was destroyed, the closure's `self` access can crash.

**How to avoid (surgical, per CONTEXT.md `<discretion>`):** Block the network at the test boundary — `monkeypatch.setattr("urllib.request.urlopen", ...)` for any test that instantiates `NowPlayingPanel`. The daemon thread will still run but won't make a real network call, so its `on_done` callback either fires synchronously (on the worker thread, still triggering the queued-signal token guard which fails safely) or returns without invoking the callback. **This is what D-12 option (a) already prescribes** — extending its scope to cover `urlopen` in addition to `urlretrieve` closes the cross-file `test_phase72_now_playing_panel → test_phase72_assumptions` race too.

**Warning signs:** Crash stack traces landing in `QObjectPrivate::deleteChildren` after a `urllib`-related stack frame. Cross-file ordering crashes that disappear when `urllib.request.urlopen` is mocked.

### Pitfall 6: MPRIS2 register/unregister loop — leaked bus names accumulate across test runs

**What goes wrong:** Per-test unique suffix solves the collision, but if teardown skips `bus.unregisterService(SERVICE_NAME)`, the names stay registered on the session bus for the lifetime of the test process. With 7 tests × N runs × hundreds of suffixes, the session bus accumulates dead names. They're not user-visible but eat bus memory and are a slow leak in long-running CI.

**Why it happens:** Production `LinuxMprisBackend.shutdown()` (`mpris2.py:295-302`) already calls `unregisterService(SERVICE_NAME)` — so if the test calls `backend.shutdown()` before exit, no leak. But pytest fixtures don't auto-call `shutdown()`.

**How to avoid:** Fixture pattern explicitly unregisters (D-11). The example fixture in Pattern 2 above does this. **Recommendation:** if every test that uses the fixture also calls `backend.shutdown()`, the fixture-side unregister is redundant — but keeping it in the fixture is the safer default and matches the project's "test fixtures clean up after themselves" convention.

[VERIFIED: `musicstreamer/media_keys/mpris2.py:299-302` calls `bus.unregisterObject(OBJECT_PATH)` + `bus.unregisterService(SERVICE_NAME)` inside a try/except.]

## Code Examples

Verified patterns from official sources and live probes:

### Canonical FakePlayer signal list (every Signal currently declared on Player)

```python
# Source: musicstreamer/player.py lines 241-282 (probed 2026-05-17)
# Phase 77 D-07 — these 18 signals MUST be mirrored on tests/_fake_player.py
title_changed              = Signal(str)
failover                   = Signal(object)
offline                    = Signal(str)
twitch_resolved            = Signal(str)
youtube_resolved           = Signal(str)
youtube_resolution_failed  = Signal(str)
playback_error             = Signal(str)
cookies_cleared            = Signal(str)
elapsed_updated            = Signal(int)
buffer_percent             = Signal(int)
_cancel_timers_requested   = Signal()
_error_recovery_requested  = Signal()
_try_next_stream_requested = Signal()
_playbin_playing_state_reached = Signal()
_underrun_cycle_opened     = Signal()
_underrun_cycle_closed     = Signal(object)
underrun_recovery_started  = Signal()
audio_caps_detected        = Signal(int, int, int)
```

### D-16 drift-guard test (name + arity parity)

```python
# Source: tests/test_fake_player_signal_parity.py — proposed for D-16
"""Phase 77 D-16 drift-guard: FakePlayer must mirror every Signal declared on
musicstreamer.player.Player — by name AND by argument arity.

This file fails the moment a new Signal lands on Player without a parity
update in tests/_fake_player.py.
"""
import re
from pathlib import Path
from PySide6.QtCore import Signal
from musicstreamer.player import Player
from tests import _fake_player as fp_mod

ROOT = Path(__file__).resolve().parent.parent


def _signal_names(cls):
    return {name for name, value in cls.__dict__.items() if isinstance(value, Signal)}


def _grep_signal_decls(path: Path) -> dict[str, str]:
    """Extract `name = Signal(...)` declarations from source file.
    Returns {signal_name: argument_list_text}.
    """
    text = path.read_text(encoding="utf-8")
    # Match: indented or top-level `NAME = Signal(ARGS)` with optional comment
    pattern = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Signal\(([^)]*)\)', re.M)
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(text)}


def test_fake_player_mirrors_every_player_signal():
    """Every Signal on Player must be present on FakePlayer (name parity)."""
    player_sigs = _signal_names(Player)
    fake_sigs = _signal_names(fp_mod.FakePlayer)
    missing = player_sigs - fake_sigs
    assert not missing, (
        f"FakePlayer missing Player signal(s): {sorted(missing)}. "
        f"Add `<name> = Signal(...)` to tests/_fake_player.py mirroring the "
        f"declaration in musicstreamer/player.py."
    )


def test_fake_player_signal_arity_matches_player():
    """Every shared signal must have IDENTICAL argument list (catches Signal(object)
    vs Signal(int, int, int) drift — the audio_caps_detected gotcha)."""
    player_decls = _grep_signal_decls(ROOT / "musicstreamer" / "player.py")
    fake_decls = _grep_signal_decls(ROOT / "tests" / "_fake_player.py")
    mismatches = []
    for name, player_args in player_decls.items():
        if name not in fake_decls:
            continue  # name-parity test above already covers this
        if player_args != fake_decls[name]:
            mismatches.append(
                f"{name}: Player has `Signal({player_args})`, "
                f"FakePlayer has `Signal({fake_decls[name]})`"
            )
    assert not mismatches, (
        "FakePlayer signal arity drift:\n  " + "\n  ".join(mismatches)
    )
```

### D-17 drift-guard test (source-grep no-inline)

```python
# Source: tests/test_fake_player_no_inline.py — proposed for D-17
"""Phase 77 D-17 drift-guard: only tests/_fake_player.py may define a
FakePlayer subclass of QObject. Any test file that re-introduces an inline
FakePlayer class fails this guard immediately.

Mirrors the existing tests/test_yt_dlp_opts_drift.py source-grep pattern.
"""
import re
from pathlib import Path

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
    assert not offenders, (
        "Inline FakePlayer(QObject) class definitions found in tests/. "
        "Phase 77 D-17 invariant: only tests/_fake_player.py may declare this "
        "class. Each offender below should `from tests._fake_player import "
        "FakePlayer` and delete its local copy:\n  " + "\n  ".join(offenders)
    )
```

### D-10/D-11 MPRIS2 fixture (already shown in Pattern 2 above)

See **Pattern 2** for the `unique_mpris_service_name` fixture body. Wire it into each test in `tests/test_media_keys_mpris2.py`:

```python
# Source: tests/test_media_keys_mpris2.py — proposed migration shape
def test_linux_mpris_backend_constructs(qtbot, unique_mpris_service_name):
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend
    backend = LinuxMprisBackend(qapp_singleton())
    try:
        assert backend is not None
        # ... existing assertions ...
    finally:
        backend.shutdown()  # also unregisters; fixture has a belt-and-suspenders unregister
```

### D-15 fix: replace isVisibleTo with stack-page check

```python
# Source: tests/test_station_list_panel.py:326,332 — proposed rewrite
def test_filter_strip_hidden_in_favorites_mode(qtbot):
    """Search box and chip rows are on page 0; not present on page 1 (favorites)."""
    from PySide6.QtWidgets import QStackedWidget
    panel = StationListPanel(_sample_repo_with_favorites())
    qtbot.addWidget(panel)

    # In Stations mode, search box is on page 0 — semantic equivalent of
    # "search box visible". isVisibleTo() returns False on unshown ancestors,
    # so we check stack-page-active state directly (Phase 77 D-15 option b).
    assert panel._stack.currentIndex() == 0

    # Switch to Favorites
    panel._favorites_btn.click()
    assert panel._stack.currentIndex() == 1
    # Search box is on page 0, so it's not on the active page.
```

### Cluster 4 fix: delete _aa_quality orphan assertions

```python
# Source: tests/test_import_dialog_qt.py:141-154 — proposed deletion
# DELETE these two functions wholesale. Phase 56 commit 414e236 removed
# the production widget; D-04 deletes the orphan tests. If the AudioAddict
# quality dropdown is ever wanted back, file a NEW feature phase.

# (lines 141-145 — delete) test_audioaddict_tab_widgets — full function
# (lines 152-154 — delete) test_audioaddict_quality_combo — full function
```

### Cluster 5a fix: update recent-played count to 5

```python
# Source: tests/test_station_list_panel.py:504-520 — proposed change
def test_refresh_recent_updates_list(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    new_top = make_station(99, "New Top Station", "TestFM")
    repo._recent = [new_top] + repo._recent

    panel.refresh_recent()

    # Phase 77 D-06: production calls list_recently_played(5); _sample_repo's
    # backing list has >=5 entries so rowCount must equal min(5, len(_recent)).
    expected = min(5, len(repo._recent))
    assert panel.recent_view.model().rowCount() == expected
    top_station = panel.recent_view.model().index(0, 0).data(Qt.UserRole)
    assert isinstance(top_station, Station)
    assert top_station.id == 99
```

Note: prefer `min(5, len(repo._recent))` over a hardcoded `== 5` — robust if the fake repo's seed data changes.

### Cluster 6 corrected fix: rewrite test, NOT production

```python
# Source: tests/test_twitch_auth.py — proposed rewrite per CORRECTED D-05
# Phase 77 — research found streamlink.set_plugin_option() was REMOVED in
# streamlink 6.0.0 (PR #5033). Project pins streamlink>=8.3. Production at
# musicstreamer/player.py:1156 uses the correct migrated API:
#     session.set_option("twitch-api-header", [...])
# Test must follow.

def test_play_twitch_sets_option_when_token_present(qtbot, tmp_path, monkeypatch):
    """When the token file exists and has content, the worker calls
    session.set_option('twitch-api-header', [...])."""
    from streamlink.session import Streamlink  # NEW: import for spec=
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    token_file = tmp_path / "twitch-token.txt"
    token_file.write_text("abc123")

    # spec=Streamlink so calling a removed method (set_plugin_option) raises
    # AttributeError immediately — drift-guard against re-introducing the
    # deleted API.
    session = MagicMock(spec=Streamlink)
    session.streams.return_value = {"best": _FakeStream("https://ok.m3u8")}

    p = make_player(qtbot)
    with patch("streamlink.session.Streamlink", return_value=session):
        with qtbot.waitSignal(p.twitch_resolved, timeout=2000):
            p._twitch_resolve_worker("https://www.twitch.tv/testchannel")

    session.set_option.assert_called_once_with(
        "twitch-api-header", [("Authorization", "OAuth abc123")]
    )
```

Update the module docstring at lines 1-9 to match.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `session.set_plugin_option("twitch", "api-header", ...)` | `session.set_option("twitch-api-header", ...)` | streamlink 6.0.0 (2023-07-20, PR #5033) | Phase 31 docstring is 2-year-stale; test must follow impl |
| Per-test-file inline FakePlayer subclass | Single shared `tests/_fake_player.py` import | Phase 77 (this phase) | 11 files lose ~20-line stub each; one canonical source |
| Drift catch via deferred-items.md logging | Drift catch via in-process pytest assertion | Phase 77 (this phase) | Failure visible at first run, not after manual audit |

**Deprecated/outdated:**
- `Streamlink.set_plugin_option()` / `Streamlink.get_plugin_option()` — removed in streamlink 6.0. Test docstring at `tests/test_twitch_auth.py:1-9` references this API; rewrite needed.
- `_aa_quality` widget on `ImportDialog` — removed in Phase 56 commit `414e236`. Two orphan test references remain at `tests/test_import_dialog_qt.py:143,153`.
- AudioAddict quality dropdown UX — removed in Phase 56; if wanted back, requires a new feature phase per CONTEXT.md D-04.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Qt teardown crashes in `test_main_window_integration → test_now_playing_panel` and `test_phase72_now_playing_panel → test_phase72_assumptions` share the same daemon-thread urllib leak root cause | Pitfall 5; D-13 disposition | If the crashes have a different root cause, blocking the network won't help. Mitigation: planner runs the cross-file reproducer **before** declaring the fix done. The reproducer is `uv run pytest tests/test_main_window_integration.py tests/test_now_playing_panel.py -x` (and the Phase 72 pair). If those still crash after the network-block fixture lands, planner must escalate to D-13's secondary "fix at production-code layer" path. |
| A2 | `_YtScanWorker` Qt-teardown abort (Plan 65 deferred) is fixed by ensuring `qtbot.waitSignal(worker.finished, timeout=3000)` runs to completion AND adding an explicit `worker.wait(2000)` after the test body | D-14; not explicitly probed | If the worker leaks because the dialog (its parent) is destroyed BEFORE the worker finishes, the fix is in the test scope by reordering teardown OR adding an explicit `dialog._yt_scan_worker = None; worker.wait()` at test exit. Planner verifies via the reproducer chain documented in Plan 65 deferred-items.md. |
| A3 | The 11 FakePlayer sites enumerated below are complete; no additional sites have been added since 2026-05-16 | D-09; `<phase_requirements>` section | If the planner finds a 12th site during execution (e.g., added by a parallel Phase 76 plan), it must be folded into the migration list. Re-grep at plan-execute time using `grep -rn "class _\?FakePlayer\s*(QObject" tests/` is the safety net. |
| A4 | `pytest-socket` is not adopted (D-12 option b is REJECTED) | Standard Stack alternatives table | If the planner judges global network protection is worth the dep, the planner picks option (b) per CONTEXT.md `<discretion>`. Both paths are pre-approved; this assumption only locks the default recommendation. |

## Open Questions

1. **D-05 correction — does the planner accept the inversion?**
   - What we know: streamlink 6.0 (PR #5033) removed `set_plugin_option`. Project pins `streamlink>=8.3`. Production uses correct API.
   - What's unclear: CONTEXT.md D-05 LOCKED the direction as "impl follows test". This research found that lock is based on a Phase 31 docstring that references a deleted API.
   - Recommendation: Planner amends D-05 to "test follows impl" with a 2-line CONTEXT.md update citing this research. Alternatively, the user re-opens discuss-phase if they want to re-decide. The mechanics matter: if the planner ships an "impl follows test" change, production will fail at runtime as soon as a Twitch URL is played because `session.set_plugin_option(...)` raises AttributeError on the real streamlink session.

2. **Cluster 3 — Qt teardown crashes: how aggressive should the network-block fixture be?**
   - What we know: All 4 reproducers involve worker threads that call urllib. The cleanest surgical fix is per-test monkeypatch of `urllib.request.urlretrieve` and `urllib.request.urlopen`.
   - What's unclear: Should it be a session-level fixture in `conftest.py` (applies to all tests by default, requires opt-out for the integration tests), or per-file fixture (opt-in)? CONTEXT.md `<discretion>` covers this.
   - Recommendation: Per-file opt-in for Phase 77. Adopt a session-wide auto-block only after we have data on which tests legitimately need real network (none in `tests/`; the integration tests under `tests/integration/` are marked with `@pytest.mark.integration` and skipped by default per `pyproject.toml` test markers).

3. **D-14 — `_YtScanWorker` cleanup: production fix vs. test fix?**
   - What we know: `_YtScanWorker` is a QThread at `musicstreamer/ui_qt/import_dialog.py:75-101`. The dialog stores it as `self._yt_scan_worker` (line 346). Production cleanup in the dialog's lifecycle is partially in place (other workers have `_shutdown_X_worker` methods at `edit_station_dialog.py:1327,1344`).
   - What's unclear: does `ImportDialog` have an analogous `_shutdown_yt_scan_worker` method? Quick grep needed at plan time.
   - Recommendation: Planner reads `musicstreamer/ui_qt/import_dialog.py` end-to-end during Plan 77's D-14 task. If a `_shutdown_*` helper is missing, add one mirroring `edit_station_dialog.py:1327-1342` exactly. If present, the fix is test-side (`qtbot.waitSignal` + `worker.wait(2000)`).

## Environment Availability

> Required because Phase 77 depends on a live D-Bus session bus (for cluster 2 MPRIS2 tests) and a populated `streamlink` install (for cluster 6 test rewrite).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `streamlink` (Python pkg) | Cluster 6 rewrite + `spec=Streamlink` MagicMock | ✓ | 8.3.0 | — |
| `PySide6` | All Qt-touching test work | ✓ | 6.11.0 | — |
| `pytest` | Phase verification | ✓ | 9.0.3 | — |
| `pytest-qt` | `qtbot` fixture | ✓ | 4.5.0 | — |
| D-Bus session bus | Cluster 2 MPRIS2 tests | ✓ (Linux dev/CI assumed) | — | None viable for Linux; Windows test runs skip MPRIS2 entirely via existing import-guard |
| `gi` / PyGObject | Indirect — `musicstreamer.player` imports `gi` | Mixed: system Python 3.14 has it; `uv` venv with Python 3.13 does NOT | system 3.14 | If running tests under `uv`, set `include-system-site-packages = true` in `.venv/pyvenv.cfg` OR run pytest with system Python 3.14 explicitly. Planner verifies before plan execution. |

**Missing dependencies with no fallback:** None blocking.

**Missing dependencies with fallback:**
- `gi` under `uv`-managed venv: separate issue, not Phase-77-blocking. Plan execution may need to use system Python (`/usr/bin/python3 -m pytest`) rather than `uv run pytest`. Planner verifies which interpreter `uv run pytest` actually invokes during scope-lock.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-qt 4.5.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` + `tests/conftest.py` |
| Quick run command | `uv run pytest tests/<file>.py::<test_name> -x` (or `/usr/bin/python3 -m pytest tests/<file>.py::<test_name> -x` if uv-venv lacks `gi`) |
| Full suite command | `uv run pytest tests/` (no `-x`) |

### Phase Requirements → Test Map

> The planner adds `INFRA-01` (or equivalent) to `REQUIREMENTS.md` when scope-locking. Below is the requirement-level acceptance shape implied by D-02 ("`pytest tests/` exits 0 with no `xfail`/`skip` masking"):

| Req ID (planner-assigned) | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01-a | FakePlayer signal parity holds | unit | `pytest tests/test_fake_player_signal_parity.py -x` | ❌ Wave 0 |
| INFRA-01-b | No inline FakePlayer in tests/ | unit | `pytest tests/test_fake_player_no_inline.py -x` | ❌ Wave 0 |
| INFRA-01-c | 11 FakePlayer sites import shared module | derived from -b | (covered by -b above) | ✅ existing |
| INFRA-01-d | MPRIS2 7 tests pass with unique-suffix | integration | `pytest tests/test_media_keys_mpris2.py -x` | ✅ existing — needs fixture wired |
| INFRA-01-e | _aa_quality orphan assertions deleted | unit | `pytest tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets tests/test_import_dialog_qt.py::test_audioaddict_quality_combo` returns "not collected" (deleted) | ✅ existing — assertions deleted |
| INFRA-01-f | Twitch test rewritten to set_option | unit | `pytest tests/test_twitch_auth.py::test_play_twitch_sets_option_when_token_present -x` | ✅ existing — function renamed |
| INFRA-01-g | recent_view shows 5 rows (production unchanged) | unit | `pytest tests/test_station_list_panel.py::test_refresh_recent_updates_list -x` | ✅ existing |
| INFRA-01-h | filter strip hidden test uses stack index | unit | `pytest tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode -x` | ✅ existing |
| INFRA-01-i | test_main_window_underrun.py::test_first_call_shows_toast in mid-suite | integration | `pytest tests/test_main_window_integration.py tests/test_main_window_underrun.py -x` | ✅ existing — needs network-block fixture |
| INFRA-01-j | test_phase72_now_playing_panel → test_phase72_assumptions cross-file pair | integration | `pytest tests/test_phase72_now_playing_panel.py tests/test_phase72_assumptions.py -x` | ✅ existing — needs network-block fixture |
| INFRA-01-k | test_yt_scan_passes_through mid-suite | integration | `pytest tests/ -x` (must reach this test without abort) | ✅ existing |
| INFRA-01-l | full suite green | phase gate | `uv run pytest tests/` exits 0 | — |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_<file>.py -x` (just the modified file)
- **Per wave merge:** `uv run pytest tests/ -x` (full suite must reach final test or stop on regression)
- **Phase gate:** `uv run pytest tests/` exits 0 with zero xfail/skip masking the named clusters

### Wave 0 Gaps
- [ ] `tests/_fake_player.py` — new shared module, mirror Player Signals + method stubs
- [ ] `tests/test_fake_player_signal_parity.py` — covers D-16
- [ ] `tests/test_fake_player_no_inline.py` — covers D-17
- [ ] No framework install needed — pytest/pytest-qt already in `pyproject.toml` test extras

## Security Domain

> `security_enforcement` posture: applies, but the changes here are test-infrastructure-only with no new attack surface.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | partial | The Twitch token file is read at `musicstreamer/player.py:1149-1152` with `paths.twitch_token_path()` (already path-confined via `paths._root_override`). Phase 77 changes only the test scaffolding, not the read path. No new validation needed. |
| V6 Cryptography | no | The OAuth token is stored as a single line in `paths.twitch_token_path()` (Phase 31 design); Phase 77 does not touch token storage. |
| V7 Errors & Logging | partial | The MPRIS2 test fixture catches `RuntimeError` on `bus.unregisterService` failure (best-effort cleanup); this mirrors production `mpris2.py:300-302` `pass  # ignore errors at shutdown` and is consistent with the project's "shutdown is best-effort" convention. |

### Known Threat Patterns for {test infrastructure}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Test pollution via leaked DBus name | Information Disclosure / Repudiation (low — local dev bus only) | Per-test unique suffix + explicit unregister (D-10/D-11) |
| Real network call from test process | Spoofing (low) / Information Disclosure (low) | monkeypatch `urllib.request.urlretrieve` and `urllib.request.urlopen` at test boundary (D-12 option a) |
| Stale API reference reanimated by drift-guard regression | Tampering (low) | `MagicMock(spec=Streamlink)` so removed-API calls raise AttributeError instead of silently accepting (Pitfall 1) |

## Project Constraints (from CLAUDE.md)

The project's `CLAUDE.md` is intentionally minimal — a single routing rule:

- **Spike findings for MusicStreamer** (Windows packaging patterns, GStreamer+PyInstaller+conda-forge, PowerShell gotchas) → `Skill("spike-findings-musicstreamer")`

Phase 77 does NOT touch Windows packaging, GStreamer, PyInstaller, or PowerShell. The skill is not relevant to this phase's work surface; no spike-findings consultation needed.

Project-wide testing conventions (from `.planning/codebase/TESTING.md`):
- All tests under `tests/` directory
- `unittest.mock` (stdlib) for mocking
- `tests/conftest.py` for shared fixtures; underscore-prefixed (`_FakeRepo`) for non-fixture helper classes
- `QT_QPA_PLATFORM=offscreen` set in `tests/conftest.py:13` before any PySide6 import
- `uv run pytest tests/` is the canonical run command per CONTEXT.md `<canonical_refs>`
- No coverage target enforced
- Integration tests under `tests/integration/` with `@pytest.mark.integration`

## Phase Requirements

> The planner assigns the requirement ID at scope-lock; CONTEXT.md `<deferred>` notes "TBD planner adds an `INFRA-01` (or similar) row".

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 (proposed) | Clean full-suite `pytest tests/` exit 0 across the six failure clusters, with two drift-guard tests installed to prevent recurrence | Full research above — six clusters mapped to verified root causes; drift-guard shapes (D-16/D-17) probed live |

## Sources

### Primary (HIGH confidence)
- `musicstreamer/player.py:241-282` — live inspection: 18 Player-specific Signals (probed 2026-05-17)
- `musicstreamer/player.py:1140-1167` — `_twitch_resolve_worker` source; confirmed `session.set_option("twitch-api-header", ...)` call
- `musicstreamer/media_keys/mpris2.py:56,254-261,295-302` — SERVICE_NAME constant + registerService + shutdown lifecycle
- `musicstreamer/ui_qt/edit_station_dialog.py:63-131,1327-1370` — `_LogoFetchWorker` with `urllib.request.urlretrieve` at lines 94 (YouTube) and 125 (AudioAddict); `_shutdown_logo_fetch_worker` pattern
- `musicstreamer/ui_qt/import_dialog.py:75-101,346` — `_YtScanWorker` QThread class + storage
- `musicstreamer/cover_art.py:91-128` — `_itunes_attempt` using `threading.Thread(daemon=True)` (NOT QThread; explains daemon-thread leak in Pitfall 5)
- `musicstreamer/ui_qt/now_playing_panel.py:1414-1445,1979` — `_fetch_cover_art_async` + `_cover_fetch_token` guard + `_aa_live_worker.wait(16000)` precedent
- `musicstreamer/ui_qt/station_list_panel.py:485-498` — `_populate_recent` calls `self._repo.list_recently_played(5)` (D-06 production-correct site)
- `tests/conftest.py:1-225` — existing shared-double pattern at `_FakeRepo`/`_FakeStation`/`_FakeStream` (lines 102-207)
- `tests/test_yt_dlp_opts_drift.py:1-44` — Phase 79 source-grep drift-guard precedent (D-17 mirror)
- `tests/test_constants_drift.py` — Phase 61 source-grep drift-guard precedent
- Live `pytest tests/test_media_keys_mpris2.py` reproducer (6th test fails with `RuntimeError: registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error`) — confirms cluster 2 is real
- Live `pytest tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` reproducer (fails at line 326 `isVisibleTo` returns False because `panel.show()` was never called) — confirms cluster 5b root cause
- Live `pytest tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets` reproducer (`AttributeError: 'ImportDialog' object has no attribute '_aa_quality'`) — confirms cluster 4

### Secondary (MEDIUM confidence)
- streamlink/streamlink PR #5033 [CITED: https://github.com/streamlink/streamlink/pull/5033] — confirms `Streamlink.set_plugin_option()` removal + migration path
- streamlink changelog [CITED: https://streamlink.github.io/changelog.html] — confirms removal landed in streamlink 6.0.0 (2023-07-20)
- pytest-socket PyPI metadata + pypistats.org/pytest-socket — verifies the package is legitimate, well-maintained (11.3M downloads/month)
- Direct CPython probes of `streamlink.session.Streamlink`, `PySide6.QtCore.Signal`, and `Player.__dict__` — all probed live 2026-05-17 against the project's pinned dependency versions

### Tertiary (LOW confidence)
- None — every claim above is verified by live probe, file inspection, or authoritative source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dependency already pinned, versions verified live
- Architecture patterns: HIGH — every pattern has an established same-project precedent (cited)
- Pitfalls: HIGH — Pitfall 1 verified by streamlink source + changelog; Pitfall 2 verified by live `pytest` reproducer; Pitfall 3-4 verified by direct introspection; Pitfall 5 derived from cover_art.py source structure + project's existing worker-token convention
- D-05 correction: HIGH — direct API probe `hasattr(Streamlink(), 'set_plugin_option') == False` plus authoritative PR/changelog citations
- Signal arity drift discovery: HIGH — direct grep across both test files

**Research date:** 2026-05-17
**Valid until:** 2026-06-16 (30 days; stable test-infrastructure scope, no fast-moving deps)

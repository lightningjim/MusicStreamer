---
phase: 41-platform-media-keys
plan: "01"
subsystem: media-keys
tags: [pyside6, qobject, mpris2, media-keys, platform-factory, testing]

requires: []
provides:
  - "musicstreamer/media_keys/ package with abstract MediaKeysBackend(QObject) (D-02 surface)"
  - "NoOpMediaKeysBackend fallback (D-06)"
  - "create(player, repo) platform factory dispatching on sys.platform"
  - "smtc.py Windows stub raising NotImplementedError pending Phase 43.1"
affects:
  - "41-02 (LinuxMprisBackend implements against this base)"
  - "41-03 (main_window.py wiring uses create() factory)"
  - "43.1 (Windows SMTC fills smtc.py stub)"

tech-stack:
  added: []
  patterns:
    - "NotImplementedError in method bodies instead of abc.ABCMeta (PySide6/QObject metaclass constraint)"
    - "Base-class input validation wrapper (_apply_playback_state hook) so all subclasses get Literal validation for free"
    - "Lazy platform imports inside create() — mpris2/smtc never imported at module scope on wrong platform"
    - "All factory failure paths catch Exception and return NoOpMediaKeysBackend (D-06 startup-never-blocks rule)"

key-files:
  created:
    - musicstreamer/media_keys/__init__.py
    - musicstreamer/media_keys/base.py
    - musicstreamer/media_keys/smtc.py
    - tests/test_media_keys_scaffold.py
  modified: []

key-decisions:
  - "Used NotImplementedError in method bodies (not abc.ABCMeta) — PySide6 QObject metaclass conflict makes ABCMeta unusable"
  - "set_playback_state validates in base, delegates to _apply_playback_state hook — subclasses get validation free"
  - "smtc.py uses # comments for TODO-43.1 block (not a module docstring) — avoids triple-quote nesting with em-dash characters"
  - "Factory catches all Exception (not just ImportError) on Linux path — runtime D-Bus failures in LinuxMprisBackend.__init__ also degrade gracefully"

patterns-established:
  - "MediaKeysBackend pattern: QObject subclass with Signal() class vars + NotImplementedError abstract methods"
  - "Factory pattern: sys.platform dispatch + try/except fallback to NoOp, log warning on every failure path"

requirements-completed: [MEDIA-01]

duration: 3 min
completed: 2026-04-15
---

# Phase 41 Plan 01: Media Keys Scaffold Summary

**`musicstreamer/media_keys/` package scaffolded: abstract `MediaKeysBackend(QObject)` with D-02 signal+method surface, `NoOpMediaKeysBackend` fallback, `create()` platform factory, and Windows `smtc.py` stub — 9/9 pytest-qt tests passing**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-15T15:30:28Z
- **Completed:** 2026-04-15T15:33:41Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `MediaKeysBackend(QObject)` abstract class with exact D-02 signal surface (4 signals, 3 abstract methods); no `abc.ABCMeta` (metaclass conflict with QObject)
- `set_playback_state` validates `Literal["playing","paused","stopped"]` in the base; invalid values raise `ValueError` immediately, surfacing wiring bugs early
- `NoOpMediaKeysBackend` silent fallback implements all three methods as no-ops; safe to call at any time
- `create(player, repo)` platform factory: Linux lazy-imports `mpris2` (Plan 02), win32 lazy-imports `smtc` stub, any failure falls back to `NoOp` (D-06 — startup never blocks)
- `smtc.py` stub raises `NotImplementedError` with MEDIA-03/43.1 message; no `winrt` at module scope (importable on Linux)

## Task Commits

1. **RED — failing tests** - `725a484` (test)
2. **Task 1: base.py + __init__.py scaffold** - `77aa8fe` (feat)
3. **Task 2: create() factory + smtc.py stub** - `5bba04d` (feat)

## Files Created/Modified

- `musicstreamer/media_keys/__init__.py` — package entry point, re-exports, `create()` platform factory
- `musicstreamer/media_keys/base.py` — `MediaKeysBackend` abstract class + `NoOpMediaKeysBackend` fallback
- `musicstreamer/media_keys/smtc.py` — Windows stub (raises `NotImplementedError` pending Phase 43.1)
- `tests/test_media_keys_scaffold.py` — 9 pytest-qt tests covering all scaffold behaviour

## Decisions Made

- **NotImplementedError over abc.ABCMeta:** PySide6's `type(QObject)` metaclass conflicts with `ABCMeta`; method-body `NotImplementedError` is the documented PySide6 pattern.
- **Validation hook pattern:** `set_playback_state` (public, non-abstract) validates then calls `_apply_playback_state` (protected, abstract). Subclasses override only `_apply_playback_state`; base handles validation.
- **smtc.py comment block:** TODO-43.1 notes written as `#` comments rather than a module docstring to avoid triple-quote/em-dash encoding issues.
- **Broad Exception catch on Linux path:** Catches `ImportError` (Plan 02 not landed) and any runtime exception from `LinuxMprisBackend.__init__` (e.g. D-Bus failure at construction time), per D-06.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed qtbot.addWidget() calls for QObject instances**
- **Found during:** Task 1 GREEN (tests 1-3)
- **Issue:** Test file called `qtbot.addWidget(backend)` on `NoOpMediaKeysBackend`, which is a `QObject` not a `QWidget`. pytest-qt's `addWidget` enforces `isinstance(widget, QWidget)` and raises `TypeError`.
- **Fix:** Removed `qtbot.addWidget()` calls from tests 1-3 and tests 5-7. `qtbot.waitSignal` works directly on any `QObject` signal without registration.
- **Files modified:** `tests/test_media_keys_scaffold.py`
- **Verification:** Tests 1-4 pass after fix.
- **Committed in:** `77aa8fe` (part of Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed smtc.py module docstring swallowing comment block**
- **Found during:** Task 2 GREEN (test 8)
- **Issue:** Original `smtc.py` had a `"""` module docstring opening on line 1 with no closing `"""` before the `# TODO-43.1:` comment block, causing `SyntaxError: unterminated triple-quoted string literal`.
- **Fix:** Rewrote file using `#` comments for the TODO block instead of embedding them inside a docstring.
- **Files modified:** `musicstreamer/media_keys/smtc.py`
- **Verification:** `python -c "import musicstreamer.media_keys.smtc"` exits 0; test 8 passes.
- **Committed in:** `5bba04d` (part of Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both were test/file authoring bugs; no architectural changes. No scope creep.

## Issues Encountered

None — both deviations were caught immediately by the test runner and fixed inline.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `musicstreamer/media_keys/` package is importable on Linux with no Windows dependencies
- `create(None, None)` returns `NoOpMediaKeysBackend` on Linux (Plan 02 not yet landed — expected)
- Plan 41-02 (`LinuxMprisBackend`) can now implement against `MediaKeysBackend` and the factory will automatically pick it up once `mpris2.py` exists
- Full test suite: 429 passing, 1 pre-existing failure (`test_station_list_panel::test_filter_strip_hidden_in_favorites_mode` — unrelated, pre-dates this plan)

---
*Phase: 41-platform-media-keys*
*Completed: 2026-04-15*

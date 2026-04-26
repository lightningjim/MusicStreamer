---
phase: 41-platform-media-keys
plan: "02"
subsystem: media-keys
tags: [pyside6, qtdbus, mpris2, dbus, linux, media-keys, cover-art, testing]

requires:
  - phase: 41-01
    provides: "MediaKeysBackend abstract class + NoOpMediaKeysBackend + create() factory"

provides:
  - "LinuxMprisBackend(MediaKeysBackend): registers org.mpris.MediaPlayer2.musicstreamer on session bus"
  - "_MprisRootAdaptor: org.mpris.MediaPlayer2 interface (Identity, CanRaise=False, CanQuit=False, SupportedUriSchemes/MimeTypes)"
  - "_MprisPlayerAdaptor: org.mpris.MediaPlayer2.Player interface (all 14 properties + 6 slots)"
  - "_art_cache.py: cover_path_for_station() + write_cover_png() with stable per-station paths"
  - "user_cache_dir() helper in paths.py (honors _root_override for tests)"
  - "12 pytest-qt tests (11/12 non-integration passing; Test 10 skipped — playerctl not installed)"

affects:
  - "41-03 (main_window.py wiring uses LinuxMprisBackend via create() factory)"
  - "43.1 (Windows SMTC implementation reuses same ClassInfo + QDBusAbstractAdaptor patterns)"
  - "future phases touching paths.py (user_cache_dir() now available)"

tech-stack:
  added:
    - "PySide6.QtDBus (QDBusAbstractAdaptor, QDBusConnection, QDBusMessage, QDBusObjectPath)"
  patterns:
    - "PySide6 ClassInfo idiom: @ClassInfo({'D-Bus Interface': 'org.mpris...'}) from PySide6.QtCore"
    - "QDBusAbstractAdaptor subclasses parented to backend QObject; QtDBus picks them up via ExportAdaptors"
    - "PropertiesChanged emitted manually via QDBusMessage.createSignal() + bus.send()"
    - "Stable cover-art path: user_cache_dir()/mpris-art/{station_id}.png, overwrite in place"
    - "shutdown() wraps unregister in try/except for idempotency"

key-files:
  created:
    - musicstreamer/media_keys/mpris2.py
    - musicstreamer/media_keys/_art_cache.py
    - tests/test_media_keys_mpris2.py
  modified:
    - musicstreamer/paths.py
    - pyproject.toml

key-decisions:
  - "ClassInfo({'D-Bus Interface': ...}) decorator works in PySide6 6.11 — confirmed via smoke test"
  - "adaptors hold a _backend reference (not inheriting from backend) to keep D-Bus interface clean"
  - "_player_adaptor exposed as backend attribute for test-only slot invocation (Test 11)"
  - "shutdown() uses try/except around unregister — idempotent, safe at app quit"
  - "xesam:artist is a list (per MPRIS spec 'as' type) containing station name"

patterns-established:
  - "PySide6 ClassInfo pattern: @ClassInfo({'D-Bus Interface': 'org.iface.Name'}) on QDBusAbstractAdaptor subclass"
  - "D-Bus property updates: emit PropertiesChanged manually after every state mutation"

requirements-completed: [MEDIA-02, MEDIA-05]

duration: 3min
completed: 2026-04-15
---

# Phase 41 Plan 02: LinuxMprisBackend Summary

**`LinuxMprisBackend` implemented via PySide6.QtDBus with Root + Player MPRIS2 adaptors, cover-art PNG cache, and 11/12 pytest-qt tests passing — `playerctl` can target the service by name on any machine with a D-Bus session bus**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-15T15:35:47Z
- **Completed:** 2026-04-15T15:39:09Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `_art_cache.py`: `cover_path_for_station()` + `write_cover_png()` with stable per-station PNG paths under `user_cache_dir()/mpris-art/` (D-04 no-tmp-churn contract)
- `user_cache_dir()` helper added to `paths.py` mirroring the existing `_root_override` test-hook pattern
- `LinuxMprisBackend` registers `org.mpris.MediaPlayer2.musicstreamer` at `/org/mpris/MediaPlayer2`
- `_MprisRootAdaptor` and `_MprisPlayerAdaptor` expose full MPRIS2 property/slot surface (2 + 6 slots, 7 + 14 properties)
- `PropertiesChanged` emitted on every `publish_metadata` and `set_playback_state` call
- All construction failure modes raise `RuntimeError`, caught by Plan 01 factory which returns `NoOpMediaKeysBackend` (D-06)

## Resolved PySide6 ClassInfo Idiom

**For Plan 03 and Phase 43.1 reuse:**

```python
from PySide6.QtCore import ClassInfo

@ClassInfo({"D-Bus Interface": "org.mpris.MediaPlayer2"})
class _MprisRootAdaptor(QDBusAbstractAdaptor):
    ...
```

- `ClassInfo` lives in `PySide6.QtCore` (not `PySide6.QtDBus`)
- Accepts a plain Python dict `{str: str}`
- Works on `QDBusAbstractAdaptor` subclasses in PySide6 6.11
- Injects the key/value as `Q_CLASSINFO` metadata that QtDBus reads to identify the interface
- Verified via smoke test before committing: `metaObject().classInfo(i).name()` returns `"D-Bus Interface"`

## Task Commits

1. **RED — failing tests** - `248ba3c` (test)
2. **Task 1: _art_cache.py + user_cache_dir + pyproject.toml** - `aa7ca10` (feat)
3. **Task 2: mpris2.py LinuxMprisBackend** - `f57c12b` (feat)

## Files Created/Modified

- `musicstreamer/media_keys/mpris2.py` — `LinuxMprisBackend` + `_MprisRootAdaptor` + `_MprisPlayerAdaptor`
- `musicstreamer/media_keys/_art_cache.py` — `cover_path_for_station()` + `write_cover_png()`
- `musicstreamer/paths.py` — added `user_cache_dir()` helper
- `tests/test_media_keys_mpris2.py` — 12 tests (5 art-cache + 7 backend)
- `pyproject.toml` — registered `integration` pytest mark

## Decisions Made

- **ClassInfo dict syntax confirmed:** `@ClassInfo({"D-Bus Interface": "..."})` from `PySide6.QtCore` works in PySide6 6.11 — no `Q_CLASSINFO` macro workaround needed.
- **Adaptors hold `_backend` reference:** Adaptors delegate to the backend rather than inheriting from it, keeping the D-Bus interface class hierarchy clean.
- **`_player_adaptor` as attribute:** Exposed on `LinuxMprisBackend` for Test 11 slot invocation; acceptable test surface for an internal class.
- **`shutdown()` try/except:** Wraps both `unregisterObject` and `unregisterService` in a single try/except to guarantee idempotency at app quit regardless of bus state.
- **`xesam:artist` as list:** Per MPRIS2 spec the type is `as` (array of strings); contains station name as the single element.

## Deviations from Plan

None — plan executed exactly as written. The PySide6 ClassInfo idiom probed in the plan notes worked on first attempt; no fallback to QtDBusVirtualObject was needed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `LinuxMprisBackend` is constructable and fully tested; `create()` in Plan 01 factory will pick it up automatically on Linux
- Plan 41-03 can now wire `LinuxMprisBackend` into `MainWindow` (connect Player signals → `publish_metadata` / `set_playback_state`)
- Phase 43.1 can reuse the `@ClassInfo({"D-Bus Interface": ...})` + `QDBusAbstractAdaptor` pattern for Windows SMTC
- No pre-existing test regressions introduced (all gi-dependent failures are pre-existing environment issues)

## Self-Check

- `musicstreamer/media_keys/mpris2.py` — FOUND
- `musicstreamer/media_keys/_art_cache.py` — FOUND
- `tests/test_media_keys_mpris2.py` — FOUND
- commit `248ba3c` — FOUND (test RED)
- commit `aa7ca10` — FOUND (feat Task 1)
- commit `f57c12b` — FOUND (feat Task 2)

## Self-Check: PASSED

---
*Phase: 41-platform-media-keys*
*Completed: 2026-04-15*

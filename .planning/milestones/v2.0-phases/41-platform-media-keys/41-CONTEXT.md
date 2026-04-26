---
phase: 41
phase_slug: platform-media-keys
status: context_gathered
created: 2026-04-14
source: interactive_discuss_chain
scope_note: |
  Phase 41 narrowed from "Platform Media Keys (Linux + Windows)" to
  "Linux Media Keys (MPRIS2)" on 2026-04-14. Windows SMTC split out
  to Phase 43.1 (depends on Phase 43 GStreamer Windows Spike for
  confirmed Windows runtime before implementing the winrt async
  button_pressed pattern).
---

# Phase 41 Context — Linux Media Keys (MPRIS2)

## Scope (narrowed)

Implement the `musicstreamer/media_keys/` package with a platform factory and a working Linux MPRIS2 backend built on `PySide6.QtDBus` + `QDBusAbstractAdaptor`. Windows SMTC backend is a stub that raises `NotImplementedError` pending Phase 43.1.

## Requirements covered

- **MEDIA-01** — `musicstreamer/media_keys/` package + platform factory selecting Linux or Windows backend at runtime based on `sys.platform`. (Linux implemented; Windows stub.)
- **MEDIA-02** — Linux MPRIS2 adaptor via `PySide6.QtDBus` + `QDBusAbstractAdaptor`; `dbus-python` stays absent from the codebase.
- **MEDIA-04** (Linux slice) — Play/pause + stop from OS media session wire into `Player`. Next/Previous exposed as `CanGoNext = CanGoPrevious = false` (no-op, see D-03).
- **MEDIA-05** (Linux slice) — Station name + ICY track title + cover art pixmap published to MPRIS2; updates on every `title_changed`.

MEDIA-03 + Windows slice of MEDIA-04/05 deferred to Phase 43.1.

## Prior-art reference

v1.5 had a dbus-python-based MPRIS implementation at `musicstreamer/mpris.py` which was **deleted** during the GTK→Qt cutover (Phase 36-03 commit 97e61b8 "refactor(36-03): delete GTK ui/, mpris.py, test_mpris.py"). The researcher should read that deleted file via `git show 97e61b8^:musicstreamer/mpris.py` to understand the MPRIS2 interface surface the app previously exposed — NOT to copy code, but to know what `org.mpris.MediaPlayer2.*` methods + properties had been implemented before (CanControl, CanPause, PlaybackStatus, Metadata map with mpris:trackid/xesam:title/xesam:artist/mpris:artUrl, etc.).

## Decisions (locked)

- **D-01 — Package layout:** `musicstreamer/media_keys/__init__.py` exports `create(player, repo) -> MediaKeysBackend`. Abstract class lives in `musicstreamer/media_keys/base.py`. Linux impl in `musicstreamer/media_keys/mpris2.py`. Windows stub in `musicstreamer/media_keys/smtc.py` (imported only when `sys.platform == "win32"`; otherwise never touched).

- **D-02 — Abstract API:**
  ```python
  class MediaKeysBackend(QObject):
      play_pause_requested = Signal()
      stop_requested = Signal()
      next_requested = Signal()        # wired but backend may emit nothing
      previous_requested = Signal()    # wired but backend may emit nothing

      def publish_metadata(self, station: Station | None, title: str, cover_pixmap: QPixmap | None) -> None: ...
      def set_playback_state(self, state: Literal["playing", "paused", "stopped"]) -> None: ...
      def shutdown(self) -> None: ...  # unregister from OS session cleanly
  ```

- **D-03 — Next/Previous semantics:** No-op on Linux for v2.0. MPRIS2 `CanGoNext = CanGoPrevious = false` so OS overlays grey out those buttons. MusicStreamer has no playlist/queue concept; revisit when one lands.

- **D-04 — Cover art transport (Linux):** Serialize `QPixmap` → PNG written to a stable per-station path at `paths.user_cache_dir() / "mpris-art" / f"{station.id}.png"`. Publish `file://` URI as `mpris:artUrl`. Reuse same path across publishes for the same station so no tmp-file churn. Bump the PNG only when the underlying logo changes (caller tracks via station.id).

- **D-05 — Metadata update cadence:** Publish on every `Player.title_changed` emission + every `bind_station()` rebind. No debounce — emissions are rare (every 2-5 min for typical ICY) and QtDBus property updates are cheap. Simpler than throttling.

- **D-06 — Failure modes:** If `QDBusConnection.sessionBus().isConnected()` returns false at backend construction (headless, broken session, flatpak without D-Bus passthrough, etc.), log a warning via the existing logging helper and return a no-op backend (subclass with empty method bodies). App startup never blocks on this. Media keys are nice-to-have, not blocking for playback.

- **D-07 — Dependencies:** No new deps for Phase 41. QtDBus ships with PySide6 under `PySide6.QtDBus`. `winrt-Windows.Media.Playback` is deferred to Phase 43.1 (under `[project.optional-dependencies].windows`).

## Signal wiring (Player ↔ MediaKeysBackend)

- Player emits `title_changed(str)` → `MediaKeysBackend.publish_metadata(self._current_station, title, cover_pixmap)`
- Player emits state changes → `set_playback_state("playing" | "paused" | "stopped")`
- MediaKeysBackend emits `play_pause_requested` → wired to `Player.play_pause()` (or whatever the existing toggle method is)
- MediaKeysBackend emits `stop_requested` → wired to `Player.stop()`
- Next/Previous: wire signals defined on the abstract class, but MPRIS2 impl does not emit them (Next/Previous buttons are disabled in the overlay)

## Integration point

`main_window.py.__init__` constructs the backend after Player + Repo are ready:
```python
self._media_keys = media_keys.create(self._player, self._repo)
self._media_keys.play_pause_requested.connect(self._player.play_pause)
self._media_keys.stop_requested.connect(self._player.stop)
self._player.title_changed.connect(self._on_title_changed_for_media_keys)
```
`_on_title_changed_for_media_keys` bridges to `publish_metadata`.

## Files to create/modify

- `musicstreamer/media_keys/__init__.py` — factory
- `musicstreamer/media_keys/base.py` — `MediaKeysBackend` abstract class
- `musicstreamer/media_keys/mpris2.py` — Linux implementation (QtDBus + QDBusAbstractAdaptor)
- `musicstreamer/media_keys/smtc.py` — Windows stub raising `NotImplementedError` with TODO-43.1 comment
- `musicstreamer/ui_qt/main_window.py` — wire backend into Player signals
- `tests/test_media_keys.py` — unit tests for factory + abstract class + Linux backend (mocked D-Bus where possible)

## Success criteria (verification targets)

1. `musicstreamer/media_keys/` package with factory; `sys.platform` selects backend.
2. Linux: `playerctl status` returns the correct state; `playerctl metadata` shows station/title/artUrl after playback starts.
3. Pressing the keyboard media-play key pauses/resumes the stream (manual UAT).
4. `grep -r "dbus-python\|import dbus$" musicstreamer/` returns zero matches.
5. Cover art pixmap appears in the OS media-session overlay (manual UAT).
6. Headless / no-D-Bus environment: app starts normally, logs one warning, backend is no-op.

## Out of scope

- Windows SMTC (Phase 43.1)
- Next/Previous navigation (deferred until a queue concept exists)
- Multiple concurrent MPRIS2 instances (not a real use case)
- MPRIS2 `Raise` method to focus the window (possible future polish, not required)
- Volume control via MPRIS2 `Volume` property (future — connected to the SEED-001 volume slider idea)

## Deferred ideas (do not act on this phase)

- Volume slider + MPRIS2 `Volume` round-trip (future phase)
- MPRIS2 `Seek`/`Position` properties — meaningless for live streams, ignore

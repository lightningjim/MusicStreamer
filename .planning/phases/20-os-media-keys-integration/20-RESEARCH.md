# Phase 20: Playback Controls & Media Keys - Research

**Researched:** 2026-04-05
**Domain:** GTK4 button state management + MPRIS2 D-Bus service (dbus-python)
**Confidence:** HIGH

## Summary

Phase 20 has two independent sub-problems: (1) adding pause state to the player and a toggle button to the UI, and (2) wiring MPRIS2 so OS media keys drive the same state. Both are straightforward given the existing codebase patterns.

The pause implementation (Plan 20-01) is pure GTK4/Python: add a `_paused` flag to player.py, set pipeline to NULL on pause (D-04 decision), and add a `pause_btn` to `controls_box` mirroring `stop_btn`. The MPRIS2 implementation (Plan 20-02) uses `dbus-python` (already installed as a system package, version 1.4.0 confirmed), registers a service object at `/org/mpris/MediaPlayer2` under bus name `org.mpris.MediaPlayer2.MusicStreamer`, and proxies calls to `MainWindow` methods.

**Primary recommendation:** Use `dbus-python` directly (`dbus.service.Object` subclass) rather than any wrapper library. `pydbus` is not installed and adds nothing needed here. `dbus-python` + `dbus.mainloop.glib` integrates cleanly with the existing GLib main loop.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single toggle button — shows `media-playback-pause-symbolic` while playing, swaps to `media-playback-start-symbolic` while paused. Icon-only, matches stop button style (`suggested-action` CSS class).
- **D-02:** Button inserts between `star_btn` and `stop_btn` in `controls_box`.
- **D-03:** Now-playing panel stays visually identical when paused — no dimming, no "Paused" label. State is communicated solely by the button icon.
- **D-04:** Pause = set GStreamer pipeline to `NULL`. Resume = call `play()` again. No `Gst.State.PAUSED` — radio servers drop HTTP connections after a short idle period.
- **D-05:** `_current_station` is NOT cleared on pause. Only cleared on stop.
- **D-06:** A `_paused_station` (or equivalent flag) tracks the paused station so resume can call `play()` with the right station.
- **D-07:** Stop behavior unchanged — calls `player.stop()`, clears `_current_station`, hides now-playing panel. Pause state implicitly reset when stop is called.
- **D-08:** MPRIS2 org.mpris.MediaPlayer2.Player interface with: `PlayPause`, `Stop`, read-only metadata (station name as `xesam:title`, ICY track title as `xesam:artist`, artwork URL if available).
- **D-09:** `Next` and `Previous` raise `NotSupported` / do nothing.
- **D-10:** `CanGoNext`, `CanGoPrevious` = False. `CanPlay`, `CanPause`, `CanControl` = True when a station is selected.

### Claude's Discretion

- D-Bus service name (e.g., `org.mpris.MediaPlayer2.MusicStreamer`)
- Exact MPRIS2 property stubs required vs optional (Shuffle, LoopStatus, Rate — all read-only False/1.0)
- Whether to use `dbus-python`, `pydbus`, or `gi.repository.Gio` for the D-Bus binding
- How to handle MPRIS2 metadata update when ICY title changes mid-stream

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTRL-01 | Play/pause button between star and stop. Pause keeps station selected and now-playing panel visible; resume restores stream. Stop unchanged. | GTK4 button pattern confirmed from codebase; player NULL-state pause confirmed viable (D-04). |
| CTRL-02 | OS media keys control playback via MPRIS2 D-Bus on Linux. System play/pause key toggles same behavior as CTRL-01. | dbus-python 1.4.0 confirmed installed; session bus accessible; `org.mpris.MediaPlayer2.MusicStreamer` bus name claimable. |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dbus-python | 1.4.0 (system) | D-Bus service registration and method dispatch | System package, already installed, integrates with GLib mainloop |
| gi.repository.Gtk / Adw | system GTK4 | Pause button widget | Already used throughout project |
| gi.repository.Gst | system GStreamer | Pipeline NULL state for pause | Already used in player.py |

[VERIFIED: dbus-python 1.4.0 — `python3 -c "import dbus; print(dbus.__version__)"`]
[VERIFIED: session bus accessible — dbus.mainloop.glib + dbus.SessionBus() confirmed working]
[VERIFIED: `org.mpris.MediaPlayer2.MusicStreamer` bus name claimable — tested with dbus.service.BusName]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dbus.mainloop.glib | (bundled with dbus-python) | Integrates D-Bus event loop with GLib | Required once at startup before SessionBus() |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dbus-python | pydbus | pydbus not installed; dbus-python is system package and sufficient |
| dbus-python | gi.repository.Gio D-Bus API | More verbose XML introspection setup; no benefit for this scope |

**Installation:** No new packages needed. `dbus-python` is available as a system package.

---

## Architecture Patterns

### Recommended Project Structure

```
musicstreamer/
├── player.py           # Add pause/resume state (_paused, _paused_station)
├── mpris.py            # NEW: MprisService class (dbus.service.Object)
└── ui/
    └── main_window.py  # Add pause_btn, _toggle_pause(), wire MPRIS callbacks
```

### Pattern 1: Player Pause State (NULL + resume)

**What:** `player.pause()` sets pipeline to NULL and stores `_paused_station`. `player.resume(on_title)` calls `play(_paused_station, on_title)`. `player.stop()` clears both.

**When to use:** Per D-04 — Gst.State.PAUSED is unreliable for HTTP radio streams.

```python
# Source: codebase player.py + CONTEXT.md D-04/D-05/D-06
def pause(self):
    self._paused_station = self._current_station  # caller's responsibility per D-06
    self._on_title = None
    self._stop_yt_proc()
    self._pipeline.set_state(Gst.State.NULL)

# Note: _current_station lives in main_window.py, not player.py
# player.py needs only a _paused flag or the window tracks pause state
```

**Implementation note:** `_current_station` is tracked in `main_window.py` (line 256, 681, 664). The simplest approach is to keep pause state in `main_window.py` as `_paused: bool` and `_paused_station: Station | None`, and have `player.py` expose only `pause()` (set to NULL) alongside existing `play()` and `stop()`.

### Pattern 2: Pause Button in controls_box

**What:** A `Gtk.Button` inserted between `star_btn` and `stop_btn` in `controls_box`. Icon and sensitivity toggle on state change.

**When to use:** Follows exact `stop_btn` pattern.

```python
# Source: main_window.py lines 115-120 (stop_btn pattern)
self.pause_btn = Gtk.Button()
self.pause_btn.set_icon_name("media-playback-pause-symbolic")
self.pause_btn.add_css_class("suggested-action")
self.pause_btn.set_sensitive(False)
self.pause_btn.set_tooltip_text("Pause")
self.pause_btn.connect("clicked", lambda *_: self._toggle_pause())
# Insert into controls_box before stop_btn:
controls_box.append(self.pause_btn)   # must come after star_btn, before stop_btn
```

**controls_box insertion order:** `star_btn` → `pause_btn` → `stop_btn`. Current code appends `star_btn` then `stop_btn`. `pause_btn` must be appended between them (or `controls_box` must be built with the correct order from the start).

### Pattern 3: dbus-python MPRIS2 Service Object

**What:** Subclass `dbus.service.Object` to implement both `org.mpris.MediaPlayer2` (root) and `org.mpris.MediaPlayer2.Player` interfaces at `/org/mpris/MediaPlayer2`.

**When to use:** Per D-08. Called once at app startup after `dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)`.

```python
# Source: [CITED: dbus.freedesktop.org/doc/dbus-python/dbus.service.html]
import dbus
import dbus.service
import dbus.mainloop.glib

MPRIS_IFACE = "org.mpris.MediaPlayer2"
MPRIS_PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
MPRIS_OBJECT_PATH = "/org/mpris/MediaPlayer2"
BUS_NAME = "org.mpris.MediaPlayer2.MusicStreamer"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

class MprisService(dbus.service.Object):
    def __init__(self, window):
        self._window = window
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        self._bus_name = dbus.service.BusName(BUS_NAME, bus)
        super().__init__(bus, MPRIS_OBJECT_PATH)

    # --- org.mpris.MediaPlayer2 (root) ---
    @dbus.service.method(MPRIS_IFACE, in_signature="", out_signature="")
    def Raise(self):
        self._window.present()

    @dbus.service.method(MPRIS_IFACE, in_signature="", out_signature="")
    def Quit(self):
        pass  # CanQuit = False; no-op

    # --- org.mpris.MediaPlayer2.Player ---
    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def PlayPause(self):
        GLib.idle_add(self._window._toggle_pause)

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Stop(self):
        GLib.idle_add(self._window._stop)

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Next(self):
        pass  # CanGoNext = False

    @dbus.service.method(MPRIS_PLAYER_IFACE, in_signature="", out_signature="")
    def Previous(self):
        pass  # CanGoPrevious = False

    # --- Properties ---
    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self._get_all(interface).get(prop, dbus.String(""))

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self._get_all(interface)

    @dbus.service.signal(PROPS_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass  # signal emission only

    def emit_properties_changed(self, props: dict):
        self.PropertiesChanged(MPRIS_PLAYER_IFACE, props, dbus.Array([], signature="s"))
```

### Pattern 4: PropertiesChanged on ICY Title Update

**What:** When ICY title changes, the existing `on_title` callback in `main_window.py` is called via `GLib.idle_add`. MPRIS2 must emit `PropertiesChanged` for the `Metadata` property at the same point.

**When to use:** Per D-08 (read-only metadata). Wire into `_on_icy_title()` or equivalent in `main_window.py`.

```python
# In main_window.py, where on_title callback is received:
def _on_icy_title(self, title: str):
    # ... existing title label update ...
    if self.mpris:
        self.mpris.emit_properties_changed({
            "Metadata": dbus.Dictionary({
                "mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/CurrentTrack"),
                "xesam:title": dbus.String(self._current_station.name if self._current_station else ""),
                "xesam:artist": dbus.Array([dbus.String(title)], signature="s"),
            }, signature="sv"),
            "PlaybackStatus": dbus.String(self._playback_status()),
        })
```

### Pattern 5: PlaybackStatus Value

**What:** MPRIS2 `PlaybackStatus` must be one of `"Playing"`, `"Paused"`, or `"Stopped"`. For this app: `"Playing"` when stream active, `"Paused"` when `_paused=True`, `"Stopped"` otherwise.

```python
def _playback_status(self) -> str:
    if self._paused:
        return "Paused"
    elif self._current_station:
        return "Playing"
    return "Stopped"
```

### Anti-Patterns to Avoid

- **Gst.State.PAUSED for HTTP radio:** HTTP servers drop idle connections; PAUSED will silently hang or error. Use NULL (D-04).
- **Sharing state via player.py for `_paused_station`:** `_current_station` already lives in `main_window.py`. Keep pause state there too — player.py only needs `pause()` to set pipeline NULL.
- **Blocking D-Bus callbacks on GTK thread:** MPRIS method calls arrive on D-Bus thread. Use `GLib.idle_add()` to dispatch to GTK main thread.
- **Skipping `dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)` call:** Must be called before any `dbus.SessionBus()` call. Calling it after breaks the mainloop integration silently.
- **Omitting `mpris:trackid` from Metadata dict:** The MPRIS2 spec requires `mpris:trackid` (D-Bus type `o`) when a track is active. Use a fixed path like `/org/mpris/MediaPlayer2/CurrentTrack`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| D-Bus service registration | Custom socket/IPC | dbus.service.BusName + dbus.service.Object | Handles name claiming, introspection, signal dispatch |
| PropertiesChanged signal | Custom polling | dbus.service.signal decorator emission | Standard DBUS signal with correct interface |
| GTK/D-Bus mainloop integration | Custom thread | dbus.mainloop.glib.DBusGMainLoop | Merges D-Bus event dispatch into the GLib main loop already used by GTK4 |

---

## Common Pitfalls

### Pitfall 1: DBusGMainLoop Called Too Late

**What goes wrong:** D-Bus method calls appear to work but signals (PropertiesChanged) are never delivered; media key integration is unreliable.
**Why it happens:** `dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)` must be the first dbus call — before any `SessionBus()` instantiation. Calling it after `SessionBus()` silently uses a different mainloop.
**How to avoid:** Call `DBusGMainLoop(set_as_default=True)` at module import time in `mpris.py`, before the class is instantiated.
**Warning signs:** Signals not received by `playerctl`; `playerctl status` returns stale values.

### Pitfall 2: D-Bus Callbacks on GTK Thread

**What goes wrong:** Crash or freeze when MPRIS2 `PlayPause` is called from a media key — the method runs on the D-Bus dispatch thread and modifies GTK widgets.
**Why it happens:** GTK4 is not thread-safe. D-Bus method handlers run outside the GTK main thread.
**How to avoid:** Wrap all `self._window.*` calls in `GLib.idle_add()` inside every `@dbus.service.method` handler.
**Warning signs:** Intermittent crashes or assertion failures when using media keys.

### Pitfall 3: Missing `mpris:trackid` in Metadata

**What goes wrong:** `playerctl` and GNOME shell media overlay show no metadata or crash.
**Why it happens:** MPRIS2 spec requires `mpris:trackid` key of D-Bus type `o` (ObjectPath) in the Metadata dict when a track is active.
**How to avoid:** Always include `"mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/CurrentTrack")`.
**Warning signs:** `playerctl metadata` returns empty; GNOME media overlay shows nothing.

### Pitfall 4: controls_box Button Insertion Order

**What goes wrong:** `pause_btn` appears after `stop_btn` instead of between `star_btn` and `stop_btn`.
**Why it happens:** `controls_box.append()` adds at the end. `stop_btn` is currently the last appended widget.
**How to avoid:** Build `controls_box` in order: `star_btn` → `pause_btn` → `stop_btn`. Since GTK4's `Gtk.Box` uses `append`/`prepend`/`insert_child_after`, insert `pause_btn` via `controls_box.insert_child_after(pause_btn, star_btn)` after `star_btn` is appended, before `stop_btn`.
**Warning signs:** Visual button order is wrong; stops at test.

### Pitfall 5: MPRIS2 Service Startup Failure is Silent

**What goes wrong:** D-Bus not available (rare in desktop sessions) causes unhandled exception at startup.
**Why it happens:** `dbus.exceptions.DBusException` if session bus is unavailable.
**How to avoid:** Wrap MPRIS instantiation in try/except; log warning and set `self.mpris = None`; app continues without MPRIS support.
**Warning signs:** App fails to start in minimal environments (headless, SSH).

---

## Code Examples

### Minimal working dbus.service.Object registration

```python
# Source: [VERIFIED: dbus.service.BusName claimed as org.mpris.MediaPlayer2.MusicStreamer in test]
import dbus
import dbus.service
import dbus.mainloop.glib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
bus_name = dbus.service.BusName("org.mpris.MediaPlayer2.MusicStreamer", bus)
```

### MPRIS2 root interface required property stubs

```python
# Source: [CITED: specifications.freedesktop.org/mpris/latest/Media_Player.html]
# All required read-only properties for org.mpris.MediaPlayer2:
def _get_all_root(self):
    return {
        "CanQuit": dbus.Boolean(False),
        "CanRaise": dbus.Boolean(True),
        "HasTrackList": dbus.Boolean(False),
        "Identity": dbus.String("MusicStreamer"),
        "DesktopEntry": dbus.String("org.example.MusicStreamer"),
        "SupportedUriSchemes": dbus.Array(["http", "https"], signature="s"),
        "SupportedMimeTypes": dbus.Array(["audio/mpeg", "audio/ogg", "audio/aac"], signature="s"),
    }
```

### MPRIS2 Player interface property stubs

```python
# Source: [CITED: specifications.freedesktop.org/mpris/latest/Player_Interface.html]
def _get_all_player(self):
    st = self._window._current_station
    paused = getattr(self._window, "_paused", False)
    return {
        "PlaybackStatus": dbus.String(self._window._playback_status()),
        "LoopStatus": dbus.String("None"),
        "Rate": dbus.Double(1.0),
        "Shuffle": dbus.Boolean(False),
        "Metadata": self._build_metadata(),
        "Volume": dbus.Double(1.0),
        "Position": dbus.Int64(0),
        "MinimumRate": dbus.Double(1.0),
        "MaximumRate": dbus.Double(1.0),
        "CanGoNext": dbus.Boolean(False),
        "CanGoPrevious": dbus.Boolean(False),
        "CanPlay": dbus.Boolean(st is not None),
        "CanPause": dbus.Boolean(st is not None),
        "CanSeek": dbus.Boolean(False),
        "CanControl": dbus.Boolean(True),
    }

def _build_metadata(self):
    st = self._window._current_station
    icy = getattr(self._window, "_last_cover_icy", None) or ""
    if st:
        return dbus.Dictionary({
            "mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/CurrentTrack"),
            "xesam:title": dbus.String(st.name),
            "xesam:artist": dbus.Array([dbus.String(icy)], signature="s"),
        }, signature="sv")
    return dbus.Dictionary({"mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/NoTrack")}, signature="sv")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MPRIS1 | MPRIS2 (v2.2) | ~2011 | GNOME/KDE/playerctl all use MPRIS2; MPRIS1 is dead |
| pydbus (popular 2016–2020) | dbus-python still standard for server-side | Ongoing | pydbus better for client; dbus-python better for service implementation |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DesktopEntry` value `"org.example.MusicStreamer"` matches installed desktop file basename | Code Examples | GNOME media overlay may not find app icon; cosmetic only |
| A2 | GNOME Shell on this system picks up MPRIS2 PlayPause via `mpris-proxy` (already running, confirmed in busctl output) | Environment Availability | Media keys may not work without mpris-proxy or direct GNOME integration |

---

## Open Questions

1. **YouTube station pause behavior**
   - What we know: `player.py` uses `mpv` subprocess for YouTube; setting pipeline to NULL doesn't affect `mpv`.
   - What's unclear: Should `pause()` also terminate `_yt_proc`? If so, resume is identical to play — acceptable since radio streams aren't seekable anyway.
   - Recommendation: Yes, pause for YouTube = stop yt_proc (same as current `stop()` minus clearing `_current_station`). The resume path is always `play()` regardless of stream type.

2. **MPRIS2 `Play` method (not `PlayPause`)**
   - What we know: MPRIS2 requires a `Play` method distinct from `PlayPause`.
   - What's unclear: If paused, `Play` should resume. If stopped, `Play` should do nothing (no station context).
   - Recommendation: `Play` = same as `PlayPause` when paused; no-op when stopped or already playing.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| dbus-python | MPRIS2 D-Bus service | ✓ | 1.4.0 | Wrap in try/except; app runs without MPRIS |
| dbus session bus | MPRIS2 | ✓ | — | Same fallback |
| mpris-proxy | Media key relay to MPRIS2 | ✓ | running (PID 7844) | GNOME Shell may handle natively; mpris-proxy confirmed present |
| GTK4 / libadwaita | Pause button UI | ✓ | system | — |
| GStreamer playbin3 | NULL-state pause | ✓ | system | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (auto-discovery) |
| Quick run command | `python3 -m pytest tests/ -x -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTRL-01 | `player.pause()` sets pipeline NULL without clearing `_on_title` | unit | `pytest tests/test_player_pause.py -x` | ❌ Wave 0 |
| CTRL-01 | `player.stop()` after pause clears state completely | unit | `pytest tests/test_player_pause.py::test_stop_from_paused -x` | ❌ Wave 0 |
| CTRL-02 | `MprisService` claims bus name on session D-Bus | unit (mock bus) | `pytest tests/test_mpris.py::test_bus_name -x` | ❌ Wave 0 |
| CTRL-02 | `MprisService.PlayPause()` invokes window `_toggle_pause` via idle_add | unit (mock) | `pytest tests/test_mpris.py::test_playpause_dispatches -x` | ❌ Wave 0 |
| CTRL-02 | `MprisService.Stop()` invokes window `_stop` via idle_add | unit (mock) | `pytest tests/test_mpris.py::test_stop_dispatches -x` | ❌ Wave 0 |
| CTRL-02 | `GetAll` returns correct `PlaybackStatus` for playing/paused/stopped | unit (mock) | `pytest tests/test_mpris.py::test_getall_playback_status -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/ -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

**Current baseline:** 169 tests, all passing. [VERIFIED]

### Wave 0 Gaps
- [ ] `tests/test_player_pause.py` — covers CTRL-01 player pause/resume/stop state
- [ ] `tests/test_mpris.py` — covers CTRL-02 service registration, method dispatch, property values

Test pattern to follow: `tests/test_player_volume.py` — uses `MagicMock` for GStreamer pipeline, patches `Gst.ElementFactory.make`. MPRIS tests should mock `dbus.SessionBus` and `dbus.service.BusName`.

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a — local D-Bus session bus, no auth needed |
| V3 Session Management | no | n/a |
| V4 Access Control | no | Session D-Bus is user-scoped; no cross-user exposure |
| V5 Input Validation | yes (minimal) | ICY title strings passed to D-Bus as `dbus.String` — type-safe by construction |
| V6 Cryptography | no | n/a |

**Threat note:** MPRIS2 on the session D-Bus is user-local. Any process running as the same user can call `PlayPause`/`Stop`. This is standard MPRIS2 behavior and not a concern for a desktop audio player. [ASSUMED]

---

## Sources

### Primary (HIGH confidence)
- Codebase — `musicstreamer/player.py`, `musicstreamer/ui/main_window.py` — verified player state management, controls_box structure, `_current_station` location
- [VERIFIED: dbus-python 1.4.0 installed, session bus accessible, BusName claimable] — live environment probes
- [CITED: specifications.freedesktop.org/mpris/latest/Player_Interface.html] — MPRIS2 Player interface properties and methods
- [CITED: specifications.freedesktop.org/mpris/latest/Media_Player.html] — MPRIS2 root interface properties
- [CITED: dbus.freedesktop.org/doc/dbus-python/dbus.service.html] — dbus.service.Object, BusName, method/signal decorators

### Secondary (MEDIUM confidence)
- [CITED: specifications.freedesktop.org/mpris/latest/] — bus name format, object path requirement, interface names
- busctl output — confirmed `mpris-proxy` running on this system (PID 7844)

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — dbus-python confirmed installed and working
- Architecture: HIGH — patterns derived directly from existing codebase and verified dbus-python docs
- Pitfalls: HIGH — GLib.idle_add threading pitfall is well-known; others derived from spec reading

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable libraries; MPRIS2 spec is frozen at v2.2)

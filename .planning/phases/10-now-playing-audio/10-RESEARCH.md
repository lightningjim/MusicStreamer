# Phase 10: Now Playing & Audio - Research

**Researched:** 2026-03-22
**Domain:** GTK4/Libadwaita widget composition, GStreamer volume API, mpv CLI, SQLite settings persistence
**Confidence:** HIGH

## Summary

This phase makes two independent changes to `main_window.py` and `player.py`. Both are straightforward wiring tasks against well-understood APIs already used in the project.

The provider display (NP-01) requires reformatting `station_name_label` in `_play_station()` and `_stop()`. The existing label and visibility logic are already in place — only the text content changes.

The volume slider (AUDIO-01, AUDIO-02) requires a `Gtk.Scale` widget added to the center column of the now-playing panel, a `set_volume()` method on `Player`, and load/save calls to the existing `repo.get_setting()` / `repo.set_setting()` infrastructure. The mpv path requires passing `--volume` as a CLI arg and does not support live adjustment without IPC setup (store and apply on next launch is the correct approach).

**Primary recommendation:** Implement in two tasks — (1) provider label, (2) volume slider — since they touch different parts of the codebase and can be reviewed independently.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Show provider inline in the same label as the station name: "Station Name · Provider"
- **D-02:** Only show provider suffix when a station is playing and has a provider assigned (no empty · suffix)
- **D-03:** Volume slider lives inline near the play/stop button (not in the header bar, not in a separate panel)
- **D-04:** Volume persists between sessions via `repo.get_setting()` / `repo.set_setting()`

### Claude's Discretion
- Volume range (0–100% recommended, maps to GStreamer 0.0–1.0)
- Default volume on first launch
- Whether to include a mute button or just slide to zero
- YouTube (mpv) volume handling approach

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NP-01 | Now Playing panel shows the provider name alongside the station name | `station_name_label` already exists and is updated in `_play_station()` / `_stop()`; only text format changes |
| AUDIO-01 | Volume slider in main window controls playback volume | `Gtk.Scale` widget; `Player.set_volume()` calling `_pipeline.set_property("volume", float)`; mpv `--volume` arg |
| AUDIO-02 | Volume setting persists between sessions | `repo.get_setting("volume", "80")` on init; `repo.set_setting("volume", str(val))` in `value-changed` handler |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 / gi.repository.Gtk | 4.x (system) | `Gtk.Scale` volume slider widget | Already used throughout |
| GStreamer playbin3 | 1.x (system) | `set_property("volume", float)` | Already used in `player.py` |
| mpv | system | YouTube audio playback subprocess | Already used in `_play_youtube()` |
| SQLite settings table | existing | `repo.get_setting` / `repo.set_setting` | Already used for `recently_played_count` |

No new dependencies. All APIs are already imported and initialized.

**Installation:** None required.

---

## Architecture Patterns

### Recommended Project Structure

No new files needed. All changes land in:
```
musicstreamer/
├── player.py           # add set_volume(float)
└── ui/
    └── main_window.py  # provider label format + volume slider widget + handlers
```

### Pattern 1: Provider Label Format

**What:** On `_play_station()`, format `station_name_label` text as `"{name} · {provider}"` when provider is non-empty, or just `"{name}"` when provider is None/empty. On `_stop()`, hide the label (existing behavior, no change needed).

**When to use:** Every call to `_play_station()`.

**Example:**
```python
# In _play_station(self, st: Station):
if st.provider_name:
    self.station_name_label.set_text(f"{st.name} \u00b7 {st.provider_name}")
else:
    self.station_name_label.set_text(st.name)
self.station_name_label.set_visible(True)
```

The middle dot is U+00B7 (`\u00b7`), surrounded by single spaces. ICY `_on_title` updates only `title_label` — `station_name_label` is set once on play and cleared on stop.

### Pattern 2: Gtk.Scale Volume Slider

**What:** `Gtk.Scale` with horizontal orientation, range 0–100, placed below `stop_btn` in the center column.

**When to use:** Constructed once in `__init__`, initialized from settings, value-changed signal drives both player and persistence.

**Example:**
```python
# Construction in __init__:
self.volume_slider = Gtk.Scale.new_with_range(
    Gtk.Orientation.HORIZONTAL, 0, 100, 1
)
self.volume_slider.set_digits(0)
self.volume_slider.set_draw_value(False)
self.volume_slider.set_increments(1, 10)
self.volume_slider.set_size_request(120, -1)
self.volume_slider.set_hexpand(True)
initial_vol = int(self.repo.get_setting("volume", "80"))
self.volume_slider.set_value(initial_vol)
self.volume_slider.connect("value-changed", self._on_volume_changed)
center.append(self.volume_slider)

# Handler:
def _on_volume_changed(self, slider):
    val = int(slider.get_value())
    self.player.set_volume(val / 100.0)
    self.repo.set_setting("volume", str(val))
```

### Pattern 3: Player.set_volume()

**What:** Public method on `Player` that clamps and applies volume to the GStreamer pipeline. Called on init and on every slider change.

**Example:**
```python
# In Player:
def set_volume(self, value: float):
    clamped = max(0.0, min(1.0, value))
    self._pipeline.set_property("volume", clamped)
```

GStreamer `playbin3` accepts volume changes at any pipeline state (NULL, READY, PLAYING) — no state guard required.

### Pattern 4: mpv Volume (YouTube)

**What:** Pass `--volume={int_val}` to the mpv subprocess. If the slider changes while mpv is running, there is no live IPC path (IPC socket requires socket setup). The correct approach: store current volume in `Player` and apply on the next mpv launch. Live mpv volume changes are not required by any requirement.

**Example:**
```python
# In Player.__init__:
self._volume = 1.0  # default; set via set_volume() before play

def set_volume(self, value: float):
    clamped = max(0.0, min(1.0, value))
    self._volume = clamped
    self._pipeline.set_property("volume", clamped)

def _play_youtube(self, url, fallback_name, on_title):
    self._stop_yt_proc()
    self._pipeline.set_state(Gst.State.NULL)
    mpv_vol = int(self._volume * 100)
    self._yt_proc = subprocess.Popen(
        ["mpv", "--no-video", "--really-quiet", f"--volume={mpv_vol}", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    on_title(fallback_name)
```

### Pattern 5: Apply Initial Volume After Player Construction

**What:** In `__init__`, after both `self.player` and the slider are created, apply the loaded volume to the player immediately so the first stream starts at the correct volume.

**Example:**
```python
# In __init__ after player and slider are constructed:
self.player.set_volume(initial_vol / 100.0)
```

### Anti-Patterns to Avoid

- **Debouncing `value-changed`:** Volume set is a local GStreamer property write — no debounce needed. Adding a timer adds latency with no benefit.
- **Setting `set_draw_value(True)`:** The inline numeric label would widen the panel and conflict with the compact 160px height constraint.
- **mpv IPC socket:** Adding a socket and protocol for live volume adjustments is out of scope and significantly more complex than the `--volume` arg approach.
- **Modifying `station_name_label` in `_on_title`:** ICY title updates must only touch `title_label`. Updating `station_name_label` from the ICY callback would overwrite the provider suffix.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Volume slider widget | Custom slider drawing | `Gtk.Scale` | GTK standard; accessibility, keyboard, theming all built in |
| Volume persistence | Custom config file | `repo.get_setting` / `repo.set_setting` | Already implemented and tested; adds zero new infrastructure |
| mpv live volume | IPC socket protocol | Store value, apply on next launch | Requirements don't need live adjustment; IPC is high complexity |

---

## Common Pitfalls

### Pitfall 1: Panel Height Expansion

**What goes wrong:** Adding a `Gtk.Scale` to the center column pushes the now-playing panel height past 160px.

**Why it happens:** `Gtk.Scale` has a natural minimum height. If the center column grows, the panel expands vertically.

**How to avoid:** Set `set_draw_value(False)` (removes the value label above the slider). Keep `panel.set_size_request(-1, 160)`. Do not add margins that accumulate beyond the budget.

**Warning signs:** Panel appears taller than the logo/cover art (160px) during manual testing.

### Pitfall 2: ICY Update Overwriting Provider Label

**What goes wrong:** If `_on_title` is extended to also update `station_name_label`, the provider suffix disappears when the first ICY tag arrives.

**Why it happens:** ICY tag fires after play starts and would clobber the label set in `_play_station()`.

**How to avoid:** `_on_title` only ever updates `title_label`. `station_name_label` is set once in `_play_station()` and cleared in `_stop()`.

### Pitfall 3: Volume Applied Before Player Constructed

**What goes wrong:** Calling `player.set_volume()` before `Player.__init__` completes — `_pipeline` would not exist yet.

**Why it happens:** Ordering error in `__init__`.

**How to avoid:** Apply initial volume only after both `self.player = Player()` and the slider are constructed. The sequence is: construct player → construct slider → set slider value → call `player.set_volume(initial / 100.0)`.

### Pitfall 4: GStreamer Volume Range

**What goes wrong:** Passing a value > 1.0 to `set_property("volume", ...)` — GStreamer `playbin3` treats volume as 0.0–1.0 for normal range; values > 1.0 amplify (can distort).

**Why it happens:** Forgetting to divide by 100 when mapping from the 0–100 slider scale.

**How to avoid:** Always divide by 100.0 and clamp to `[0.0, 1.0]` in `Player.set_volume()`.

### Pitfall 5: Empty Provider Suffix

**What goes wrong:** `station_name_label` shows "Station Name · " (with trailing dot and space) when provider is None.

**Why it happens:** Using string concatenation unconditionally.

**How to avoid:** Guard with `if st.provider_name:` before appending the suffix (D-02 locked decision).

---

## Code Examples

### NP-01: _play_station provider label
```python
# Source: 10-CONTEXT.md D-01, D-02
if st.provider_name:
    self.station_name_label.set_text(f"{st.name} \u00b7 {st.provider_name}")
else:
    self.station_name_label.set_text(st.name)
self.station_name_label.set_visible(True)
```

### AUDIO-01: Gtk.Scale construction
```python
# Source: 10-UI-SPEC.md Widget Inventory + Interaction Contract
self.volume_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
self.volume_slider.set_digits(0)
self.volume_slider.set_draw_value(False)
self.volume_slider.set_increments(1, 10)
self.volume_slider.set_size_request(120, -1)
self.volume_slider.set_hexpand(True)
```

### AUDIO-02: Load/save volume
```python
# Source: 10-UI-SPEC.md Interaction Contract
# On init:
initial_vol = int(self.repo.get_setting("volume", "80"))
self.volume_slider.set_value(initial_vol)
self.player.set_volume(initial_vol / 100.0)

# Handler:
def _on_volume_changed(self, slider):
    val = int(slider.get_value())
    self.player.set_volume(val / 100.0)
    self.repo.set_setting("volume", str(val))
```

### Player.set_volume
```python
# Source: GStreamer playbin3 docs; 10-UI-SPEC.md GStreamer Volume section
def set_volume(self, value: float):
    clamped = max(0.0, min(1.0, value))
    self._volume = clamped
    self._pipeline.set_property("volume", clamped)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No volume control | `Gtk.Scale` + GStreamer volume property | Phase 10 | User can control volume persistently |
| Station name only in now-playing | "Name · Provider" inline | Phase 10 | Provider visible without opening editor |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml or pytest.ini (check project root) |
| Quick run command | `pytest tests/test_repo.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NP-01 | Provider appended to station_name_label when provider_name non-empty | unit (label text logic is pure string formatting) | manual-only — GTK widget requires display | N/A |
| NP-01 | No provider suffix when provider_name is empty/None | unit (same) | manual-only | N/A |
| AUDIO-01 | `Player.set_volume()` clamps and sets GStreamer property | unit | `pytest tests/test_player_volume.py -x -q` | ❌ Wave 0 |
| AUDIO-02 | Volume persists via `repo.get_setting` / `repo.set_setting` | unit | `pytest tests/test_repo.py::test_settings_round_trip -x -q` | ✅ (existing) |
| AUDIO-02 | Default volume "80" returned when key absent | unit | `pytest tests/test_repo.py::test_settings_default -x -q` | ✅ (existing) |

**NP-01 note:** Label text formatting is a one-liner string operation. The GTK widget update itself is not unit-testable without a display. The existing pattern in this project is to test such logic manually. No new test file needed for NP-01.

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_player_volume.py` — covers AUDIO-01 (`Player.set_volume` clamp + property set)

Test sketch:
```python
# tests/test_player_volume.py
from unittest.mock import MagicMock, patch

def test_set_volume_clamps_high():
    with patch("gi.repository.Gst"):
        from musicstreamer.player import Player
        p = Player()
        p._pipeline = MagicMock()
        p.set_volume(1.5)
        p._pipeline.set_property.assert_called_with("volume", 1.0)

def test_set_volume_clamps_low():
    with patch("gi.repository.Gst"):
        from musicstreamer.player import Player
        p = Player()
        p._pipeline = MagicMock()
        p.set_volume(-0.5)
        p._pipeline.set_property.assert_called_with("volume", 0.0)

def test_set_volume_normal():
    with patch("gi.repository.Gst"):
        from musicstreamer.player import Player
        p = Player()
        p._pipeline = MagicMock()
        p.set_volume(0.8)
        p._pipeline.set_property.assert_called_with("volume", 0.8)
```

---

## Open Questions

1. **Panel height with slider added**
   - What we know: Panel is `set_size_request(-1, 160)`. `Gtk.Scale` with `set_draw_value(False)` has a natural height of ~20–24px on typical GNOME themes.
   - What's unclear: Whether the 4-item center column (title, station_name_label, stop_btn, slider) fits within 160px without the panel expanding.
   - Recommendation: Verify visually during implementation. If the panel expands, reduce `stop_btn` or slider margin. The constraint is a size_request (minimum), not a maximum — the panel can grow if child natural sizes exceed it.

2. **mpv volume on slider-while-playing scenario**
   - What we know: `--volume` is only read at mpv launch. Live volume change while a YouTube station plays will not affect current mpv subprocess.
   - What's unclear: Whether this is an acceptable UX limitation.
   - Recommendation: The UI-SPEC already documents this as the accepted approach. Apply to next launch. No action needed unless user reports it.

---

## Sources

### Primary (HIGH confidence)
- Source code: `musicstreamer/player.py` — GStreamer `playbin3` pipeline, `set_property("volume", ...)` confirmed available
- Source code: `musicstreamer/ui/main_window.py` — `station_name_label`, `title_label`, `stop_btn`, center column layout confirmed
- Source code: `musicstreamer/repo.py` — `get_setting` / `set_setting` confirmed working
- `.planning/phases/10-now-playing-audio/10-CONTEXT.md` — locked decisions D-01 through D-04
- `.planning/phases/10-now-playing-audio/10-UI-SPEC.md` — widget choices, interaction contract, layout contract
- `tests/test_repo.py` — settings round-trip tests confirm persistence infrastructure is tested

### Secondary (MEDIUM confidence)
- GStreamer playbin3 volume property: 0.0–1.0 range, writable at any state — established from prior phases; not re-verified via external docs this session
- mpv `--volume` flag: standard mpv CLI, well-known; not re-verified against current mpv manpage

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all APIs already in use in the codebase
- Architecture: HIGH — follows existing patterns (settings, label updates, player methods)
- Pitfalls: HIGH — identified from direct code reading

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (stable domain — GTK4/GStreamer APIs)

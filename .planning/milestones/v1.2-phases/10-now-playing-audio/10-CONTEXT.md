# Phase 10: Now Playing & Audio - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Add provider name to the now-playing display and a persistent volume slider. No new playback capabilities — just provider display and volume control.

</domain>

<decisions>
## Implementation Decisions

### Provider display
- **D-01:** Show provider inline in the same label as the station name: "Station Name · Provider"
- **D-02:** Only show provider suffix when a station is playing and has a provider assigned (no empty · suffix)

### Volume slider placement
- **D-03:** Volume slider lives inline near the play/stop button (not in the header bar, not in a separate panel)
- **D-04:** Volume persists between sessions via `repo.get_setting()` / `repo.set_setting()`

### Claude's Discretion
- Volume range (0–100% recommended, maps to GStreamer 0.0–1.0)
- Default volume on first launch
- Whether to include a mute button or just slide to zero
- YouTube (mpv) volume handling approach

</decisions>

<specifics>
## Specific Ideas

No specific references — standard inline volume control pattern.

</specifics>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above.

### Key files for implementors
- `musicstreamer/player.py` — GStreamer `playbin3` pipeline; `volume` property is float 0.0–1.0; mpv subprocess used for YouTube
- `musicstreamer/ui/main_window.py` — `title_label` (line 72) is the now-playing label to update; play/stop buttons for volume slider placement
- `musicstreamer/repo.py` — `get_setting(key, default)` / `set_setting(key, value)` for volume persistence

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `repo.get_setting` / `repo.set_setting`: already used for `recently_played_count` — same pattern for volume
- `Player._pipeline`: `playbin3` supports `.set_property("volume", 0.0–1.0)` directly

### Established Patterns
- `title_label` updated on play/stop/ICY tag — extend same pattern to include provider suffix
- `_current_station` holds the active `Station` object which has `provider_name`

### Integration Points
- `_on_play()` / `_on_stop()` in `main_window.py` — update `title_label` format here
- `Player` class — add `set_volume(float)` method
- Volume slider widget added near play/stop buttons in the toolbar/content area

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-now-playing-audio*
*Context gathered: 2026-03-22*

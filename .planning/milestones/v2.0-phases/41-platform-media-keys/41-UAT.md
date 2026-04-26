---
status: complete
phase: 41-platform-media-keys
source: [41-01-SUMMARY.md, 41-02-SUMMARY.md, 41-03-SUMMARY.md]
started: 2026-04-16T02:18:18Z
updated: 2026-04-16T02:18:18Z
---

## Current Test

## Current Test

[testing complete]

## Tests

### 1. Service Registration
expected: Run the app (`uv run python -m musicstreamer`), then run `playerctl --list-all`. Output should include `musicstreamer`.
result: pass

### 2. Status + Metadata (no playback)
expected: With app running but no station playing, run `playerctl -p musicstreamer status` and `playerctl -p musicstreamer metadata`. Status should be `Stopped`. Metadata shows NoTrack trackid or is empty.
result: issue
reported: "When I haven't started anything yet, yes. When I've stopped a stream with the stop button, it does show metadata"
severity: minor

### 3. Playback Metadata
expected: Click a station with ICY support (e.g. SomaFM) and wait 5-10s for ICY title. Then run `playerctl -p musicstreamer status` and `playerctl -p musicstreamer metadata`. Status should be `Playing`, `xesam:title` = ICY title, `xesam:artist` = station name, `mpris:artUrl` starts with `file://`. Also verify `ls ~/.cache/musicstreamer/mpris-art/<station_id>.png` exists.
result: pass

### 4. playerctl Control
expected: With a station playing, run `playerctl -p musicstreamer play-pause` (stream pauses), then again (stream resumes), then `playerctl -p musicstreamer stop` (stream stops). Each command should produce the expected state change.
result: pass
note: play-pause after stop also restarts the stream (standard MPRIS behavior)

### 5. Keyboard Media Keys
expected: With a station playing, press the hardware play/pause media key. Stream should toggle pause/resume.
result: pass

### 6. GNOME Overlay
expected: Open the system status menu. A media overlay should appear showing MusicStreamer with the station name, ICY title, and cover art.
result: pass
note: GNOME moved media overlay to notification window (not status menu) — visible and controllable from there

### 7. ICY Update Propagation
expected: Let the stream run until the next ICY title update (2-5 min). Run `playerctl -p musicstreamer metadata`. The `xesam:title` field should reflect the new ICY title.
result: pass

### 8. Clean Shutdown
expected: Close the app. Run `playerctl --list-all`. The output should NOT include `musicstreamer` — the service should have unregistered cleanly.
result: pass

### 9. No-D-Bus Fallback
expected: Run `DBUS_SESSION_BUS_ADDRESS=/dev/null uv run python -m musicstreamer`. App should start normally, logging one warning like `Media keys disabled...`. The rest of the app should function normally without crashing.
result: issue
reported: "App runs but no 'Media keys disabled' warning visible. GStreamer crash seen but confirmed pre-existing/unrelated."
severity: minor

## Summary

total: 9
passed: 7
issues: 2
skipped: 0
blocked: 0
pending: 0

## Gaps

- truth: "After stopping a stream, playerctl metadata should be cleared (NoTrack or empty)"
  status: diagnosed
  reason: "User reported: metadata still shows when stream stopped via stop button"
  severity: minor
  test: 2
  root_cause: "_on_panel_stopped and _on_media_key_stop call set_playback_state('stopped') but never call publish_metadata(None, '', None) to clear _station. _build_metadata_dict returns NoTrack only when _station is None."
  artifacts:
    - path: "musicstreamer/ui_qt/main_window.py"
      issue: "_on_panel_stopped and _on_media_key_stop missing publish_metadata(None, '', None) call"
  missing:
    - "Call publish_metadata(None, '', None) in _on_panel_stopped, _on_media_key_stop, _on_failover, and _on_offline before/after set_playback_state('stopped')"

- truth: "No-D-Bus fallback should log a 'Media keys disabled' warning on startup"
  status: diagnosed
  reason: "App runs correctly without D-Bus but no warning is logged"
  severity: minor
  test: 9
  root_cause: "The warning is emitted via _log.warning() in media_keys/__init__.py create() on the Linux MPRIS fallback path, but Python's logging module has no handler configured to output to the terminal — so it's silently swallowed."
  artifacts:
    - path: "musicstreamer/media_keys/__init__.py"
      issue: "Warning logged via _log.warning() but no stdout/stderr logging handler configured for the module"
  missing:
    - "Configure a basicConfig or StreamHandler in __main__.py so module-level warnings reach the terminal, or use print() for the specific media keys warning"

---
status: diagnosed
phase: 82-twitch-only-station-still-tries-to-play-youtube-stream-first
source: [82-VERIFICATION.md]
started: 2026-05-22T13:50:00Z
updated: 2026-05-22T14:05:00Z
---

## Current Test

[diagnosed — see Gaps]

## Tests

### 1. Real-world Lofi Girl repro
expected: Pick Twitch stream in dropdown, pause player, resume — Twitch plays (not YT). Restart app, re-pick Lofi Girl — Twitch still selected and plays.
why_human: Requires live YT-resolution-failure path + Twitch stream; cannot be exercised with mocked GStreamer pipeline.
result: partial
issue: "Playback honors preferred_stream_id correctly (Twitch plays after restart) — but the stream-picker combo box visually shows YouTube as selected instead of Twitch. Audio is correct; UI is desynced."

### 2. Dropdown survives station re-click
expected: After picking Twitch on Lofi Girl, click a different station then click Lofi Girl again — Twitch plays, not YT.
why_human: Visual confirmation that all `_on_station_activated` entry points (D-03) honor the sticky pick; requires a live DB state with a real `preferred_stream_id` persisted.
result: pass
note: "User confirmed 'otherwise everything else works as intended' — playback half of test 2 implicit-passes since test 1 already confirmed Twitch is what plays."

## Summary

total: 2
passed: 1
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

### GAP-01: Stream-picker combo box doesn't sync currentIndex to station.preferred_stream_id on bind_station

**Severity:** minor (UI visual desync; functional behavior correct)
**Surface:** `musicstreamer/ui_qt/now_playing_panel.py::_populate_stream_picker`

**Root cause:**
`_sync_stream_picker` is wired only to `player.failover` (main_window.py:455). When the preferred stream succeeds first try (no failover), `_sync_stream_picker` never fires. `_populate_stream_picker` populates the combo and leaves `currentIndex` at its default (0 = whichever stream `order_streams` ranks first — YouTube on Lofi Girl). Player picks Twitch at queue head (Plan 82-02), playback is correct, but the UI dropdown still shows YouTube.

**Missing symmetry:** Plan 82-02 added preferred-stream-id precedence to `Player.play()` queue build. The UI counterpart — preferred-stream-id precedence to the combo's initial `currentIndex` — was not specified by CONTEXT.md D-NN and not caught by VERIFICATION (no must_have covered this).

**Fix sketch (~6 lines in `_populate_stream_picker`, after the addItem loop, still inside the `blockSignals(True)` window):**
```python
preferred_id = getattr(station, "preferred_stream_id", None)
if preferred_id is not None:
    for i in range(self.stream_combo.count()):
        if self.stream_combo.itemData(i) == preferred_id:
            self.stream_combo.setCurrentIndex(i)
            break
```

Plus 1 unit test in `tests/test_stream_picker.py` covering: bind_station with `preferred_stream_id` set → combo's `currentIndex` resolves to that stream, NOT index 0; bind_station with `preferred_stream_id = None` → combo defaults to 0 (existing behavior).

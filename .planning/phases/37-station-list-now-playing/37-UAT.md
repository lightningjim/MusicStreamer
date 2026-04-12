---
status: diagnosed
phase: 37-station-list-now-playing
source: [37-01-SUMMARY.md, 37-02-SUMMARY.md, 37-03-SUMMARY.md, 37-04-SUMMARY.md]
started: 2026-04-12T19:00:00Z
updated: 2026-04-12T19:20:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Station Tree Display
expected: Left panel shows stations grouped by provider with bold headings, station icons, all groups expanded. Provider rows not selectable.
result: pass

### 2. Recently Played Section
expected: Above the station tree, a "Recently Played" section shows up to 3 recently played stations with icons. Clicking one activates that station.
result: pass

### 3. Station Activation
expected: Click a station in the tree. A "Connecting..." toast appears briefly at the bottom center. The now-playing panel on the right shows the station name and provider. Audio begins playing.
result: issue
reported: "Almost, I see Connecting on the middle right as its own panel that disappears after it connects"
severity: minor

### 4. Now Playing Panel Layout
expected: Right panel has three columns: 180x180 station logo on the left, center area with station name/provider + ICY title + elapsed time + controls, and a 160x160 cover art slot on the right.
result: pass

### 5. Play/Pause/Stop Controls
expected: Play/Pause button toggles between play and pause icons. Clicking pause stops audio and shows the play icon. Clicking play resumes. Stop button stops playback entirely.
result: issue
reported: "Yes, though right now the apparently functionality differences between the two are indistinguishable. Stop does not clear the now playing."
severity: minor

### 6. Volume Slider
expected: Volume slider is present in the control row. Dragging it changes audio volume in real-time. The volume setting persists across app restarts.
result: pass

### 7. ICY Metadata Display
expected: While a station plays, the ICY title label updates with the current track info (artist - title). Text is plain (no HTML rendering).
result: pass

### 8. Toast Overlay
expected: Toasts appear at the bottom center of the window, fade in/out smoothly, and are click-through. Toast repositions if window is resized.
result: issue
reported: "Toast appears as a separate widget in the middle right, not as a bottom-center overlay. Same behavior for Connecting and Stream exhausted toasts."
severity: minor

### 9. Error Handling
expected: If a stream fails, a toast shows error info. The app does NOT crash. Playing state is cleared.
result: pass

### 10. Splitter Resize
expected: The divider between station list and now-playing panel can be dragged to resize both panels. Station list has minimum width ~280px, now-playing has minimum ~560px.
result: issue
reported: "I can extend the stations list to the point it seems to remove the now playing panel and I can't get it back without a restart."
severity: major

## Summary

total: 10
passed: 6
issues: 4
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Toast renders as floating overlay at bottom center with fade animation"
  status: failed
  reason: "User reported: toast appears as a separate widget in the middle right, not as a bottom-center overlay"
  severity: minor
  test: 3, 8
  root_cause: "ToastOverlay is parented to QSplitter, which lays it out as a third child widget. windowOpacity only works on top-level windows, so fade animation is also broken. Toast needs to either (a) be reparented to the QMainWindow with raise_() and manual repositioning, or (b) use QGraphicsOpacityEffect for child-widget opacity."
  artifacts:
    - path: "musicstreamer/ui_qt/toast.py"
      issue: "windowOpacity animation does nothing on child widgets"
    - path: "musicstreamer/ui_qt/main_window.py:83"
      issue: "ToastOverlay(self._splitter) — splitter treats it as a laid-out child"
  missing:
    - "Reparent toast to MainWindow (not splitter) and use QGraphicsOpacityEffect instead of windowOpacity"
    - "Ensure toast raise_() keeps it above splitter children"

- truth: "Stop button clears the now-playing panel state (distinct from pause)"
  status: failed
  reason: "User reported: pause and stop are indistinguishable, stop does not clear now playing"
  severity: minor
  test: 5
  root_cause: "Player.stop() and Player.pause() are identical (both set pipeline to NULL, clear queue). NowPlayingPanel._on_stop_clicked calls player.stop() but does not clear labels/cover art. No MainWindow handler distinguishes stop from pause."
  artifacts:
    - path: "musicstreamer/ui_qt/now_playing_panel.py"
      issue: "_on_stop_clicked calls player.stop() but does not reset panel state"
  missing:
    - "NowPlayingPanel._on_stop_clicked should call on_playing_state_changed(False) and clear ICY label, elapsed, and cover art"

- truth: "Splitter enforces minimum widths so neither panel can be collapsed"
  status: failed
  reason: "User reported: can extend station list to remove now-playing panel entirely, cannot recover without restart"
  severity: major
  test: 10
  root_cause: "QSplitter.setChildrenCollapsible defaults to True. Even with minimumWidth set on children, QSplitter allows collapsing past the minimum to zero."
  artifacts:
    - path: "musicstreamer/ui_qt/main_window.py:63"
      issue: "QSplitter missing setChildrenCollapsible(False)"
  missing:
    - "Add self._splitter.setChildrenCollapsible(False) after splitter construction"

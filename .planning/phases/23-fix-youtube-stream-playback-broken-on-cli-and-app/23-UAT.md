---
status: complete
phase: 23-fix-youtube-stream-playback-broken-on-cli-and-app
source: [23-01-SUMMARY.md, inline fix 8c828bd, inline fix 44fbd23]
started: 2026-04-07T13:00:00Z
updated: 2026-04-07T13:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. YouTube playback from desktop shortcut
expected: Launch from GNOME desktop shortcut. Play a YouTube station. Audio plays (not just UI state change — actual sound).
result: pass

### 2. Original cookies.txt preserved after playback
expected: Before playing, note mtime of ~/.local/share/musicstreamer/cookies.txt. Play a YouTube station for 10+ seconds, then stop. Check mtime again — it should be unchanged.
result: pass

### 3. Temp cookie files cleaned up after stop
expected: Play a YouTube station, then stop. Run `ls /tmp/ms_cookies_*` — should return "No such file or directory" (no leftover temp files).
result: pass (after fix 44fbd23)

### 4. YouTube playback from terminal
expected: Launch MusicStreamer from terminal. Play a YouTube station. Audio plays normally (baseline check).
result: pass

### 5. Non-YouTube station unaffected
expected: Play a non-YouTube station (regular radio stream). Audio plays normally, no regressions.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Temp cookie files are cleaned up after playback stops"
  status: resolved
  reason: "Fixed in 44fbd23 — stale cleanup on init + _stop_yt_proc always resets state"
  severity: major
  test: 3

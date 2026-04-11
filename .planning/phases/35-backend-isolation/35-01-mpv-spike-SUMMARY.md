---
phase: 35-backend-isolation
plan: 01
subsystem: backend
tags: [spike, dependencies, gstreamer, yt-dlp, mpv]
requires: []
provides:
  - "Phase 35 runtime + test deps installed (PySide6, yt-dlp, streamlink, platformdirs, pytest-qt)"
  - "Binding decision for Plan 35-04: KEEP_MPV"
  - "Reproducible spike harness for future re-evaluation"
affects:
  - pyproject.toml
  - .planning/phases/35-backend-isolation/35-SPIKE-MPV.md
  - .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py
tech-stack:
  added:
    - "PySide6 6.11.0"
    - "yt-dlp 2026.03.17"
    - "streamlink 8.3.0"
    - "platformdirs 4.9.6"
    - "pytest-qt 4.5.0"
  patterns:
    - "yt_dlp.YoutubeDL.extract_info worker thread (never block GLib main loop)"
    - "GLib.MainLoop bus watch with message::error / message::tag / message::state-changed"
key-files:
  created:
    - .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py
    - .planning/phases/35-backend-isolation/35-SPIKE-MPV.md
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - "KEEP_MPV: cookie-protected YouTube path fails through yt-dlp library API; mpv subprocess fallback retained for _play_youtube()"
metrics:
  duration_min: 12
  tasks: 2
  files_changed: 4
  completed: 2026-04-11
requirements: [PORT-09]
---

# Phase 35 Plan 01: mpv-Drop Spike Summary

**One-liner:** Installed Phase 35 deps and ran the playbin3-vs-mpv spike; cookie-protected YouTube path fails through the yt-dlp library API, locking the KEEP_MPV branch for Plan 35-04.

## What Shipped

1. **Phase 35 dependency stack installed** via `uv sync --extra test`. PySide6 6.11.0, yt-dlp 2026.03.17, streamlink 8.3.0, platformdirs 4.9.6, pytest-qt 4.5.0 all importable. PyGObject system packages (`python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `gir1.2-gst-1.0`) intentionally untouched — GTK and GStreamer gi bindings remain alive through Phase 35 per D-10.
2. **Spike harness** (`spike/spike_mpv_drop.py`) — standalone Python script with no `musicstreamer/` imports. Resolves URLs via `yt_dlp.YoutubeDL.extract_info` on a worker thread (never blocks the main thread per RESEARCH pitfall), then constructs a `playbin3` pipeline with fakesink audio/video, attaches `message::error`, `message::tag`, and `message::state-changed` handlers to a `GLib.MainLoop`, and decides PASS/FAIL based on whether `Gst.State.PLAYING` or a tag message arrives within 15 seconds.
3. **Decision record** (`35-SPIKE-MPV.md`) — case results table, environment versions, binding `**Decision:** KEEP_MPV` line, and explicit consequences for Plan 35-04.

## Spike Results

| Case | Result |
|------|--------|
| a — YouTube live (no cookies) | PASS (5.3s) |
| b — HLS manifest (mux test stream) | PASS (1.4s) |
| c — YouTube live + cookies.txt | **FAIL** — yt-dlp `No video formats found` |
| d — YouTube live + format selector | PASS (3.8s) |

Spike was run twice with identical results for reproducibility.

## Decision: KEEP_MPV

**Rationale:** Three of four cases pass cleanly through `playbin3` after yt-dlp library resolution. However, attaching `cookiefile` to `yt_dlp.YoutubeDL` causes the same LoFi Girl live URL that passes case (a) to return `DownloadError: No video formats found` — confirming the A8 risk from 35-RESEARCH.md (cookie-jar injection is the most fragile yt-dlp surface). Per D-22, any failing case mandates retention of the mpv fallback so authenticated/age-gated streams keep working for real users.

## Branch That Plan 35-04 Will Take

- **`_play_youtube()` retained** as a subprocess launcher around mpv. Internal timers (cookie-retry one-shot, YouTube poll loop) still convert from `GLib.timeout_add` to `QTimer.singleShot` / `QTimer` per D-08 — only the subprocess itself stays.
- **`musicstreamer/_popen.py`** introduced as a minimal Popen wrapper this phase (PKG-03 pre-stage) so the future Windows port (Phase 44) only needs to add `CREATE_NO_WINDOW` in one place. This was conditionally scoped in D-19 and is now confirmed required.
- **`PKG-05` stays active** in REQUIREMENTS.md — do not retire. The cookie-protected case is the documented retention reason.
- **`yt_import.py`** still ports to the library API (D-17) — playlist scanning is unaffected by the cookie regression.
- **`_play_twitch()`** still ports to `streamlink.Streamlink().streams()` (D-18) — independent of this spike.

## Deviations from Plan

None — plan executed exactly as written. Spike completed end-to-end with real network and real cookies; no environmental fallbacks needed.

## Authentication Gates

None.

## Followups Tracked

- **mpv re-evaluation trigger:** If a future yt-dlp release fixes cookies-injection regression for YouTube live, re-run `spike_mpv_drop.py`. If case (c) flips to PASS, mpv can be dropped as a separate cleanup plan.
- **Plan 35-04** must explicitly reference this SUMMARY when scoping the `_play_youtube()` retention and `_popen.py` creation.

## Verification

- `python -c "import PySide6.QtCore, yt_dlp, streamlink, platformdirs, pytestqt"` exits 0
- `grep -E '^\s*"?(PySide6|yt-dlp|streamlink|platformdirs|pytest-qt)' pyproject.toml` matches all five
- `test -f .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py` exits 0
- `grep -q "yt_dlp.YoutubeDL" spike/spike_mpv_drop.py` matches
- `grep -q "playbin3" spike/spike_mpv_drop.py` matches
- `grep -q "GLib.MainLoop" spike/spike_mpv_drop.py` matches
- `grep -qE "\*\*Decision:\*\* (DROP_MPV|KEEP_MPV)" 35-SPIKE-MPV.md` matches
- `grep -c "PASS\|FAIL\|SKIPPED" 35-SPIKE-MPV.md` returns 5 (≥4 required)

## Commits

- `20b0788` feat(35-01): install Phase 35 deps (PySide6, yt-dlp, streamlink, platformdirs, pytest-qt)
- `605c94e` feat(35-01): mpv-drop spike — KEEP_MPV decision

## Self-Check: PASSED

All listed files exist on disk; both commit hashes resolve in `git log`.

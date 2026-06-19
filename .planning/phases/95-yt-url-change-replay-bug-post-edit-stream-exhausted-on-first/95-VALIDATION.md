---
phase: 95
slug: yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-18
---

# Phase 95 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini / pyproject.toml (existing) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_player.py tests/test_player_failover.py tests/test_edit_station_dialog.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | quick ~30–60s; full suite >600s (scope tightly — see [[run-tests-with-venv-python]]) |

**Note:** Use `.venv/bin/python`, NOT system `python3` (lacks `PySide6.QtWidgets` → false failures).

---

## Sampling Rate

- **After every task commit:** Run the quick run command (player + edit-dialog subset).
- **After every plan wave:** Run the relevant test files; reserve the full suite for the final wave (it is slow).
- **Before `/gsd:verify-work`:** Targeted player/edit-dialog tests must be green; spot-check full suite.
- **Max feedback latency:** ~60 seconds for the scoped subset.

---

## Per-Task Verification Map

*Filled by the planner once tasks are defined. Each task maps to one or more of the validation behaviors V1–V10 from 95-RESEARCH.md "Validation Architecture".*

| Task ID | Plan | Wave | Behaviors | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-----------|------------|-----------------|-----------|-------------------|-------------|--------|
| 95-01-01 (RED) | 01 | 1 | V1-V7,V10 (RED) | — | N/A | unit+integration | `.venv/bin/python -m pytest tests/test_player_edit_invalidation.py -x -q` | ⬜ created in task | ⬜ pending |
| 95-01-02 (GREEN) | 01 | 1 | V1-V6,V10 + V9 (parity) | T-95-02 | seq-guard no-ops stale YT resolution (CPython-atomic int, queued Signal) | unit | `.venv/bin/python -m pytest tests/test_player_edit_invalidation.py tests/test_fake_player_signal_parity.py -x -q` | ✅ | ⬜ pending |
| 95-01-03 (wire) | 01 | 1 | V7 + V8 (regression) | T-95-01 | restart reuses existing play()→_set_uri path; no new input surface | integration | `.venv/bin/python -m pytest tests/test_main_window_integration.py -k "sync or edit or invalidate" -x -q` | ✅ | ⬜ pending |

---

## Wave 0 Requirements

- [ ] Extend `tests/test_edit_station_dialog.py` and/or `tests/test_player.py` with cases for: first-play-after-edit uses the new URL; metadata-only edit does NOT restart; non-playing edit; same-URL no-op; in-flight-resolution race (per 95-RESEARCH.md V1–V10).
- [ ] If `youtube_resolved` signal arity changes (seq guard), update `tests/_fake_player.py` to preserve signal parity (`tests/test_fake_player_signal_parity.py`, D-16).

*Otherwise: existing infrastructure (test_player_failover.py, test_player.py, test_edit_station_dialog.py, test_main_window_integration.py) covers most phase behaviors.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Edit a live YouTube station's URL → hear the new stream on first play, no "stream exhausted" toast | (acceptance) | End-to-end depends on real yt-dlp resolution + GStreamer audio | Play a YouTube station, edit its URL to a different valid YouTube source, save; confirm new audio starts immediately with no error toast and no second play needed. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (scoped subset)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

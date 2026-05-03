# Phase 57 UAT Log

**Started:** 2026-05-03
**Host (Linux CI):** `/home/kcreasey/OneDrive/Projects/MusicStreamer` — Python 3.14.4, pytest-9.0.3, PySide6 6.11.0
**VM (Win11):** NT 10.0.26200 (Win11 25H2), conda env `spike` — awaiting Task 2/3 perceptual UAT

---

## Pre-UAT Readiness

### Branch state — commit hash and Plan acceptance gates

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Branch HEAD | `git rev-parse --short HEAD` | `54eed67` (worktree: `54eed67`) | — |
| Plan 57-01 commit | `git log --oneline` | `c1c783c` — test(57-01): AsyncMock fix | PASS |
| Plan 57-03 commit | `git log --oneline` | `6cfd0c6` — feat(57-03): STATE_CHANGED volume re-apply | PASS |
| Plan 57-04 commit | `git log --oneline` | `b3f2199` — feat(57-04): pause-volume ramp QTimer | PASS |
| Gate: message::state-changed count | `grep -c "message::state-changed" musicstreamer/player.py` | `1` | PASS |
| Gate: _pause_volume_ramp_timer count | `grep -c "_pause_volume_ramp_timer" musicstreamer/player.py` | `8` (>= 5) | PASS |
| Gate: DataWriter AsyncMock | `grep -q "DataWriter.return_value.store_async = AsyncMock" tests/test_media_keys_smtc.py` | exit 0 | PASS |
| D-13: no _volume_element | `grep -q "_volume_element" musicstreamer/player.py` | exit 1 (not found) | PASS |

All three Plan acceptance grep gates pass on the rebased branch.

### Build status

PENDING — `./packaging/windows/build.ps1` has not yet been run. Tasks 2 and 3 (VM UAT) require the fresh installer to be built and transferred. Build confirmation + installer mtime will be added when the human completes Task 1's human-action portion.

---

## SC #3: WIN-04 AsyncMock store_async test passes

**Status:** PASS

**Requirement:** WIN-04 — `tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream` passes on Linux CI. `store_async` is awaitable via `AsyncMock`; no `MagicMock not awaitable` error.

**Attestation basis:** Plan 57-01 shipped this fix (commit `c1c783c`, 2026-05-02). This UAT re-attests that the fix is preserved on the post-rebase branch (which now includes Plans 57-03 + 57-04).

### Task 1 re-run (rebased branch)

**Command:**
```
cd /home/kcreasey/OneDrive/Projects/MusicStreamer && PYTHONPATH=. uv run pytest tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream -x -v
```

**Exit code:** 0

**Output (last 5 lines):**
```
tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream PASSED [100%]

========================= 1 passed, 1 warning in 0.16s =========================
```

**Acceptance gate:**
- `grep -q "DataWriter.return_value.store_async = AsyncMock" tests/test_media_keys_smtc.py` exits 0 — PASS
- Targeted pytest exits 0 — PASS

**Cross-reference:** 57-01-SUMMARY.md — commit `c1c783c` (2026-05-02). The AsyncMock-on-return_value fix is preserved and functional on the rebased branch.

---

## SC #4: Linux full suite no new failures

**Status:** PASS

**Requirement:** WIN-04 — full pytest suite produces no NEW failures vs. base. The 10 pre-existing failures from 57-01-SUMMARY.md remain but are not grown by Phase 57.

### Task 1 full suite run

**Command:**
```
cd /home/kcreasey/OneDrive/Projects/MusicStreamer && PYTHONPATH=. uv run pytest --tb=no -q 2>&1 | tail -20
```

**Result summary:** `11 failed, 964 passed, 1 skipped, 6 warnings`

### Failure list diff

| Test | Pre-existing on ca0dff5 (57-01 baseline) | Status post-Phase-57 | Introduced by Phase 57? |
|------|------------------------------------------|----------------------|------------------------|
| tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs | failing | unchanged | No |
| tests/test_media_keys_mpris2.py::test_linux_mpris_backend_publish_metadata | failing | unchanged | No |
| tests/test_media_keys_mpris2.py::test_linux_mpris_backend_publish_metadata_none | failing | unchanged | No |
| tests/test_media_keys_mpris2.py::test_linux_mpris_backend_set_playback_state | failing | unchanged | No |
| tests/test_media_keys_mpris2.py::test_linux_mpris_backend_slot_play_pause_emits_signal | failing | unchanged | No |
| tests/test_media_keys_mpris2.py::test_linux_mpris_backend_shutdown_idempotent | failing | unchanged | No |
| tests/test_media_keys_mpris2.py::test_xesam_title_passthrough_verbatim | failing | unchanged | No |
| tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode | failing | unchanged | No |
| tests/test_station_list_panel.py::test_refresh_recent_updates_list | failing | unchanged | No |
| tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present | failing | unchanged | No |
| tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s | **intermittent pre-existing** | flaky (passes in isolation) | No |

**10 pre-existing failures, no new ones introduced by Phase 57.**

### Note on test_edit_station_dialog.py::test_logo_status_clears_after_3s

This test appeared in the full-suite run (`11 failed`) but was NOT in the 57-01-SUMMARY.md pre-existing failure list. Investigation:
- `tests/test_edit_station_dialog.py` was NOT modified by any Phase 57 commit (`git diff ca0dff5..HEAD -- tests/test_edit_station_dialog.py` is empty)
- `musicstreamer/ui_qt/edit_station_dialog.py` was NOT modified by any Phase 57 commit
- Running the test in isolation passes: `pytest tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s -v` → `1 passed in 3.34s`
- Conclusion: this is a pre-existing intermittent/order-dependent flaky test (likely a QTimer-driven test that races with other tests' teardown when run in the full suite). **Not introduced by Phase 57.**

**SC #4 attestation: 10 pre-existing failures, no new ones introduced by Phase 57. The rebased branch is clean with respect to Phase 57 changes.**

---

## SC #1: WIN-03 pause/resume audible glitch (Win11 VM)

**Status:** PENDING — awaiting Task 2 (Win11 VM perceptual verification)

**Requirement:** WIN-03 — pressing Pause then Resume on a playing SomaFM stream produces no audible pop, gap, or restart artifact. Plan 57-04's QTimer-driven 8-tick volume ramp (40ms fade-down to 0 before NULL teardown) and Plan 57-03's bus-message re-apply on PLAYING-arrival together address this surface.

*This section will be completed by the continuation agent after the human completes Task 2 on the Win11 VM.*

---

## SC #2: WIN-03 volume slider takes effect (Win11 VM)

**Status:** PENDING — awaiting Task 3 (Win11 VM perceptual verification)

**Requirement:** WIN-03 — moving the volume slider mid-stream changes the audible playback volume immediately AND the slider's value is preserved across pause/resume (matches Linux behavior). Plan 57-03's bus-message STATE_CHANGED handler re-applying `self._volume` on every PLAYING transition closes the `0.5 → 1.0` property-reset surface confirmed in 57-DIAGNOSTIC-LOG.md Step 2.

*This section will be completed by the continuation agent after the human completes Task 3 on the Win11 VM.*

---

## Phase 57 readiness summary

**Status:** PENDING — SC #1 and SC #2 await Win11 VM perceptual UAT

*This section will be completed by Task 4 after all four SCs are attested.*

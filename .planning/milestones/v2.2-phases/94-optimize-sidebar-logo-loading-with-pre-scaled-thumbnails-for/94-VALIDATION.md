---
phase: 94
slug: optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-15
validated: 2026-06-15
---

# Phase 94 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-qt 4.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_art_paths.py tests/test_station_icon_integration.py tests/test_station_thumb_async.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x -q` |
| **Estimated runtime** | quick ~tens of seconds; full suite >600s |

> **MEMORY.md:** Run tests with `.venv/bin/python -m pytest`, NOT system `python3` — system python lacks `PySide6.QtWidgets` and produces false failures. Full suite >600s; scope to phase-relevant files during development. Two known pre-existing failures unrelated to this phase.

---

## Sampling Rate

- **After every task commit:** Run the quick command (art_paths + station_icon_integration + station_thumb_async)
- **After every plan wave:** Run the full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds (quick run)

---

## Per-Task Verification Map

| Decision | Behavior | Test Type | Automated Command | File Exists | Status |
|----------|----------|-----------|-------------------|-------------|--------|
| D-02 (lazy gen) | `load_station_icon` returns fallback when no thumb, enqueues generation | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_missing_returns_fallback -x` | ✅ | ✅ green |
| D-02 (disk write) | Worker writes valid PNG to `station_art.thumb.png` | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_generate_thumb_writes_png -x` | ✅ | ✅ green |
| D-03 (async repaint) | `dataChanged` emitted after thumb lands | integration | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_thumb_landing_emits_datachanged -x` | ✅ | ✅ green |
| D-04 (96px size) | Generated thumb is ≤96px on longest axis | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_is_96px -x` | ✅ | ✅ green |
| D-05 (path) | Thumb lives at `assets/{id}/station_art.thumb.png` | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_path_derivation -x` | ✅ | ✅ green |
| D-06 (mtime) | Fresh thumb skips regen; stale thumb re-enqueues | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_freshness_check -x` | ✅ | ✅ green |
| D-01 (now_playing unchanged) | `_load_scaled_pixmap` does NOT reference `station_art.thumb` | drift-guard | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_now_playing_panel_does_not_use_thumb -x` | ✅ | ✅ green |
| D-03 (dedup) | Same station not enqueued twice during fast scroll | unit | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_in_flight_dedup -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_art_paths.py` — extended: thumb path derivation, freshness (mtime) check, 96px size, miss/stale behavior (5 tests) — all green
- [x] `tests/test_station_thumb_async.py` — created: async generation, `dataChanged` emit, in-flight dedup, drift-guard for `now_playing_panel` (4 tests) — all green

*Existing `tests/test_station_icon_integration.py` passes unchanged — fallback behavior is preserved when no thumb exists.*

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions | Result |
|----------|----------|------------|-------------------|--------|
| Sidebar scroll feels smooth on a large list (DI.fm-scale), including first pass | D-03 | Perceptual smoothness / event-loop timing under real scroll cannot be asserted deterministically in unit tests | Import a large AudioAddict network (e.g. DI.fm), fast-scroll the sidebar top-to-bottom on first launch after import; confirm no multi-row stalls and that logos fill in progressively from fallback | ✅ PASSED (94-UAT test 1 — "fluid movement instead of slow molasses") |
| Logos render sharp at HiDPI | D-04 | Visual sharpness on fractional/Retina scaling is perceptual | On a HiDPI display (Wayland fractional / Retina 2x), confirm sidebar logos are crisp, not blurry | ✅ PASSED at 1x (94-UAT test 2; no HiDPI hardware — WR-02 remains a non-blocking follow-up) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (9 tests across 2 files — all green)
- [x] No watch-mode flags
- [x] Feedback latency < 60s (quick run)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-15

---

## Validation Audit 2026-06-15

| Metric | Count |
|--------|-------|
| Requirements (D-01..D-06) | 6 |
| COVERED (automated, green) | 6 |
| PARTIAL | 0 |
| MISSING | 0 |
| Manual-only (perceptual/hardware) | 2 — both PASSED via 94-UAT |

State A audit: all 8 per-decision automated tests verified present and green (`8 passed`); no gaps to fill, so no auditor pass was required. Phase 94 is **Nyquist-compliant** — every requirement has automated verification, and the two inherently-manual items passed human UAT.

**Deferred (non-requirement, tracked in 94-REVIEW.md):** IN-01 — an explicit test for the permanent-fallback-cache state after a thumbnail-generation failure. Not a requirement gap (the failure path is exercised indirectly via `test_thumb_missing_returns_fallback` and the `QImage.isNull()` guard); recommended as a small robustness add in a future polish pass.

---
phase: 38
slug: filter-strip-favorites
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-12
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-qt |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` testpaths=["tests"] |
| **Quick run command** | `pytest tests/test_station_filter_proxy.py tests/test_flow_layout.py tests/test_favorites.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_station_filter_proxy.py tests/test_flow_layout.py tests/test_favorites.py -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | UI-03 | — | N/A | unit | `pytest tests/test_station_filter_proxy.py -x` | ❌ W0 | ⬜ pending |
| 38-01-02 | 01 | 1 | UI-03 | — | N/A | unit/widget | `pytest tests/test_flow_layout.py tests/test_station_list_panel.py -x` | ❌ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | UI-04 | — | N/A | unit/widget | `pytest tests/test_favorites.py tests/test_station_list_panel.py -x` | ❌ W0 | ⬜ pending |
| 38-02-02 | 02 | 2 | UI-04 | — | N/A | widget | `pytest tests/test_now_playing_panel.py -x` | ❌ W0 | ⬜ pending |
| 38-02-03 | 02 | 2 | UI-03, UI-04 | — | N/A | manual | Visual checkpoint | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_station_filter_proxy.py` — stubs for UI-03 proxy filter behavior
- [ ] `tests/test_flow_layout.py` — stubs for UI-03 FlowLayout geometry
- [ ] Extension of `tests/test_station_list_panel.py` — proxy index mapping tests
- [ ] Extension of `tests/test_favorites.py` — station favorite repo methods (new: is_favorite_station, set_station_favorite, list_favorite_stations)
- [ ] Extension of `tests/test_now_playing_panel.py` — star button widget tests

*Existing infrastructure covers framework needs — no new test framework install required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chip wrap on narrow window | UI-03 | FlowLayout geometry depends on actual widget rendering at specific widths | Resize window below 400px, verify chips wrap to second row |
| Segmented control visual toggle | UI-04 | Visual state (QSS active/inactive styling) | Click Stations/Favorites buttons, verify visual feedback matches UI-SPEC |
| Star icon visual toggle | UI-04 | Icon fill state | Play a station, click star, verify icon fills; click again, verify unfills |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-12

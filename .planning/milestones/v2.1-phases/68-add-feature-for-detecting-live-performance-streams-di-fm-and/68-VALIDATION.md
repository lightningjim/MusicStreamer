---
phase: 68
slug: add-feature-for-detecting-live-performance-streams-di-fm-and
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-10
---

# Phase 68 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `68-RESEARCH.md` §"Validation Architecture" — see RESEARCH for behavior-by-decision-ID test mapping with full citations.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-qt |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_aa_live.py -x --tb=short` |
| **Full suite command** | `uv run pytest tests/ -q --tb=line` |
| **Estimated runtime** | quick: ~2 s; full: ~15 s (excluding pre-existing media-keys segfault subset) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_aa_live.py -x` (covers all unit-level decisions)
- **After every plan wave:** Run the wave's affected test files (per Per-Task Verification Map below)
- **Before phase verification:** Run full suite (`uv run pytest tests/ -q --tb=line`); must be green excluding pre-existing failures (`test_audioaddict_tab_widgets`, `test_audioaddict_quality_combo`, the media-keys Qt segfault subset documented in Phase 67 verification)
- **Max feedback latency:** 5 seconds (quick run); 30 seconds (full suite)

---

## Per-Task Verification Map

| Decision Ref | Plan | Wave | Behavior | Test Type | Automated Command | File Exists | Status |
|--------------|------|------|----------|-----------|-------------------|-------------|--------|
| A-02 | TBD | 1 | `_parse_live_map` detects event currently in window | unit | `pytest tests/test_aa_live.py::test_parse_live_map_event_in_window -x` | ❌ W0 | ⬜ pending |
| A-02 | TBD | 1 | `_parse_live_map` returns empty when no event in window | unit | `pytest tests/test_aa_live.py::test_parse_live_map_no_live -x` | ❌ W0 | ⬜ pending |
| A-02 | TBD | 1 | `_parse_live_map` handles multiple channels from one show | unit | `pytest tests/test_aa_live.py::test_parse_live_map_multi_channel -x` | ❌ W0 | ⬜ pending |
| A-04 | TBD | 1 | HTTP failure → empty dict (no exception propagation) | unit | `pytest tests/test_aa_live.py::test_fetch_live_map_http_error -x` | ❌ W0 | ⬜ pending |
| P-01 | TBD | 1 | `detect_live_from_icy("LIVE: DJ Set")` → `"DJ Set"` | unit | `pytest tests/test_aa_live.py::test_icy_live_prefix_colon -x` | ❌ W0 | ⬜ pending |
| P-01 | TBD | 1 | `detect_live_from_icy("LIVE - Set")` → `"Set"` | unit | `pytest tests/test_aa_live.py::test_icy_live_prefix_dash -x` | ❌ W0 | ⬜ pending |
| P-02 | TBD | 1 | `detect_live_from_icy("Live and Let Die")` → `None` (no false positive) | unit | `pytest tests/test_aa_live.py::test_icy_no_false_positive -x` | ❌ W0 | ⬜ pending |
| P-01 | TBD | 1 | Case-insensitive match: `"live: Set"` → `"Set"` | unit | `pytest tests/test_aa_live.py::test_icy_case_insensitive -x` | ❌ W0 | ⬜ pending |
| A-06 | TBD | 1 | `get_di_channel_key` maps stream URL to events channel key | unit | `pytest tests/test_aa_live.py::test_channel_key_from_di_url -x` | ❌ W0 | ⬜ pending |
| U-01/U-04 | TBD | 2 | Badge hidden on non-live station bind | widget | `pytest tests/test_now_playing_panel.py::test_live_badge_hidden_on_non_live_bind -x` | ❌ W0 | ⬜ pending |
| U-01/U-04 | TBD | 2 | Badge visible when live_map has station's channel key | widget | `pytest tests/test_now_playing_panel.py::test_live_badge_visible_when_live -x` | ❌ W0 | ⬜ pending |
| T-01a | TBD | 2 | Bind-to-already-live → live_status_toast emitted | widget | `pytest tests/test_now_playing_panel.py::test_bind_to_live_emits_toast -x` | ❌ W0 | ⬜ pending |
| T-01b | TBD | 2 | Off→On mid-listen → live_status_toast emitted | widget | `pytest tests/test_now_playing_panel.py::test_off_to_on_transition_toast -x` | ❌ W0 | ⬜ pending |
| T-01c | TBD | 2 | On→Off mid-listen → live_status_toast emitted | widget | `pytest tests/test_now_playing_panel.py::test_on_to_off_transition_toast -x` | ❌ W0 | ⬜ pending |
| T-03 | TBD | 2 | Poll update on non-bound station → no toast | widget | `pytest tests/test_now_playing_panel.py::test_poll_update_no_toast_for_unbound -x` | ❌ W0 | ⬜ pending |
| B-03/B-04 | TBD | 2 | Poll loop starts when key present, stops when cleared | integration | `pytest tests/test_now_playing_panel.py::test_poll_loop_starts_with_key -x` | ❌ W0 | ⬜ pending |
| F-01/F-07 | TBD | 3 | Chip hidden when no listen_key | widget | `pytest tests/test_station_list_panel.py::test_live_chip_hidden_without_key -x` | ❌ W0 | ⬜ pending |
| F-02/F-03 | TBD | 3 | Chip ON + provider chip → AND filter | proxy | `pytest tests/test_station_filter_proxy.py::test_live_only_and_provider -x` | ❌ W0 | ⬜ pending |
| F-04 | TBD | 3 | Chip ON + no live channels → empty tree | proxy | `pytest tests/test_station_filter_proxy.py::test_live_only_empty -x` | ❌ W0 | ⬜ pending |

> Plan IDs are filled in by the planner after wave/plan partition is finalized. Decision-ID anchors stay stable.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_aa_live.py` — new file: pure unit tests for ICY pattern matcher (P-01/P-02), `_parse_live_map` (A-02/A-04), channel key mapping (A-06). No qtbot, no Qt imports.
- [ ] `tests/fixtures/aa_live/events_no_live.json` — fixture: all events in future
- [ ] `tests/fixtures/aa_live/events_with_live.json` — fixture: one event with `start_at <= now < end_at`
- [ ] `tests/fixtures/aa_live/events_multiple_live.json` — fixture: multiple concurrent events on different channels
- [ ] `tests/fixtures/aa_live/events_http_error.txt` — fixture: simulated HTTP 500 / non-JSON body
- [ ] Extend `tests/test_now_playing_panel.py` — `_live_badge` visibility, three transition toasts, poll-loop lifecycle integration
- [ ] Extend `tests/test_station_list_panel.py` — Live now chip widget visibility (with/without listen_key)
- [ ] Extend `tests/test_station_filter_proxy.py` — `set_live_map`, `set_live_only`, AND-composition with existing chip filters

---

## Manual-Only Verifications

| Behavior | Decision Ref | Why Manual | Test Instructions |
|----------|--------------|------------|-------------------|
| Real DI.fm `/v1/di/events` round-trip works against the live API at runtime | A-02 | Live network call; flaky in CI; researcher already verified via curl probe | While playing any DI.fm station, open the app, wait 60s, observe whether the LIVE badge appears for any of the channels currently scheduled with live events at di.fm/live |
| Badge styling reads correctly under each Phase 66 theme preset | U-03 | Visual inspection only — no programmatic theme contrast assertion exists | Switch through all Phase 66 theme presets (vaporwave, pastel, etc.), confirm LIVE badge text remains readable on each background |
| Toast text doesn't truncate on common station names | T-01a/b/c | Visual inspection — `ToastOverlay` width is dynamic and platform-dependent | Trigger each of the three transition toasts (use bind to a live channel, wait for transition mid-listen, wait for transition out) and confirm full text fits on Linux Wayland at DPR=1.0 |
| Adaptive cadence (60s vs 5min) works without leaking timers across station switches | B-01 | Hard to assert timer state from inside a test; depends on QTimer event loop | Switch repeatedly between DI.fm and non-DI.fm stations over 10 minutes; confirm only one poll worker is alive at a time (process inspection) |

---

## Validation Sign-Off

- [ ] All decisions have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive decisions without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5 s (quick), < 30 s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

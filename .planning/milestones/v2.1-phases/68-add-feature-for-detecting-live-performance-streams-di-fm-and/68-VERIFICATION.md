---
phase: 68-add-feature-for-detecting-live-performance-streams-di-fm-and
verified: 2026-05-10T14:00:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 68: Live Performance Stream Detection Verification Report

**Phase Goal:** When the user is playing — or browsing — a DI.fm station, MusicStreamer surfaces whether that channel is currently broadcasting a live show. Hybrid detection: AudioAddict /v1/di/events (no auth required) + ICY title prefix fallback (LIVE: / LIVE -). Three UI surfaces: inline LIVE badge in NowPlayingPanel, toast notifications on three transitions (bind-to-already-live, off→on, on→off), 'Live now' filter chip in StationListPanel filter strip. Adaptive 60s/5min poll cadence. Silent fallback when no listen_key.
**Verified:** 2026-05-10T14:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `aa_live.py` exists with `fetch_live_map`, `_parse_live_map`, `detect_live_from_icy`, `get_di_channel_key`, `_parse_iso_utc` | VERIFIED | File at `musicstreamer/aa_live.py` (168 lines); all 5 symbols confirmed at lines 37, 55, 68, 111, 145 |
| 2 | BL-01: `_parse_iso_utc` normalizes Z suffix and naive datetimes | VERIFIED | `aa_live.py:48` — `raw.endswith("Z")` → replace with `+00:00`; `dt.tzinfo is None` → `dt.replace(tzinfo=timezone.utc)`; confirmed by runtime test (Z-suffix event correctly detected as live) |
| 3 | BL-02: `stop_aa_poll_loop` calls `self._aa_live_worker.wait(16000)` | VERIFIED | `now_playing_panel.py:1534-1537` — worker.isRunning() guard + `self._aa_live_worker.wait(16000)` |
| 4 | BL-03: `_reschedule_aa_poll` wraps `get_di_channel_key` in try/except | VERIFIED | `now_playing_panel.py:1593-1602` — comment "BL-03:" + try/except around `get_di_channel_key(self._station)` with `is_playing_di = False` fallback; `_detect_live_for_current_station` also has broader try/except at line 1408 |
| 5 | BL-04: `start_aa_poll_loop` early-returns when worker in flight or timer armed | VERIFIED | `now_playing_panel.py:1516-1521` — `worker_running` check + `if self._aa_poll_timer.isActive() or worker_running: return` |
| 6 | `_AaLiveWorker(QThread)` in NowPlayingPanel with adaptive cadence (60s/5min) | VERIFIED | `now_playing_panel.py:103-130` defines `_AaLiveWorker`; `_reschedule_aa_poll` at line 1584 sets 60_000 for DI.fm, 300_000 otherwise |
| 7 | LIVE badge widget inline next to icy_label, hidden by default, Qt.PlainText | VERIFIED | `now_playing_panel.py:378-395` — `icy_row` QHBoxLayout with `_live_badge` (left) + `icy_label` (right, stretch=1); `setVisible(False)` and `setTextFormat(Qt.PlainText)` at lines 381-383 |
| 8 | `live_status_toast` signal wired through MainWindow to show_toast via bound method (QA-05) | VERIFIED | `main_window.py:345` — `self.now_playing.live_status_toast.connect(self.show_toast)`; no lambda; `test_no_lambda_on_live_status_toast_connection` PASSED |
| 9 | Three toast transitions (T-01a bind-to-live, T-01b off→on, T-01c on→off) | VERIFIED | `now_playing_panel.py:1450-1469` — all three branches with correct text format; confirmed by `test_bind_to_live_emits_toast`, `test_off_to_on_transition_toast`, `test_on_to_off_transition_toast` passing |
| 10 | StationListPanel "Live now" chip hidden when no listen_key (F-07) | VERIFIED | `station_list_panel.py:292-293` — `_has_aa_key = bool(...)` gates initial visibility; `set_live_chip_visible(False)` also unchecks chip; `test_live_chip_exists_and_hidden_without_key` PASSED |
| 11 | StationFilterProxyModel `set_live_map`/`set_live_only` with Pitfall 7 invalidate guard | VERIFIED | `station_filter_proxy.py:57-79` — `set_live_map` calls `invalidate()` only when `_live_only is True`; `test_set_live_map_no_invalidate_when_chip_off` PASSED |
| 12 | MainWindow `_check_and_start_aa_poll` reactive hook on dialog close (B-04) and closeEvent stops poll (BL-02) | VERIFIED | `main_window.py:894` (import dialog) and `main_window.py:925` (accounts dialog) both call `_check_and_start_aa_poll()`; `closeEvent` at line 501-504 calls `stop_aa_poll_loop()` in try/except |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/aa_live.py` | Pure helper module with 5 public functions | VERIFIED | 168 lines, zero Qt imports, `_parse_iso_utc` (BL-01), `detect_live_from_icy`, `_parse_live_map`, `fetch_live_map`, `get_di_channel_key` |
| `musicstreamer/ui_qt/now_playing_panel.py` | `_AaLiveWorker`, badge, signals, poll lifecycle | VERIFIED | `_AaLiveWorker` at line 103; `live_status_toast` at 256; `live_map_changed` at 266; `_live_badge` at 381; `start_aa_poll_loop`/`stop_aa_poll_loop` with BL-02/BL-04 fixes |
| `musicstreamer/ui_qt/main_window.py` | Signal wiring, B-04 hook, closeEvent | VERIFIED | Wiring at lines 345 + 351; `_check_and_start_aa_poll` at 453; closeEvent at 497-504 |
| `musicstreamer/ui_qt/station_filter_proxy.py` | `set_live_map`/`set_live_only` + Pitfall 7 guard | VERIFIED | 149 lines; methods at lines 57-100; Pitfall 7 guard at line 69-70 |
| `musicstreamer/ui_qt/station_list_panel.py` | `_live_chip` + F-07 hidden-when-no-key | VERIFIED | `_live_chip` at line 283; F-07 gating at lines 291-293; `set_live_chip_visible` at 574 |
| `tests/test_aa_live.py` | 21 pure-helper tests | VERIFIED | All 21 pass (ICY pattern 7, events parser 6, HTTP layer 3, channel key 5) |
| `tests/fixtures/aa_live/*.json` | 4 fixture files | VERIFIED | All 4 exist: events_no_live, events_with_live (contains "Deeper Shades of House"), events_multiple_live, events_aliased_channel (contains "classictechno") |
| `tests/test_now_playing_panel.py` | Phase 68 section with 14 tests | VERIFIED | All 14 pass |
| `tests/test_station_list_panel.py` | Phase 68 section with 3 chip tests | VERIFIED | All 3 pass |
| `tests/test_station_filter_proxy.py` | Phase 68 section with 7 proxy tests | VERIFIED | All 7 pass |
| `tests/test_main_window_integration.py` | Phase 68 section with 6 integration tests | VERIFIED | All 6 pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_AaLiveWorker.run()` | `fetch_live_map` | local import `from musicstreamer.aa_live import fetch_live_map as _fetch` | WIRED | `now_playing_panel.py:123-124` |
| `NowPlayingPanel._on_aa_live_ready` | `live_map_changed.emit` | direct emit after cache update | WIRED | `now_playing_panel.py:1572` |
| `MainWindow.__init__` | `now_playing.live_status_toast` | `connect(self.show_toast)` bound method | WIRED | `main_window.py:345` |
| `MainWindow.__init__` | `now_playing.live_map_changed` | `connect(self._on_live_map_changed)` | WIRED | `main_window.py:351` |
| `MainWindow._on_live_map_changed` | `station_panel.update_live_map` | isinstance guard + forward | WIRED | `main_window.py:449-451` |
| `StationListPanel._on_live_chip_toggled` | `_proxy.set_live_only` | direct call | WIRED | `station_list_panel.py:563` |
| `StationListPanel.update_live_map` | `_proxy.set_live_map` | direct call | WIRED | `station_list_panel.py:572` |
| `NowPlayingPanel.bind_station` | `_refresh_live_status` | direct call after `_refresh_similar_stations` | WIRED | `now_playing_panel.py:758-759` |
| `NowPlayingPanel.on_title_changed` | `_refresh_live_status` | appended call | WIRED | `now_playing_panel.py:841` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_AaLiveWorker.run()` | return value | `fetch_live_map("di")` via `urllib.request.urlopen` to AA events API | Yes (live AA events JSON → `_parse_live_map`) | FLOWING |
| `NowPlayingPanel._live_badge` | visibility | `_live_map[ch_key]` from poll cache OR `detect_live_from_icy(self._last_icy_title)` | Yes (badge only shown when real live data present) | FLOWING |
| `StationFilterProxyModel.filterAcceptsRow` | `_live_channel_keys` | `set_live_map(live_map)` from poll fan-out | Yes (keys from real poll results) | FLOWING |
| `live_status_toast` | text | `show_name` from `_live_map` or ICY match, `station_name` from `self._station.name` | Yes (real station + show data) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| BL-01: Z-suffix parse | `python3 -c "_parse_live_map([{...Z timestamps...}], now=...)"` | `{'house': 'Z-suffix Show'}` | PASS |
| BL-01: naive datetime parse | `python3 -c "_parse_live_map([{naive timestamps}], now=...)"` | `{'trance': 'Naive Show'}` | PASS |
| All 21 aa_live unit tests | `pytest tests/test_aa_live.py` | 21 passed | PASS |
| All 6 integration tests | `pytest tests/test_main_window_integration.py -k "aa_poll or live_status"` | 6 passed | PASS |
| QA-05 no-lambda | `grep "live_status_toast.connect(lambda" main_window.py` | No match | PASS |
| Pitfall 7 invalidate guard | `pytest test_station_filter_proxy.py::test_set_live_map_no_invalidate_when_chip_off` | 1 passed | PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| D-01 | Hybrid detection (AA API + ICY fallback) | SATISFIED | `_detect_live_for_current_station` implements both paths |
| D-02 | DI.fm only scope for AA API path | SATISFIED | `get_di_channel_key` checks `slug != "di"` → None |
| D-03 | No master toggle | SATISFIED | Feature always-on when conditions met |
| D-04 | Silent fallback when no listen_key | SATISFIED | `start_aa_poll_loop` returns early; badge uses ICY path |
| P-01 | LIVE: / LIVE - prefix match | SATISFIED | `_LIVE_ICY_RE = re.compile(r'^\s*LIVE\s*[:\-]\s*(.+?)\s*$', re.IGNORECASE)` |
| P-02 | No substring matches | SATISFIED | Separator required; "Live and Let Die" → None (test passes) |
| P-03 | No state on ICY detection beyond current title | SATISFIED | `on_title_changed` re-evaluates stateless on each fire |
| A-01 | Use existing audioaddict_listen_key | SATISFIED | `self._repo.get_setting("audioaddict_listen_key", "")` |
| A-02..A-06 | AA API client correctness | SATISFIED | 21 tests pass including fixtures for parse, HTTP errors, channel key |
| B-01 | Adaptive cadence 60s/5min | SATISFIED | `_reschedule_aa_poll`: 60_000 (DI.fm) / 300_000 (other) |
| B-02..B-05 | Poll loop architecture | SATISFIED | QThread worker, single-shot QTimer, main-thread result via Signal |
| C-01 | Detect on bind | SATISFIED | `_first_bind_check = True; _refresh_live_status()` in `bind_station` |
| C-02 | Detect on track change | SATISFIED | `on_title_changed` calls `_refresh_live_status()` |
| C-03 | Decision tree | SATISFIED | `_detect_live_for_current_station` implements full decision tree |
| U-01..U-04 | Badge in icy_row, LIVE text, hidden by default | SATISFIED | `_live_badge` at lines 381-395 |
| T-01..T-04 | Three toast triggers, no cooldown, per-bound-station only | SATISFIED | Three branches in `_refresh_live_status`; `test_poll_update_no_toast_for_unbound_channel` passes |
| F-01..F-07 | Live chip, toggle, AND-compose, F-07 hidden without key | SATISFIED | All 10 proxy + chip tests pass |
| N-01..N-03 | Silent fallback, no prompt, reactive activation | SATISFIED | `start_aa_poll_loop` no-op without key; `_check_and_start_aa_poll` on dialog close |
| TD-01..TD-03 | Wave 0 RED first, fixture-based, no QA-05 lambda grep needed | SATISFIED | 50 tests written in Plan 01 RED, turned GREEN in Plans 02-05 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `musicstreamer/aa_live.py` | 161 | `url = streams[0].url` — direct attribute access without `getattr` | Warning | Low — both callers (`_reschedule_aa_poll` line 1596, `_detect_live_for_current_station` line 1408) wrap in try/except; crash path is protected. REVIEW recommended `getattr(streams[0], "url", None)` at the function level, but caller-level protection achieves the same safety outcome. |
| `musicstreamer/ui_qt/station_filter_proxy.py` | 136 | Same `streams[0].url` direct access | Warning | Low — only reached when `_live_only is True`; station nodes come from the DB and malformed streams are an edge case. |
| `musicstreamer/ui_qt/station_list_panel.py` | 344 | `self.show()` in `__init__` | Warning | Very low — deliberate workaround for `isVisible()` semantics in headless Qt tests; documented in comments; Wayland deployment target makes this a no-op flash risk. REVIEW WR-06 flagged this. |

**No blockers.** All anti-patterns are warnings inherited from implementation decisions that were either explicitly defended in SUMMARY.md or already noted in REVIEW.md as warnings (not blockers).

### Human Verification Required

None required. All phase behaviors are verifiable programmatically and through tests.

### Gaps Summary

No gaps. All 12 must-have truths are VERIFIED:

- `aa_live.py` module is complete with all required functions and BL-01 `_parse_iso_utc` fix
- BL-02/BL-03/BL-04 blocker fixes are present in `now_playing_panel.py`
- All three UI surfaces (badge, toasts, filter chip) are wired end-to-end
- Test suite: 254 passed; 2 pre-existing failures (`test_filter_strip_hidden_in_favorites_mode`, `test_refresh_recent_updates_list`) confirmed to pre-date Phase 68 on base commit 5663b15

The three remaining REVIEW warnings (WR-01 through WR-07) are code quality items, not functionality blockers — the feature works correctly as specified in CONTEXT.md.

---

_Verified: 2026-05-10T14:00:00Z_
_Verifier: Claude (gsd-verifier)_

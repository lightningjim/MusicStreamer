---
phase: 87-gbs-fm-marquee-themed-day-detection
plan: "04"
subsystem: gbs-marquee
tags:
  - gbs.fm
  - themed-day
  - logo-swap
  - compute_logo_theme
  - hash-drift
dependency_graph:
  requires:
    - 87-03 (GbsMarqueeWorker signals, _fetch_marquee, buffer_log handler)
    - 87-02 (MARQUEE_URL, parse_marquee, extract_noticearea_text)
    - 87-01 (SHA-256 harvested hash bd2b83... seeding GBS_LOGO_BASELINE_HASHES)
  provides:
    - GBS_THEMED_DAY_KEYWORDS frozenset in musicstreamer/constants.py
    - GBS_LOGO_BASELINE_HASHES dict[str,str] in gbs_marquee.py (1 entry — themed only)
    - ThemeResult NamedTuple + compute_logo_theme pure function in gbs_marquee.py
    - _fetch_logo_bytes module-level helper in gbs_marquee.py
    - GbsMarqueeWorker._on_first_gbs_bind one-shot + _on_tick extension
    - NowPlayingPanel.set_themed_logo_override slot + attach_gbs_marquee_worker + cadence wiring
    - MainWindow GbsMarqueeWorker construction + teardown
  affects:
    - 87-05 (marquee banner; install_gbs_marquee_handler already called in MainWindow)
    - 87-06 (drift-guard greps: cover_label, open(, gbs.themed_day.* log event names)
tech_stack:
  added: []
  patterns:
    - TDD (RED a64c01bf / d30a5db0 → GREEN 61cecefb / b9957e67)
    - D-12 hash-drift fallback (unknown hash treated as themed day; keyword only labels)
    - D-09 once-per-session gate (_themed_day_detected_this_session try/finally flip — T-87-04-05)
    - Cross-thread QPixmap delivery via themed_logo_ready Signal + Qt.QueuedConnection
    - Pitfall #2 cadence wiring via bind_station + on_playing_state_changed (not Player signals)
key_files:
  created: []
  modified:
    - musicstreamer/constants.py
    - musicstreamer/gbs_marquee.py
    - musicstreamer/ui_qt/now_playing_panel.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_gbs_marquee.py
decisions:
  - "GBS_LOGO_BASELINE_HASHES ships with 1 entry (themed only — no canonical PNG captured in Plan 87-01; canonical accretes post-Memorial-Day window)"
  - "_on_first_gbs_bind fires AFTER marquee fetch+parse within the same _on_tick so keyword search has populated _last_full_marquee_text on the very first tick (not the second)"
  - "T-87-04-05 mitigation: _themed_day_detected_this_session flipped in try/finally so any exception mid-routine still prevents retry loops"
  - "_FakeRepoForPanel added inline in test_gbs_marquee.py to avoid importing from test_now_playing_panel (no cross-test-file import per project convention)"
  - "_show_station_logo extended to re-apply _themed_logo_override on tier-change replay so the override persists across LAYOUT-03 art-tier transitions"
metrics:
  duration: "~13 minutes"
  completed: "2026-06-15"
  tasks: 2
  files: 5
---

# Phase 87 Plan 04: Themed-Day Correlator + Logo-Swap UI Wiring Summary

## What Was Built

**compute_logo_theme pure function + GBS_LOGO_BASELINE_HASHES + GbsMarqueeWorker one-shot themed-day detection + NowPlayingPanel logo-slot override + MainWindow construction/teardown.**

### Task 1 — GBS_THEMED_DAY_KEYWORDS + compute_logo_theme + GBS_LOGO_BASELINE_HASHES (TDD)

`musicstreamer/constants.py`:
- Added `GBS_THEMED_DAY_KEYWORDS: frozenset[str]` with 9 D-12 literal keywords (da troops, ho ho, spooky, halloween, christmas, thanksgiving, fourth, easter, valentine).

`musicstreamer/gbs_marquee.py`:
- Added `GBS_LOGO_BASELINE_HASHES: dict[str, str]` hardcoded dict literal — 1 entry seeded from Plan 87-01 harvest: `bd2b83fbe2b4bfe9baf8237a8919494e10cc7cf42ad3c42b1fcd605942881be3: "da troops (Memorial Day 2026-05-25)"`. No canonical entry captured (themed window was live on 2026-05-25). Zero file IO at module import (Pitfall 4 refinement).
- Added `ThemeResult(NamedTuple)` with fields `is_themed, logo_hash, theme_label, fallback_unknown_theme`.
- Added `compute_logo_theme(logo_bytes, full_marquee_text) -> ThemeResult` pure function implementing D-12 verbatim: `is_drift = (hash NOT IN table) OR (table[hash] != "canonical")`. Drift applies the themed logo; fallback fires when no keyword matches; canonical suppresses.

`tests/test_gbs_marquee.py`:
- 7 new tests: `test_compute_logo_theme_hashes_logo_bytes`, `test_themed_detection_keyword_match`, `test_themed_detection_no_keyword_fallback`, `test_themed_detection_empty_marquee_fallback`, `test_canonical_logo_not_themed` (monkeypatched), `test_baseline_table_has_harvest_entries`, `test_gbs_themed_day_keywords_constant`.

### Task 2 — Worker One-Shot + NowPlayingPanel Slot + MainWindow Wiring (TDD)

`musicstreamer/gbs_marquee.py`:
- Added `_fetch_logo_bytes() -> bytes | None`: anonymous `urlopen` against `gbs_api.GBS_STATION_METADATA["logo_url"]`; logs `gbs.themed_day.logo_fetch_failed` WARN on failure; no auth needed (public asset).
- Added `GbsMarqueeWorker._on_first_gbs_bind()`: fetches logo → calls `compute_logo_theme` → if `is_themed`, decodes to QPixmap and emits `themed_logo_ready`; if `fallback_unknown_theme`, logs `gbs.themed_day.unknown_theme_observed hash=<hex>` (hash only, no marquee body — T-87-04-02); flips `_themed_day_detected_this_session = True` in `try/finally` (T-87-04-05 mitigation).
- Extended `_on_tick`: calls `_on_first_gbs_bind()` AFTER the marquee fetch+parse so `_last_full_marquee_text` is populated before keyword search. Gate: `if not self._themed_day_detected_this_session`.

`musicstreamer/ui_qt/now_playing_panel.py`:
- Added `self._themed_logo_override: Optional[QPixmap] = None` and `self._gbs_marquee_worker = None` in `__init__`.
- Added `set_themed_logo_override(pixmap)` slot: scales pixmap to current tier, sets `logo_label` only (GBS-THEME-03), caches on `_themed_logo_override`.
- Added `attach_gbs_marquee_worker(worker)`: connects `themed_logo_ready → set_themed_logo_override` with `Qt.QueuedConnection`; stores reference.
- Added `_refresh_gbs_marquee_cadence()`: `set_cadence(60_000)` if playing, `set_cadence(300_000)` if not.
- Extended `bind_station`: if GBS.FM, re-applies cached `_themed_logo_override` (D-09) and calls `_refresh_gbs_marquee_cadence()`; else `set_cadence(0)`. Pitfall #2 wiring (not Player signals).
- Extended `on_playing_state_changed`: if GBS.FM + worker, calls `_refresh_gbs_marquee_cadence()`. Pitfall #2 wiring.
- Extended `_show_station_logo`: after setting canonical logo, re-applies `_themed_logo_override` if present + GBS.FM station (tier-change replay safety).

`musicstreamer/ui_qt/main_window.py`:
- In `__init__`: imports `GbsMarqueeWorker` + calls `install_gbs_marquee_handler()` + constructs `self._gbs_marquee_worker = GbsMarqueeWorker(parent=self)` + `self.now_playing.attach_gbs_marquee_worker(...)` + `self._gbs_marquee_worker.start()`.
- In `closeEvent`: calls `self._gbs_marquee_worker.stop_and_wait(5_000)` BEFORE `stop_aa_poll_loop` (teardown ordering per plan assumptions). Wrapped in `try/except` per AA precedent.

`tests/test_gbs_marquee.py`:
- Added `_FakeRepoForPanel` (inline fake repo for NowPlayingPanel construction without a real DB).
- `test_once_per_session_gate`: monkeypatches `_fetch_logo_bytes` + `_fetch_marquee`, drives two ticks, asserts logo-fetch counter == 1 (D-09/D-17).
- `test_themed_logo_targets_logo_slot_only_behavior`: asserts `set_themed_logo_override` writes to `logo_label` only; `cover_label` is unchanged (GBS-THEME-03 behavioral assertion).

## MARQUEE_URL / Logo URL Fetch Ladder Outcomes

- `MARQUEE_URL = "https://gbs.fm/"` (homepage HTML, confirmed by Plan 87-01).
- `logo_url = gbs_api.GBS_STATION_METADATA["logo_url"] = "https://gbs.fm/images/logo_3.png"` — public asset, anonymous fetch.
- No live network calls made during test suite (both `_fetch_marquee` and `_fetch_logo_bytes` are monkeypatched for all tests that exercise them).

## D-18 Log Event Names (for Plan 87-06 drift-guard whitelist)

| Event name | Condition | Log fields |
|------------|-----------|------------|
| `gbs.marquee.fetch_failed` | URLError/OSError/Exception in `_fetch_marquee` or `_on_tick` belt-and-suspenders | `url=MARQUEE_URL error=<ClassName>` |
| `gbs.marquee.auth_expired` | GbsAuthExpiredError in `_fetch_marquee` | `url=MARQUEE_URL` |
| `gbs.themed_day.logo_fetch_failed` | URLError/OSError/Exception in `_fetch_logo_bytes` | `url=logo_url error=<ClassName>` |
| `gbs.themed_day.unknown_theme_observed` | D-12 fallback (drift + no keyword) | `hash=<64-hex>` |

No body text (first_segment, full_text, marquee body) appears in any log line.

## GBS_LOGO_BASELINE_HASHES Entry Count

Ships with **1 entry** (themed only). No canonical entry was captured during the Plan 87-01 Memorial Day harvest — the live URL served the themed asset throughout. The canonical baseline will accrete as the operator captures non-themed states post-Memorial-Day. Plan 87-06 creates `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` to track this.

Implication for Plan 87-06 drift-guard wording: the TODO should note that `GBS_LOGO_BASELINE_HASHES` contains 1 entry as of Phase 87 release and is expected to grow to 2+ entries once the canonical logo is captured.

## Pitfall #2 Wiring Deviations

None. Cadence transitions are wired exclusively via:
- `NowPlayingPanel.bind_station` (line ~889) — calls `_refresh_gbs_marquee_cadence()` when GBS.FM; calls `set_cadence(0)` for other providers.
- `NowPlayingPanel.on_playing_state_changed` (line ~1007) — calls `_refresh_gbs_marquee_cadence()` when GBS.FM + worker present.

No references to `Player.state_changed` or `Player.station_bound` were introduced. The comment in `bind_station` and `on_playing_state_changed` explicitly cites Pitfall #2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] _show_station_logo extended to re-apply override on tier change**
- **Found during:** Task 2 implementation analysis
- **Issue:** The plan specified that `_show_station_logo` should check for `_themed_logo_override` "after computing the canonical pixmap." Without this extension, a LAYOUT-03 art-tier resize (which calls `_apply_art_tier → _show_station_logo`) would overwrite the themed logo with the canonical station art.
- **Fix:** Added a check at the end of `_show_station_logo`: if `_themed_logo_override is not None AND station is GBS.FM`, call `set_themed_logo_override(_themed_logo_override)` to re-apply at the new tier size.
- **Files modified:** `musicstreamer/ui_qt/now_playing_panel.py`
- **Commit:** `b9957e67`

**2. [Rule 2 - Missing critical functionality] _FakeRepoForPanel added to test file**
- **Found during:** Task 2 RED phase — `test_themed_logo_targets_logo_slot_only_behavior` needed a NowPlayingPanel instance but the full Repo + SQLite migration would require complex test setup.
- **Issue:** The plan's task 2 test used `from musicstreamer.repo import Repo, db_connect` with a tempdir, which caused `sqlite3.OperationalError: no such table: settings` (no migration was run).
- **Fix:** Replaced with an inline `_FakeRepoForPanel` class mirroring the existing `FakeRepo` in `test_now_playing_panel.py`. Avoids cross-test-file import per project convention.
- **Files modified:** `tests/test_gbs_marquee.py`
- **Commit:** `d30a5db0` (RED) → `b9957e67` (GREEN)

## Known Stubs

None. All API surface is fully implemented:
- `compute_logo_theme` — pure function, tested against live fixture.
- `_fetch_logo_bytes` — full urllib fetch with D-18 quiet failure handling.
- `GbsMarqueeWorker._on_first_gbs_bind` — one-shot routine, D-17 gate, try/finally flip.
- `NowPlayingPanel.set_themed_logo_override` — applies scaled pixmap to logo_label only.
- `MainWindow` GbsMarqueeWorker construction + teardown — matches AA precedent.

## Threat Flags

No new network endpoints, auth paths, or schema changes beyond those in the plan's threat model (T-87-04-01 through T-87-04-SC). The logo fetch is an anonymous GET to a public PNG URL — no credentials involved. The `themed_logo_ready` Signal crosses the worker→main-thread boundary via Qt.QueuedConnection; the QPixmap object is serialized by Qt's signal mechanism (T-87-04-01 mitigated by `pix.loadFromData` returning False on decode failure).

## Self-Check: PASSED

- `grep -c "^GBS_THEMED_DAY_KEYWORDS" musicstreamer/constants.py` → 1
- `grep -c "^GBS_LOGO_BASELINE_HASHES" musicstreamer/gbs_marquee.py` → 1
- `grep -c "def compute_logo_theme" musicstreamer/gbs_marquee.py` → 1
- `grep -c "_fetch_logo_bytes" musicstreamer/gbs_marquee.py` → 3 (function def + 2 call sites in _on_first_gbs_bind + logo_url ref)
- `grep -c "_on_first_gbs_bind" musicstreamer/gbs_marquee.py` → 2 (def + call in _on_tick)
- `grep -c "themed_logo_ready.emit" musicstreamer/gbs_marquee.py` → 1
- `grep -c "gbs.themed_day.unknown_theme_observed" musicstreamer/gbs_marquee.py` → 2
- `grep -c "gbs.themed_day.logo_fetch_failed" musicstreamer/gbs_marquee.py` → 3
- `grep -c "set_themed_logo_override" musicstreamer/ui_qt/now_playing_panel.py` → 5
- `grep -c "_refresh_gbs_marquee_cadence" musicstreamer/ui_qt/now_playing_panel.py` → 3
- `grep -c "GbsMarqueeWorker" musicstreamer/ui_qt/main_window.py` → 4
- `grep -c "install_gbs_marquee_handler" musicstreamer/ui_qt/main_window.py` → 2
- `grep -c "self._gbs_marquee_worker.stop_and_wait" musicstreamer/ui_qt/main_window.py` → 1
- `grep -E "cover_label|set_station_art|set_cover" musicstreamer/gbs_marquee.py` → 0 hits
- `grep -E "show_toast|libnotify|QSystemTrayIcon" musicstreamer/gbs_marquee.py` → 0 hits
- `grep -E "^\s*open\(" musicstreamer/gbs_marquee.py` → 0 hits (Pitfall 4 — no file IO)
- Task 1 RED commit `a64c01bf` — exists
- Task 1 GREEN commit `61cecefb` — exists
- Task 2 RED commit `d30a5db0` — exists
- Task 2 GREEN commit `b9957e67` — exists
- `uv run --with pytest pytest tests/test_gbs_marquee.py -v` → 24/24 passed

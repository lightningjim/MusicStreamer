---
phase: 82-twitch-only-station-still-tries-to-play-youtube-stream-first
verified: 2026-05-22T13:24:00Z
reverified: 2026-05-22T13:45:00Z
status: human_needed
score: 15/15 must-haves verified
overrides_applied: 0
gaps_closed:
  - truth: "FakeRepo regression-shield: pre-existing UI suites keep passing because their inline FakeRepo gains a set_preferred_stream no-op"
    original_status: failed
    resolved_status: resolved
    fix_commit: "6755a03 test(82-01): backfill FakeRepo.set_preferred_stream shield in third inline double"
    note: "Patched inline as part of phase execution — same 4-line shield as the other two FakeRepo doubles. tests/test_phase72_1_stream_picker_reflow.py now 11/11 GREEN. Goal-unrelated regression-shield miss, not a feature gap."
human_verification:
  - test: "Real-world Lofi Girl repro"
    expected: "Pick Twitch stream in dropdown, pause player, resume — Twitch plays (not YT). Restart app, re-pick Lofi Girl — Twitch still selected and plays."
    why_human: "Requires live YT-resolution-failure path + Twitch stream; cannot be exercised with mocked GStreamer pipeline."
  - test: "Dropdown survives station re-click"
    expected: "After picking Twitch on Lofi Girl, click a different station then click Lofi Girl again — Twitch plays, not YT."
    why_human: "Visual confirmation that all _on_station_activated entry points (D-03) honor the sticky pick; requires a live DB state with a real preferred_stream_id persisted."
---

# Phase 82: User-selected stream provider is honored on next Play — Verification Report

**Phase Goal:** Twitch-only station still tries to play YouTube stream first — lofi girl station has only one (Twitch) stream but player attempts YT first; can't fix at YT source due to false copyright claims on Lofi Girl's channel. User's selected stream provider should be honored on the next Play action.
**Verified:** 2026-05-22T13:24:00Z
**Re-verified:** 2026-05-22T13:45:00Z — gap closed inline (commit 6755a03)
**Status:** human_needed — all 15 must-haves verified; live UAT items below remain
**Re-verification:** Yes — sole gap (FakeRepo shield miss) patched inline

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-01: stations table carries a `preferred_stream_id INTEGER NULL REFERENCES station_streams(id) ON DELETE SET NULL` column after db_init | VERIFIED | repo.py:278 — ALTER TABLE uses `REFERENCES station_streams(id) ON DELETE SET NULL`; no `NOT NULL`, no `DEFAULT`. FK target is `station_streams` (known deviation from plan text, auto-fixed by executor per Rule 1). |
| 2 | D-01: Station dataclass exposes `preferred_stream_id: Optional[int] = None` | VERIFIED | models.py:40 — `preferred_stream_id: Optional[int] = None  # Phase 82 D-01: per-station sticky preferred stream` appended after `is_favorite`. |
| 3 | D-08: schema migration uses try/except ALTER TABLE idiom (NOT PRAGMA user_version) | VERIFIED | `grep -c user_version musicstreamer/repo.py` = 0. The Phase 73 cover_art_source try/except pattern is replicated exactly at repo.py:276-282. |
| 4 | D-02: Repo.set_preferred_stream(station_id, stream_id) round-trips (set non-None; set None clears) | VERIFIED | repo.py:574-580 — method exists, uses parameterized UPDATE, accepts Optional[int]. 12 repo tests pass including all 6 round-trip tests. |
| 5 | FakeRepo regression-shield: pre-existing UI suites keep passing because inline FakeRepo gains a set_preferred_stream no-op | FAILED | tests/test_stream_picker.py (line 56) and tests/test_now_playing_panel.py (line 95) received no-ops. However tests/test_phase72_1_stream_picker_reflow.py FakeRepo (line 75) was NOT updated. `test_signal_survives_round_trip` fails with `AttributeError: 'FakeRepo' object has no attribute 'set_preferred_stream'`. |
| 6 | D-03: Player.play(station) consults station.preferred_stream_id and places that stream at HEAD of failover queue | VERIFIED | player.py:521-544 — `getattr(station, "preferred_stream_id", None)` → `next(filter on station.streams)` → placed at queue head via `[preferred] + [s for s in streams_by_position if s is not preferred]`. 8 player tests pass. |
| 7 | D-03: preferred_stream_id beats preferred_quality kwarg; when None, preferred_quality keeps existing behavior | VERIFIED | player.py:534-539 — `preferred_by_id` fills `preferred` first; `preferred_quality` branch only runs `if preferred is None`. `test_preferred_stream_id_beats_preferred_quality` passes. |
| 8 | D-04: Player.play_stream() is unchanged — only Player.play() is modified | VERIFIED | `grep -c 'def play_stream' musicstreamer/player.py` = 1. play_stream body at lines 549-559 unchanged. |
| 9 | D-05: when the picked stream fails, _try_next_stream advances through the rest in order_streams order | VERIFIED | queue-build dedup uses `is not` identity check (not `!=`); `test_failover_after_preferred_stream_advances_queue` passes. |
| 10 | Drift-guard (player.py): source-grep test pins preferred_stream_id in non-comment lines | VERIFIED | `grep -v '^\s*#' musicstreamer/player.py \| grep -c preferred_stream_id` = 3. `test_preferred_stream_id_drift_guard` passes. |
| 11 | D-02: every _on_stream_selected invocation that resolves to a stream writes the pick via self._repo.set_preferred_stream(self._station.id, s.id) | VERIFIED | now_playing_panel.py:1289-1290 — two-line insertion after play_stream(s), before break. `grep -c 'self._repo.set_preferred_stream' now_playing_panel.py` = 1. |
| 12 | D-04: _on_stream_selected continues to call self._player.play_stream(s) exactly once per pick | VERIFIED | now_playing_panel.py:1288 — play_stream(s) present at original position; `grep -c 'self._player.play_stream(s)' now_playing_panel.py` = 1. |
| 13 | D-07: silent UX — no pin icon, no tooltip, no menu action added | VERIFIED | `grep -n 'set_preferred_stream' now_playing_panel.py` shows only line 1290 (_on_stream_selected body). No QIcon, QToolTip, or QAction additions in _on_stream_selected vicinity. _sync_stream_picker and _populate_stream_picker unchanged. |
| 14 | Drift-guard (now_playing_panel.py): source-grep test pins set_preferred_stream in non-comment lines | VERIFIED | `grep -v '^\s*#' now_playing_panel.py \| grep -c set_preferred_stream` = 1. `test_set_preferred_stream_drift_guard_now_playing_panel` passes. |
| 15 | blockSignals invariant: set_preferred_stream NOT called during _populate_stream_picker | VERIFIED | `test_bind_station_does_not_persist_preferred_stream_id` passes (0 calls recorded on bind_station). |

**Score:** 14/15 truths verified

### Deferred Items

None — all truths are expected to be achieved in this phase.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/models.py` | preferred_stream_id field on Station dataclass | VERIFIED | Line 40: `preferred_stream_id: Optional[int] = None` appended after is_favorite. |
| `musicstreamer/repo.py` | ALTER TABLE migration + Station propagation + set_preferred_stream setter | VERIFIED | Migration at line 276-282; setter at lines 574-580; `preferred_stream_id=r["preferred_stream_id"]` in 4 Station-builders (lines 474, 511, 607, 720). |
| `tests/test_repo.py` | migration idempotency + Repo round-trip tests | VERIFIED | `grep -k preferred_stream` returns 12 passes (3 migration/schema + 6 round-trip + 3 other). |
| `musicstreamer/player.py` | preferred_stream_id head-of-queue logic inside Player.play() | VERIFIED | Lines 521-544: Phase 82 D-01/D-03 block present and working. 3 non-comment occurrences. |
| `tests/test_player.py` | head-of-queue + failover regression + drift-guard tests | VERIFIED | 8 tests pass (1 minimal RED + 6 behavioral + 1 drift-guard). |
| `musicstreamer/ui_qt/now_playing_panel.py` | set_preferred_stream call inside _on_stream_selected after play_stream | VERIFIED | Lines 1289-1290 inserted exactly as planned. |
| `tests/test_stream_picker.py` | behavioral + drift-guard test for new persistence call | VERIFIED | 5 new tests pass (4 behavioral + 1 drift-guard); FakeRepo upgraded to call-recorder. |
| `tests/test_phase72_1_stream_picker_reflow.py` | FakeRepo shielded with set_preferred_stream no-op | FAILED | FakeRepo at line 75 has no set_preferred_stream method. test_signal_survives_round_trip fails. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| musicstreamer/repo.py:db_init | stations.preferred_stream_id column | try/except sqlite3.OperationalError ALTER TABLE | WIRED | repo.py:276-282 |
| Repo.list_stations / get_station / list_recently_played / list_favorite_stations | Station(preferred_stream_id=r["preferred_stream_id"]) | SELECT s.* wildcard + explicit kwarg in all 4 builders | WIRED | `grep -c preferred_stream_id=r` = 4 |
| musicstreamer/player.py:Player.play | station.preferred_stream_id lookup | getattr(station, "preferred_stream_id", None) + next(filter on station.streams) | WIRED | player.py:528-532 |
| musicstreamer/ui_qt/now_playing_panel.py:_on_stream_selected | Repo.set_preferred_stream | self._repo.set_preferred_stream(self._station.id, s.id) | WIRED | now_playing_panel.py:1289-1290 |
| tests/test_player.py:test_preferred_stream_id_drift_guard | musicstreamer/player.py source | Path.read_text + non-comment grep | WIRED | Passes: 3 non-comment hits confirmed. |
| tests/test_stream_picker.py:test_set_preferred_stream_drift_guard_now_playing_panel | musicstreamer/ui_qt/now_playing_panel.py source | Path.read_text + non-comment grep | WIRED | Passes: 1 non-comment hit confirmed. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| musicstreamer/player.py:Player.play | station.preferred_stream_id | Repo.list_stations / get_station (DB column INTEGER) | Yes — reads INTEGER FK value from SQLite row | FLOWING |
| musicstreamer/ui_qt/now_playing_panel.py:_on_stream_selected | s.id (StationStream) | self._streams (populated from repo.list_streams → DB) | Yes — integer PK from DB-backed stream list | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 12 preferred_stream repo tests pass | `uv run pytest tests/test_repo.py -k preferred_stream -x -q` | 12 passed | PASS |
| 8 player preferred_stream_id tests pass | `uv run pytest tests/test_player.py -k "preferred_stream_id or failover_after_preferred_stream" -x -q` | 8 passed | PASS |
| 5 stream picker persistence tests pass | `uv run pytest tests/test_stream_picker.py -k "preferred_stream or set_preferred_stream or persist" -x -q` | 5 passed | PASS |
| test_now_playing_panel full suite still green | `uv run pytest tests/test_now_playing_panel.py -x -q` | 142 passed | PASS |
| test_phase72_1_stream_picker_reflow full suite | `uv run pytest tests/test_phase72_1_stream_picker_reflow.py -q --tb=no` | 1 failed (test_signal_survives_round_trip) | FAIL |

### Probe Execution

No probes declared for this phase (not a migration/tooling phase).

### Requirements Coverage

Phase 82 PLAN frontmatter declares `requirements: []` (no formal REQ-NN ID assigned). REQUIREMENTS.md has no traceability row for Phase 82. This is consistent — the phase is a bug fix driven by D-01..D-08 CONTEXT decisions, not a separate REQUIREMENTS.md entry. No orphaned requirements flagged.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| tests/test_phase72_1_stream_picker_reflow.py | 75 | FakeRepo missing set_preferred_stream no-op | BLOCKER | test_signal_survives_round_trip fails with AttributeError at runtime; the Phase 82 _on_stream_selected change is not guarded against this FakeRepo instance. |

No TBD/FIXME/XXX debt markers found in Phase 82 modified files. No placeholder or hardcoded-empty stub patterns found. D-04 invariant confirmed (play_stream unchanged). D-07 invariant confirmed (no QIcon/QToolTip/QAction additions to _on_stream_selected).

### Human Verification Required

#### 1. Real-world Lofi Girl repro (live stream required)

**Test:** Start app, pick Lofi Girl from station list. Open stream dropdown, select Twitch. Pause player. Resume — confirm Twitch plays (not YT). Restart app, re-pick Lofi Girl — confirm Twitch is still selected and plays.
**Expected:** The preferred_stream_id persisted to DB is read back by Player.play() and the Twitch stream is placed at queue head on every subsequent play action.
**Why human:** Requires live YT-resolution-failure path and a real Twitch stream. GStreamer mock tests cannot exercise the live failover loop.

#### 2. Dropdown survives station re-click

**Test:** After picking Twitch on Lofi Girl, click a different station in the list, then click Lofi Girl again.
**Expected:** Twitch plays immediately (not YT), and the stream combo shows Twitch as the selected item via _sync_stream_picker.
**Why human:** Visual confirmation that _on_station_activated and all D-03 entry points honor the sticky pick. Requires a live DB state with preferred_stream_id persisted.

### Gaps Summary

One gap blocks passing: `tests/test_phase72_1_stream_picker_reflow.py` contains a third inline FakeRepo (line 75, used only by the Phase 72.1 stream-picker reflow tests) that was not given a `set_preferred_stream` no-op when Plan 82-01 added the method to `now_playing_panel.py`'s call path. The Phase 82-01 plan text explicitly scoped its FakeRepo shield to only `tests/test_stream_picker.py` and `tests/test_now_playing_panel.py`, missing this third consumer. The fix is a two-line addition to that class. All other D-01 through D-08 decisions are correctly implemented and verified.

The two pre-existing failures (`test_hamburger_menu_actions`, `test_end_to_end_factory_fallback_on_win32_without_winrt`) documented in Phase 81 VERIFICATION.md and Phase 82-02 SUMMARY are NOT Phase 82 regressions and are excluded from this count.

---

_Verified: 2026-05-22T13:24:00Z_
_Verifier: Claude (gsd-verifier)_

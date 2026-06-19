---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
verified: 2026-06-19T00:00:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 7/7
  gaps_closed:
    - "Spurious 'Stream exhausted' toast after URL edit: _recovery_seq generation guard added to error-recovery path (Plan 95-02)"
    - "FakePlayer _error_recovery_requested arity widened to Signal(int) — parity guard green"
    - "V11/V12/V13 unit coverage: stale recovery suppressed, genuine exhaustion still toasts, metadata-only unaffected"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Play a YouTube station, edit its URL to a different valid YouTube source, save."
    expected: "New audio starts immediately on the first play — NO 'Stream exhausted' toast appears at any point during the transition. Control: a station whose every stream genuinely fails STILL shows 'Stream exhausted' exactly once."
    why_human: "End-to-end depends on real yt-dlp resolution, the GStreamer bus-thread timing of the old stream's EOS error, and live playbin3 audio output. The spurious-toast race is a QueuedConnection timing issue observable only with a real pipeline."
---

# Phase 95: YT URL-change replay bug Verification Report (Re-verification after Plan 95-02)

**Phase Goal:** First play after editing a station's stream URL always uses the saved URL (no "stream exhausted"), by invalidating the Player's stale cached state (`_streams_queue`/`_current_stream`/loaded URI/in-flight YouTube resolution) on edit and restarting immediately when the actively-playing stream's URL changed (D-01..D-05). Additionally, no spurious "Stream exhausted" toast appears during the edit-to-restart transition (95-02 gap closure).
**Verified:** 2026-06-19T00:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after Plan 95-02 gap closure (spurious toast suppression)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | D-01: editing the playing-stream URL while actively playing restarts on the new URL (no "stream exhausted") | ✓ VERIFIED | `player.py:2102` — `is_playing` → `self.play(station)` (full rebuild). V1 green. |
| 2 | D-02: metadata-only edit (same URL) on playing stream does NOT interrupt audio | ✓ VERIFIED | `player.py:2110-2128` — URL-unchanged + no sibling change → no-op beyond seq bump. No `set_state` anywhere in the method body. V2/V4/V13 green. |
| 3 | D-03: cached state never serves a stale URL; first-play/second-play asymmetry gone | ✓ VERIFIED | Restart path reuses `play()` which resets `_streams_queue=[]` (`player.py:699`); seq bump (`:2076`) invalidates in-flight resolution. V1/V5 green. |
| 4 | D-04: editing a NON-playing sibling stream does not interrupt audio; queue invalidated for fresh failover | ✓ VERIFIED | `player.py:2124-2125` — `others_changed` → `self._streams_queue = []` only, no restart. V3 green. |
| 5 | D-05: editing an idle/paused/stopped station does not restart; next play() rebuilds fresh | ✓ VERIFIED | `player.py:2104-2107` (changed+not-playing → clear queue + `_current_stream=None`) and `:2086-2088` (no playing stream → clear queue). V6 green. |
| 6 | In-flight YouTube resolution completing after an edit no-ops (seq guard); never re-feeds old URL to `_set_uri` | ✓ VERIFIED | `_youtube_resolve_seq` declared `:591`; bumped at `invalidate_for_edit` entry `:2076`; carried through worker→`emit(resolved,is_live,seq)`; guarded in `_on_youtube_resolved`. V5 green; parity green. |
| 7 | Same-URL no-op: editing a URL to an identical value triggers no restart | ✓ VERIFIED | `.strip()` equality at `player.py:2094` → `playing_changed=False` → no restart. V4 green. |
| 8 | GAP CLOSED (95-02): spurious "Stream exhausted" toast suppressed after URL edit — a stale, pre-restart `_error_recovery_requested` delivery no-ops in `_handle_gst_error_recovery` | ✓ VERIFIED | `_recovery_seq` bumped at `play()` entry `:708`; `_on_gst_error` emits `self._error_recovery_requested.emit(self._recovery_seq)` `:1017`; `-1` sentinel guard at `_handle_gst_error_recovery` `:1039`: `if recovery_seq != -1 and recovery_seq != self._recovery_seq: return`. V11 green. |
| 9 | HARD CONSTRAINT: a genuine current-generation exhaustion (error posted AFTER the restart) still reaches `_try_next_stream()` → `failover.emit(None)` → toast | ✓ VERIFIED | Guard passes through when explicit stamp == `_recovery_seq`. V12 asserts both `_try_next_stream` called AND `failover.emit(None)` fires. No over-suppression possible: D-04/D-05 no-restart branches do NOT bump `_recovery_seq`. |
| 10 | BACKWARD COMPAT: all pre-existing no-arg `_handle_gst_error_recovery()` callers stay green without edits (-1 sentinel skips the staleness check) | ✓ VERIFIED | Signature `def _handle_gst_error_recovery(self, recovery_seq: int = -1)` `:1019`. `test_recovery_coalesces_cascading_errors` (test_multiple_gst_errors_advance_queue_once), `test_recovery_guard_resets_between_distinct_url_failures`, `test_gst_error_triggers_failover`, D-09/D-10/CR-01 in test_player.py — all PASS with no edits (100 total, 0 failures). |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/player.py` | `invalidate_for_edit` (D-01..D-05) + `_youtube_resolve_seq` guard + `_recovery_seq` guard (95-02) | ✓ VERIFIED | `_recovery_seq: int = 0` `:604`; `Signal(int)` `:286`; bump at `play()` entry `:708`; emit with stamp `:1017`; `-1` sentinel guard `:1039` above `_recovery_in_flight` check `:1047`. |
| `musicstreamer/ui_qt/main_window.py` | `_sync_now_playing_station` wires player invalidation | ✓ VERIFIED | Calls `self._player.invalidate_for_edit(updated_station, is_playing=...)` unconditionally on a valid station. |
| `tests/_fake_player.py` | `_error_recovery_requested = Signal(int)` (parity mirror, 95-02) | ✓ VERIFIED | `_error_recovery_requested = Signal(int)` `:79` with inline comment. Parity test green. |
| `tests/test_player_edit_invalidation.py` | V1-V6, V10 (95-01) + V11/V12/V13 (95-02) — 445 lines | ✓ VERIFIED | V11 `:326`, V12 `:367`, V13 `:404`. 14 total tests in this module, all pass. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `main_window._sync_now_playing_station` | `Player.invalidate_for_edit` | direct main-thread call | ✓ WIRED | Unconditional call on every committed edit. |
| `Player._play_youtube` | `Player._on_youtube_resolved` | `youtube_resolved Signal(str,bool,int)` carrying `_youtube_resolve_seq` | ✓ WIRED | seq captured at spawn, carried through worker, guarded in slot. |
| `Player.invalidate_for_edit` | `Player.play` | D-01 restart re-issues full rebuild (which bumps `_recovery_seq`) | ✓ WIRED | `player.py:2102` `self.play(station)`. |
| `Player._on_gst_error` | `Player._handle_gst_error_recovery` | `_error_recovery_requested Signal(int)` carrying `_recovery_seq` at POST time | ✓ WIRED | emit `:1017`; QueuedConnection slot `:523-524`; guard `:1039`. |
| `Player.play` | `_recovery_seq` bump (supersedes pre-restart recoveries) | `_recovery_seq += 1` at play() entry `:708` | ✓ WIRED | Covers every restart including `invalidate_for_edit` D-01 delegation; D-04/D-05 no-restart branches confirmed NOT to bump. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `_sync_now_playing_station` | `updated_station` | `self._repo.get_station(station_id)` (live DB fetch) | Yes | ✓ FLOWING |
| `invalidate_for_edit` URL diff | `match.url` vs `playing.url` | Stored `StationStream.url.strip()`, not resolved URI | Yes | ✓ FLOWING |
| `_handle_gst_error_recovery` guard | `recovery_seq` vs `self._recovery_seq` | Bus-thread int stamp vs main-thread counter; int read atomic in CPython | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| V11 stale recovery suppressed | `.venv/bin/python -m pytest tests/test_player_edit_invalidation.py -k "v11" -q` | 1 passed | ✓ PASS |
| V12 genuine exhaustion still toasts | `.venv/bin/python -m pytest tests/test_player_edit_invalidation.py -k "v12" -q` | 1 passed | ✓ PASS |
| V13 metadata-only unaffected | `.venv/bin/python -m pytest tests/test_player_edit_invalidation.py -k "v13" -q` | 1 passed | ✓ PASS |
| FakePlayer parity guard | `.venv/bin/python -m pytest tests/test_fake_player_signal_parity.py -q` | 2 passed | ✓ PASS |
| Full scoped suite (all 4 modules) | `.venv/bin/python -m pytest test_player_edit_invalidation.py test_player_failover.py test_player.py test_fake_player_signal_parity.py -q` | 100 passed, 0 failures | ✓ PASS |
| Cascade-coalescing regression | `test_multiple_gst_errors_advance_queue_once`, `test_recovery_guard_resets_between_distinct_url_failures` | 2 passed | ✓ PASS |
| End-to-end YT edit → first-play audio, no toast | (manual) | — | ? SKIP → human |

### Requirements Coverage

No REQ-IDs mapped (`requirements: []` in both PLAN files). Behavior contract is D-01..D-05 from 95-CONTEXT.md plus the spurious-toast suppression gap from 95-UAT.md, all verified above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | None found in phase-95 code paths | — | No TBD/FIXME/XXX markers; no stub returns; no over-suppression (V12 enforces the hard constraint). |

### Human Verification Required

#### 1. End-to-end YouTube URL edit → first-play audio with NO spurious toast

**Test:** Play a YouTube station. Edit its stream URL to a different valid YouTube source. Save. Observe immediately after save.
**Expected:** (a) New audio starts playing — no second play needed. (b) NO "Stream exhausted" toast appears at any point during the transition. Control check: stop a station whose every stream is genuinely unreachable — "Stream exhausted" must STILL appear exactly once, confirming the guard is not over-suppressing.
**Why human:** The spurious-toast race is a QueuedConnection timing issue: the GStreamer bus thread posts `_error_recovery_requested` for the old URL's EOS, then `play()` restarts synchronously on the main thread, then the queued delivery runs after. This timing sequence requires a real pipeline and real yt-dlp network resolution to observe. The V12 unit test enforces the hard constraint in isolation, but the full race (both events in sequence with real timing) can only be confirmed interactively.

### Gaps Summary

No gaps remain. All 10 must-have truths are VERIFIED in source:

**Plan 95-01 truths (D-01..D-05 + seq guard):** `invalidate_for_edit` implements the full decision tree; URL comparison on stored `StationStream.url.strip()`; restart delegates to `play()` (full rebuild); `_youtube_resolve_seq` generation guard wired end-to-end; `_sync_now_playing_station` → `invalidate_for_edit` wiring; FakePlayer `youtube_resolved` Signal arity parity.

**Plan 95-02 truths (spurious toast suppression):** `_recovery_seq: int = 0` declared alongside `_youtube_resolve_seq`; `Signal(int)` on `_error_recovery_requested`; bump at `play()` entry (single bump covers every restart path including D-01 delegation; D-04/D-05 no-restart branches confirmed NOT to bump); `_on_gst_error` stamps `self._recovery_seq` at POST time; `-1` sentinel guard in `_handle_gst_error_recovery` placed ABOVE the `_recovery_in_flight` check; FakePlayer `_error_recovery_requested` arity parity mirrored; V11/V12/V13 all pass (100 total tests, 0 failures).

Status remains `human_needed` solely because the one Manual-Only end-to-end scenario (real yt-dlp + GStreamer pipeline + live audio + QueuedConnection timing) cannot be verified without running the app.

**Note on combined-run Qt teardown abort:** Running multiple Qt test modules in one process can abort at interpreter teardown (pre-existing leaked GBS marquee QThread, documented in project MEMORY). Each module passes cleanly in isolation; the 100-test count above is the scoped 4-module run which also passes cleanly (0 failures).

---

_Verified: 2026-06-19T00:00:00Z_
_Verifier: Claude (gsd-verifier)_

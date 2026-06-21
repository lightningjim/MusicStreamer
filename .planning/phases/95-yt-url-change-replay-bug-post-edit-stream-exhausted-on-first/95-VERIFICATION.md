---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
verified: 2026-06-20T22:30:00Z
status: passed
score: 6/6 must-haves verified (automated) + 4/4 human UAT passed
has_blocking_gaps: false
human_uat: "4/4 passed 2026-06-20 (95-HUMAN-UAT.md): D-01 edit-no-toast, CR-01 leak (dead station still toasts after edit-to-direct), CR-01 spurious A->B (both timing variants clean), D-03 genuine exhaustion toasts once"
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 10/10
  previous_verified: 2026-06-19T00:00:00Z
  previous_note: "Stale — describes 95-02 era state; 95-03 CR-01 BLOCKER and 95-04 gap closure postdate it"
  gaps_closed:
    - "CR-01 BLOCKER: youtube_resolution_failed Signal widened to Signal(str, int) carrying per-worker seq; staleness keyed off carried seq, not the overwrite-prone _youtube_resolve_in_flight_seq instance attribute (removed)"
    - "CR-01 LEAK: _set_uri and stop() now clear _youtube_resolve_in_flight = False so YouTube->direct restart cannot strand the gate"
    - "CR-01 SPURIOUS-EXHAUSTION: play() and stop() bump _youtube_resolve_seq so a plain A->B station switch invalidates the old worker's failure delivery"
    - "V16d false-green test reconciled to drive real _play_youtube arming path (threading.Thread patched)"
    - "V17/V18/V19 added as regression locks for CR-01 leak, spurious-exhaustion, and stop() gate cleanup"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Play a YouTube station, edit its URL to a different valid YouTube source, save."
    expected: "New audio starts immediately on the first play — NO 'Stream exhausted' toast appears at any point during the transition."
    why_human: "D-01 end-to-end depends on real yt-dlp resolution, the GStreamer bus-thread timing of the old stream EOS error, and live playbin3 audio output."
  - test: "Play a YouTube station. While it is resolving (or shortly after it starts playing), edit its URL to a non-YouTube/direct stream URL and save."
    expected: "The direct stream starts playing. Later, trigger a genuine stream failure on any station (all streams broken). 'Stream exhausted' toast STILL fires — the gate is not stranded."
    why_human: "CR-01 leak closure (V17) is unit-proven but the real mid-resolve timing window requires a live pipeline."
  - test: "Rapidly switch from YouTube station A to YouTube station B (both YouTube). Wait for B to resolve and play."
    expected: "B plays with NO spurious 'Stream exhausted' toast during B's resolve window. No failover toast should appear."
    why_human: "CR-01 spurious-exhaustion closure (V18) is unit-proven but same-generation race timing requires a live yt-dlp resolve."
  - test: "A station whose every stream genuinely fails (broken URLs). Trigger playback."
    expected: "'Stream exhausted' toast fires exactly once."
    why_human: "D-03 genuine exhaustion must still surface; unit-proven by V15/V17/V12 but real GStreamer error path needs live confirmation."
---

# Phase 95: YT URL-change Replay Bug Verification Report (Post 95-04 Gap Closure)

**Phase Goal:** After editing a YouTube stream with a changed URL, first play must not surface a spurious "Stream exhausted" toast; replay picks up the new URL. Behavior contract D-01..D-05 in 95-CONTEXT.md.
**Verified:** 2026-06-20T21:00:00Z
**Status:** human_needed
**Re-verification:** Yes — supersedes stale 2026-06-19 report; covers Plans 95-01 through 95-04.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-01: editing the playing station's stream URL while actively playing restarts immediately on the new URL — first play uses the new URL, no "stream exhausted" | VERIFIED (unit) | `invalidate_for_edit` calls `self.play(station)` when `playing_changed and is_playing`; wired from `_sync_now_playing_station`; V1 GREEN |
| 2 | D-02: metadata-only edit on the playing stream does NOT interrupt audio (no restart, no set_state NULL) | VERIFIED | `invalidate_for_edit` exits after seq bump when URL unchanged and only metadata changed; V2/V4 GREEN |
| 3 | D-03: Player cached state (`_streams_queue`, `_current_stream`, loaded URI, in-flight YouTube resolution) never serves a stale URL after an edit; first-play-exhausts/second-play-works asymmetry gone | VERIFIED | `invalidate_for_edit` always bumps `_youtube_resolve_seq`; D-01 restart path calls `play()` which resets `_streams_queue`; `_set_uri` + `stop()` clear the gate; V17 genuine-exhaustion leg GREEN |
| 4 | D-04: editing a non-playing stream of the playing station does NOT interrupt audio; player queue invalidated for fresh failover | VERIFIED | `invalidate_for_edit` sets `_streams_queue = []` on `others_changed` path when `is_playing` and playing stream URL unchanged; V3 GREEN |
| 5 | D-05: editing a station not currently playing clears `_streams_queue`/`_current_stream`; next `play()` rebuilds from fresh DB state | VERIFIED | `invalidate_for_edit` `is_playing=False` branch sets `_streams_queue = []` and `_current_stream = None`; V6 GREEN |
| 6 | CR-01 CLOSED: failure path carries per-worker generation stamp on `Signal(str, int)`; stale failure delivery rejected by carried-seq guard; gate cannot leak across non-YouTube restart paths; `_youtube_resolve_in_flight_seq` removed | VERIFIED | `youtube_resolution_failed = Signal(str, int)` in both `player.py:274` and `_fake_player.py:65`; all three worker emits carry `seq`; `_on_youtube_resolution_failed(msg, seq=-1)` uses `if seq != -1 and seq != self._youtube_resolve_seq: return`; `_set_uri` clears gate at entry (:1614); `stop()` clears gate and bumps seq (:935-936); `play()` bumps seq (:731); `_youtube_resolve_in_flight_seq` — only descriptive comments remain, no executable references; V16c/V16d/V17/V18/V19 GREEN |

**Score:** 6/6 truths verified (automated)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/player.py` | `invalidate_for_edit`; `youtube_resolution_failed = Signal(str, int)`; carried-seq failure handler; `play()` + `stop()` seq bumps; `_set_uri` + `stop()` gate clears; `_youtube_resolve_in_flight_seq` removed | VERIFIED | All items confirmed by code read and grep |
| `musicstreamer/ui_qt/main_window.py` | `_sync_now_playing_station` calls `self._player.invalidate_for_edit(updated_station, is_playing=self.now_playing.is_playing)` | VERIFIED | `main_window.py:1451` — confirmed |
| `tests/_fake_player.py` | `youtube_resolution_failed = Signal(str, int)` parity; `invalidate_for_edit` stub | VERIFIED | `_fake_player.py:65` — confirmed; parity guard GREEN |
| `tests/test_player_edit_invalidation.py` | V1-V19 (21 tests) covering D-01..D-05, seq guard, gate, CR-01 regressions | VERIFIED | 21 tests collected and GREEN |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main_window._sync_now_playing_station` | `Player.invalidate_for_edit` | direct main-thread method call | WIRED | `main_window.py:1451` confirmed; V7 GREEN |
| `Player._youtube_resolve_worker` | `Player._on_youtube_resolution_failed` | `youtube_resolution_failed.emit(msg, seq)` carrying generation stamp | WIRED | All 3 emits at player.py:2063, 2072, 2077 carry `seq`; confirmed by code read |
| `Player.play` | staleness guard in `_on_youtube_resolved` / `_on_youtube_resolution_failed` | `_youtube_resolve_seq += 1` at play():731 invalidates prior in-flight resolves | WIRED | `player.py:731` confirmed; V18 regression GREEN |
| `Player._set_uri` / `Player.stop` | `_youtube_resolve_in_flight` gate | `_youtube_resolve_in_flight = False` cleared at `_set_uri` entry (:1614) and in `stop()` reset block (:935) | WIRED | Both sites confirmed by code read; V17/V19 GREEN |
| `Player.invalidate_for_edit` | `Player.play` | D-01 restart delegates to `self.play(station)` | WIRED | `player.py:2197` confirmed |

### Data-Flow Trace (Level 4)

Not applicable — this phase fixes a state-invalidation race condition, not a data-rendering pipeline. All relevant data flows are through Qt Signals (QueuedConnection) carrying `seq` payloads; correctness is verified at the unit level by V5/V16c/V16d/V17/V18/V19.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 21 edit-invalidation tests pass | `.venv/bin/python -m pytest tests/test_player_edit_invalidation.py -v` | 21 passed, 1 warning in 0.18s | PASS |
| FakePlayer parity guard passes | `.venv/bin/python -m pytest tests/test_fake_player_signal_parity.py -v` | 2 passed, 1 warning in 0.18s | PASS |
| `_youtube_resolve_in_flight_seq` fully removed (no executable refs) | `grep -n "_youtube_resolve_in_flight_seq" musicstreamer/player.py` | 3 hits — all descriptive comments/docstrings; no executable assignment or read | PASS |
| `youtube_resolution_failed = Signal(str, int)` in player.py | `grep -n "youtube_resolution_failed" musicstreamer/player.py \| head -2` | `:274: youtube_resolution_failed  = Signal(str, int)` | PASS |
| `_youtube_resolve_seq += 1` appears in play() AND stop() AND invalidate_for_edit | `grep -n "_youtube_resolve_seq += 1" musicstreamer/player.py` | Lines 731 (play), 936 (stop), 2171 (invalidate_for_edit) | PASS |
| `_youtube_resolve_in_flight = False` cleared in 4 places | `grep -cn "_youtube_resolve_in_flight = False" musicstreamer/player.py` | 4 (init default + `_on_youtube_resolved` + `_on_youtube_resolution_failed` + `_set_uri` + `stop()`) | PASS |
| RED commit 06cdc5dd exists | `git log --oneline \| grep 06cdc5dd` | `06cdc5dd test(95-04): add failing V17/V18/V19 + reconcile V16c/V16d` | PASS |
| GREEN commit 1ac58133 exists | `git log --oneline \| grep 1ac58133` | `1ac58133 feat(95-04): close CR-01 — carried-seq failure staleness...` | PASS |

### Probe Execution

No probe scripts declared for this phase.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| D-01 | Playing-stream URL change while playing restarts immediately on new URL | SATISFIED | `invalidate_for_edit` restart branch; V1 GREEN |
| D-02 | Metadata-only edit does not interrupt audio | SATISFIED | URL comparison gate in `invalidate_for_edit`; V2/V4 GREEN |
| D-03 | No stale player state survives an edit; first-play asymmetry gone | SATISFIED | `play()` + `stop()` seq bumps; `_set_uri` gate clear; V17 genuine-exhaustion leg GREEN |
| D-04 | Non-playing sibling stream edit does not interrupt audio; queue invalidated | SATISFIED | `others_changed` branch in `invalidate_for_edit`; V3 GREEN |
| D-05 | Edit while not playing clears state; next play() rebuilds fresh | SATISFIED | `is_playing=False` branch clears `_streams_queue`/`_current_stream`; V6 GREEN |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX debt markers found in modified files | — | None |

Scan of modified files (`musicstreamer/player.py`, `tests/_fake_player.py`, `tests/test_player_edit_invalidation.py`) found no unresolved debt markers, no stub returns, and no hardcoded empty data on any rendering path.

### Carried-Forward Non-Blocking Items (from 95-REVIEW.md re-review)

These are explicitly carried from the code review as non-blocking and are NOT gaps:

- **WR-05** (was WR-04): `_try_next_stream` gate consult sits inside the `if not self._streams_queue:` block only — the gate is not a uniform "one resolve owns the next transition" invariant. Practical risk materially reduced after CR-01 fix. Defer-acceptable per reviewer.
- **IN-02** (was IN-01): `_on_youtube_resolved` uses `seq=0` default while `_on_youtube_resolution_failed` uses `seq=-1` — divergent sentinels. Cosmetic; no behavioral impact. Defer-acceptable per reviewer.

### Human Verification Required

The automated suite (23 tests GREEN) proves the unit-level contracts for D-01..D-05 and CR-01. The following require a live pipeline because they depend on real yt-dlp resolution timing, GStreamer bus-thread EOS error timing, and QueuedConnection delivery races that cannot be reproduced with a mocked pipeline:

#### 1. D-01 Original Repro (primary user-facing fix)

**Test:** Play a YouTube station. Edit its stream URL to a different valid YouTube URL. Save.
**Expected:** The new stream starts playing immediately — NO "Stream exhausted" toast appears at any point during the transition. No second play press is needed.
**Why human:** End-to-end depends on real yt-dlp resolution + GStreamer playbin3 EOS race. The spurious-toast race is a QueuedConnection timing issue observable only with a real pipeline.

#### 2. CR-01 Leak Fix (YouTube-to-direct restart mid-resolve)

**Test:** Play a YouTube station. Immediately after pressing play (while it is still resolving), edit its URL to a non-YouTube direct stream URL (e.g. an Icecast/SHOUTcast HTTP stream) and save.
**Expected:** The direct stream starts playing. Then — to confirm the gate is not stranded — open a station whose every stream URL is broken and press play. "Stream exhausted" toast STILL fires.
**Why human:** The mid-resolve timing window (edit landing while the yt-dlp worker is running) requires a live pipeline; V17 unit-proves the state machine but not the delivery race.

#### 3. CR-01 Spurious-Exhaustion Fix (rapid YouTube A-to-B switch)

**Test:** Rapidly click away from YouTube station A to YouTube station B (both YouTube URLs). Wait for B to resolve and begin playing.
**Expected:** B plays with NO spurious "Stream exhausted" toast during B's resolve window.
**Why human:** Requires two live yt-dlp resolves racing; V18 unit-proves the state machine but the real timing race needs a real pipeline.

#### 4. D-03 Genuine Exhaustion Preserved

**Test:** Configure a station with one or more broken stream URLs (URLs that return 404 or connection refused). Press play.
**Expected:** "Stream exhausted" toast fires exactly once after all streams fail.
**Why human:** Requires real GStreamer error events from the bus thread; V15/V17 prove the unit logic.

---

## Gaps Summary

No automated gaps. All 6 must-haves are VERIFIED at the unit level. All 23 tests GREEN. CR-01 BLOCKER closed and confirmed by the re-review (status: clean). The remaining `human_needed` items are interactive YouTube playback behaviors that require a live pipeline and cannot be verified programmatically — they are the same class of UAT that applied to Plans 95-01 and 95-02.

---

_Verified: 2026-06-20T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Phase coverage: Plans 95-01 through 95-04 (full phase)_

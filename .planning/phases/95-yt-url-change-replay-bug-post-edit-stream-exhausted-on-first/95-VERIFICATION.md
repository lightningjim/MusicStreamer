---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
verified: 2026-06-18T20:15:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Play a YouTube station, edit its URL to a different valid YouTube source, save."
    expected: "New audio starts immediately on the first play — no 'stream exhausted' toast, no second play needed."
    why_human: "End-to-end depends on real yt-dlp resolution + live GStreamer playbin3 audio; cannot be verified without running the app and a network YouTube fetch."
---

# Phase 95: YT URL-change replay bug Verification Report

**Phase Goal:** First play after editing a station's stream URL always uses the saved URL (no "stream exhausted"), by invalidating the Player's stale cached state (`_streams_queue`/`_current_stream`/loaded URI/in-flight YouTube resolution) on edit and restarting immediately when the actively-playing stream's URL changed (D-01..D-05).
**Verified:** 2026-06-18T20:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | D-01: editing the playing-stream URL while actively playing restarts on the new URL (no "stream exhausted") | ✓ VERIFIED | `player.py:2050-2055` — `playing_changed and is_playing` → `self.play(station)` (full rebuild). Test `test_player_edit_invalidation.py` V1 green. |
| 2 | D-02: metadata-only edit (same URL) on playing stream does NOT interrupt audio — no restart, no `set_state(NULL)` | ✓ VERIFIED | `player.py:2063-2079` — URL-unchanged + no sibling change → no-op beyond seq bump. No `set_state` anywhere in the method body (grep confirmed). V2/V4 green. |
| 3 | D-03: cached state never serves a stale URL; first-play/second-play asymmetry gone | ✓ VERIFIED | Restart path reuses `play()` which resets `_streams_queue=[]` (`player.py:686`); seq bump (`:2029`) invalidates in-flight resolution. V1/V5 green. |
| 4 | D-04: editing a NON-playing sibling stream does not interrupt audio; queue invalidated for fresh failover | ✓ VERIFIED | `player.py:2069-2078` — `others_changed` → `self._streams_queue = []` only, no restart. V3 green. |
| 5 | D-05: editing an idle/paused/stopped station does not restart; next play() rebuilds fresh | ✓ VERIFIED | `player.py:2056-2060` (changed+not-playing → clear queue + `_current_stream=None`) and `:2039-2041` (no playing stream → clear queue). V6 green. |
| 6 | In-flight YouTube resolution completing after an edit no-ops (seq guard); never re-feeds old URL to `_set_uri` | ✓ VERIFIED | `_youtube_resolve_seq` declared `:591`; captured at spawn `:1879`; carried through worker→`emit(resolved,is_live,seq)` `:1965`; `_on_youtube_resolved` early-return `if seq != self._youtube_resolve_seq` `:1985`. V5 green; parity green. |
| 7 | Same-URL no-op: editing a URL to an identical value triggers no restart | ✓ VERIFIED | `.strip()` equality at `player.py:2047` → `playing_changed=False` → no restart. V4 green. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/player.py` | `invalidate_for_edit` decision method + `_youtube_resolve_seq` guard | ✓ VERIFIED | `def invalidate_for_edit` `:2001`; full D-01..D-05 tree `:2026-2081`; seq guard wired through `_play_youtube`/worker/`_on_youtube_resolved`. |
| `musicstreamer/ui_qt/main_window.py` | `_sync_now_playing_station` wires player invalidation | ✓ VERIFIED | `:1446-1448` calls `self._player.invalidate_for_edit(updated_station, is_playing=self.now_playing.is_playing)` unconditionally on a valid station, before the panel rebind. |
| `tests/_fake_player.py` | invalidate stub + `youtube_resolved` arity parity | ✓ VERIFIED | `youtube_resolved = Signal(str, bool, int)` `:64`; `invalidate_calls` list `:110`; `def invalidate_for_edit` stub `:135-139`. |
| `tests/test_player_edit_invalidation.py` | V1-V6, V10 coverage (≥80 lines) | ✓ VERIFIED | 9 tests pass; references `invalidate_for_edit`, `_youtube_resolve_seq`, 3-arg `youtube_resolved.emit`. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `main_window._sync_now_playing_station` | `Player.invalidate_for_edit` | direct main-thread call after fetch | ✓ WIRED | `main_window.py:1446`; integration V7 records exactly one call. |
| `Player._play_youtube` | `Player._on_youtube_resolved` | `youtube_resolved` Signal carrying `_youtube_resolve_seq` | ✓ WIRED | seq captured `:1879`, carried `:1965`, guarded `:1985`. |
| `Player.invalidate_for_edit` | `Player.play` | D-01 restart re-issues full rebuild path | ✓ WIRED | `player.py:2055` `self.play(station)`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `_sync_now_playing_station` | `updated_station` | `self._repo.get_station(station_id)` (live DB fetch) | Yes (fresh DB read of edited streams) | ✓ FLOWING |
| `invalidate_for_edit` URL diff | `match.url` vs `playing.url` | STORED `StationStream.url` (`.strip()`), NOT resolved playbin3 URI | Yes (user-typed URL) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Invalidation + seq guard unit suite | `pytest test_player_edit_invalidation.py test_fake_player_signal_parity.py -q` | 11 passed | ✓ PASS |
| Failover regression | `pytest test_player_failover.py -q` | 27 passed | ✓ PASS |
| Player regression | `pytest test_player.py -q` | 59 passed | ✓ PASS |
| Edit-dialog regression (V8) | `pytest test_edit_station_dialog.py -q` | 96 passed | ✓ PASS |
| V7 integration wiring | `pytest test_main_window_integration.py -k "sync or edit or invalidate" -q` | 2 passed | ✓ PASS |
| End-to-end YT edit → first-play audio | (manual) | — | ? SKIP → human |

### Requirements Coverage

No REQ-IDs mapped (PLAN `requirements: []`). The behavior contract is decisions D-01..D-05 + the V5 race guard, all verified above against `95-CONTEXT.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | None in phase-95 code paths | — | No TBD/FIXME/XXX debt markers; no stub returns; no `set_state(NULL)` on no-restart paths. |

### Human Verification Required

#### 1. End-to-end YouTube URL edit → first-play audio

**Test:** Play a YouTube station, edit its URL to a different valid YouTube source, save.
**Expected:** New audio starts immediately on the first play — no "stream exhausted" toast, no second play needed.
**Why human:** Depends on real yt-dlp resolution and live GStreamer playbin3 audio output; cannot be exercised without running the app against a network YouTube fetch. (95-VALIDATION.md Manual-Only.)

### Gaps Summary

No gaps. All 7 must-have truths are VERIFIED in source (not merely "tests exist"): `invalidate_for_edit` implements the full D-01..D-05 decision tree with restart delegated to `play()`, no `set_state(NULL)` on the D-02/D-04/D-05 no-restart paths, URL comparison on the stored `StationStream.url.strip()` rather than the resolved URI, the `_youtube_resolve_seq` generation guard wired end-to-end with an early-return in `_on_youtube_resolved`, FakePlayer signal arity parity, and the `_sync_now_playing_station` → `invalidate_for_edit` wiring that closed the panel-only gap. All phase-relevant test modules pass individually (9/27/59/96/2 + V7 subset 2), matching the documented counts.

**Note on the combined-run segfault:** Running `test_player_failover.py + test_player.py + test_edit_station_dialog.py` together aborts at interpreter teardown (Fatal Python error: Segmentation fault) — this is the DOCUMENTED pre-existing Qt-teardown crash (leaked GBS marquee QThread, `gbs_marquee.py:657`), confirmed by the project MEMORY note ("two known pre-existing failures") and reproduced standalone. Each module passes cleanly in isolation, and the V7 integration subset passes standalone, so this is NOT attributable to Phase 95.

Status is `human_needed` (not `passed`) solely because of the one Manual-Only end-to-end verification in 95-VALIDATION.md. All automated checks pass.

---

_Verified: 2026-06-18T20:15:00Z_
_Verifier: Claude (gsd-verifier)_

---
status: passed
phase: 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected
source: [98-VERIFICATION.md]
started: 2026-06-27T00:00:00Z
updated: 2026-06-27T00:00:00Z
---

## Current Test

[complete — all 4 human-verification items approved on live streams after 4 gap-closure rounds]

## Tests

### 1. Real-playback Stats-for-Nerds population
expected: Play any MP3 or AAC stream, open Stats for Nerds. All four rows (Encoding, Bitrate, Sample rate, Bit depth) populate within a few seconds. Encoding shows detected codec + "(exp: DECLARED)"; Bitrate shows detected kbps + expected kbps if declared.
result: issue — On YouTube streams the Encoding row shows a brief "AAC" then reverts to blank. A later tag (after a re-armed guard) re-emits with no codec, blanking the row. (gap G-01)

### 2. Amber mismatch visual legibility on light theme
expected: With a mismatched stream (declared ≠ actual), the detected value renders in amber (_AMBER_LIGHT = RGB 180,120,0), clearly distinct from muted gray; "(exp: X)" suffix readable.
result: pass — amber rendering is legible.

### 3. Amber mismatch visual legibility on dark theme
expected: Flip to a dark Qt theme while a mismatched stream plays — amber label transitions to _AMBER_DARK (RGB 255,180,60) and stays legible on dark background.
result: pass — dark-theme amber legible.

### 4. Station-switch clears all four rows (bind_station reset)
expected: After switching stations, all four format rows reset to "—" with no stale values or amber; they repopulate on the new stream's tags.
result: issue — After a mismatched (orange) stream, switching to a matching stream keeps the Bitrate/Encoding row highlighted orange; the amber is not reset even though the new stream matches. (gap G-03)

### 5. FLAC playback stability (GBS.FM) — regression discovered during UAT
expected: Playing the GBS.FM FLAC stream plays normally with a responsive UI.
result: issue — Player locks up / acts "funky" when streaming the GBS.FM FLAC stream. Frequent PAUSED→PLAYING rebuffer transitions re-arm the codec guard repeatedly, producing an audio_format_detected emit storm over a QueuedConnection that floods the main-thread event loop. (gap G-02, severity blocking)

## Summary

total: 5
passed: 2
issues: 3
pending: 0
skipped: 0
blocked: 0

## Gaps

### G-01 — YouTube encoding row blanks after brief codec display
severity: blocking (phase goal: show actually-playing encoding)
root_cause: `Player._on_playbin_state_changed` re-arms `_codec_tag_armed_for_stream_id` on every PLAYING transition (player.py:1394-1395). A later tag for the same stream (bitrate present, codec absent/unknown) re-emits `audio_format_detected(sid, "", bitrate)`, and `update_detected_format` blanks the Encoding row to "—". (Matches code-review WR-02.)
fix_direction: Make the guard truly one-shot per stream — track the already-detected stream id and do NOT re-arm in `_on_playbin_state_changed` for a stream already detected.

### G-02 — FLAC (GBS.FM) playback lockup
severity: blocking
root_cause: Same re-arm defect (WR-02). High-bitrate FLAC with frequent rebuffer PLAYING transitions re-arms the guard repeatedly → repeated cross-thread `audio_format_detected` emits flood the main-thread event queue via QueuedConnection → UI freeze.
fix_direction: One-shot-per-stream guard (shared with G-01) stops the re-emit storm.

### G-03 — Mismatch amber not reset on station switch
severity: blocking (phase goal: amber flags ONLY a real mismatch)
root_cause: Guard arms after `set_state(PLAYING)` (code-review WR-01), so an emission can carry the previous stream's sid. `update_detected_format` then looks up the wrong declared stream and paints a false mismatch (amber) after `bind_station` already cleared it; no later correct emission repaints. 
fix_direction: Arm before `set_state(PLAYING)` (WR-01) AND add a stale-sid guard in `update_detected_format` / `update_detected_caps` so emissions whose stream_id != currently-bound station are ignored.

---

## Resolution (commit 8f360533)

All three gaps share one root cause: the codec guard re-arming. Fixes applied:

- **player.py** — added `_codec_tag_detected_for_stream_id`; `_on_playbin_state_changed` no longer re-arms the guard for an already-detected stream (closes G-01 blank + G-02 emit-storm lockup). Guard now armed BEFORE `set_state(PLAYING)` in `_set_uri` so emissions carry the correct stream id (closes G-03 stale-sid false-amber).
- **now_playing_panel.py** — `update_detected_format` ignores emissions whose `stream_id` is not among the bound station's streams (G-03 defense-in-depth).
- **Regression tests** added (all green): `test_no_rearm_after_detected_on_rebuffer`, `test_rearm_allowed_for_new_stream`, `test_set_uri_arms_guard_before_playing` (player); `test_stream_switch_clears_prior_mismatch_amber`, `test_stale_cross_station_emission_ignored` (panel).

**Re-test round 1 results:**
- G-01 (YT blank) — ✅ PASS (user confirmed YouTube works).
- G-02 (FLAC lockup) — ✅ lockup gone, but FLAC bitrate no longer displayed.
- G-03 (amber stuck) — ❌ STILL happening on any station.
- NEW: SomaFM preroll stations never populate the Stats rows (stop/restart works).

## Resolution round 2 (commit 9cfd9f92) — detection redesign

Root cause of the remaining issues: the one-shot "first tag wins, then disarm"
model is too fragile — codec and bitrate arrive in SEPARATE tag messages, so the
first-and-only capture loses late/corrected fields.

Replaced with **accumulate-and-emit-on-change**:
- player.py: per-stream accumulator (`_codec_detect_codec/_bitrate/_last`).
  Detection stays armed for the stream lifetime; each tag merges new fields
  (never downgrading a known codec to blank), emits only when the merged value
  changes (de-dup → no storm). New `_arm_codec_detect_for_stream()` helper,
  idempotent per stream, called from `_set_uri` (before PLAYING), the PLAYING
  transition, AND the gapless preroll handoff.
- Fixes: #2 FLAC late bitrate now captured; #3 corrected bitrate clears false
  amber; SomaFM preroll now arms detection for the real stream.
- 11 player codec tests green (added codec-then-late-bitrate, no-downgrade,
  dedup, idempotent-rearm, new-stream-reset, arm-before-PLAYING, preroll-handoff).

**Re-test round 2 results:**
- #2 FLAC (GBS.FM) bitrate — ✅ PASS.
- SomaFM preroll populate — ✅ PASS.
- G-01 YouTube — ✅ PASS (no problems).
- #3 amber reset — ❌ STILL stuck.

## Resolution round 3 (commit c4cacff9) — stale-emission race

#3 was never a detection-accuracy problem. On a stream switch a late
audio_format_detected queued from the just-replaced (mismatched) stream arrives
AFTER the new stream's update and repaints amber against its own declared row;
nothing corrects it afterward. The round-2 redesign (more frequent emits) made
this more likely.

Fix: `now_playing_panel.update_detected_format` ignores any emission whose
`stream_id` is not the currently-selected/active stream (the stream picker's
current selection, kept in sync by bind_station / _on_stream_selected /
_sync_stream_picker). Cross-station declared-None guard retained as fallback.
Adds `test_stale_same_station_emission_ignored`.

**Re-test round 3 result:**
- #3 amber reset — ❌ NO change at all (rounds 1-3 all misdiagnosed it as a
  detection/stale-emission problem).

## Resolution round 4 (commit 400e7388) — palette-group corruption (THE bug)

#3 was never about detection. `_StatLabel.set_mismatch(True)` applied amber via
the 2-arg `QPalette.setColor(role, color)`, which sets the role for ALL color
groups — including Disabled. `_MutedLabel` derives its muted color by reading
`Disabled/WindowText` back. So once amber was applied, Disabled held amber, and
`set_mismatch(False)` read amber as the "muted" colour and re-applied it — the
highlight could never visually revert no matter what the detector emitted.

Fix: set amber only on Active/Inactive groups, leaving Disabled (the muted
source) intact. Backed out the speculative round-3 active-stream-id guard (wrong
theory, risked blocking valid updates). Added `test_mismatch_color_reverts_on_clear`
(fails before this fix); removed the round-3 test.

**Re-test round 4 (human):**
- #3 amber reset — [pending] mismatched (orange) stream → switch to a matching
  stream → orange must now clear. (This is the real fix — the colour revert is
  now covered by an automated test.)

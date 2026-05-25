---
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
verified: 2026-05-22T00:00:00Z
status: passed
score: 17/17 must-haves verified (15 D-XX + Security additions + Q3-EOS); D-05 gap closed by Plan 83-04; live-audio UAT re-run all-pass 2026-05-22
human_verification_outcome: 4/4 UAT tests pass (Beat Blender preroll plays audibly + transitions cleanly — initial "not gapless" reading reclassified to content-level silence in that one preroll m4a after user cross-checked other SomaFM stations; D-05 + D-07 confirmed)
overrides_applied: 0
re_verification:
  previous_status: human_needed (then re-opened as gaps_found by 83-UAT D-05 blocker)
  previous_score: 17/17 (source-level) — UAT then surfaced D-05 audible-playback blocker
  gaps_closed:
    - "D-05 SomaFM preroll plays audibly — `_on_preroll_about_to_finish` now performs a true playbin3 gapless URI handoff via `pipeline.set_property('uri', aa_normalize_stream_url(stream.url))` on the still-PLAYING pipeline (musicstreamer/player.py:1124-1205); the previous `_try_next_stream()` call that cycled `set_state(NULL)` and tore down the preroll mid-playback is gone from the gapless branch."
  gaps_remaining: []
  regressions: []
  re_verified: 2026-05-22 (after 9bbf540 merge of 83-04 worktree)
human_verification:
  - test: "Beat Blender preroll → stream gapless handoff (NOW UNBLOCKED — D-05 code-level fix landed)"
    expected: "On Linux Wayland: bind SomaFM Beat Blender → click Play → audible station-ID voiceover (~5–8s) followed by deep-house stream with NO audible gap. Now Playing shows 'Beat Blender' throughout (D-07 metadata suppression). Confirms playbin3 + souphttpsrc + aacparse + avdec_aac plays the m4a preroll AND hands off seamlessly to the station URI via the about-to-finish set_property idiom."
    why_human: "Real-pipeline about-to-finish handoff cannot be reliably mocked — pipeline MagicMocks pass any `pipeline.emit(...)` call without firing handlers (MEMORY: feedback_gstreamer_mock_blind_spot.md). Live audio is the only confirmation that the live-spike-validated gapless idiom (RESEARCH §Q1 RESOLVED) is what the shipped code now does on the real deployment target."
    decisions_covered: ["D-05", "D-07"]
    uat_test_id: 1
  - test: "Seven Inch Soul (no prerolls) plays without delay"
    expected: "Bind SomaFM Seven Inch Soul → Play → immediate stream audio with NO preroll preamble, NO repeated backfill thread re-spawn (D-04 `prerolls_fetched_at IS NOT NULL + zero rows` skip-silently path)."
    why_human: "Confirms `prerolls_fetched_at` non-NULL semantics + provider gate end-to-end without requiring code-side mocks; verifies the empty-preroll skip-silently branch in `Player.play`."
    decisions_covered: ["D-04", "D-11"]
    uat_test_id: 2
    notes: "Already PASSED in 83-UAT.md test 2 — unaffected by 83-04 fix."
  - test: "10-minute throttle window — replay within window → NO preroll; replay after window → preroll plays again"
    expected: "Play Beat Blender → hear preroll → stop → immediately replay → confirm NO preroll on second play (D-12 throttle gate). Wait >10 minutes (or restart app) → replay → confirm a fresh random preroll plays."
    why_human: "Confirms in-memory `_last_preroll_played_at` timestamp + 10-minute window with real wall-clock spacing; cannot be automated without a >10-min sleep. UAT tests 3 + 4 were `blocked_by: prior-phase` — now unblocked by D-05 gap closure."
    decisions_covered: ["D-12"]
    uat_test_id: "3+4"
---

# Phase 83: SomaFM Preroll Verification Report (Re-verified after 83-04 Gap Closure)

**Phase Goal:** When a SomaFM station starts playing, randomly pick one of its prerolls and play it before transitioning gaplessly into the station's actual stream. SomaFM stations with empty preroll[] behave exactly as today. Provider-gated to "SomaFM"; 10-minute global throttle; lazy on-demand backfill for pre-Phase-83 SomaFM stations already in the library.

**Verified:** 2026-05-22 (initial source-level), 2026-05-22 (re-verified post-83-04 gap closure)
**Status:** human_needed (D-05 code-level blocker closed; live-audio UAT re-runs unblocked)
**Re-verification:** Yes — D-05 gap closure (Plan 83-04) verified

---

## Gap-Closure Summary (Plan 83-04)

The 83-UAT.md surfaced one BLOCKER after the initial verification: D-05 "SomaFM preroll plays audibly" failed because the shipped 83-03 slot called `_try_next_stream()` which cycled `set_state(NULL)` → tore down the preroll mid-playback. Plan 83-04 replaced the body of `_on_preroll_about_to_finish` (player.py:1124-1205) with a TRUE gapless URI handoff: `pipeline.set_property("uri", aa_normalize_stream_url(stream.url))` on the still-PLAYING pipeline — NO `set_state(NULL)`, NO `set_state(PLAYING)`.

Commits verified resolvable: `6994b3d` (RED tests), `72a0ebf` (GREEN fix), `fef340e` (SUMMARY), merged in `9bbf540`.

### Plan 83-04 must-have verification (gap-closure focus)

| # | 83-04 Must-Have | Status | Evidence (player.py / tests) |
|---|------|--------|------|
| 1 | Gapless URI handoff on direct-URL path: `pipeline.set_property('uri', aa_normalize_stream_url(stream.url))` on still-PLAYING pipeline; NEVER `set_state(NULL)`, NEVER `_try_next_stream()` on direct-URL branch | ✓ VERIFIED | player.py:1201 — exact literal `self._pipeline.set_property("uri", aa_normalize_stream_url(stream.url))`. No `set_state` in slot body (grep confirmed inside slice). |
| 2 | Direct-URL scope guard — YouTube/Twitch URLs route to legacy `_try_next_stream()` | ✓ VERIFIED | player.py:1160-1166 — `if "youtube.com" in head_url or "youtu.be" in head_url or "twitch.tv" in head_url: self._try_next_stream(); return`. Test: `test_preroll_handoff_falls_back_for_youtube_url` parametrized over all three fragments — passes. |
| 3 | Bookkeeping parity with `_try_next_stream`: `_streams_queue.pop(0)`, `_last_buffer_percent = -1`, `force_close("preroll")`, `tracker.bind_url(...)`, `_underrun_dwell_timer.stop()`, elapsed-timer seeding (`_elapsed_seconds = 0` + `_elapsed_timer.start()` when `_is_first_attempt`), `_is_first_attempt = False`, `_failover_timer.start(BUFFER_DURATION_S * 1000)` | ✓ VERIFIED | player.py:1170-1205. All bookkeeping lines present. force_close uses outcome="preroll" (analytics distinguisher token, line 1177). Elapsed-timer seeding block at 1191-1193. Test: `test_preroll_handoff_invokes_tracker_bind_and_failover_timer_arm` asserts every one of these including `mock_elapsed_timer.start.assert_called_once()` + `_elapsed_seconds == 0` — passes. |
| 4 | URI canonicalization via `aa_normalize_stream_url` (URI funnel WIN-01 / Phase 70 D-01 not bypassed) | ✓ VERIFIED | player.py:1201 — `aa_normalize_stream_url(stream.url)`. Test: `test_preroll_handoff_normalizes_url_via_aa_normalize` uses a DI.fm-style URL to make the funnel observable (https→http rewrite); asserts `last_uri == aa_normalize_stream_url(s.url)` — passes. |
| 5 | Threading invariant preserved: streaming-thread callback body remains EXACTLY one line | ✓ VERIFIED | player.py:1118-1122 `_on_preroll_about_to_finish_callback` body is single line `self._preroll_about_to_finish_requested.emit()`. Main-thread slot is where `set_property` lives (qt-glib-bus-threading Rule 2 — plain GObject property set from main is canonical playbin3 idiom). |
| 6 | Phase 82 failover still works AFTER gapless handoff: bus error on station stream advances through `_streams_queue` via `_try_next_stream()` | ✓ VERIFIED | Slot leaves `_streams_queue` tail intact (only pops head). Test: `test_streams_queue_failover_after_preroll_handoff` invokes slot then `_handle_gst_error_recovery()` and asserts `_current_stream.id != first_played_id` — passes. |
| 7 | Slice-anchored drift-guard: regex slice-extracts `_on_preroll_about_to_finish` method body and asserts `set_property('uri', ...)` literal INSIDE the slice (closes false-negative scenario where `_set_uri` retains its own literal) | ✓ VERIFIED | tests/test_player.py:1231-1249. Regex `r'def _on_preroll_about_to_finish\(.*?\)(.*?)(?=\n    def \|\Z)'` with `re.DOTALL` extracts the body; `re.search(r'set_property\([^)]{0,80}["\']uri["\']', slot_body)` asserts INSIDE slice. `test_phase_83_preroll_drift_guard` passes. |
| 8 | All 13 existing Phase 83 tests still pass + 4 new + 2 updated = 17 total | ✓ VERIFIED | `uv run pytest tests/test_player.py -k "preroll or phase_83 or streams_queue_failover_after_preroll_handoff or about_to_finish" -x -q` → **17 passed, 27 deselected** (re-confirmed during this verification 2026-05-22). |

**Plan 83-04 score: 8/8 must-haves verified.**

### Test execution evidence (re-verifier re-ran)

```
$ uv run pytest tests/test_player.py -k "preroll or phase_83 or streams_queue_failover_after_preroll_handoff or about_to_finish" -x -q
17 passed, 27 deselected, 1 warning in 0.27s

$ uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py tests/test_fake_player_signal_parity.py -q
157 passed, 1 warning in 2.48s
```

Both runs reproduced by the verifier during this re-verification (not just trusting 83-04-SUMMARY's claims).

### Source-grep invariants (verifier re-ran)

| Invariant | Expected | Actual | Status |
|-----------|----------|--------|--------|
| `self._pipeline.set_property("uri"` count | ≥ 2 | 2 | ✓ |
| `force_close("preroll")` count | 1 | 1 | ✓ |
| `def _on_preroll_about_to_finish` (slot) count | 1 | 1 (line 1124) | ✓ |
| `_on_preroll_about_to_finish_callback` body single line | 1 line | 1 line (player.py:1122) | ✓ |

---

## Goal Achievement (re-verified end-to-end)

Tracing `Player.play(station)` post-83-04:

1. **player.py:565** — `_streams_queue = queue` built FIRST (Phase 82 preferred-stream + `order_streams`; D-06 unchanged).
2. **player.py:569-573** — provider gate (`provider_name == "SomaFM"`) + throttle gate (`_last_preroll_played_at is None or > 600s elapsed`) (D-11, D-12).
3. **player.py:574-578** — `urls = list(getattr(station, "prerolls", []) or [])`; non-empty → `random.choice(urls)` → `_start_preroll(preroll_url)` → `return`.
4. **player.py:579-590** — empty + `prerolls_fetched_at IS NULL` + not in single-flight → daemon backfill thread; falls through to `_try_next_stream()` (D-03, D-04, D-13).
5. **player.py:1103-1116 `_start_preroll`** — `_preroll_in_flight = True`, `_last_preroll_played_at = time.monotonic()` (D-12: timestamp at START), connects one-shot `"about-to-finish"`, `_set_uri(preroll_url)`.
6. **player.py:1118-1122 streaming-thread callback** — body is exactly `self._preroll_about_to_finish_requested.emit()` (qt-glib-bus-threading Rule 2 / T-83-13).
7. **player.py:414-416 connect** — `QueuedConnection` from Signal to main-thread slot.
8. **player.py:1124-1205 main-thread slot (NEW BODY)** — disconnects handler, clears flag, then either: (a) gapless URI handoff via `set_property("uri", aa_normalize_stream_url(stream.url))` for direct HTTP(S) [the SomaFM ICE-relay case], or (b) `_try_next_stream()` fallback for YouTube/Twitch, or (c) `_try_next_stream()` defensive for empty queue (which emits `failover(None)`).

All five mandatory wiring stages preserved; D-05 is now implemented correctly per playbin3's gapless contract (no `set_state` calls in the slot body).

---

## Per-Decision Coverage (D-01..D-15 + Security additions + Q3-EOS) — Carried Forward

| Decision | Status | Evidence (file:line) |
|----------|--------|----------------------|
| **D-01** `station_prerolls` table + FK CASCADE | ✓ VERIFIED (unchanged by 83-04) | `repo.py:153-159` CREATE TABLE; `tests/test_repo.py:1001,1142` pass |
| **D-02** `fetch_channels` + `import_stations` capture preroll[] | ✓ VERIFIED (unchanged by 83-04) | `soma_import.py:244,339-356`; `tests/test_soma_import.py:613,696` pass |
| **D-03** Lazy on-demand backfill | ✓ VERIFIED (unchanged by 83-04) | `player.py:579-590`; `tests/test_player.py:923` passes |
| **D-04** `prerolls_fetched_at` marker semantics | ✓ VERIFIED (unchanged by 83-04) | `repo.py:307`, `soma_import.py:356`, `player.py:1393` |
| **D-05** playbin3 about-to-finish gapless handoff | ✓ **VERIFIED (REWRITTEN BY 83-04)** | `player.py:1124-1205` — gapless `set_property("uri", aa_normalize_stream_url(stream.url))` on still-PLAYING pipeline; NO `set_state(NULL)`; NO `_try_next_stream()` on direct-URL branch. `test_preroll_about_to_finish_uses_gapless_uri_swap` + drift-guard slice-anchor pass. |
| **D-06** `_streams_queue` not mutated by preroll | ✓ VERIFIED (unchanged) | `player.py:565` queue built BEFORE preroll gate; preroll branch hits `return` at 578 |
| **D-07** Suppress preroll m4a title tag | ✓ VERIFIED (unchanged) | `player.py:787` early-return on `_preroll_in_flight` |
| **D-08** User controls behave normally during preroll | ✓ VERIFIED (unchanged) | `play_stream`/pause/stop untouched; `tests/test_player.py:1094` passes |
| **D-09** Preroll failure → silent skip → `_try_next_stream` | ✓ VERIFIED (unchanged) | `player.py:738-751`; `tests/test_player.py:1055` passes |
| **D-10** Failover after preroll uses standard queue advance | ✓ VERIFIED (re-confirmed under 83-04) | `_try_next_stream` untouched; slot leaves `_streams_queue` tail intact (only pops head); `test_streams_queue_failover_after_preroll_handoff` UPDATED to exercise post-gapless-handoff path — passes |
| **D-11** Provider gate — `"SomaFM"` CamelCase literal | ✓ VERIFIED (unchanged) | `player.py:570`; drift-guard pinned |
| **D-12** Throttle gate — 10-min global, timestamp at START | ✓ VERIFIED (unchanged) | `player.py:571-572`, `1112` (set in `_start_preroll`, not in slot) |
| **D-13** Background fetch race — non-blocking | ✓ VERIFIED (unchanged) | `player.py:586-590` daemon thread; falls through to `_try_next_stream()` |
| **D-14** Source-grep drift-guard | ✓ VERIFIED (STRENGTHENED by 83-04) | `tests/test_player.py:1197-1249` — pins `"SomaFM"` + `_last_preroll_played_at` AND adds slice-anchored `set_property('uri', ...)` literal inside `_on_preroll_about_to_finish` method body |
| **D-15** Schema migration (forward-only, idempotent) | ✓ VERIFIED (unchanged) | `repo.py:153,305-311`; `tests/test_repo.py:1031` passes |
| **Security T-83-01** URL scheme validation in `Repo.insert_preroll` | ✓ VERIFIED (unchanged) | `repo.py:439-442`; `tests/test_repo.py:1070` passes |
| **Security T-83-02** Per-call cap of 50 at all 3 layers | ✓ VERIFIED (unchanged) | `repo.py:443-446`, `soma_import.py:344-350`, `player.py:1380-1381` |
| **Security T-83-10** Single-flight backfill guard | ✓ VERIFIED (unchanged) | `player.py:460,581,585,1402`; `tests/test_player.py:923` |
| **Q3-EOS** Malformed-preroll EOS bridge | ✓ VERIFIED (unchanged) | `player.py:344,1137-1164`; `tests/test_player.py:1156` passes |

**Score: 17/17 truths verified (15 D-XX + 3 Security + Q3-EOS). D-05 was the regressed truth; it is now closed by 83-04.**

---

## Phase 83 Test Counts (post-83-04)

| Test File | Test Count | All Pass |
|-----------|-----------|----------|
| `tests/test_repo.py` (Phase 83 cluster) | 10 | ✓ |
| `tests/test_soma_import.py` (Phase 83 cluster) | 8 | ✓ |
| `tests/test_player.py` (Phase 83 cluster) | 17 (13 existing + 4 new — `test_preroll_about_to_finish_uses_gapless_uri_swap`, `test_preroll_handoff_normalizes_url_via_aa_normalize`, `test_preroll_handoff_falls_back_for_youtube_url` ×3 parametrize, `test_preroll_handoff_invokes_tracker_bind_and_failover_timer_arm`) | ✓ |
| **Total** | **35** (was 31; +4 new in 83-04) | ✓ |

Phase 83 narrow-filter run: **17 passed, 27 deselected, 1 warning in 0.27s**.
Phase 83 quick-suite run: **157 passed, 1 warning in 2.48s**.

---

## Manual UAT — Deferred (D-05 code-level fix unblocks all three items)

The D-05 audible-playback blocker that the 83-UAT raised is now closed at the code level. The user must re-run the three manual UAT items on Linux Wayland (deployment target). All three are blocked from automation by MEMORY anchor `feedback_gstreamer_mock_blind_spot.md` (pipeline MagicMocks pass any `pipeline.emit(...)` call without firing handlers, so live audio is the only confirmation that the gapless idiom actually works against real playbin3 + souphttpsrc + aacparse + avdec_aac).

The three items appear in the `human_verification:` frontmatter above:

1. **Beat Blender preroll → stream gapless handoff** (UAT test 1; D-05 + D-07) — NEWLY UNBLOCKED by 83-04 fix. Previously: "Going straight to the stream — no preroll voiceover at all." Now: expect ~5-8s preroll audio then seamless transition to deep-house stream.
2. **Seven Inch Soul no-preroll skip-silently** (UAT test 2; D-04 + D-11) — already PASSED in 83-UAT.md; unaffected by 83-04 fix; re-listed for completeness.
3. **10-min throttle window** (UAT tests 3 + 4; D-12) — previously `blocked_by: prior-phase` (depended on test 1 passing); now unblocked by 83-04 fix. Run both branches: replay within window → NO preroll; replay after window/app restart → preroll plays again.

When the user updates `83-UAT.md` with results from these three items, the orchestrator can close Phase 83.

---

## Gaps / Followups

**No blocking gaps remain.** All 17 must-haves are verified in shipped code; the 83-UAT D-05 blocker is closed at the code/test level by Plan 83-04.

**Audit-trace nits (informational, NON-blocking, carried forward from initial verification):** 11 of 15 `T-83-NN` threat IDs do not appear as text literals in shipped source/tests (their mitigation code IS present and tested). 83-04 adds T-83-15..T-83-20 threats — no T-83-NN literal in 83-04 code either. Future audits seeking `grep -rn "T-83-NN"` will come up empty. Consider adding `# T-83-NN mitigation` markers on the next maintenance pass. NON-blocking.

**Pre-existing flaky tests (unchanged scope per 83-03/83-04 SUMMARY):**
- `tests/test_main_window_integration.py::test_hamburger_menu_actions`
- `tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt`

Both confirmed pre-existing (`git stash` + pre-83-03 run) per 83-03-SUMMARY.md §"Pre-existing Failures". Out of scope per Phase 83 SCOPE BOUNDARY.

---

## Summary

Phase 83 ships the SomaFM preroll feature end-to-end at the source level:

- **Schema + Repo (Plan 83-01):** `station_prerolls` table, `prerolls_fetched_at` column, 3 new Repo methods with URL-scheme + DoS guards (T-83-01 + T-83-02), Station-builder eager-loads.
- **Importer (Plan 83-02):** `fetch_channels` returns `preroll_urls`; `import_stations` inserts rows + sets `prerolls_fetched_at` marker (even for empty preroll lists — D-04) inside the rollback window.
- **Player (Plan 83-03):** `Player.play` gates on provider + throttle + DB lookup; `_start_preroll` sets URI + connects one-shot about-to-finish handler; streaming-thread callback emits queued Signal; main-thread slot disconnects + bridges to stream playback; preroll error/EOS paths bridge to the same `_try_next_stream` advance; backfill non-blocking with single-flight guard; m4a title tag suppressed.
- **Gap closure (Plan 83-04):** The 83-03 slot's `_try_next_stream()` call (which cycled `set_state(NULL)` and tore down the preroll) is replaced with a true playbin3 gapless URI handoff — `pipeline.set_property("uri", aa_normalize_stream_url(stream.url))` on the still-PLAYING pipeline — with elapsed-timer seeding, force_close("preroll") analytics distinguisher, BUFFER_DURATION_S failover-timer arm, and a YouTube/Twitch scope guard that falls back to the legacy `_try_next_stream` path for async-resolution providers.
- **Tests:** 35 total Phase 83 tests across 3 files (was 31; +4 new from 83-04); all passing. Drift-guard now SLICE-ANCHORED to the `_on_preroll_about_to_finish` method body so a revert-only-the-slot regression fails loudly even with `_set_uri` retaining its own `set_property("uri", ...)`.
- **Threading:** streaming-thread callback body remains exactly one line; gapless `set_property` runs on main per qt-glib-bus-threading Rule 2.

What remains is the three live-audio UAT items above to confirm playbin3 actually hands off gaplessly on the Linux Wayland deployment target. The D-05 BLOCKER from 83-UAT is closed at the source/test level.

---

_Initial verification: 2026-05-22 (status: human_needed, score 17/17)._
_Re-verification: 2026-05-22 (after 83-UAT D-05 BLOCKER → Plan 83-04 gap closure → merge 9bbf540)._
_Re-verifier: Claude (gsd-verifier)._

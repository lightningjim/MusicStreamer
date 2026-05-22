---
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
verified: 2026-05-22T00:00:00Z
status: human_needed
score: 17/17 must-haves verified (15 D-XX + Security additions + Q3-EOS)
overrides_applied: 0
human_verification:
  - test: "Live SomaFM Beat Blender preroll plays then transitions gaplessly to deep-house stream"
    expected: "On Linux Wayland: bind Beat Blender → click Play → audible station-ID voiceover (~5–8s) followed by the deep-house stream with no audible gap. Now Playing keeps showing 'Beat Blender' throughout (D-07 metadata suppression)."
    why_human: "Real-pipeline about-to-finish handoff cannot be reliably mocked — pipeline mocks pass any `pipeline.emit(...)` call without firing handlers (MEMORY anchor: feedback_gstreamer_mock_blind_spot.md). Live audio test is the only confirmation that playbin3 + souphttpsrc + aacparse + avdec_aac actually plays the m4a preroll and hands off."
    decisions_covered: ["D-05", "D-07"]
  - test: "Seven Inch Soul (no prerolls) plays without delay"
    expected: "Bind SomaFM Seven Inch Soul → Play → immediate stream audio with NO preroll preamble, NO repeated backfill thread re-spawn (D-04 `prerolls_fetched_at IS NOT NULL + zero rows` skip-silently path)."
    why_human: "Confirms `prerolls_fetched_at` non-NULL semantics + provider gate end-to-end without requiring code-side mocks; verifies the empty-preroll skip-silently branch in `Player.play`."
    decisions_covered: ["D-04", "D-11"]
  - test: "10-minute throttle window: replay within window → NO preroll; replay after window → preroll plays again"
    expected: "Play Beat Blender → hear preroll → stop → immediately replay → confirm NO preroll on second play (D-12 throttle gate). Wait >10 minutes → replay → confirm a fresh random preroll plays."
    why_human: "Confirms in-memory `_last_preroll_played_at` timestamp + 10-minute window with real wall-clock spacing; cannot be automated without a >10-min sleep."
    decisions_covered: ["D-12"]
---

# Phase 83: SomaFM Preroll Verification Report

**Phase Goal:** At start of playing a SomaFM station, randomly select and play one of its prerolls (from `api.somafm.com/channels.json`) before the station's actual stream begins.

**Verified:** 2026-05-22
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement: PASSED (pending live audio UAT)

The shipped code path delivers the phase goal. Tracing `Player.play(station)`:

1. **Line 565** — `self._streams_queue = queue` is built first (Phase 82 preferred-stream + `order_streams`; unchanged per D-06).
2. **Lines 569–573** — provider gate (`station.provider_name == "SomaFM"`) + throttle gate (`_last_preroll_played_at is None or > 600s elapsed`).
3. **Lines 574–578** — `urls = list(getattr(station, "prerolls", []) or [])`; if non-empty, `random.choice(urls)` → `self._start_preroll(preroll_url)` → `return` (stream is NOT played yet).
4. **Line 1103 `_start_preroll`** — sets `_preroll_in_flight = True`, `_last_preroll_played_at = time.monotonic()`, connects one-shot `"about-to-finish"` handler, calls `_set_uri(preroll_url)` on playbin3.
5. **Line 1118 streaming-thread callback** — body is EXACTLY one line: `self._preroll_about_to_finish_requested.emit()` (qt-glib-bus-threading Rule 2 / T-83-13).
6. **Line 414 connect** — queued connection from class-level Signal to `_on_preroll_about_to_finish` (main thread).
7. **Line 1124 main-thread slot** — disconnects handler, clears `_preroll_in_flight`, calls `_try_next_stream()` which plays `_streams_queue[0]`.

All five mandatory wiring stages are present and correct.

---

## Per-Decision Coverage (D-01..D-15 + Security + Q3-EOS)

| Decision | Status | Evidence (file:line) |
|----------|--------|----------------------|
| **D-01** `station_prerolls` table + FK CASCADE | ✓ VERIFIED | `repo.py:153-159` CREATE TABLE; `tests/test_repo.py:1001,1142` schema + CASCADE tests pass |
| **D-02** `fetch_channels` + `import_stations` capture preroll[] | ✓ VERIFIED | `soma_import.py:244` capture; `soma_import.py:339-356` insert loop + marker; `tests/test_soma_import.py:613,696` pass |
| **D-03** Lazy on-demand backfill | ✓ VERIFIED | `player.py:579-590` schedules `_preroll_backfill_worker` only if `prerolls_fetched_at IS NULL` AND not single-flight; `tests/test_player.py:923 test_preroll_backfill_scheduled_when_unfetched` passes |
| **D-04** `prerolls_fetched_at` marker semantics | ✓ VERIFIED | `repo.py:307` ALTER; `soma_import.py:356` always-set on import; `player.py:1393` always-set on backfill; `tests/test_soma_import.py:749 test_import_sets_prerolls_fetched_at_for_empty_preroll` (canonical name verbatim per VALIDATION.md) passes |
| **D-05** playbin3 about-to-finish gapless handoff | ✓ VERIFIED | `player.py:269,344,414-416,1103-1135` — Signal declaration, EOS bus connection, queued-connection wire, `_start_preroll` + streaming-thread callback (one-line emit) + main-thread slot disconnect-and-`_try_next_stream`; `tests/test_player.py:813 test_preroll_sets_uri_and_connects_handler` passes |
| **D-06** `_streams_queue` not mutated by preroll | ✓ VERIFIED | `player.py:565` queue built BEFORE preroll gate; preroll branch hits `return` at line 578 leaving queue untouched; `tests/test_player.py:900 test_preroll_does_not_pollute_streams_queue` passes |
| **D-07** Suppress preroll m4a title tag | ✓ VERIFIED | `player.py:787` `if self._preroll_in_flight: return` early-return inside `_on_gst_tag`; `tests/test_player.py:1024 test_title_tag_suppressed_during_preroll` passes |
| **D-08** User controls behave normally during preroll | ✓ VERIFIED | `play_stream` (line 594, direct-play path) and `pause`/`stop`/`resume` untouched — flag is only set/cleared in `Player.play` + `_on_preroll_about_to_finish` + error/EOS recovery paths; `tests/test_player.py:1094 test_preroll_in_flight_pause_does_not_clear_flag` passes |
| **D-09** Preroll failure → silent skip → `_try_next_stream` | ✓ VERIFIED | `player.py:738-751` `_handle_gst_error_recovery` preroll-aware branch disconnects handler, clears flag, calls `_try_next_stream()`; `tests/test_player.py:1055 test_preroll_bus_error_advances_to_stream` passes |
| **D-10** Failover after preroll uses standard queue advance | ✓ VERIFIED | `_try_next_stream` is untouched; preroll already consumed for the play call; `tests/test_player.py:1117 test_streams_queue_failover_after_preroll_handoff` passes |
| **D-11** Provider gate — `"SomaFM"` CamelCase literal | ✓ VERIFIED | `player.py:570` non-comment literal `"SomaFM"` (drift-guard pinned); `tests/test_player.py:997 test_non_somafm_provider_bypasses_preroll` passes |
| **D-12** Throttle gate — 10-min global window, timestamp at START | ✓ VERIFIED | `player.py:571-572` throttle check; `player.py:1112` timestamp set INSIDE `_start_preroll` (preroll START, not handoff); `tests/test_player.py:851 test_throttle_window_suppresses_preroll` + `878 test_throttle_timestamp_set_on_start` pass |
| **D-13** Background fetch race — non-blocking | ✓ VERIFIED | `player.py:586-590` daemon `threading.Thread`, gate falls through to `_try_next_stream()` at line 592; `tests/test_player.py:966 test_backfill_non_blocking` passes |
| **D-14** Source-grep drift-guard | ✓ VERIFIED | `tests/test_player.py:1193 test_phase_83_preroll_drift_guard` pins both `"SomaFM"` and `_last_preroll_played_at` after stripping comment lines via `re.sub(r"^\s*#.*$", "", ln)` (stronger than the `lstrip startswith #` baseline per Pitfall 8); passes |
| **D-15** Schema migration (forward-only, idempotent) | ✓ VERIFIED | `repo.py:153` CREATE TABLE IF NOT EXISTS station_prerolls; `repo.py:305-311` ALTER TABLE ... ADD COLUMN prerolls_fetched_at wrapped in try/except OperationalError; `tests/test_repo.py:1031 test_db_init_is_idempotent_for_phase_83_additions` passes |
| **Security T-83-01** URL scheme validation in `Repo.insert_preroll` | ✓ VERIFIED | `repo.py:439-442` rejects non-`http(s)://` URLs with ValueError; `tests/test_repo.py:1070 test_insert_preroll_rejects_non_http_scheme` passes |
| **Security T-83-02** Per-call cap of 50 at all 3 layers | ✓ VERIFIED | Repo layer: `repo.py:443-446` ValueError on position > 50. Importer layer: `soma_import.py:344-350` truncates + `_log.warning`. Backfill worker layer: `player.py:1380-1381` `preroll_urls[:50]` double-defense. `tests/test_repo.py:1080` + `tests/test_soma_import.py:842` pass |
| **Security T-83-10** Single-flight backfill guard | ✓ VERIFIED | `player.py:460` `_backfill_in_flight: set[int]`; line 581 gate (`station.id not in self._backfill_in_flight`); line 585 add; line 1402 discard in `finally`. `tests/test_player.py:923 test_preroll_backfill_scheduled_when_unfetched` asserts station_id added to set |
| **Q3-EOS** Malformed-preroll EOS bridge | ✓ VERIFIED | `player.py:344` `bus.connect("message::eos", self._on_gst_eos_during_preroll)`; handler at line 1137-1164 gates on `if not self._preroll_in_flight: return` AND emits queued `_try_next_stream_requested.emit()` (NEVER set_property from streaming thread); `tests/test_player.py:1156 test_preroll_eos_without_about_to_finish_advances_to_stream` passes |

**Score: 17/17 (15 decisions + 3 security/Q3 truths) all VERIFIED.**

---

## Test Counts

| Test File | New Tests | All Pass |
|-----------|-----------|----------|
| `tests/test_repo.py` | 10 (lines 1001–1142) | ✓ |
| `tests/test_soma_import.py` | 8 (lines 613–903) | ✓ |
| `tests/test_player.py` | 13 (lines 813–1214) | ✓ |
| **Total** | **31** | ✓ |

### Test runs

```
$ uv run pytest tests/test_repo.py tests/test_soma_import.py tests/test_player.py -q
149 passed, 1 warning in 2.55s
```

```
$ uv run pytest -q --tb=line
1727 passed, 1 skipped, 2 failed
```

The 2 full-suite failures are **PRE-EXISTING and NOT introduced by Phase 83** (as declared by the verification context):
- `tests/test_main_window_integration.py::test_hamburger_menu_actions` — pre-existing UI test issue (fails on pre-Phase-83 commit `5a0fdd6`).
- `tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt` — Windows-only test; skips/fails on Linux.

Neither failure touches preroll, SomaFM, repo, or player code paths.

---

## Threat-Mitigation Literal Audit

Plans 83-01..03 declare 15 `T-83-NN` threat IDs. The following are searchable in shipped code/tests by literal label:

| Threat ID | Literal present in shipped code? | Mitigation code present? | Status |
|-----------|----------------------------------|--------------------------|--------|
| T-83-01 (URL-scheme validation) | ✓ `repo.py:427`, `tests/test_repo.py:1071` | ✓ `repo.py:439-442` | VERIFIED |
| T-83-02 (DoS cap of 50) | ✓ `repo.py:433`, `soma_import.py:339,347`, `player.py:1381`, `tests/test_repo.py:1081`, `tests/test_soma_import.py:843` | ✓ all 3 layers | VERIFIED |
| T-83-03 (SQLi) | ✓ `repo.py:436` comment | ✓ parameterized query | VERIFIED |
| T-83-04 (preroll URL information disclosure) | ✗ no literal in code | n/a — "accept" mitigation; public CDN URLs by design | INFORMATIONAL (audit-label gap only; behaviorally correct) |
| T-83-05 (lost provenance) | ✗ no literal in code | n/a — "accept" mitigation | INFORMATIONAL (audit-label gap only; behaviorally correct) |
| T-83-06 (giant preroll array at import) | ✗ no literal — uses T-83-02 label instead | ✓ `soma_import.py:344-350` (same code path as T-83-02) | VERIFIED (mitigation code present; threat-ID label deduplicated to T-83-02) |
| T-83-07 (file:// URL via importer) | ✗ no literal | ✓ relies on T-83-01 at Repo layer (transferred) | VERIFIED (mitigation code present) |
| T-83-08 (log information disclosure) | ✗ no literal | n/a — "accept" | INFORMATIONAL (audit-label gap only) |
| T-83-09 (set_prerolls_fetched_at availability) | ✗ no literal | ✓ Pitfall 4 ordering (within rollback window) | VERIFIED (mitigation code present) |
| T-83-10 (single-flight backfill guard) | ✓ `player.py:454,460,584,1365`, `tests/test_player.py:961` | ✓ `_backfill_in_flight` set | VERIFIED |
| T-83-11 (file:// URL via Player backfill) | ✗ no literal | ✓ `player.py:1388-1390` catches ValueError from T-83-01 | VERIFIED (mitigation code present) |
| T-83-12 (m4a TAG → Now Playing leak) | ✗ no literal | ✓ `player.py:787` early-return | VERIFIED (mitigation code present) |
| T-83-13 (streaming-thread property write) | ✗ no literal | ✓ `player.py:1118-1122` one-line emit-only body | VERIFIED (mitigation code present) |
| T-83-14 (hostile m4a decoder attack) | ✗ no literal | n/a — "accept" | INFORMATIONAL (audit-label gap only) |
| T-83-15 (silent backfill failures audit) | ✗ no literal | ✓ `player.py:1397` `_log.warning` | VERIFIED (mitigation code present; logged via `_log.warning`) |

**Summary:** Of the 15 declared T-83-NN IDs, only 4 (T-83-01, -02, -03, -10) appear as literals in shipped source/tests. The remaining 11 have correct mitigation code present and tested where applicable, but lack the textual `T-83-NN` label. This is an audit-traceability nit, not a behavioral gap — every "mitigate" threat has corresponding code, and the "accept" threats are intentional non-implementations by design. Documented here as **WARNING (informational)** for future reference; does not block phase closure.

---

## Manual UAT — Deferred to HUMAN-UAT.md

Per Phase 82 precedent, these 3 items cannot be automated. They are captured in this VERIFICATION.md frontmatter under `human_verification:` and 83-VALIDATION.md §"Manual-Only Verifications" lines 78-80 already enumerates them verbatim:

1. **Beat Blender preroll → stream gapless handoff** (D-05, D-07) — live audio test.
2. **Seven Inch Soul no-preroll skip-silently** (D-04, D-11) — confirms empty-preroll non-rescheduling.
3. **10-min throttle behavior** (D-12) — replay-within-window NO preroll; replay-after-window YES preroll.

Recommend the user open `83-HUMAN-UAT.md` and record outcomes (file does not yet exist; follow Phase 82 shape).

---

## Gaps / Followups

**No blocking gaps.** All 17 must-haves are verified in shipped code with passing automated tests.

**Audit-trace nits (informational, NON-blocking):** 11 of 15 T-83-NN threat IDs do not appear as text literals in shipped source/tests (their mitigation code IS present and tested). Future audits seeking `grep -rn "T-83-12"` etc. will come up empty. Consider adding a short comment block at the relevant code site for each (e.g. `# T-83-12 mitigation`) on the next maintenance pass.

**Followup recommended:** Create `83-HUMAN-UAT.md` (Phase 82 shape) and capture the 3 manual UAT items above before closing the phase.

---

## Summary

The shipped Phase 83 code achieves the phase goal end-to-end at the source level:
- **Schema + Repo (Plan 83-01):** `station_prerolls` table, `prerolls_fetched_at` column, 3 new Repo methods with URL-scheme + DoS guards, 4 Station-builder eager-loads.
- **Importer (Plan 83-02):** `fetch_channels` returns `preroll_urls` per channel; `import_stations` inserts rows + sets marker (even for empty preroll lists, per D-04) inside the rollback window.
- **Player (Plan 83-03):** `Player.play` gates on provider + throttle + DB lookup; `_start_preroll` sets URI + connects one-shot about-to-finish handler; streaming-thread callback emits queued Signal; main-thread slot disconnects + `_try_next_stream()`; preroll error/EOS paths bridge to the same `_try_next_stream` advance; backfill is non-blocking with single-flight guard; m4a title tag is suppressed.
- **Tests:** 31 new tests across 3 files, all passing; full suite at 1727 passing (the 2 failures are pre-existing and unrelated).
- **Drift-guard:** pins `"SomaFM"` literal + `_last_preroll_played_at` token in non-comment text of `player.py`, with re.sub stripping (stronger than `lstrip startswith #`).
- **Q3-EOS:** `message::eos` bus handler connected, gated on `_preroll_in_flight`, emits queued Signal (never sets pipeline properties from streaming thread).

What remains is live-audio UAT to confirm playbin3 actually hands off gaplessly with MusicStreamer's buffer-flagged pipeline on the deployment target (Linux Wayland).

---

_Verified: 2026-05-22_
_Verifier: Claude (gsd-verifier)_

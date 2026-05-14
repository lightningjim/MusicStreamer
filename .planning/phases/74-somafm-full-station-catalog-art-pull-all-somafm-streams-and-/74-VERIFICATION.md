---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
verified: 2026-05-14T00:00:00Z
status: gaps_found
score: 15/17
overrides_applied: 0
gaps:
  - truth: "D-06 re-import idempotence toast — clicking 'Import SomaFM' a second time emits 'SomaFM import: no changes' toast (SOMA-11, UAT-07)"
    status: failed
    reason: "_SomaImportWorker.finished = Signal(int, int) shadows QThread.finished (the no-arg C++ signal auto-emitted when run() returns). Connecting worker.finished to _on_soma_import_done wires to Signal(int, int), but PySide6 dispatches QThread::finished() (no-arg) at thread exit — causing a TypeError inside the Qt event dispatcher that is swallowed silently, producing no toast. Confirmed by live UAT-07 failure. Code review CR-02 + WR-04 document the root cause."
    artifacts:
      - path: "musicstreamer/ui_qt/main_window.py"
        issue: "Line 159: 'finished = Signal(int, int)' on _SomaImportWorker shadows QThread.finished. Line 1506: 'self._soma_import_worker.finished.connect(self._on_soma_import_done)' connects to the shadowed Signal(int, int) rather than naming it distinctly (e.g. import_finished). Same latent bug exists in _GbsImportWorker (line 132), _ExportWorker (line 89), _ImportPreviewWorker (line 107)."
    missing:
      - "Rename _SomaImportWorker.finished to import_finished (Signal(int, int)) and update the connect call at line 1506 and the emit at line 172 to match."
      - "Add a RED qtbot regression test: mock import_stations to return (inserted=0, skipped=46) and assert the toast text is exactly 'SomaFM import: no changes'."
      - "Optionally apply the same rename to _GbsImportWorker, _ExportWorker, _ImportPreviewWorker to clear the latent bug project-wide."

  - truth: "Stored bitrate_kbps correctly reflects the actual stream bitrate (SOMA-02, SOMA-03 / CR-01 / UAT Finding F-01)"
    status: failed
    reason: "_TIER_BY_FORMAT_QUALITY hardcodes bitrate_kbps=128 for (mp3, highest). There is no URL-slug parser in soma_import.py (no 'import re', no regex). SomaFM channels like Synphaera Radio publish a 256 kbps MP3 stream at ice2.somafm.com/synphaera-256-mp3, but the stored bitrate_kbps is 128. This corrupts Phase 70 hi-res indicator sorting and the tier quality map (hi/hi2/med/low) for any non-128 MP3 channel. Confirmed by UAT Finding F-01 and code review CR-01."
    artifacts:
      - path: "musicstreamer/soma_import.py"
        issue: "Lines 62-67: _TIER_BY_FORMAT_QUALITY[('mp3', 'highest')] returns bitrate_kbps=128 unconditionally. Lines 131-138: relay URL slug (e.g. '-256-mp3') is never parsed for bitrate. No _bitrate_from_url helper or regex exists."
      - path: "tests/test_soma_import.py"
        issue: "Test stubs (_make_resolve_pls_stub, _make_any_resolve_pls_stub) return URLs with correct bitrate in the slug but the assertion in test_fetch_channels_maps_four_tiers_twenty_streams_per_channel (line 167) only checks (codec, quality, bitrate_kbps) multiset against the table default of 128 — the test does not catch the wrong-bitrate scenario."
    missing:
      - "Add _bitrate_from_url(url, default) helper in soma_import.py using re.compile(r'-(\\d+)-(?:mp3|aac|aacp)\\b') and override the table default per stream in fetch_channels."
      - "Add a RED unit test feeding a PLS body with 'synphaera-256-mp3' URLs and asserting the stored bitrate_kbps is 256 (not 128)."
---

# Phase 74: SomaFM Full-Station Catalog Import — Verification Report

**Phase Goal:** Bulk-import all ~46 SomaFM channels into the library as real Station rows (provider_name="SomaFM") with 4 quality tiers × 5 ICE relays = 20 streams per channel + per-channel logos, via a hamburger-menu "Import SomaFM" action that mirrors the AudioAddict + GBS.FM importer UX (toast-driven, worker-threaded, dedup-by-URL, idempotent re-import as full no-op on URL match).
**Verified:** 2026-05-14
**Status:** gaps_found — 2 blockers
**Re-verification:** No — initial verification

---

## Step 0: Previous Verification

No previous VERIFICATION.md found. Initial mode.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SOMA-01: Every imported SomaFM station has provider_name="SomaFM" | VERIFIED | soma_import.py:193 `provider_name="SomaFM"` literal; UAT-09 PASS (DB query confirmed); test_import_three_channels_full_path_creates_stations_and_streams PASS |
| 2 | SOMA-02: 4-tier × 5-relay = 20 streams per channel with correct (codec, quality, bitrate_kbps) tuples | FAILED (BLOCKER) | _TIER_BY_FORMAT_QUALITY hardcodes bitrate_kbps=128 for mp3/highest; synphaera-256-mp3 and other 256 kbps channels stored as 128 (UAT F-01, CR-01). UAT-10 showed correct stream counts (20 per channel) but wrong bitrate metadata. |
| 3 | SOMA-03: Position = tier_base * 10 + relay_index | VERIFIED | soma_import.py:135 formula confirmed; test_fetch_channels_position_numbering_tier_base_times_ten PASS |
| 4 | SOMA-04: aacp stores codec as "AAC" not "AAC+" | VERIFIED | _TIER_BY_FORMAT_QUALITY uses "AAC" for aacp tiers; test_aacp_codec_maps_to_AAC_not_aacplus + test_no_aacplus_codec_literal_in_source both PASS |
| 5 | SOMA-05: Stored URLs are ice*.somafm.com direct URLs, not .pls URLs | VERIFIED | _resolve_pls returns parse_playlist entries; test_resolve_pls_returns_all_five_direct_urls PASS (caveat: fallback returns [pls_url] on error — WR-03, not a blocker for this requirement as the success path is correct) |
| 6 | SOMA-06: Dedup-by-URL skips whole channel if any stream URL exists | VERIFIED | soma_import.py:185-188 any() check; test_import_skips_when_url_exists PASS |
| 7 | SOMA-07: Re-import is full no-op (inserted=0, skipped=N) on all-URL-match | VERIFIED | Code path confirmed via test_import_skips_when_url_exists; dedup logic correct for the import_stations function itself |
| 8 | SOMA-08: Logo failure is non-fatal; update_station_art not called on failure | VERIFIED | _download_logo wraps in try/except Exception: pass; test_logo_failure_is_non_fatal PASS |
| 9 | SOMA-09: Per-channel exception isolation; malformed channel only increments skipped | VERIFIED | import_stations for-loop wrapped in try/except; test_per_channel_exception_skips_only_that_channel PASS |
| 10 | SOMA-10: "Import SomaFM" QAction in hamburger menu, wired via bound method | VERIFIED | main_window.py:233-234 `act_soma_import = self._menu.addAction("Import SomaFM")` + bound method connect; test_import_soma_menu_entry_exists + test_no_self_capturing_lambda_in_soma_action both PASS |
| 11 | SOMA-11: Toast verbatim strings on click / done / error (including re-import "no changes") | FAILED (BLOCKER) | Click toast ("Importing SomaFM…") VERIFIED via UAT-01 PASS. "N stations added" toast VERIFIED via UAT-03 PASS. Re-import "no changes" toast FAILED — UAT-07: no toast emitted on second import. Root cause: _SomaImportWorker.finished shadows QThread.finished (CR-02/WR-04); QThread::finished() (no-arg) fires at thread exit, dispatches into _on_soma_import_done with wrong arity, TypeError swallowed by Qt. |
| 12 | SOMA-12: Worker stored in _soma_import_worker on click; reset to None on done/error | VERIFIED | main_window.py:1505,1517,1523; test_import_soma_triggers_worker_start_and_retains_reference PASS; done/error slots reset confirmed in code |
| 13 | SOMA-13/14: User-Agent literal "MusicStreamer/" and GitHub URL in soma_import.py | VERIFIED | soma_import.py:49-51; test_user_agent_literal_present_in_source PASS |
| 14 | SOMA-15: No "AAC+" literal in _TIER_BY_FORMAT_QUALITY | VERIFIED | grep confirms no "AAC+" in non-comment source; test_no_aacplus_codec_literal_in_source PASS |
| 15 | SOMA-16: musicstreamer/__main__.py registers soma_import logger at INFO | VERIFIED | __main__.py:236 `logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)`; test_soma_import_logger_registered PASS |
| 16 | SOMA-17: Network failure produces clean error toast (not partial import) | VERIFIED | _SomaImportWorker.run() wraps fetch_channels + import_stations in try/except; error signal emits str(exc); _on_soma_import_error produces truncated toast; test_import_soma_error_truncates_message_at_80_chars PASS |
| 17 | SOMA-10+12 wiring: hamburger click → _SomaImportWorker → fetch_channels + import_stations → DB writes → station tree refresh | VERIFIED (with caveat) | Code path verified: main_window.py _on_soma_import_clicked creates worker, worker.run calls soma_import.fetch_channels + import_stations, _on_soma_import_done calls _refresh_station_list; UAT-01/02/03 PASS for initial import. Caveat: re-import toast suppressed by QThread.finished shadowing (G-01). |

**Score: 15/17 truths verified (2 BLOCKER failures)**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/soma_import.py` | Public API: fetch_channels, import_stations, _resolve_pls, _TIER_BY_FORMAT_QUALITY, _USER_AGENT | VERIFIED | File exists, 281 lines, all public API present. Contains both required UA literals. Per-channel try/except in import_stations. ThreadPoolExecutor(max_workers=8) for logos. |
| `musicstreamer/ui_qt/main_window.py` | _SomaImportWorker class + act_soma_import + 3 handler methods + _soma_import_worker attribute | VERIFIED (with gap) | All required code exists at correct locations. Gap: finished = Signal(int, int) shadows QThread.finished — causes toast suppression on re-import (G-01). |
| `musicstreamer/__main__.py` | soma_import logger registration at INFO | VERIFIED | Line 236 confirmed by grep and test_soma_import_logger_registered. |
| `tests/test_soma_import.py` | 11 test functions covering SOMA-01..09+15 | VERIFIED | All 11 tests exist and PASS (26 total tests in the three test files: 7+11+8 = 26, all PASS). |
| `tests/test_main_window_soma.py` | 7 test functions covering SOMA-10..12 | VERIFIED | All 7 tests exist and PASS. Note: test_import_soma_done_zero_inserted_emits_no_changes_toast PASSES because it calls _on_soma_import_done directly, bypassing the QThread.finished signal shadowing that triggers in the live run. |
| `tests/test_constants_drift.py` | 2 new drift-guard functions | VERIFIED | test_soma_import_logger_registered + test_soma_nn_requirements_registered both PASS. |
| `tests/fixtures/soma_channels_3ch.json` | 3-channel canonical fixture | VERIFIED | Exists; python validation confirms 3 channels each with 4 playlists. |
| `tests/fixtures/soma_channels_with_dedup_hit.json` | 1-channel dedup fixture | VERIFIED | Exists; python validation confirms 1 channel with 4 playlists. |
| `.planning/REQUIREMENTS.md` | SOMA-01..SOMA-17 rows + Traceability + Coverage 55 total | VERIFIED | All 17 SOMA-NN checklist rows present; Traceability table has 17 rows for Phase 74; Coverage block reads "v2.1 requirements: 55 total" and "Pending: 35". |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| musicstreamer/soma_import.py | musicstreamer.playlist_parser.parse_playlist | import inside _resolve_pls | VERIFIED | Line 88: `from musicstreamer.playlist_parser import parse_playlist` inside _resolve_pls body |
| musicstreamer/soma_import.py | musicstreamer.assets.copy_asset_for_station | logo persistence | VERIFIED | Line 30: `from musicstreamer.assets import copy_asset_for_station`; used at line 263 |
| musicstreamer/soma_import.py | musicstreamer.repo.Repo + db_connect | per-thread Repo for logo | VERIFIED | Lines 31, 264: `Repo(db_connect())` in _download_logo |
| musicstreamer/ui_qt/main_window.py::_SomaImportWorker.run | musicstreamer.soma_import.fetch_channels + import_stations | QThread.run body | VERIFIED | Lines 169-171: soma_import.fetch_channels() and soma_import.import_stations(channels, repo) |
| act_soma_import.triggered | MainWindow._on_soma_import_clicked | QAction.triggered.connect(bound_method) | VERIFIED | Line 234: `act_soma_import.triggered.connect(self._on_soma_import_clicked)` |
| _SomaImportWorker.finished | MainWindow._on_soma_import_done | Signal connect | FAILED (BLOCKER) | Signal named "finished" (line 159) shadows QThread.finished. Connection at line 1506 wires to Signal(int, int), but QThread::finished() (no-arg C++ signal) fires on thread completion — arity mismatch TypeError swallowed by Qt, no toast emitted on re-import. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| _on_soma_import_done | inserted: int | _SomaImportWorker.finished.emit(int(inserted), int(skipped)) | Yes, for first import | HOLLOW on re-import — Signal shadowing causes Qt to discard the slot call on second run; toast never fires |
| fetch_channels | bitrate_kbps | _TIER_BY_FORMAT_QUALITY dict lookup | Hardcoded 128 for mp3/highest — does not reflect URL slug | STATIC for MP3 256 kbps channels |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 11 soma_import tests pass | `uv run --with pytest pytest tests/test_soma_import.py -v` | 11 passed | PASS |
| All 7 main_window soma tests pass | `uv run --with pytest pytest tests/test_main_window_soma.py -v` | 7 passed | PASS |
| Both drift-guard tests pass | `uv run --with pytest pytest tests/test_constants_drift.py -v` | 8 passed (incl. 2 new) | PASS |
| REQUIREMENTS.md has 17 SOMA rows | `grep -c "^- \[ \] \*\*SOMA-" .planning/REQUIREMENTS.md` | 17 | PASS |
| soma_import logger registration present | `grep -F 'logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)' musicstreamer/__main__.py` | 1 match | PASS |
| No "AAC+" in non-comment soma_import.py | `grep -v '^\s*#' musicstreamer/soma_import.py \| grep '"AAC+"'` | (empty) | PASS |
| No `import re` / bitrate URL parser | `grep "import re" musicstreamer/soma_import.py` | (empty) | FAIL — confirms G-02: no bitrate parser |
| _SomaImportWorker.finished signal name | `grep "finished = Signal" musicstreamer/ui_qt/main_window.py` | `finished = Signal(int, int)` at line 159 | FAIL — confirms G-01: shadows QThread.finished |

---

### Probe Execution

Step 7c: SKIPPED — no probe scripts declared for this phase (`scripts/*/tests/probe-*.sh` not found; phase is a Python library import feature without a conventional probe script).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SOMA-01 | 74-01, 74-02 | provider_name = "SomaFM" | SATISFIED | soma_import.py:193 literal; test passes; UAT-09 PASS |
| SOMA-02 | 74-01, 74-02 | 4-tier × 5-relay stream scheme with correct bitrate_kbps tuples | BLOCKED | Bitrate hardcoded 128 for mp3/highest; G-02 / CR-01 |
| SOMA-03 | 74-01, 74-02 | position = tier_base * 10 + relay_index | SATISFIED | soma_import.py:135; test passes |
| SOMA-04 | 74-01, 74-02 | aacp → codec "AAC" not "AAC+" | SATISFIED | _TIER_BY_FORMAT_QUALITY; tests pass |
| SOMA-05 | 74-01, 74-02 | Stored URLs are ice*.somafm.com, not .pls | SATISFIED | _resolve_pls returns parse_playlist entries; test passes |
| SOMA-06 | 74-01, 74-02 | Dedup-by-URL skip | SATISFIED | any() check in import_stations; test passes |
| SOMA-07 | 74-01, 74-02 | Full no-op on re-import | SATISFIED (import logic) | import_stations logic is correct; dedup works. Toast NOT emitted — covered by SOMA-11 gap |
| SOMA-08 | 74-01, 74-02 | Logo failure non-fatal | SATISFIED | try/except in _download_logo; test passes |
| SOMA-09 | 74-01, 74-02 | Per-channel exception isolation | SATISFIED | try/except in import_stations loop; test passes |
| SOMA-10 | 74-01, 74-03 | Hamburger entry, bound method | SATISFIED | act_soma_import wired to bound method; tests pass |
| SOMA-11 | 74-01, 74-03 | Toast verbatim strings (all 3 cases) | BLOCKED | Click and "N added" toasts work. "no changes" toast suppressed by QThread.finished shadowing; G-01 / CR-02 / WR-04 |
| SOMA-12 | 74-01, 74-03 | Worker retention in _soma_import_worker | SATISFIED | main_window.py:1505,1517,1523; test passes |
| SOMA-13 | 74-01, 74-02 | User-Agent literal in outbound requests | SATISFIED | _USER_AGENT built from literals; test passes |
| SOMA-14 | 74-01, 74-02 | Source-grep gate for UA | SATISFIED | Both UA substrings in soma_import.py; test passes |
| SOMA-15 | 74-01, 74-02 | Source-grep gate: no AAC+ in _TIER_BY_FORMAT_QUALITY | SATISFIED | Confirmed by grep and test |
| SOMA-16 | 74-01, 74-03 | Logger registration in __main__.py | SATISFIED | __main__.py:236; drift-guard test passes |
| SOMA-17 | 74-01, 74-02 | Network failure → clean error toast | SATISFIED | Worker exception handler emits error signal; test passes |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| musicstreamer/ui_qt/main_window.py | 159 | `finished = Signal(int, int)` shadows `QThread.finished` | BLOCKER | QThread::finished() (no-arg) fires at thread exit and mismatches the slot arity, TypeError swallowed by Qt, toast never emitted on re-import. Root cause of UAT-07 FAIL. |
| musicstreamer/soma_import.py | 63 | `"bitrate_kbps": 128` hardcoded for mp3/highest | BLOCKER | All MP3-highest SomaFM streams stored as 128 kbps regardless of actual bitrate (256 kbps for Synphaera, ~192 for Groove Salad). Corrupts Phase 70 hi-res sort and stream quality labels. |
| musicstreamer/ui_qt/main_window.py | 132 | `_GbsImportWorker.finished = Signal(int, int)` same shadowing pattern | WARNING | Latent bug; GBS is rarely re-imported so has not manifested, but identical root cause. |
| musicstreamer/ui_qt/main_window.py | 89, 107 | `_ExportWorker.finished = Signal(str)`, `_ImportPreviewWorker.finished = Signal(object)` same shadowing | WARNING | Latent; affects export and import-preview workers. |
| musicstreamer/soma_import.py | 92-94 | `return [pls_url]` fallback in _resolve_pls returns the input PLS URL as a relay URL | WARNING | On PLS fetch failure, the stored stream URL is the .pls URL itself (unplayable); breaks dedup correctness on re-import of a previously-failed import (WR-03 / CR-02) |
| musicstreamer/soma_import.py | 271-272 | `except Exception: pass` in _download_logo | WARNING | No log line on logo failure; zero diagnostic data when station art fails (WR-01) |

---

### Human Verification Required

No additional human verification items are needed. UAT-07 (re-import toast) failed programmatically and is accounted for in G-01. UAT-05 (logos render) shows "SOMA FM live ones have the placeholder" per the user's note — this is ambiguous but the user ticked [X] and the import logic (station + streams inserted, logo download async) is confirmed working. UAT-06 (playback) confirmed by user. No further human items needed beyond the two gap closures.

---

## Gaps Summary

Two confirmed blockers prevent phase closure.

**G-01 (SOMA-11 / UAT-07):** Re-import emits no toast ("SomaFM import: no changes" never appears). Root cause: `_SomaImportWorker.finished = Signal(int, int)` shadows `QThread.finished`. When the thread run() completes, Qt's C++ layer auto-emits `QThread::finished()` with no arguments. PySide6 dispatches this into the slot `_on_soma_import_done(inserted, skipped)` which expects 2 ints — a `TypeError` is raised inside the Qt event dispatcher and silently swallowed. The `_on_soma_import_done` slot is correctly implemented (test_import_soma_done_zero_inserted_emits_no_changes_toast passes because it calls the slot directly). Fix: rename the signal to `import_finished` on `_SomaImportWorker` and update the emit and connect calls.

**G-02 (SOMA-02 / UAT F-01):** Bitrate metadata is wrong for non-128 SomaFM MP3 streams. `_TIER_BY_FORMAT_QUALITY[("mp3", "highest")]` hardcodes `bitrate_kbps=128`. The SomaFM catalog has channels (Synphaera Radio: 256 kbps; Groove Salad: ~192 kbps) where the MP3-highest tier is not 128 kbps. The bitrate is encoded in the relay URL slug (`-256-mp3`, `-192-mp3`) but `soma_import.py` has no `import re` and no URL-slug parser. Fix: add `_bitrate_from_url(url, default)` regex helper and override the table default per stream in `fetch_channels`.

Both gaps are scoped to `musicstreamer/soma_import.py` and `musicstreamer/ui_qt/main_window.py`. Neither requires changes to the test fixture infrastructure (though new unit tests are required for both). Use `/gsd-plan-phase 74 --gaps` to plan gap closure.

---

_Verified: 2026-05-14_
_Verifier: Claude (gsd-verifier)_

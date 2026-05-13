---
phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio
verified: 2026-05-13T01:30:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/9 must-haves verified (3 gaps from code review CR-01/CR-02/CR-03)
  gaps_closed:
    - truth: "User can unlink a manually-linked sibling via the × button on its chip"
      resolution: "CR-02 fix landed in commit 547b3ec. EditStationDialog._refresh_siblings (musicstreamer/ui_qt/edit_station_dialog.py:714-726) now builds `aa_ids` first and skips manual chips for station_ids already present in `aa_ids` — AA-wins precedence matching merge_siblings semantics (musicstreamer/url_helpers.py:265-276) used by NowPlayingPanel. Both surfaces render identical chip variants for the AA+manual collision. Two new regression tests added in tests/test_edit_station_dialog.py (test_aa_and_manual_collision_renders_as_aa_chip_no_x, test_aa_and_manual_collision_matches_merge_siblings_semantics) — both PASSED. UAT Test 5 documented this collision case is now unreachable through the UI because CR-03's AA exclusion in AddSiblingDialog blocks the construction path; verifier accepted UAT skip with automation evidence."
    - truth: "ZIP export/import round-trip correctly persists sibling links across machines via station NAMES"
      resolution: "CR-01 fix landed in commit a8a0336. settings_export.commit_import (musicstreamer/settings_export.py:376-419) now builds `key_to_id: dict[(name, provider_name), id]` from `LEFT JOIN stations + providers` rather than `name → id`. Editing-station lookups use the full (name, provider) tuple. For sibling-name resolution (the ZIP carries only names), searches every provider bucket — links only when exactly one match exists; multi-match cases silently drop per D-07 (ambiguous-resolution). `ambiguous_keys: set` defensively handles same-(name,provider) duplicates. New regression test test_siblings_round_trip_with_cross_provider_duplicate_names in tests/test_settings_export.py seeds 4 stations across 2 providers with cross-provider duplicate names and asserts no cross-pollination of sibling rows — PASSED."
    - truth: "AddSiblingDialog picker exclusion set correctly reflects the station's current state during editing"
      resolution: "CR-03 fix landed in commit 710645c. AddSiblingDialog.__init__ (musicstreamer/ui_qt/add_sibling_dialog.py:73-87) gains optional `live_url: Optional[str]` parameter. _repopulate_station_list (lines 283-288) prefers the live URL when provided (None→fallback, ''→honored). EditStationDialog._on_add_sibling_clicked (musicstreamer/ui_qt/edit_station_dialog.py:893-898) passes `live_url=self.url_edit.text().strip()`. Three new regression tests added in tests/test_add_sibling_dialog.py (test_live_url_drives_aa_exclusion, test_stale_url_no_longer_drives_aa_exclusion, test_live_url_omitted_falls_back_to_streams) — all PASSED."
  gaps_remaining: []
  regressions: []
human_verification: []
---

# Phase 71: Sister Station Expansion — Verification Report

**Phase Goal:** Add ability to link manually-chosen sister stations to a current station (complementing Phase 51's auto-detected AA siblings), with persistence via a new `station_siblings` table, ZIP round-trip via station NAMES (forward-compat), and a chip-row UI in EditStationDialog with `+ Add sibling` picker and `×` unlink controls.

**Verified:** 2026-05-13T01:30:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (8 fix commits + 1 UAT commit since 2026-05-12T23:55:00Z)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | New `station_siblings` SQLite table with CHECK(a_id < b_id), UNIQUE(a_id, b_id), double ON DELETE CASCADE | VERIFIED | musicstreamer/repo.py:66-73 contains the CREATE TABLE IF NOT EXISTS block as specified by D-05/D-06/D-08. `pytest tests/test_station_siblings.py::test_schema_create_with_check_unique_cascade` PASSED. db_init idempotency + CASCADE tests PASSED. |
| 2 | Repo CRUD: add_sibling_link / remove_sibling_link / list_sibling_links with (min,max) normalization + INSERT OR IGNORE idempotence + UNION symmetric lookup | VERIFIED | musicstreamer/repo.py:235-258. All 6 CRUD tests in test_station_siblings.py PASSED. |
| 3 | Pure helpers `find_manual_siblings` + `merge_siblings` in url_helpers.py, mirroring find_aa_siblings shape | VERIFIED | musicstreamer/url_helpers.py:237-276. Tuple shape, self-exclusion, alphabetical sort, AA-wins dedup all asserted by the 4 helper tests in test_station_siblings.py. |
| 4 | EditStationDialog chip row with `+ Add sibling` button + × on manual chips + plain AA chips | VERIFIED | musicstreamer/ui_qt/edit_station_dialog.py:629-735 (_refresh_siblings with AA-wins dedup), 728-735 (+ Add sibling btn always-last), 737+ (chip construction helpers via functools.partial per WR-06). All chip-row tests in test_edit_station_dialog.py PASSED including the two new CR-02 regression tests. |
| 5 | AddSiblingDialog two-step picker (provider QComboBox → filtered QListWidget) with self+AA+already-linked exclusion using LIVE url_edit.text() | VERIFIED | musicstreamer/ui_qt/add_sibling_dialog.py — __init__ accepts live_url (lines 73-87); _repopulate_station_list prefers live URL over streams[0].url (lines 283-288); filter by provider_id via currentData() (WR-03). All 12 tests in test_add_sibling_dialog.py PASSED including the three new CR-03 regression tests. |
| 6 | NowPlayingPanel surfaces merged AA + manual siblings on the existing 'Also on:' line (no new label) | VERIFIED | musicstreamer/ui_qt/now_playing_panel.py:1215-1232 calls merge_siblings(find_aa_siblings(...), find_manual_siblings(...)) inside the existing try/except wrapper. test_now_playing_shows_merged_siblings PASSED. |
| 7 | MainWindow wires EditStationDialog.sibling_toast → show_toast at both spawn sites (bound-method, QA-05) | VERIFIED | musicstreamer/ui_qt/main_window.py:789 + :804. Both lines `dlg.sibling_toast.connect(self.show_toast)` — bound-method, no lambda. |
| 8 | ZIP export/import round-trip persists siblings by station NAME (CR-01-fixed: cross-provider-safe), forward-compat (missing key = empty), unresolved silently drops | VERIFIED | musicstreamer/settings_export.py:376-419 builds `key_to_id: dict[(name, provider_name), id]` via LEFT JOIN; sibling-name resolution searches every provider bucket and silently drops multi-match cases (D-07). `ambiguous_keys` defensively handles intra-bucket duplicates. test_siblings_round_trip_with_cross_provider_duplicate_names PASSED — 4 stations across 2 providers, two "Groove Salad"-style entries, zero cross-pollination. WR-05 documented additive merge-mode semantic inline. |
| 9 | × button reliably removes the visible chip when clicked AND surfaces stay in sync (CR-02-fixed: AA-wins precedence) | VERIFIED | musicstreamer/ui_qt/edit_station_dialog.py:714-726 — builds `aa_ids` first, suppresses manual chips for any station_id in `aa_ids`. Matches merge_siblings AA-wins at musicstreamer/url_helpers.py:265-276 (NowPlayingPanel surface). Both surfaces now render the same chip variant for the AA∩manual collision. test_aa_and_manual_collision_renders_as_aa_chip_no_x and test_aa_and_manual_collision_matches_merge_siblings_semantics PASSED. |

**Score:** 9/9 truths verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/repo.py` | station_siblings DDL + 3 CRUD methods | VERIFIED | Lines 66-73 (DDL), 235-258 (CRUD); INSERT OR IGNORE + UNION as designed |
| `musicstreamer/url_helpers.py` | find_manual_siblings + merge_siblings | VERIFIED | Lines 237-276; merge_siblings AA-wins precedence verified at lines 261-276 |
| `musicstreamer/ui_qt/edit_station_dialog.py` | FlowLayout chip row, sibling_toast Signal, AddSiblingDialog launch with live_url | VERIFIED | _refresh_siblings:629-735 (AA-wins per CR-02); _on_add_sibling_clicked:893-898 (passes live_url per CR-03); WR-06 partial-based chip wiring; WR-04 narrow except sqlite3.Error |
| `musicstreamer/ui_qt/add_sibling_dialog.py` | AddSiblingDialog class with live_url parameter | VERIFIED | __init__:73-87 accepts live_url; _repopulate_station_list:275-298 honors live_url (None→fallback, ""→honored); WR-03 filter by provider_id via currentData(); WR-07 split itemDoubleClicked slot |
| `musicstreamer/ui_qt/now_playing_panel.py` | _refresh_siblings call-site swap | VERIFIED | Line 1225 uses merge_siblings(find_aa_siblings(...), find_manual_siblings(...)) |
| `musicstreamer/ui_qt/main_window.py` | sibling_toast → show_toast wiring at both spawn sites | VERIFIED | Lines 789 + 804, bound-method per QA-05 |
| `musicstreamer/settings_export.py` | siblings emit + commit_import (name,provider)-keyed second pass | VERIFIED | Line 132 (key); 169-179 (enrich); 376-419 (CR-01-fixed: key_to_id keyed by (name,provider_name) via LEFT JOIN; multi-match resolution with ambiguous_keys defense) |
| `tests/test_station_siblings.py` | 13 tests | VERIFIED — 13/13 PASSED |
| `tests/test_add_sibling_dialog.py` | 9 original + 3 new CR-03 regression tests | VERIFIED — 12/12 PASSED |
| `tests/test_edit_station_dialog.py` | 6 sibling/chip tests + 2 new CR-02 regression tests | VERIFIED — all PASSED |
| `tests/test_now_playing_panel.py` | 1 merged test + FakeRepoWithSiblings | VERIFIED — PASSED |
| `tests/test_settings_export.py` | 3 sibling round-trip tests + 1 new CR-01 regression test | VERIFIED — 4/4 PASSED |
| `tests/test_constants_drift.py` | RichText baseline drift guard (EXPECTED_RICHTEXT_COUNT = 3) | VERIFIED — PASSED; live count = 3 |
| `.planning/REQUIREMENTS.md` | SIB-01 marked complete | VERIFIED — line 50 `- [x] **SIB-01**: ...`; traceability table line 114 (`Complete`); last-updated note line 125 |
| `.planning/ROADMAP.md` | Phase 71 marked 9/9 complete | VERIFIED — line 601: `Plans: 9/9 plans complete` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| EditStationDialog._on_add_sibling_clicked | AddSiblingDialog | exec() modal + Accepted branch with live_url passthrough | WIRED | edit_station_dialog.py:893-898 — passes `live_url=self.url_edit.text().strip()` (CR-03 fix) |
| AddSiblingDialog accept | Repo.add_sibling_link | self._repo.add_sibling_link inside _accept_selected | WIRED | confirmed via test_accept_calls_add_sibling_link PASSED |
| EditStationDialog._on_unlink_sibling | Repo.remove_sibling_link | direct call + refresh + sibling_toast | WIRED | edit_station_dialog.py — bound via functools.partial (WR-06 fix) |
| EditStationDialog.sibling_toast | MainWindow.show_toast | bound-method connect at both spawn sites | WIRED | main_window.py:789, 804 |
| NowPlayingPanel._refresh_siblings | merge_siblings | direct call composing find_aa_siblings + find_manual_siblings | WIRED | now_playing_panel.py:1225 |
| settings_export.commit_import | station_siblings table | INSERT OR IGNORE second pass with (name,provider)-keyed resolution | WIRED | musicstreamer/settings_export.py:376-419 (CR-01 fix); cross-provider duplicate-name safe |
| EditStationDialog._refresh_siblings dedup | merge_siblings semantics | AA-wins on both surfaces (matches url_helpers.merge_siblings) | WIRED | edit_station_dialog.py:714-726 builds aa_ids first, skips manual entries already in aa_ids; CR-02 fix |
| AddSiblingDialog exclusion | live url_edit.text() | Forwarded via live_url param; falls back to streams[0].url when None | WIRED | add_sibling_dialog.py:283-288 (CR-03 fix) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full Phase-71-affected test suite green | `pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py tests/test_edit_station_dialog.py tests/test_main_window_integration.py tests/test_now_playing_panel.py tests/test_settings_export.py tests/test_constants_drift.py --tb=no -p no:randomly` | 337 passed, 5 warnings in 6.77s | PASS |
| All 6 new CR-01/CR-02/CR-03 regression tests GREEN | `pytest <6 test ids>` | 6/6 PASSED in 0.25s | PASS |
| New test files exist + collect cleanly | `pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py --collect-only` | 25 items collected (13 + 12), no errors | PASS |
| Sibling-related tests across all 5 sibling-relevant files | `pytest <files> -k "sibling or richtext or chip or navigate_to_sibling"` | 52 passed, 219 deselected in 0.52s | PASS |
| RichText baseline drift guard | `grep -rn "setTextFormat(Qt.RichText)" musicstreamer/ \| wc -l` | 3 (was 4 pre-Plan-71-03) | PASS |
| Phase 71 source files have NO debt markers | `grep -E "TODO\|FIXME\|XXX\|HACK\|TBD\|PLACEHOLDER" <Phase 71 files>` | no matches | PASS |
| Phase 71-affected files (excluding network-dependent NowPlaying tests) | `pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py tests/test_edit_station_dialog.py tests/test_settings_export.py tests/test_constants_drift.py` | 135 passed in 4.00s | PASS |

### Anti-Patterns Found

None in Phase-71-modified files. No TODO/FIXME/XXX/HACK/TBD/PLACEHOLDER markers in the seven files Phase 71 touched. No console.log stubs. No empty-implementation returns.

The flaky `test_logo_status_clears_after_3s` test in test_edit_station_dialog.py and `test_icy_disabled_suppresses_itunes_call` in test_now_playing_panel.py are pre-existing tests (added in Phase 40.1-05 and earlier) with timing/network-thread teardown sensitivities unrelated to Phase 71. They pass consistently when run with the full Phase 71-affected test suite together (`337 passed`).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| SIB-01 | Phase 71 | Manual sibling-station linking via GUI replaces hand-DB-edits. Picker, per-chip ×, merge with AA, ZIP by name. | SATISFIED | All UI surfaces, persistence, and ZIP round-trip exist and tests pass. SIB-01 marked complete in `.planning/REQUIREMENTS.md` (line 50: `- [x]`; traceability row line 114: `Complete`). CR-01/CR-02/CR-03 fixes verified at line-level evidence and via 6 new regression tests. 4 UAT tests passed in `.planning/phases/71-.../71-UAT.md`; 1 UAT skipped with documented automation coverage. |

### Human Verification Required

None remaining. All 4 manual UAT items from VALIDATION.md's "Manual-Only Verifications" table were executed by the user and recorded in `.planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/71-UAT.md`:

- Test 1: Cross-provider AA name-mismatch link — **passed**
- Test 2: SomaFM 3× Groove Salad multi-link — **passed**
- Test 3: ZIP export/import round-trip carries siblings — **passed**
- Test 4: AA auto + manual co-exist on "Also on:" line — **passed**
- Test 5: CR-02 collision regression — **skipped** (cannot construct via UI because CR-03 fix correctly excludes AA-detected stations from AddSiblingDialog picker; verified at code-level by automated regression tests `test_aa_and_manual_collision_renders_as_aa_chip_no_x` + `test_aa_and_manual_collision_matches_merge_siblings_semantics`)

Verifier accepts the Test 5 skip with automation evidence — the collision-state regression is asserted at the unit-test level on both rendering surfaces (EditStationDialog + NowPlayingPanel) and the construction path is now unreachable through normal UX as a side effect of the CR-03 fix.

### Gaps Summary

No gaps remain. All 3 BLOCKERS (CR-01, CR-02, CR-03) from the initial verification (2026-05-12T23:55:00Z) have landed fixes verified at line-level in the codebase:

- **CR-01** — `musicstreamer/settings_export.py:376-419` keys by `(name, provider_name)` tuple. Regression test `test_siblings_round_trip_with_cross_provider_duplicate_names` constructs the exact SomaFM-variant case and asserts zero cross-pollination.
- **CR-02** — `musicstreamer/ui_qt/edit_station_dialog.py:714-726` implements AA-wins dedup matching `merge_siblings` (`musicstreamer/url_helpers.py:265-276`). Both surfaces now render identical chip variants for the AA∩manual collision case.
- **CR-03** — `musicstreamer/ui_qt/add_sibling_dialog.py:73-87,283-288` accepts and honors `live_url`. Spawn site `edit_station_dialog.py:893-898` forwards `self.url_edit.text().strip()`.

All 22 original Wave 0 RED tests remain GREEN; 6 new regression tests covering the Critical fixes also GREEN; 0 regressions in the broader Phase 71-affected test suite (337 passed). SIB-01 marked `[x]` complete in REQUIREMENTS.md; ROADMAP Phase 71 at 9/9 plans complete; UAT logged with 4 passed + 1 skipped (skip-reason documented and accepted).

Phase 71 goal is fully achieved. Ready to proceed.

---

_Verified: 2026-05-13T01:30:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — gaps closure validated against 8 fix commits (547b3ec, a8a0336, 710645c, e05ca6d, 1f8d3fc, aa87e22, a50ee0b, 3feaa6e) + 1 UAT commit (ba2eb77)_

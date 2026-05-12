---
phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio
verified: 2026-05-12T23:55:00Z
status: gaps_found
score: 6/9 must-haves verified (3 gaps from code review CR-01/CR-02/CR-03)
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "User can unlink a manually-linked sibling via the × button on its chip"
    status: partial
    reason: "CR-02 — When a station is both manually linked AND AA-auto-detected, EditStationDialog renders a manual chip with × (using manual-wins precedence) but NowPlayingPanel uses merge_siblings (AA-wins) so the same station shows as a bare AA chip there. Clicking × in EditStationDialog calls Repo.remove_sibling_link successfully — but the chip immediately reappears in EditStationDialog (now as an AA chip after the manual row is gone), and the NowPlayingPanel was already showing it as AA-only. The user sees an unlink action that 'does nothing'. This violates the must-have: × must reliably remove the visible chip."
    artifacts:
      - path: "musicstreamer/ui_qt/edit_station_dialog.py"
        issue: "Lines 682-693 implement manual-wins dedup ('manual_ids' suppresses AA chips for the same station_id) — contradicts merge_siblings' AA-wins precedence at musicstreamer/url_helpers.py:265-276 which is used by NowPlayingPanel"
      - path: "musicstreamer/url_helpers.py"
        issue: "Lines 261-276 implement AA-wins dedup — disagrees with EditStationDialog manual-wins"
      - path: "musicstreamer/ui_qt/now_playing_panel.py"
        issue: "Line 1225 uses merge_siblings (AA-wins); displays a bare AA chip for stations the EditStationDialog displays as manual-chip with ×"
    missing:
      - "Pick ONE precedence rule and apply it in both surfaces. Per CONTEXT D-03 + RESEARCH Q2, AA-wins is the documented design — change EditStationDialog._refresh_siblings (lines 684-689) to skip manual chips for station_ids already in the AA set, OR change merge_siblings semantics to manual-wins and update RESEARCH/CONTEXT to match."
      - "Add a regression test seeding a station that is BOTH AA-cross-network AND in list_sibling_links; assert both surfaces render the same chip variant (currently no test triggers the collision case)."

  - truth: "ZIP export/import round-trip correctly persists sibling links across machines via station NAMES"
    status: partial
    reason: "CR-01 — settings_export.py:351-356 builds `name_to_id = {r['name']: r['id'] for r in SELECT id, name FROM stations}`. The stations table has NO UNIQUE constraint on name (musicstreamer/repo.py:23-33 — only providers.name is UNIQUE). When two stations legitimately share a name (e.g., SomaFM 'Groove Salad' + a same-named station from a different provider — the very kind of variant Phase 71 is designed to handle), the dict-comprehension silently overwrites earlier entries. The winning station_id is whichever row SQLite returns last (non-deterministic ORDER without ORDER BY). Sibling rows for the loser are silently misattributed to the winner or dropped. Forward-compat round-trip of the SomaFM Drone Zone/Groove Salad case named in CONTEXT (the primary motivating use case) can corrupt data."
    artifacts:
      - path: "musicstreamer/settings_export.py"
        issue: "Lines 351-356 build name→id dict that silently drops duplicate-name keys; lines 357-385 use this dict to resolve sibling names back to IDs"
      - path: "musicstreamer/repo.py"
        issue: "Lines 23-33 define stations table with no UNIQUE on name, making the duplicate-name case real not theoretical"
    missing:
      - "Group sibling resolution by (name, provider) tuple instead of name alone, OR capture station_id directly from the first-pass inserts via a parallel array indexed by import position."
      - "Add a regression test: import a ZIP containing two stations with the same name but different providers, each with siblings; assert each sibling row lands on the correct station_id."

  - truth: "AddSiblingDialog picker exclusion set correctly reflects the station's current state during editing"
    status: partial
    reason: "CR-03 — AddSiblingDialog._repopulate_station_list (musicstreamer/ui_qt/add_sibling_dialog.py:222-223) reads `current_url = self._current_station.streams[0].url` to feed find_aa_siblings for AA exclusion. During EditStationDialog editing, the URL field is the source of truth (Pitfall 4) — the user may have changed it without saving. If the user changes URL then clicks + Add sibling without saving, the picker uses the OLD URL to compute the AA exclusion set, so a station that becomes AA-detected under the NEW URL is not excluded from the picker. Adding it as a manual sibling then causes the AddSiblingDialog→EditStationDialog→NowPlayingPanel chain to display inconsistently after save (compounds CR-02)."
    artifacts:
      - path: "musicstreamer/ui_qt/add_sibling_dialog.py"
        issue: "Line 222-223 reads self._current_station.streams[0].url (stale saved URL) instead of receiving the live URL from EditStationDialog's url_edit.text()"
      - path: "musicstreamer/ui_qt/edit_station_dialog.py"
        issue: "Line 818 — AddSiblingDialog(self._station, self._repo, parent=self) — does not pass self.url_edit.text() down to the dialog"
    missing:
      - "Extend AddSiblingDialog.__init__ to accept a live_url: str parameter (or a callable Callable[[], str])"
      - "Pass self.url_edit.text().strip() at the call site in EditStationDialog._on_add_sibling_clicked"
      - "Test: change url_edit text without saving, open AddSiblingDialog, verify the AA exclusion reflects the new URL"

human_verification:
  - test: "Cross-provider AA name-mismatch case — 'Classical Relaxation' (DI.fm) ↔ 'Relaxing Classical' (RadioTunes)"
    expected: "Open EditStationDialog on one. Click + Add sibling. Pick the other from picker. Click 'Link Station'. Chip appears in 'Also on:' row with × button. Close + reopen — chip persists. Click partner chip name — switches to that station's editor. Open NowPlaying for either station — 'Also on:' line shows the partner."
    why_human: "Requires live AA library + cross-network playback to validate the headline use case. Visual flow and chip visibility need eyes."

  - test: "SomaFM 3× Groove Salad multi-link case"
    expected: "Open EditStationDialog on 'Groove Salad'. Add 'Classic Groove Salad' as sibling. Re-open + Add sibling, add 'Groove Salad 2'. Verify both chips present. Edit 'Classic Groove Salad' → see Groove Salad in its row but NOT Groove Salad 2 (no transitive closure per CONTEXT D-04). Click × on one chip → unlink + toast fires."
    why_human: "Live SomaFM 3-variant case validates multi-link UX, toast appearance, no-transitive-closure invariant."

  - test: "ZIP export/import round-trip carries siblings"
    expected: "Link 2 sibling pairs in source DB. Hamburger → Export settings → save ZIP. Manually delete the partner stations in source DB. Hamburger → Import settings, pick the ZIP. Verify all 4 stations restored AND sibling links restored AND 'Also on:' rows render correctly."
    why_human: "Cross-machine sync validates the persistence boundary; CR-01 could corrupt this if duplicate-named stations are present, so this test should specifically include a duplicate-named pair."

  - test: "AA auto + manual co-exist on 'Also on:' line, plus the collision case for CR-02"
    expected: "Pick a DI.fm station with a known AA cross-network sibling. Add a manual sibling to a different (non-AA) station. NowPlaying shows AA chip (plain text) + manual chip with × in same 'Also on:' line. × removes only the manual link. THEN repeat with a station that is BOTH AA-detected AND manually linked — observe whether EditStationDialog shows × and NowPlayingPanel shows the same chip variant; click × and observe whether chip disappears or reverts to AA chip."
    why_human: "Phase 51 navigation invariant + AA chip stability under manual link/unlink + the CR-02 user-visible defect all require live execution."

---

# Phase 71: Sister Station Expansion — Verification Report

**Phase Goal:** Add ability to link manually-chosen sister stations to a current station (complementing Phase 51's auto-detected AA siblings), with persistence via a new `station_siblings` table, ZIP round-trip via station NAMES (forward-compat), and a chip-row UI in EditStationDialog with `+ Add sibling` picker and `×` unlink controls.

**Verified:** 2026-05-12T23:55:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | New `station_siblings` SQLite table with CHECK(a_id < b_id), UNIQUE(a_id, b_id), double ON DELETE CASCADE | VERIFIED | musicstreamer/repo.py:66-73 contains the CREATE TABLE IF NOT EXISTS block exactly as specified by D-05/D-06/D-08. `pytest tests/test_station_siblings.py::test_schema_create_with_check_unique_cascade` PASSED. db_init idempotency PASSED. CASCADE PASSED. |
| 2 | Repo CRUD: add_sibling_link / remove_sibling_link / list_sibling_links with (min,max) normalization + INSERT OR IGNORE idempotence + UNION symmetric lookup | VERIFIED | musicstreamer/repo.py:235-258. All 6 CRUD-related tests in test_station_siblings.py PASSED (add_round_trip, idempotent, normalizes_order, remove, remove_noop, list_symmetric). |
| 3 | Pure helpers `find_manual_siblings` + `merge_siblings` in url_helpers.py, mirroring find_aa_siblings shape | VERIFIED | musicstreamer/url_helpers.py:237-276. Tuple shape, self-exclusion, alphabetical sort, AA-wins dedup all asserted by the 4 helper tests in test_station_siblings.py. |
| 4 | EditStationDialog chip row with `+ Add sibling` button + × on manual chips + plain AA chips | VERIFIED | musicstreamer/ui_qt/edit_station_dialog.py:482-498 (FlowLayout chip row), 696-702 (+ Add sibling btn), 715-728 (_add_aa_sibling_chip — bare QPushButton, objectName "sibling_aa_chip_{id}"), 730-786 (_add_manual_sibling_chip — compound widget with × button, objectName "sibling_chip_{id}"). All 6 chip-row tests in test_edit_station_dialog.py PASSED. |
| 5 | AddSiblingDialog two-step picker (provider QComboBox → filtered QListWidget) with self+AA+already-linked exclusion | VERIFIED — but see Truth 9 (CR-03) | musicstreamer/ui_qt/add_sibling_dialog.py (270 LOC) exists. All 9 tests in test_add_sibling_dialog.py PASSED — window title, "Link Station"/"Don't Link" labels, provider switch reload, exclusion logic, OK gate, accept persistence. |
| 6 | NowPlayingPanel surfaces merged AA + manual siblings on the existing 'Also on:' line (no new label) | VERIFIED | musicstreamer/ui_qt/now_playing_panel.py:1215-1232 calls merge_siblings(find_aa_siblings(...), find_manual_siblings(...)) inside the existing try/except wrapper. Existing `_sibling_label` widget at lines 354-360 unchanged. test_now_playing_shows_merged_siblings PASSED. |
| 7 | MainWindow wires EditStationDialog.sibling_toast → show_toast at both spawn sites (bound-method, QA-05) | VERIFIED | musicstreamer/ui_qt/main_window.py:789 (_on_add_station path) and :804 (_on_edit_requested path). Both lines: `dlg.sibling_toast.connect(self.show_toast)`. Bound-method, no lambda. |
| 8 | ZIP export/import round-trip persists siblings by station NAME, forward-compat (missing key = empty), unresolved silently drops | FAILED (BLOCKER CR-01) | musicstreamer/settings_export.py:132 (key declared), 169-179 (build_zip enrichment), 343-385 (commit_import second pass). The 3 settings_export sibling tests PASSED. **However:** the `name_to_id` dict at lines 351-356 silently collapses entries for duplicate station names. stations.name is NOT UNIQUE (verified at repo.py:23-33). When two stations share a name (legitimate SomaFM-variant case), the dict's last-write-wins behavior misattributes or drops sibling rows on import. Forward-compat is correct for the missing-key and unresolved-name cases but the duplicate-name path is data-corruption-prone. |
| 9 | × button reliably removes the visible chip when clicked (user can unlink a manual sibling) | FAILED (BLOCKER CR-02) | musicstreamer/ui_qt/edit_station_dialog.py:684-689 uses **manual-wins** dedup (suppresses AA chip for any station_id also in manual_ids). musicstreamer/url_helpers.py:265-276 (merge_siblings, used by NowPlayingPanel) uses **AA-wins** dedup. When a station is both AA-detected AND manually linked, EditStationDialog shows it as a × chip but NowPlayingPanel shows it as a bare AA chip. Clicking × removes the DB row, but the chip reappears in EditStationDialog as an AA chip — the user sees "× did nothing." Compounded by CR-03 (stale URL in AddSiblingDialog exclusion). |
| 10 | AddSiblingDialog exclusion set reflects the LIVE URL (not stale saved URL) during editing | FAILED (CR-03) | musicstreamer/ui_qt/add_sibling_dialog.py:222-223 reads `self._current_station.streams[0].url` (saved URL) to feed find_aa_siblings. musicstreamer/ui_qt/edit_station_dialog.py:818 — AddSiblingDialog spawn site does not pass `self.url_edit.text()` (live URL). Pitfall 4 in 71-RESEARCH names this as a real risk. No corresponding test triggers the URL-changed-without-save case. |

**Score:** 7/10 truths verified (3 failures are CR-01, CR-02, CR-03 from REVIEW — all known and intentionally surfaced).

For the higher-level must-haves derived from the phase goal (5 capabilities):

| # | Goal-Level Must-Have | Status |
| - | --- | ------ |
| 1 | Manual linking UI | VERIFIED |
| 2 | Persistence via station_siblings | VERIFIED |
| 3 | Complements Phase 51 AA detection (merged display) | VERIFIED with caveat — two surfaces disagree on dedup precedence (CR-02) |
| 4 | ZIP round-trip via station NAMES, forward-compat | VERIFIED with caveat — duplicate-name corruption risk (CR-01) |
| 5 | Chip row with + Add sibling + × | VERIFIED with caveat — × can appear broken under AA+manual collision (CR-02) |
| 6 | AA chip stability + Phase 51 navigation invariant | VERIFIED — navigate_to_sibling Signal preserved; AA chips show plain text; T-40-04 RichText baseline drops 4→3 as planned |
| 7 | SIB-01 requirement registered in REQUIREMENTS.md | VERIFIED — `.planning/REQUIREMENTS.md:50,114,125` |
| 8 | All 22 Wave 0 RED tests turn GREEN | VERIFIED — 22/22 in new files PASSED + 19/19 sibling/richtext tests in extended files PASSED |
| 9 | Full suite no regression from Phase 71 | VERIFIED — 35 pre-existing failures documented in deferred-items.md (Phase 62 FakePlayer drift, DBus MPRIS test-infra, AA quality-combo orphan); spot-check confirms these pre-date Phase 71 |

**Adjusted Score:** 6/9 must-haves (CR-01, CR-02, CR-03 fail truths 3, 4, 5 partially).

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/repo.py` | station_siblings DDL + 3 CRUD methods | VERIFIED | Lines 66-73 (DDL), 235-258 (CRUD); INSERT OR IGNORE + UNION as designed |
| `musicstreamer/url_helpers.py` | find_manual_siblings + merge_siblings | VERIFIED | Lines 237-276; mirrors find_aa_siblings shape |
| `musicstreamer/ui_qt/edit_station_dialog.py` | FlowLayout chip row, sibling_toast Signal, AddSiblingDialog launch | VERIFIED (modulo CR-02) | Lines 261 (sibling_toast), 482-498 (chip row container), 623-826 (_refresh_siblings + chip helpers + slots); _sibling_label QLabel REMOVED (T-40-04 baseline 4→3) |
| `musicstreamer/ui_qt/add_sibling_dialog.py` | NEW AddSiblingDialog class | VERIFIED (modulo CR-03) | 270 LOC; QFormLayout, QComboBox, QListWidget, "Link Station"/"Don't Link" labels |
| `musicstreamer/ui_qt/now_playing_panel.py` | _refresh_siblings call-site swap | VERIFIED | Line 1225 uses merge_siblings(find_aa_siblings(...), find_manual_siblings(...)) |
| `musicstreamer/ui_qt/main_window.py` | sibling_toast → show_toast wiring at both spawn sites | VERIFIED | Lines 789 + 804, bound-method per QA-05 |
| `musicstreamer/settings_export.py` | siblings emit + commit_import second pass | VERIFIED (modulo CR-01) | Line 132 (key), 169-179 (enrich), 343-385 (resolve); duplicate-name dict collapse at 351-356 |
| `tests/test_station_siblings.py` | 13 tests | VERIFIED — 13/13 PASSED |
| `tests/test_add_sibling_dialog.py` | 9 tests | VERIFIED — 9/9 PASSED |
| `tests/test_edit_station_dialog.py` | 6 sibling/chip tests appended | VERIFIED — 6/6 PASSED |
| `tests/test_now_playing_panel.py` | 1 merged test + FakeRepoWithSiblings | VERIFIED — PASSED |
| `tests/test_settings_export.py` | 3 sibling round-trip tests | VERIFIED — 3/3 PASSED |
| `tests/test_constants_drift.py` | RichText baseline drift guard (EXPECTED_RICHTEXT_COUNT = 3) | VERIFIED — PASSED; live count = 3 |
| `.planning/REQUIREMENTS.md` | SIB-01 row + Sibling Stations section | VERIFIED — lines 46-50, 114, 125 |
| `.planning/PROJECT.md` | 6 [Phase 71] decision rows | VERIFIED — lines 213-218 |
| `.planning/ROADMAP.md` | Phase 71 marked 9/9 complete | VERIFIED — line 601 |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| EditStationDialog._on_add_sibling_clicked | AddSiblingDialog | exec() modal + Accepted branch | WIRED | edit_station_dialog.py:810-826 |
| AddSiblingDialog accept | Repo.add_sibling_link | self._repo.add_sibling_link inside _on_accept | WIRED | add_sibling_dialog.py — confirmed via test_accept_calls_add_sibling_link PASSED |
| EditStationDialog._on_unlink_sibling | Repo.remove_sibling_link | direct call + refresh + sibling_toast | WIRED | edit_station_dialog.py:792-808 |
| EditStationDialog.sibling_toast | MainWindow.show_toast | bound-method connect at both spawn sites | WIRED | main_window.py:789, 804 |
| NowPlayingPanel._refresh_siblings | merge_siblings | direct call composing find_aa_siblings + find_manual_siblings | WIRED | now_playing_panel.py:1215-1225 |
| settings_export.commit_import | station_siblings table | INSERT OR IGNORE second pass with name_to_id resolution | PARTIALLY WIRED | Wired but vulnerable to duplicate-name collision (CR-01) |
| EditStationDialog._refresh_siblings dedup | merge_siblings semantics | INCONSISTENT — manual-wins vs AA-wins | NOT_WIRED CORRECTLY | edit_station_dialog.py:684-689 contradicts url_helpers.py:265-276 (CR-02) |
| AddSiblingDialog exclusion | live url_edit.text() | NOT WIRED — reads stale stream URL | NOT_WIRED | add_sibling_dialog.py:222-223 (CR-03) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| New test files exist + collect cleanly | `pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py --collect-only` | 22 items collected, no errors | PASS |
| All 22 new-file tests GREEN | `pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py -v` | 22/22 PASSED in 0.24s | PASS |
| Phase-71 extensions in existing test files GREEN | `pytest tests/test_edit_station_dialog.py tests/test_now_playing_panel.py tests/test_settings_export.py tests/test_constants_drift.py -k "sibling or richtext"` | 19/19 PASSED | PASS |
| Sibling chip + chip-x + navigate Signal tests GREEN | `pytest tests/test_edit_station_dialog.py -k "sibling or chip or richtext or navigate_to_sibling"` | 8/8 PASSED | PASS |
| RichText baseline drift guard | `grep -rn "setTextFormat(Qt.RichText)" musicstreamer/ \| wc -l` | 3 (was 4 pre-Plan-71-03) | PASS |
| Phase 71 source files have NO debt markers | `grep -E "TODO\|FIXME\|XXX\|HACK\|TBD\|PLACEHOLDER" <Phase 71 files>` | no matches | PASS |

### Anti-Patterns Found

None in Phase-71-modified files. No TODO/FIXME/XXX/HACK/TBD/PLACEHOLDER markers in the seven files Phase 71 touched. No console.log stubs. No empty-implementation returns. The defects flagged are design-level (CR-01/02/03) not stubs.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| SIB-01 | Phase 71 (rolling) | Manual sibling-station linking via GUI replaces hand-DB-edits. Picker, per-chip ×, merge with AA, ZIP by name. | SATISFIED with gaps | All UI surfaces, persistence, and ZIP round-trip exist and tests pass. SIB-01 added to REQUIREMENTS.md (`Sibling Stations (SIB)` section + traceability row + last-updated note). However the CR-01/02/03 defects qualify the "complete" status. |

### Human Verification Required

See `human_verification:` block in frontmatter. 4 items from VALIDATION.md's "Manual-Only Verifications" table — all require live audio playback + cross-network testing.

Critically, item 4 (AA + manual co-exist) should be expanded to specifically exercise the CR-02 collision case (station that is BOTH AA-detected AND manually linked).

### Gaps Summary

**3 BLOCKERS surfaced by code review (`71-REVIEW.md`):**

- **CR-01** is a **silent data corruption risk** on the ZIP import path. The motivating SomaFM-variant use case ("Drone Zone" + "Drone Zone 2", "Groove Salad" + "Classic Groove Salad" + "Groove Salad 2") makes duplicate station names a real, expected scenario — yet the implementation cannot distinguish them by name alone. This blocks Truth 4 (ZIP round-trip correctness) for the very use cases CONTEXT named as primary motivators.

- **CR-02** is a **user-visible UX bug** that makes the × unlink button appear broken in the cross-section of (AA-auto-detected ∩ manually-linked) stations. The two surfaces (EditStationDialog with manual-wins, NowPlayingPanel with AA-wins) actively contradict each other, breaking the must-have "User can unlink a manually-linked sibling via ×". RESEARCH Q2 + CONTEXT D-03 documented AA-wins as the intended semantics; Plan 71-03's deviation note shows the executor knowingly chose manual-wins in EditStationDialog to satisfy a Plan 71-00 RED test (test_manual_chip_has_x_button seeded the collision case). The collision case isn't documented anywhere as "intentionally manual-wins in Edit dialog only" — and the inconsistency between surfaces is a defect not a feature.

- **CR-03** is a **stale exclusion-set bug** that compounds CR-02 — the AddSiblingDialog can offer a sibling candidate that the new (unsaved) URL would already auto-detect as AA, leading to the manual link landing in a state where post-save it overlaps with an AA detection, triggering CR-02.

All three were identified during the post-implementation code review (`/gsd-code-review 71`, output at 71-REVIEW.md). They were NOT auto-fixed — REVIEW.md ends with a recommendation to run `/gsd-code-review 71 --fix` or `/gsd-execute-phase 71.1` as a polish phase.

**The phase goal is largely achieved but with three real defects that affect the cross-provider AA name-mismatch and same-provider SomaFM-variant flows — exactly the two motivating use cases CONTEXT names. Recommend gap closure before declaring Phase 71 done.**

Additionally surfacing one Warning that affects user expectations:

- **WR-01** (from REVIEW): EditStationDialog._refresh_siblings docstring (musicstreamer/ui_qt/edit_station_dialog.py:626-628) claims "URL field is the source of truth during editing", but `url_edit.textChanged` is NOT connected to `_refresh_siblings` (confirmed — line 356 connects textChanged to _on_url_text_changed which only debounces logo fetch). _refresh_siblings only fires on _populate, _on_unlink_sibling, _on_add_sibling_clicked. So if the user types a new URL, the chip row does not refresh AA detection. The docstring lies; the behavior is stale-URL-passive. This compounds CR-03's class of bugs. Either wire textChanged → _refresh_siblings (with debounce per logo-fetch pattern at line 353-356) or correct the docstring.

---

_Verified: 2026-05-12T23:55:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: No — initial verification_

---
iteration: 1
date: 2026-05-04
plans_checked:
  - 60-08-fix-302-messages
  - 60-09-fix-vote-roundtrip
  - 60-10-active-playlist-enumeration
  - 60-11-search-artist-album-panels
verdict: NEEDS REVISION
blockers: 2
warnings: 8
---

# 60-PLAN-CHECK Verification Report — Iteration 1/3

Adversarial pre-execution review of all 4 gap-closure plans (60-08 through 60-11) for Phase 60. Read all 4 plans, all 4 diagnoses, the affected production code (`gbs_api.py`, `now_playing_panel.py`, `gbs_search_dialog.py`), the existing test files, the canonical fixtures, the capture script, and the UAT report.

---

## Plan 60-08 — fix-302-messages

**Verdict: CONCERN** (1 BLOCKER, 2 WARNINGs)

| # | Criterion | Score | Note |
|---|-----------|-------|------|
| 1 | Goal alignment | PASS | Closes T6 + T13. |
| 2 | Diagnosis fidelity | PASS | Correctly applies §5a (override `http_error_302`) and §5d (Option A field-level dirty-check). |
| 3 | Cross-plan parallel-safety | CONCERN | See cross-plan section. |
| 4 | TDD discipline | PASS | RED commit before GREEN; 2 GREEN commits split correctly. |
| 5 | Frontmatter correctness | PASS | wave 5, autonomous true, gap_closure true, requirements list, closes T6/T13 implied. |
| 6 | Pre-exec gate clarity | N/A | No locked decisions. |
| 7 | Cookies-expiry timeline | N/A | No fixture capture. |
| 8 | No-op detection | **FAIL** | See BLOCKER below. |
| 9 | Test coverage | PASS | 6 new tests cover both bugs and don't-regress paths. |
| 10 | QA-05 | PASS | No `mock.patch.object(instance.method)` patterns. |

### BLOCKER: existing `test_import_idempotent` will break under Task 2 dirty-check fix

`tests/test_gbs_api.py:80-101` (`test_import_idempotent`) currently asserts `(inserted_2, updated_2) == (0, 1)` on the second `import_station` call. After Task 2 introduces field-level dirty-checking, both calls produce the same canonical state, so the second call will return `(0, 0)` — and this assertion will FAIL.

The plan's success criteria claims "All 24 tests in tests/test_gbs_api.py pass (18 pre-existing + 6 new)". That count is wrong — at least one pre-existing test must be UPDATED in Task 2, not preserved. The plan must explicitly:
1. Update `test_import_idempotent` to reflect the new semantics (assert `(0, 0)` on idempotent re-call), OR
2. Mark it for replacement by the new `test_import_no_field_changes_returns_zero_updated`, OR
3. Mutate state between the two calls in `test_import_idempotent` so it intentionally exercises a dirty re-import.

This is a regression-blind plan: an existing test will fail, and the plan does not flag it.

### WARNING: RED test approach is imprecise for `_NoRedirect` real-path coverage

Plan Task 1 says `test_open_no_redirect_returns_302_response_not_raises` should "Patch urllib.request.OpenerDirector.open to return a fake HTTPResponse-shaped object". This bypasses the `_NoRedirect` handler under test — it is the same false-assurance pattern the diagnosis §5e called out for the existing `test_submit_success_decodes_messages`. To actually exercise the bug, the test must patch lower than `OpenerDirector.open` (e.g. mock the HTTPS transport at `urllib.request.AbstractHTTPHandler.do_open` or patch `http.client.HTTPSConnection`) so the real `OpenerDirector.error` chain runs through `_NoRedirect`.

The plan provides loose guidance ("with a mock HTTP server or a patched `opener.open`...") but doesn't pin the pattern. The executor may produce a test that passes but doesn't actually exercise the bug. Plan should specify the patching layer concretely.

### WARNING: belt-and-braces 301/303/307 override is mentioned but not tested

Plan Task 2 Step 2a adds `http_error_301 = http_error_307 = http_error_303 = http_error_302`. No test in Task 1 exercises 301/303/307 paths. This is fine if the planner accepts no coverage for these (they're defensive/aspirational), but it should be stated explicitly. As-is, the RED gate doesn't validate these aliases.

---

## Plan 60-09 — fix-vote-roundtrip

**Verdict: CONCERN** (0 BLOCKERs, 2 WARNINGs)

| # | Criterion | Score | Note |
|---|-----------|-------|------|
| 1 | Goal alignment | PASS | Closes T10 (entryid affordance) and T11 cookies-disappeared path. |
| 2 | Diagnosis fidelity | PASS | Applies Fix 1 (disable until entryid) and Fix 2 (toast on cookies-None). |
| 3 | Cross-plan parallel-safety | CONCERN | See cross-plan section. |
| 4 | TDD discipline | PASS | RED first; 1 GREEN since both fixes share the same test cluster. |
| 5 | Frontmatter correctness | PASS | wave 5, autonomous true, GBS-01d listed. |
| 6 | Pre-exec gate clarity | N/A | No locked decisions. |
| 7 | Cookies-expiry timeline | N/A | No fixture capture. |
| 8 | No-op detection | PASS | Both fixes target verified-broken code paths. |
| 9 | Test coverage | PASS | 3 new tests cover all 3 paths (disabled, enabled, toast). |
| 10 | QA-05 | PASS | No `lambda` self-capture introduced; existing `_apply_vote_buttons_enabled` uses bound method on each button. |

### WARNING: existing `test_gbs_vote_no_entryid_ignores_click` will pass for the WRONG reason

`tests/test_now_playing_panel.py:1367` (`test_gbs_vote_no_entryid_ignores_click`) currently:
1. Constructs panel without entryid
2. Calls `panel._gbs_vote_buttons[2].click()` and asserts no worker was started

After plan 60-09, the buttons will be visible-but-DISABLED in this state (no entryid stamped). Qt blocks the `clicked` signal on disabled buttons, so the in-handler guard at line 1031 (`if ... self._gbs_current_entryid is None: return`) is never even reached. The test still passes — but for an unintended reason. The semantic intent of the original test (proving the in-handler guard catches the None case) is now meaningless because the click never reaches the handler.

This is a test-quality issue, not a correctness issue. Recommend the plan add a note to either:
- Update `test_gbs_vote_no_entryid_ignores_click` to bypass the disabled-button gate (e.g. directly call `panel._on_gbs_vote_clicked()` after manually setting sender) so the in-handler guard remains tested
- Or remove the test as superseded by `test_gbs_vote_buttons_disabled_until_entryid_stamped`

### WARNING: timing of `setEnabled(False)` at construction vs Qt signal connection

Plan Step 2a says construct buttons disabled. Plan Step 2b/2c then enable them in `_on_gbs_playlist_ready`. But the existing constructor (`now_playing_panel.py:411-420`) wires `btn.clicked.connect(self._on_gbs_vote_clicked)` immediately at construction. If `setEnabled(False)` is added AFTER `connect`, that's fine — disabled state is independent of signal wiring. But if the planner inserts `setEnabled(False)` before the `connect` call, no functional harm but inconsistent ordering. Minor — plan should specify position.

---

## Plan 60-10 — active-playlist-enumeration

**Verdict: NEEDS REVISION** (1 BLOCKER, 1 WARNING)

| # | Criterion | Score | Note |
|---|-----------|-------|------|
| 1 | Goal alignment | PASS | Closes T8. |
| 2 | Diagnosis fidelity | PASS | Implements §5a parser + §5b renderer; honors §5c default. |
| 3 | Cross-plan parallel-safety | CONCERN | See cross-plan section. |
| 4 | TDD discipline | PASS | 1 RED commit (4 tests), 2 GREEN (parser, renderer). |
| 5 | Frontmatter correctness | PASS | wave 5, GBS-01c, decisions D-10a/b/c locked. |
| 6 | Pre-exec gate clarity | PASS | D-10a=10, D-10b="{n}. artist - title [duration]", D-10c=replace — all unambiguous. |
| 7 | Cookies-expiry timeline | N/A | Uses existing fixtures. |
| 8 | No-op detection | **FAIL** | See BLOCKER below. |
| 9 | Test coverage | PASS | Parser tests + renderer tests + cap test. |
| 10 | QA-05 | PASS | No new mock.patch on bound methods. |

### BLOCKER: existing `test_gbs_playlist_populates_from_mock_state` will break

`tests/test_now_playing_panel.py:1005-1039` (`test_gbs_playlist_populates_from_mock_state`) passes `state["queue_summary"] = "Playlist is 11:21 long with 3 dongs"` and asserts `assert any("Playlist is 11:21" in t for t in items)` (line 1037).

After Task 3 of plan 60-10 removes the `queue_summary` rendering (per locked D-10c), the rendered widget will NOT contain "Playlist is 11:21" — the assertion will fail.

The plan's success criteria says "All 73 tests in tests/test_now_playing_panel.py pass (71 pre-existing + 2 new renderer)". This is wrong — `test_gbs_playlist_populates_from_mock_state` MUST be updated in Task 3 to (a) remove the `queue_summary` assertion, (b) instead pass `queue_rows` and assert enumerated rendering, or (c) be replaced by the new `test_gbs_playlist_renders_enumerated_queue`. The plan does not address this breakage.

### WARNING: plan does not explicitly state whether `state["queue_html_snippets"]` is preserved or removed

Plan Step 2 says "`state["queue_html_snippets"]` is retained for backward-compat" but elsewhere mentions "or remove if unused" (interface section). The plan should pick one stance. If retained, `_fold_ajax_events` line 230 stays `"queue_html_snippets": []`. If removed, the plan must scan all callers — currently no production code reads it, but any test that does (none found via grep, but worth verifying) would break.

---

## Plan 60-11 — search-artist-album-panels

**Verdict: PASS** (0 BLOCKERs, 3 WARNINGs)

| # | Criterion | Score | Note |
|---|-----------|-------|------|
| 1 | Goal alignment | PASS | Closes T12. |
| 2 | Diagnosis fidelity | PASS | Implements §5a/b/c/d; D-11a gated by Task 0 fixture inspection. |
| 3 | Cross-plan parallel-safety | CONCERN | See cross-plan section — `_ArtistAlbumParser` and `_QueueRowParser` BOTH placed "after `_SongRowParser` (~line 362)". |
| 4 | TDD discipline | PASS | RED before GREEN; integration test (Task 4) gated by Task 0 D-11a lock. |
| 5 | Frontmatter correctness | PASS | wave 5, autonomous false (correct due to checkpoint), GBS-01e listed. |
| 6 | Pre-exec gate clarity | PASS | D-11a=REQUIRES CAPTURE (gated by Task 0); D-11b=80, D-11c=hide-when-empty unambiguous. |
| 7 | Cookies-expiry timeline | WARNING | See below. |
| 8 | No-op detection | PASS | All targets are confirmed-missing in production. |
| 9 | Test coverage | PASS | Parser tests + 2 dialog tests + 1 click-integration test = 6 tests. |
| 10 | QA-05 | PASS | `itemActivated.connect(self._on_artist_link_activated)` is a bound method; no lambda self-capture. |

### WARNING: cookie expiry timeline not in success_criteria or frontmatter

Plan body acknowledges the 2026-05-17 cookie expiry (~13 day margin from 2026-05-04). But this timeline is NOT in:
- Plan frontmatter
- success_criteria
- Task 0's `<resume-signal>` (only mentions auth-refresh as a fallback path)

If execution drifts past 2026-05-17, Task 0 will fail with redirect-to-login HTML in the captured fixtures. The plan currently relies on the executor noticing the 0-byte / login-page indicator. Recommend adding a hard date guard to Task 0's verification step:
```bash
[ "$(date +%Y%m%d)" -lt "20260517" ] || echo "WARNING: dev cookies near/past expiry"
```

### WARNING: Task 4 description mixes Option A and Option B branches without committing to one

Task 4 says "**If Option A:** ... **If Option B:** ...". The locked D-11a is supposed to be set by Task 0 BEFORE Task 4 runs. After Task 0, the planner (or executor mid-stream) MUST collapse Task 4 into ONE concrete shape. As written, Task 4 is ambiguous to the executor — it asks them to "pick the matching shape" but doesn't say what happens if D-11a is mixed (e.g. "Option B for artist, Option A for album"). The plan should explicitly handle the mixed-option case:
- If artist Option B + album Option A → Task 4 becomes 2 separate tests (one per surface)
- The plan body anticipates mixed but Task 4 doesn't enumerate this branch

### WARNING: `_clear_table` ordering interacts subtly with `_render_results`

The proposed `_clear_table` (Step 3d) hides panels. `_on_search_finished` calls `_render_results` which calls `_clear_table` — hiding panels. THEN `metadata_ready` fires (later in the same `run()`) and `_on_metadata_ready` re-shows them. This works because Qt signal queue order matches emit order — but it's a subtle invariant. If a future refactor moves `metadata_ready.emit(...)` BEFORE `finished.emit(...)`, the panels would be cleared after population. Plan should add a defensive comment in `_GbsSearchWorker.run()` noting "metadata_ready MUST emit AFTER finished".

---

## Cross-plan parallel-safety analysis

| File | 60-08 | 60-09 | 60-10 | 60-11 | Conflict risk |
|------|:-----:|:-----:|:-----:|:-----:|:--------------|
| `musicstreamer/gbs_api.py` | X | — | X | X | **HIGH** — see below |
| `musicstreamer/ui_qt/now_playing_panel.py` | — | X | X | — | **MEDIUM** — see below |
| `musicstreamer/ui_qt/gbs_search_dialog.py` | — | — | — | X | None |
| `tests/test_gbs_api.py` | X | — | X | X | **MEDIUM** — append collisions |
| `tests/test_now_playing_panel.py` | — | X | X | — | **MEDIUM** — append collisions |
| `tests/test_gbs_search_dialog.py` | — | — | — | X | None |
| `scripts/gbs_capture_fixtures.sh` | — | — | — | X | None |

### `gbs_api.py` — HIGH risk

- 60-08 modifies `_NoRedirect` (~lines 170-172) and `import_station` (~lines 528-548). Different functions/classes. Distinct.
- 60-10 modifies `_fold_ajax_events` (~lines 226-262) and ADDS `_QueueRowParser` class right after `_SongRowParser` (line 362).
- 60-11 modifies `search()` (~lines 368-396) and ADDS `_ArtistAlbumParser` class right after `_SongRowParser` (line 362).

**Hard conflict:** 60-10 and 60-11 BOTH insert a new class at the same anchor point (immediately after `_SongRowParser` ends at line 362). Git auto-merge of two same-anchor inserts will produce conflict markers ~50% of the time depending on context overlap. Will not silently merge.

**Soft conflict:** 60-10 may modify a `state.setdefault("queue_rows", [])` line in `_fold_ajax_events` while 60-11 doesn't touch that function. No collision there.

### `now_playing_panel.py` — MEDIUM risk

- 60-09 modifies vote button construction (~lines 411-420), adds new helper `_apply_vote_buttons_enabled` (~line 995), modifies `_on_gbs_playlist_ready` line 957-958 (entryid stamping block), modifies `_refresh_gbs_visibility` line 902-904 (visibility-false branch), modifies `_on_gbs_vote_clicked` line 1050-1053 (cookies-None branch).
- 60-10 modifies `_on_gbs_playlist_ready` lines 963-976 (renderer block) and adds module-level constant `_GBS_QUEUE_MAX_ROWS`.

**Hard conflict:** Both plans modify `_on_gbs_playlist_ready` in the SAME function body. 60-09 changes the entryid-stamping section (lines 957-958), 60-10 changes the renderer block right below it (lines 963-976). These are very close (5 lines apart). Git merge MAY succeed if context lines suffice, but text-collision is realistic.

### `tests/test_gbs_api.py` — MEDIUM risk

- 60-08 appends 6 tests "after the existing test_decode_django_messages_garbage_returns_empty at the bottom" (line 296+).
- 60-10 appends 2 tests "after test_decode_django_messages_garbage_returns_empty" (line 296+).
- 60-11 appends 3 tests "after the existing test_search_empty test" (line 229+).

60-08 and 60-10 BOTH target the bottom of the file — append-merge conflict.

### `tests/test_now_playing_panel.py` — MEDIUM risk

- 60-09 appends 3 tests "near line 1380+".
- 60-10 appends 2 tests "after the last GBS vote test".

These are likely the same insertion point (or very near). Append-merge conflict.

### Cross-plan recommendation

The 4 plans are all wave 5 with `depends_on: []`. If the orchestrator runs them in parallel, merge conflicts are likely. Two acceptable resolutions:

1. **Re-wave them**: Keep 60-08 and 60-09 at wave 5 (no conflict between them). Move 60-10 to wave 6 (depends_on: [60-08, 60-09]). Move 60-11 to wave 7 (depends_on: [60-10]). This serializes the gbs_api.py + test file modifications.
2. **Run all in worktrees with sequential merge**: Each plan in its own worktree; merge sequentially with conflict resolution. The orchestrator's worktree mode supports this, but conflicts will require interactive resolution.

The plans should **explicitly state** which strategy is intended. As written, all 4 plans claim `wave: 5` with no deps — meaning the orchestrator will assume they're parallel-safe, which they aren't.

---

## Final verdict: NEEDS REVISION

**Required fixes for iteration 2:**

### Required for plan 60-08:
1. **Add Task 1.5 or a Task 2 step** that updates `tests/test_gbs_api.py:80-101` (`test_import_idempotent`) to handle the new `(0, 0)` semantic on idempotent re-import. Either:
   - Update the assertion to `(inserted_2, updated_2) == (0, 0)` (idempotent re-call returns no-op), OR
   - Mutate state between calls so the second call legitimately returns `(0, 1)`.
2. Update success_criteria to reflect the modified test count or note the test was updated.
3. **Specify the patching layer** for `test_open_no_redirect_returns_302_response_not_raises`. Options: `urllib.request.AbstractHTTPHandler.do_open`, or use `unittest.mock.MagicMock` with a real `_NoRedirect` instance whose chain is exercised. Add a concrete code sketch.

### Required for plan 60-09:
1. Add a paragraph noting that `test_gbs_vote_no_entryid_ignores_click` (line 1367) will pass for a different reason after the fix; either update the test to bypass the disabled-button gate (call `panel._on_gbs_vote_clicked()` directly) so the in-handler guard remains tested, or document the test as superseded.
2. Confirm `setEnabled(False)` placement in the constructor loop (after the `connect` call is fine).

### Required for plan 60-10:
1. **Add Task 3 step** that updates `tests/test_now_playing_panel.py:1005-1039` (`test_gbs_playlist_populates_from_mock_state`) to:
   - Remove `assert any("Playlist is 11:21" in t for t in items)`
   - Add `queue_rows: [...]` to the state dict
   - Assert enumerated row rendering
2. Decide explicitly whether `state["queue_html_snippets"]` is retained or removed; document in the plan body.

### Required for plan 60-11:
1. Add cookie-expiry hard guard to Task 0 verification (compare `date` against 2026-05-17).
2. Resolve Task 4's mixed-option ambiguity: enumerate the artist-only / album-only / both / mixed branches.
3. Add defensive comment in `_GbsSearchWorker.run()` requiring `metadata_ready.emit` to follow `finished.emit`.

### Required across all 4 plans (cross-plan):
1. **Choose a parallel-safety strategy and document it in each plan's frontmatter:**
   - **Option A (recommended):** Re-wave to serialize. 60-08 and 60-09 stay at wave 5 (no overlap). 60-10 moves to wave 6 (`depends_on: [60-08]`). 60-11 moves to wave 7 (`depends_on: [60-10]`). This eliminates all merge conflicts.
   - **Option B:** Keep all at wave 5 but document in each frontmatter (`merge_strategy: sequential-worktree`) that they MUST be merged serially.
2. Document specific anchor-point conflicts in each plan: 60-10 and 60-11 both add classes after `_SongRowParser` — at minimum, the second-merged plan will need to anchor its insertion differently (e.g. after the first plan's class, not after `_SongRowParser`).

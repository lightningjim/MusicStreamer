---
iteration: 2
date: 2026-05-04
plans_revised:
  - 60-08-fix-302-messages
  - 60-09-fix-vote-roundtrip
  - 60-10-active-playlist-enumeration
  - 60-11-search-artist-album-panels
status: REVISED — addresses all required-fix items in 60-PLAN-CHECK.md (iteration 1, NEEDS REVISION)
blockers_addressed: 2
warnings_addressed: 8
---

# 60-PLAN-REVISION-2 — Diff Summary

Iteration-2 revision of the 4 gap-closure plans for Phase 60. Addresses every BLOCKER and WARNING from `60-PLAN-CHECK.md` (iter 1).

This document is the diff-summary for iter-2 plan-check to read FIRST so it can focus its review on the targeted changes.

---

## Cross-plan changes (apply to all 4)

**Re-waved to serialize.** Frontmatter `wave` and `depends_on` updated:

| Plan | OLD wave | NEW wave | OLD depends_on | NEW depends_on |
|------|---------:|---------:|----------------|----------------|
| 60-08 | 5 | 5 (unchanged) | [] | [] (unchanged) |
| 60-09 | 5 | 5 (unchanged) | [] | [] (unchanged — no overlap with 60-08) |
| 60-10 | 5 | **6** | [] | **[60-08]** |
| 60-11 | 5 | **7** | [] | **[60-10]** |

Result: serial wave chain that eliminates the parallel-merge conflicts identified by iter-1 plan-check (`gbs_api.py`, `now_playing_panel.py`, `tests/test_gbs_api.py`, `tests/test_now_playing_panel.py`).

Each plan's frontmatter also gained `revision: 2` and `revision_notes:` (text varies per plan; see below).

---

## Plan 60-08 — fix-302-messages

**File:** `.planning/phases/60-gbs-fm-integration/60-08-fix-302-messages-PLAN.md`

### Changes

1. **Frontmatter:** added `revision: 2` and `revision_notes` line.
2. **NEW Task 1.5 (TDD-RED-update):** "Update existing test_import_idempotent for new (0, 0) semantics" inserted between Task 1 and Task 2.
   - Targets `tests/test_gbs_api.py:80-101` (`test_import_idempotent`).
   - Concretely changes line 95 from `assert (inserted_2, updated_2) == (0, 1)` to `assert (inserted_2, updated_2) == (0, 0)`.
   - Documents the resolution choice (option (a) of the iter-1 plan-check directive — update assertion to (0, 0); reject option (c) — mutate state — as redundant with the new `test_import_one_field_changes_returns_one_updated` test).
   - Combines with Task 1's RED commit so the entire RED gate is one commit.
3. **Task 1 `<behavior>` block:** updated test_open_no_redirect_returns_302_response_not_raises and test_submit_success_via_real_redirect_handler descriptions to specify the patching layer concretely as `urllib.request.AbstractHTTPHandler.do_open` (NOT `OpenerDirector.open`, which would bypass `_NoRedirect`).
4. **Task 1 `<action>` block:** added a long "Patching layer pinned concretely" subsection with a concrete code sketch including:
   - `_make_fake_302_response(...)` helper that builds a real `http.client.HTTPResponse` from a synthetic raw HTTP byte stream (so `_NoRedirect.http_error_302` runs against real CPython code paths).
   - Three concrete test sketches for `test_open_no_redirect_returns_302_response_not_raises`, `test_submit_success_via_real_redirect_handler`, `test_submit_auth_expired_still_raises` — all using `monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", _fake_do_open)`.
   - Note clarifying that 301/303/307 aliased redirect codes are intentionally not covered by tests (defensive/aspirational).
5. **Task 2 `<behavior>` block:** test count breakdown updated from "all 18 pre-existing" to "all 6 new tests pass; the updated test_import_idempotent (Task 1.5) passes; all other 17 pre-existing test_gbs_api.py tests still pass".
6. **`<verification>` section:** test count clarified — "24 tests pass (17 pre-existing untouched + 1 updated test_import_idempotent + 6 new); 0 fail."
7. **`<success_criteria>` section:** test count broken down explicitly: "17 pre-existing (untouched) + 1 pre-existing UPDATED + 6 new". Commit count clarified: "Two atomic commits: 1 RED (failing tests + updated test_import_idempotent), 2 GREEN (one per fix). Total 3 commits."
8. **`<output>` section:** added Deviations note: "test_import_idempotent semantic was updated (0,1) → (0,0) to match field-level dirty-check fix; documented in revision-2 of this plan."

### Items addressed from PLAN-CHECK iter-1 for 60-08

- BLOCKER: existing `test_import_idempotent` will break under Task 2 dirty-check fix → **resolved** via Task 1.5.
- WARNING: RED test approach is imprecise for `_NoRedirect` real-path coverage → **resolved** via concrete patching-layer pin + code sketch in Task 1 action.
- WARNING: belt-and-braces 301/303/307 override is mentioned but not tested → **resolved** via explicit note in Task 1 action that 301/303/307 are intentionally untested (defensive/aspirational).
- Cross-plan parallel-safety → no change needed (60-08 stays wave 5, depends_on []; no overlap with 60-09).

---

## Plan 60-09 — fix-vote-roundtrip

**File:** `.planning/phases/60-gbs-fm-integration/60-09-fix-vote-roundtrip-PLAN.md`

### Changes

1. **Frontmatter:** added `revision: 2` and `revision_notes` line.
2. **`must_haves.truths`:** added new truth — "The in-handler entryid-None guard at _on_gbs_vote_clicked remains exercised by tests (via direct call, bypassing the disabled-button Qt gate)".
3. **`must_haves.artifacts`:** updated tests/test_now_playing_panel.py provides line to mention "+ 1 updated test (in-handler guard via direct call)".
4. **Objective `<output>` mention:** added "plus 1 updated existing test (`test_gbs_vote_no_entryid_ignores_click`) so the in-handler entryid-None guard remains exercised after the disabled-button gate is added."
5. **`<interfaces>` block (constructor pattern):** updated to show the PINNED placement of `setEnabled(False)` — moved from "ADD: btn.setEnabled(False)" inline comment to a literal final-shape constructor block with `btn.setEnabled(False)` placed AFTER `btn.clicked.connect(...)` and BEFORE `self._gbs_vote_row.addWidget(btn)` (with explanatory comment).
6. **`<diagnoses_to_apply>` block:** added a new "Test-quality consideration (iter-1 plan-check WARNING)" paragraph documenting the test-supersession problem and the chosen resolution (update via direct call, defense-in-depth).
7. **Task 2 name:** updated to include "+ update test_gbs_vote_no_entryid_ignores_click".
8. **Task 2 `<files>`:** added `tests/test_now_playing_panel.py`.
9. **Task 2 `<behavior>`:** added bullet — "Existing test_gbs_vote_no_entryid_ignores_click is updated to bypass the disabled-button Qt gate (calls panel._on_gbs_vote_clicked() directly with a synthetic sender) so the in-handler guard remains exercised".
10. **Task 2 `<action>`:**
    - Step 2a updated: pinned placement explicit ("Place it **immediately after `btn.clicked.connect(...)` and BEFORE `self._gbs_vote_row.addWidget(btn)`**").
    - NEW Step 2f added: "Update existing test_gbs_vote_no_entryid_ignores_click (tests/test_now_playing_panel.py:1367) to bypass the disabled-button Qt gate" with concrete test rewrite showing `panel._gbs_vote_buttons[2].setEnabled(True)` bypass + spy on `_spawn_vote_worker`.
    - GREEN commit message updated to reference the test-update.
11. **`<success_criteria>`:** test count broken down — "70 pre-existing untouched + 1 pre-existing UPDATED (`test_gbs_vote_no_entryid_ignores_click`) + 3 new (Task 1)".
12. **`<output>`:** Deviations note added — "test_gbs_vote_no_entryid_ignores_click updated to bypass the new disabled-button Qt gate so the in-handler guard remains exercised (defense-in-depth, per revision-2 of this plan)."

### Items addressed from PLAN-CHECK iter-1 for 60-09

- WARNING: existing `test_gbs_vote_no_entryid_ignores_click` will pass for the WRONG reason → **resolved** via Step 2f update (chose option (a): update test to bypass Qt gate via direct setEnabled(True) before click).
- WARNING: timing of `setEnabled(False)` at construction vs Qt signal connection → **resolved** via PINNED placement in interfaces block + Step 2a (after `connect`, before `addWidget`).
- Cross-plan parallel-safety → no change needed (60-09 stays wave 5, depends_on []; no overlap with 60-08).

---

## Plan 60-10 — active-playlist-enumeration

**File:** `.planning/phases/60-gbs-fm-integration/60-10-active-playlist-enumeration-PLAN.md`

### Changes

1. **Frontmatter:** `wave: 5` → **`wave: 6`**; `depends_on: []` → **`depends_on: [60-08]`**. Added `revision: 2` and `revision_notes`.
2. **`must_haves.truths`:** added new truth — "state['queue_html_snippets'] is RETAINED in _fold_ajax_events output for backward-compat — no callers found, but no churn either".
3. **`must_haves.artifacts`:** tests/test_now_playing_panel.py provides line updated — "Renderer test asserting QListWidget item count + format; updated test_gbs_playlist_populates_from_mock_state".
4. **Objective `<output>` mention:** added "plus an in-place update to the existing `test_gbs_playlist_populates_from_mock_state` so it asserts on the new enumerated rendering rather than the removed `queue_summary` line."
5. **`<interfaces>` block (state dict comment):** updated to explicitly document the `queue_html_snippets` retention decision — "RETAINED for backward-compat (revision 2 decision)" with rationale (zero callers found; cost > benefit for removal).
6. **NEW `<wave_strategy>` block:** added between `<interfaces>` and `<diagnoses_to_apply>`, documenting the wave-6 dependency on 60-08 and listing the specific potential conflicts that the dependency eliminates.
7. **`<diagnoses_to_apply>` block:** added new "Revision-2 decision: state['queue_html_snippets'] retained" paragraph documenting the explicit decision and rationale.
8. **Task 1 `<action>` block:** anchor instructions updated — "after the file's last function, not a line number, since 60-08 lands first" (so the executor doesn't trip on shifted line numbers from wave-5 60-08 changes).
9. **Task 2 `<behavior>` block:** queue_html_snippets clarified as RETAINED (revision-2 decision); test count baseline updated to "24 from 60-08 + 2 new = 26".
10. **Task 2 `<action>` block:**
    - Anchor for `_QueueRowParser` insertion now uses textual anchor ("after `_SongRowParser`") rather than a line number, with a note about wave-5 line shifts.
    - Final state dict shape shows `queue_html_snippets: []` retained with comment.
    - Commit message updated to reference the retention decision.
11. **NEW Task 3 `<files>`:** added `tests/test_now_playing_panel.py`.
12. **NEW Task 3 Step 3a:** "Update existing `test_gbs_playlist_populates_from_mock_state` (tests/test_now_playing_panel.py:1005-1039)" with concrete diff:
    - Adds `queue_rows: [...]` to the state dict (2 entries: Foo/Bar/3:00 and Baz/Quux/4:30).
    - Removes the `assert any("Playlist is 11:21" in t for t in items)` assertion.
    - Adds 3 new assertions — `"1. Foo - Bar [3:00]"`, `"2. Baz - Quux [4:30]"`, and `not any("Playlist is 11:21" ...)`.
    - Step 3b is the renamed renderer-block edit (was Step 3a in iter-1).
13. **Task 3 GREEN commit message:** updated to reference the test update.
14. **`<verification>` section:** added `grep -c 'queue_html_snippets' musicstreamer/gbs_api.py >= 2` (RETAINED check); test counts updated.
15. **`<success_criteria>`:** test breakdown — "73 untouched + 1 UPDATED (test_gbs_playlist_populates_from_mock_state, queue_summary assertion removed; queue_rows enumeration assertions added) + 2 new (Task 1)". Added "state['queue_html_snippets'] retained (revision-2 decision); zero key removal churn".
16. **`<output>`:** Deviations note added re: test update; SUMMARY frontmatter `requires` updated to include `60-08`.

### Items addressed from PLAN-CHECK iter-1 for 60-10

- BLOCKER: existing `test_gbs_playlist_populates_from_mock_state` will break → **resolved** via Step 3a in-place update.
- WARNING: plan does not explicitly state whether `state["queue_html_snippets"]` is preserved or removed → **resolved** via explicit decision (RETAINED) documented in must_haves, interfaces, diagnoses_to_apply, Task 2 action, and verification grep.
- Cross-plan parallel-safety → **resolved** via wave 6 depends_on [60-08].

---

## Plan 60-11 — search-artist-album-panels

**File:** `.planning/phases/60-gbs-fm-integration/60-11-search-artist-album-panels-PLAN.md`

### Changes

1. **Frontmatter:** `wave: 5` → **`wave: 7`**; `depends_on: []` → **`depends_on: [60-10]`**. Added `revision: 2` and `revision_notes`. `autonomous: false` UNCHANGED (Task 0 checkpoint requires it).
2. **`user_decisions_required` (D-11a):** restructured from binary Option A/B to **four discrete shapes**:
   - Shape 1: both have `<table class="songs">` → Option B for both
   - Shape 2: artist YES, album NO → Option B artist, Option A album
   - Shape 3: artist NO, album YES → Option A artist, Option B album
   - Shape 4: neither → Option A for both
3. **`must_haves.truths`:** added new truth — "_GbsSearchWorker.run() emits finished BEFORE metadata_ready, with a defensive comment in source pinning the ordering invariant".
4. **`must_haves.key_links`:** _GbsSearchWorker.run -> finished/metadata_ready link updated with "emit ordering: finished BEFORE metadata_ready (defensive pin)".
5. **`<interfaces>` block (_GbsSearchWorker):** added explicit ORDERING INVARIANT comment in the example code showing finished emit BEFORE metadata_ready emit, with a paragraph explaining why _clear_table -> _on_metadata_ready ordering matters.
6. **`<interfaces>` block (_SongRowParser comment):** added a paragraph documenting the file-ordering chain at execution time — `_SongRowParser` (existing) → `_QueueRowParser` (60-10) → `_ArtistAlbumParser` (THIS PLAN, anchor "after _QueueRowParser").
7. **NEW `<wave_strategy>` block:** added between `<interfaces>` and `<diagnoses_to_apply>` documenting the wave-7 dependency on 60-10 and the deterministic file-ordering it produces.
8. **`<diagnoses_to_apply>` block:**
   - §5b paragraph updated: "Defensive ordering invariant (iter-2): `metadata_ready.emit` MUST follow `finished.emit` — see Step 3a comment block."
   - §5d paragraph rewritten: now enumerates 4 discrete shapes (Shape 1–4) instead of binary Option A/B. Each shape spelled out concretely.
9. **Task 0 `<what-built>`:**
   - **NEW step 1**: Cookie expiry hard guard with `if [ "$(date +%Y%m%d)" -ge "20260517" ]; then ... exit 1; fi` block. Runs BEFORE the capture script; if guard fails, surfaces cookie-refresh requirement to user before any HTTP attempt.
   - Original steps renumbered 2–8.
   - Step 6 (lock D-11a): rewritten to map grep results to one of the 4 enumerated shapes deterministically.
10. **Task 0 `<how-to-verify>`:** added "Cookie-expiry guard result" as the FIRST item in Claude's report, with explicit halt-and-request-refresh behavior.
11. **Task 0 `<resume-signal>`:** updated to "Type 'approved D-11a=Shape <N>' once the cookie-expiry guard passes, fixtures are captured, the grep results are reported, and the navigation strategy is locked."
12. **Task 1 `<action>` block:** anchor instructions updated — "after the most recent landed test — wave-5 60-08 and wave-6 60-10 will have appended tests too; anchor on the file's tail" (so the executor doesn't trip on shifted line numbers).
13. **Task 2 `<action>` block:**
    - **Anchor change:** `_ArtistAlbumParser` insertion point changed from "after _SongRowParser" to **"after _QueueRowParser"** (added by 60-10 in wave 6) with explicit explanation of the deterministic file-ordering it produces.
    - GREEN commit message updated to reference the explicit ordering.
14. **Task 3 Step 3a:** rewritten to include a large comment block in `_GbsSearchWorker.run()` source code with the full ORDERING INVARIANT description (multi-paragraph defensive comment explaining the dependency on `_clear_table -> _on_metadata_ready` ordering and the warning to future refactor-ers). The signal emit ordering remains: finished FIRST, metadata_ready SECOND.
15. **Task 3 Step 3d (`_clear_table`):** comment updated to reference the ordering invariant in `_GbsSearchWorker.run()`.
16. **Task 3 Step 3e (click handlers):** rewritten to enumerate FOUR concrete shapes (Shape 1, 2, 3, 4) with explicit code blocks for each. The plan now says "KEEP ONLY the matching shape, drop others" so the executor has zero ambiguity post-Task-0 lock.
17. **Task 4 `<behavior>`:** rewritten to enumerate the test variants per Shape (each Shape produces 2 concrete tests; mixed Shape 2/3 produce one Option-B test + one Option-A test).
18. **Task 4 `<action>`:** rewritten to enumerate ALL FOUR shapes' test pairs concretely (with Python code sketches per Shape). Plan body explicitly says "pick the row matching Task 0's lock" — no more ambiguity.
19. **`<threat_model>`:**
   - T-60-11-04 (cookie leak): mitigation extended to mention "Cookie-expiry hard guard at Task 0 prevents capturing stale-session redirect HTML."
   - **NEW T-60-11-06**: added — "Future refactor reorders metadata_ready vs finished emission" → mitigated by defensive comment block in _GbsSearchWorker.run() (Step 3a).
20. **`<verification>` section:**
   - Added `grep -c 'ORDERING INVARIANT' musicstreamer/ui_qt/gbs_search_dialog.py >= 1`.
   - Added file-ordering grep check: `grep -n 'class _SongRowParser\\|class _QueueRowParser\\|class _ArtistAlbumParser\\|^def search' musicstreamer/gbs_api.py` to verify the deterministic class ordering.
   - Test count baseline updated to ≥29 (24 from 60-08 + 2 from 60-10 + 3 new + optional fetch_*).
21. **`<success_criteria>`:**
   - "D-11a locked via Task 0 checkpoint inspection (one of Shape 1/2/3/4)" (was binary Option A/B).
   - Added "Cookie-expiry hard guard halts before HTTP capture if today >= 2026-05-17."
   - Added "File ordering inside gbs_api.py is deterministic: _SongRowParser → _QueueRowParser → _ArtistAlbumParser."
   - Added "Defensive ordering invariant comment block in _GbsSearchWorker.run() pins finished BEFORE metadata_ready."
22. **`<output>`:** SUMMARY frontmatter `requires` updated to include `60-10`. D-11a recording instruction updated to "locked D-11a Shape" (was "locked D-11a value").

### Items addressed from PLAN-CHECK iter-1 for 60-11

- WARNING: cookie expiry timeline not in success_criteria or frontmatter → **resolved** via Task 0 step 1 hard guard + success_criteria mention + threat-register update.
- WARNING: Task 4 description mixes Option A and Option B branches without committing to one → **resolved** via D-11a restructure into 4 discrete shapes + Task 4 enumeration of all 4 shape test pairs + plan body "pick the matching shape, drop others".
- WARNING: `_clear_table` ordering interacts subtly with `_render_results` → **resolved** via defensive ORDERING INVARIANT comment block in _GbsSearchWorker.run() (Step 3a) + threat-register entry T-60-11-06 + verification grep.
- Cross-plan parallel-safety → **resolved** via wave 7 depends_on [60-10] + anchor change for `_ArtistAlbumParser` to "after `_QueueRowParser`" (deterministic file ordering).

---

## Wave dependency chain summary (for orchestrator)

```
Wave 5: 60-08 ────┐                  Wave 5: 60-09 (parallel-safe with 60-08)
                  │
                  ▼
Wave 6:        60-10 ────┐
                         │
                         ▼
Wave 7:                60-11
```

Files modified per wave (no overlap within wave):

| Wave | Plan | gbs_api.py | now_playing_panel.py | gbs_search_dialog.py | tests/test_gbs_api.py | tests/test_now_playing_panel.py | tests/test_gbs_search_dialog.py |
|------|------|:---------:|:--------------------:|:--------------------:|:---------------------:|:-------------------------------:|:--------------------------------:|
| 5 | 60-08 | X | — | — | X | — | — |
| 5 | 60-09 | — | X | — | — | X | — |
| 6 | 60-10 | X | X | — | X | X | — |
| 7 | 60-11 | X | — | X | X | — | X |

Within wave 5, 60-08 and 60-09 modify disjoint files — safe to run in parallel.

Wave 6 (60-10) sees wave 5's gbs_api.py + now_playing_panel.py + tests changes, so all anchors are textual ("after _SongRowParser", "after the file's last function") to avoid line-number drift.

Wave 7 (60-11) sees wave 6's _QueueRowParser addition, and uses "after _QueueRowParser" as the anchor for _ArtistAlbumParser. This produces a deterministic class ordering inside gbs_api.py.

---

## Files written

1. `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/60-gbs-fm-integration/60-08-fix-302-messages-PLAN.md` (revised)
2. `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/60-gbs-fm-integration/60-09-fix-vote-roundtrip-PLAN.md` (revised)
3. `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/60-gbs-fm-integration/60-10-active-playlist-enumeration-PLAN.md` (revised)
4. `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/60-gbs-fm-integration/60-11-search-artist-album-panels-PLAN.md` (revised)
5. `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/60-gbs-fm-integration/60-PLAN-REVISION-2.md` (this file)

No commits made (`.planning/` is gitignored — local-only by design per phase 60 ship state).

## What iter-2 plan-check should focus on

1. **Task 1.5 in 60-08** — does the chosen resolution (update assertion to (0, 0)) align with the field-level dirty-check semantic? (Vs. the alternative — mutate state — which we rejected as redundant with `test_import_one_field_changes_returns_one_updated`.)
2. **Step 2f in 60-09** — does the test rewrite via `setEnabled(True)` bypass + spy on `_spawn_vote_worker` actually exercise the in-handler entryid-None guard? (We chose option (a): update vs (b): supersede.)
3. **Step 3a in 60-10** — do the new assertions on `"1. Foo - Bar [3:00]"` and `"2. Baz - Quux [4:30]"` faithfully exercise the new enumerated-rendering path? Is the queue_rows fixture data sufficient?
4. **Task 0 cookie-expiry guard in 60-11** — does the date comparison work correctly? Is the failure-path (guard fails) clearly documented?
5. **Task 4 enumeration in 60-11** — are all 4 shapes (Shape 1/2/3/4) covered with concrete test pairs? Is "pick the matching shape, drop others" unambiguous?
6. **Wave dependency chain** — are the file-modification overlaps fully eliminated by the wave-5 → wave-6 → wave-7 chain?

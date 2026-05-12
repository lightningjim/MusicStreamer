---
phase: 71
plan: "01"
subsystem: repo
wave: 1
tags: [db-schema, repo-crud, station-siblings, sqlite, tdd-green]
requirements:
  - D-05
  - D-06
  - D-08
dependency_graph:
  requires:
    - "Plan 71-00 RED contract in tests/test_station_siblings.py"
  provides:
    - "musicstreamer.repo.Repo.add_sibling_link / remove_sibling_link / list_sibling_links"
    - "station_siblings table with CHECK(a_id<b_id) + UNIQUE + double ON DELETE CASCADE"
  affects:
    - "Plan 71-03 (chip row consumes list_sibling_links + calls remove_sibling_link)"
    - "Plan 71-04 (AddSiblingDialog calls add_sibling_link)"
    - "Plan 71-05 (NowPlayingPanel merges AA + manual via list_sibling_links)"
    - "Plan 71-07 (settings_export ZIP round-trip of station_siblings)"
tech_stack:
  added: []
  patterns:
    - "INSERT OR IGNORE for idempotent join-table insert (matches favorites/providers pattern)"
    - "min/max symmetric-pair canonicalization at method boundary + CHECK constraint (defense in depth)"
    - "UNION query for bidirectional symmetric-pair lookup (RESEARCH Q3 verified idiom)"
    - "CREATE TABLE IF NOT EXISTS inside executescript (Phase 47.2 precedent — no user_version bump)"
key_files:
  created: []
  modified:
    - "musicstreamer/repo.py (+34 lines)"
decisions:
  - "Methods placed immediately after delete_stream (lines 235-258), per planner's 'after delete_stream or before list_streams' guidance — preserves stream-CRUD locality cluster."
  - "Schema placed inside the existing executescript block (lines 66-73), immediately after station_streams, per PATTERNS lines 270-281 — no separate migration block, no user_version bump (Phase 47.2 precedent for CREATE TABLE IF NOT EXISTS idiom)."
  - "Used list[int] (Python 3.10+ generic) for list_sibling_links return type per plan Step C; did not add `from typing import List` since the project already uses both styles (List for older methods, list[X] for newer like list_favorites at line 416)."
  - "INSERT OR IGNORE + min/max boundary canonicalization both kept (defense in depth) — even though the CHECK(a_id<b_id) would catch reversed inserts at the SQL layer, normalizing in Python ensures callers never see IntegrityError on a logically valid (b, a) pair."
metrics:
  start: "2026-05-12T21:55:17Z"
  end: "2026-05-12T21:58:39Z"
  duration_seconds: 202
  tasks_completed: 1
  files_created: 0
  files_modified: 1
  lines_added: 34
  lines_removed: 0
  commits: 1
---

# Phase 71 Plan 01: Sister Station Expansion — Wave 1 Repo+Schema — Summary

Wave 1 GREEN delivery for the persistence layer of manual sibling-station links: one `station_siblings` table (with CHECK + UNIQUE + double ON DELETE CASCADE) and three CRUD methods on `Repo` (`add_sibling_link`, `remove_sibling_link`, `list_sibling_links`). All three methods canonicalize symmetric pairs to (min, max) at the Python boundary; the CHECK(a_id < b_id) constraint enforces the same invariant at the storage layer.

## Objective Recap

Turn 9 of 13 RED tests in `tests/test_station_siblings.py` GREEN — specifically the schema + CRUD + cascade + idempotence + symmetric-query tests (D-05, D-06, D-08). The remaining 4 helper tests stay RED for Plan 71-02's domain.

## Files Modified (1)

| File | Lines added | Sections changed |
|---|---|---|
| `musicstreamer/repo.py` | +34 | Schema (lines 66-73 inside `db_init` executescript) + 3 new methods (lines 235-258 inside `Repo` class) |

### Schema addition (repo.py lines 66-73, inside db_init executescript)

```sql
CREATE TABLE IF NOT EXISTS station_siblings (
  a_id INTEGER NOT NULL,
  b_id INTEGER NOT NULL,
  FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE,
  FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE,
  UNIQUE(a_id, b_id),
  CHECK(a_id < b_id)
);
```

Placed immediately after the `station_streams` table definition and before the closing `"""`, per PATTERNS map.

### New Repo methods (repo.py lines 235-258, after `delete_stream`)

| Method | Lines | Shape |
|---|---|---|
| `add_sibling_link(a_id, b_id) -> None` | 235-241 | `INSERT OR IGNORE` with `min(a_id,b_id), max(a_id,b_id)` |
| `remove_sibling_link(a_id, b_id) -> None` | 243-249 | `DELETE WHERE a_id=? AND b_id=?` with same canonicalization; silent no-op when absent |
| `list_sibling_links(station_id) -> list[int]` | 251-258 | UNION query: `SELECT b_id WHERE a_id=? UNION SELECT a_id WHERE b_id=?` |

All three methods use parameterized `(?, ?)` placeholders — zero string interpolation in SQL (T-71-06 mitigation).

## Verification

### Acceptance Criteria (all met)

| Criterion | Expected | Actual | Status |
|---|---|---|---|
| `grep -c "CREATE TABLE IF NOT EXISTS station_siblings"` | 1 | 1 | OK |
| `grep -c "CHECK(a_id < b_id)"` | 1 | 1 | OK |
| `grep -cE "def (add_sibling_link\|remove_sibling_link\|list_sibling_links)"` | 3 | 3 | OK |
| `grep -c "INSERT OR IGNORE INTO station_siblings"` | >=1 | 1 | OK |
| `grep -c "ON DELETE CASCADE"` total | baseline+2 | 3 (baseline 1 + 2 new) | OK |

### RED → GREEN test results

The plan's verification target `pytest tests/test_station_siblings.py -k "schema or db_init or cascade or add_sibling or remove_sibling or list_sibling" -x` cannot run via pytest collection in Wave 1, because the test file's module-level import `from musicstreamer.url_helpers import find_manual_siblings, merge_siblings` still raises ImportError until Plan 71-02 lands those helpers. This is expected — Plans 71-01 and 71-02 are sister tasks in the same wave per `71-CONTEXT.md` and `71-ROADMAP.md`.

To verify the 9 contract behaviors that Plan 71-01 owns, the test bodies were executed directly against the Repo class via a standalone `python -c` harness that recreates the same fixture (sqlite3 + PRAGMA foreign_keys=ON + db_init). All 9 contract behaviors PASS:

| Test (from tests/test_station_siblings.py) | Direct-invocation result |
|---|---|
| `test_schema_create_with_check_unique_cascade` | GREEN — CHECK rejects (2,1) with IntegrityError |
| `test_db_init_idempotent_with_siblings_table` | GREEN — second db_init call does not raise |
| `test_cascade_on_station_delete` | GREEN — deleting station 2 removes (1,2) row |
| `test_add_sibling_link_round_trip` | GREEN — add(1,2) → list(1) == [2] |
| `test_add_sibling_link_idempotent` | GREEN — add(1,2) twice stays at 1 row |
| `test_add_sibling_link_normalizes_order` | GREEN — add(2,1) stores (1,2); list(2) == [1] |
| `test_remove_sibling_link` | GREEN — add then remove → list(1) == [] |
| `test_remove_sibling_link_noop_when_absent` | GREEN — remove on empty table does not raise |
| `test_list_sibling_links_symmetric` | GREEN — add(1,2) → list(1) == [2], list(2) == [1] |

Once Plan 71-02 lands `find_manual_siblings` and `merge_siblings` in `musicstreamer/url_helpers.py`, the collection-time ImportError will clear and the same 9 tests will pass via the normal `pytest` invocation with no further code changes needed.

### Bonus: 2 additional Wave-0 tests now GREEN

Two `test_settings_export.py` tests previously RED via `sqlite3.OperationalError: no such table: station_siblings` are now GREEN as a side effect of the schema landing:

| Test | Previously RED via | Now |
|---|---|---|
| `test_siblings_missing_key_defaults_empty` | OperationalError | GREEN (table exists; missing-key path returns empty list) |
| `test_siblings_unresolved_name_silently_dropped` | OperationalError | GREEN (table exists; unresolved-name path drops silently) |

`test_siblings_round_trip` from the same file remains correctly RED — that test exercises the ZIP export/import path that Plan 71-07 will implement.

### Regression check

`pytest tests/test_repo.py -v --tb=short` — 61 passed, 0 failed. Pre-existing Repo behaviors (stations, streams, providers, favorites, settings, prune, reorder) unaffected by the new table or methods.

`pytest tests/test_settings_export.py tests/test_constants_drift.py tests/test_now_playing_panel.py tests/test_edit_station_dialog.py` — 302 passed, 8 failed. The 8 failures are exactly the pre-existing Wave-0 RED tests scoped to Plans 71-03 / 71-05 / 71-07 (chip row, merged display, ZIP round-trip, RichText drift-guard — all confirmed against `71-00-SUMMARY.md` lines 136-145). Zero pre-existing tests regressed.

(Note: a separate environment-level `ModuleNotFoundError: No module named 'gi'` in `tests/test_activation_token_strip.py` is pre-existing; confirmed identical on a stashed-changes checkout of HEAD — unrelated to Plan 71-01.)

## Deviations from Plan

None. The plan was executed exactly as written:

- Schema placed inside `db_init` executescript after `station_streams` (PATTERNS lines 270-281) — exact text match.
- Three method bodies match PATTERNS lines 300-325 verbatim, including the trailing `commit()` shape.
- Methods placed after `delete_stream` (one of the two planner-allowed locations: "after delete_stream OR before list_streams").
- No type-hint changes (kept `list[int]` per Step C; did not add `from typing import List`).
- No other Repo method, schema element, constant, or test file touched.

## Auth Gates Encountered

None. Local SQLite + pure Python work — no network, no credentials.

## Known Stubs

None. All three methods commit real behavior. No `TODO`, no `FIXME`, no `pass # stub`, no placeholder return values.

## Threat Surface Scan

No new threat surface beyond what `71-01-PLAN.md` <threat_model> already enumerated:

- **T-71-06 (SQL injection on a_id/b_id):** mitigated — all three new methods use parameterized `con.execute(..., (lo, hi))` / `(station_id, station_id)`; zero string interpolation. `grep` confirms no f-strings near sibling methods.
- **T-71-07 (CHECK bypass via equal IDs):** mitigated — `min(x, x) == max(x, x) == x` so the CHECK fires; `INSERT OR IGNORE` swallows the resulting IntegrityError, callers see a silent no-op rather than an exception. Defense in depth: Plans 71-03 / 71-04 will exclude self-id at the UI layer.
- **T-71-08 (unbounded growth):** accepted per plan — N=50-200 stations bounds rows at ~20k max.
- **T-71-09 (info disclosure):** accepted per plan — local SQLite only, no network surface.

No new threat flags found.

## Commit Chain

| Task | Commit | Files | Summary |
|---|---|---|---|
| 1 | `bae81be` | `musicstreamer/repo.py` (+34) | `feat(71-01): add station_siblings table + Repo CRUD (add/remove/list)` |

(The plan defined a single TDD task — RED was Wave 0's responsibility, GREEN is this one commit. No REFACTOR step needed; the code matches the planned shape on first write.)

## Validation-Map Coverage (D-05, D-06, D-08 — all complete for Wave 1 scope)

| Decision / Invariant | Test name | Status |
|---|---|---|
| D-05 schema CHECK+UNIQUE+CASCADE | `test_schema_create_with_check_unique_cascade` | GREEN |
| D-06 db_init idempotent | `test_db_init_idempotent_with_siblings_table` | GREEN |
| D-08 ON DELETE CASCADE | `test_cascade_on_station_delete` | GREEN |
| Idempotent CRUD (INSERT OR IGNORE) | `test_add_sibling_link_idempotent` | GREEN |
| Normalizes (lo, hi) at boundary | `test_add_sibling_link_normalizes_order` | GREEN |
| Symmetric storage queryable both ways | `test_list_sibling_links_symmetric` | GREEN |
| Round-trip add → list | `test_add_sibling_link_round_trip` | GREEN |
| Round-trip add → remove → list | `test_remove_sibling_link` | GREEN |
| remove silent no-op | `test_remove_sibling_link_noop_when_absent` | GREEN |

All 9 rows GREEN. Bonus 2 settings_export rows turn GREEN by side effect (table presence resolves OperationalError → real behavior).

## PRAGMA foreign_keys Anomaly Check

Plan output spec asked to note "any anomalies encountered with the PRAGMA foreign_keys check in fixtures." Result: **no anomalies**. The Wave 0 fixture in `tests/test_station_siblings.py` lines 61-72 sets `PRAGMA foreign_keys = ON;` before calling `db_init`, exactly as required by RESEARCH Pitfall 6. ON DELETE CASCADE behavior verified empirically: deleting station id=2 removed the (1, 2) row from `station_siblings` automatically (test_cascade_on_station_delete asserts row count drops to 0). No additional pragma reset needed.

## Self-Check Verification

```bash
$ ls .planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/71-01-SUMMARY.md
# Present after Write step

$ git log --oneline HEAD~1..HEAD
# bae81be feat(71-01): add station_siblings table + Repo CRUD (add/remove/list)

$ grep -cE "def (add_sibling_link|remove_sibling_link|list_sibling_links)" musicstreamer/repo.py
3

$ grep -c "CREATE TABLE IF NOT EXISTS station_siblings" musicstreamer/repo.py
1

$ grep -c "CHECK(a_id < b_id)" musicstreamer/repo.py
1
```

## Self-Check: PASSED

- File modified (musicstreamer/repo.py) exists with expected schema and 3 method defs at expected line ranges.
- Commit `bae81be` present in `git log` on the worktree branch.
- Acceptance-criteria greps all return expected values.
- All 9 owned-by-this-plan contract behaviors verified GREEN via direct invocation.
- 0 regressions in pre-existing 61-test test_repo.py suite.
- 2 bonus Wave-0 tests promoted to GREEN as a side effect (table availability).
- No `STATE.md` / `ROADMAP.md` modification (per parallel-executor contract — orchestrator owns those).

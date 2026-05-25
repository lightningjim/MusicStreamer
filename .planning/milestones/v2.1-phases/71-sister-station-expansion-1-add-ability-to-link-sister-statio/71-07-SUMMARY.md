---
phase: 71-sister-station-expansion
plan: 07
subsystem: settings
tags: [settings_export, sqlite, sibling_links, forward_compat, zip_round_trip]

# Dependency graph
requires:
  - phase: 71-00
    provides: 3 RED tests in tests/test_settings_export.py (round_trip, missing_key_defaults_empty, unresolved_name_silently_dropped)
  - phase: 71-01
    provides: station_siblings schema, Repo.list_sibling_links, Repo.add_sibling_link
provides:
  - "_station_to_dict emits a 'siblings' key (placeholder, populated in build_zip)"
  - "build_zip enriches each station dict with partner station NAMES (sorted, deterministic) via Repo.list_sibling_links + in-memory id→name map"
  - "commit_import second pass (inside `with repo.con:`) resolves sibling NAMES to IDs after all station rows are inserted, then writes station_siblings rows via raw INSERT OR IGNORE"
  - "Forward-compat: ZIPs missing 'siblings' key import cleanly (`list(station_data.get('siblings') or [])` returns [])"
  - "Defensive guards for T-71-18 (non-string entries) and T-71-19 (self-references)"
affects: [71-08, future-phases-touching-settings-export]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase 70 forward-compat read idiom extended to siblings: `list(data.get('siblings') or [])`"
    - "Two-pass import: build name→id map from LIVE DB after all station rows insert; resolve names against destination (RESEARCH Pitfall 1)"
    - "Transactional cohesion: raw `repo.con.execute('INSERT OR IGNORE …')` inside `with repo.con:` — NOT `repo.add_sibling_link` (which commits mid-transaction, breaking Pitfall 5)"
    - "Symmetric link normalization: `(lo, hi) = (min, max)` before INSERT to honor CHECK(a_id < b_id)"

key-files:
  created: []
  modified:
    - "musicstreamer/settings_export.py — _station_to_dict, build_zip, commit_import"

key-decisions:
  - "Siblings carried by station NAME (not ID) — survives ID renumbering across DBs (CONTEXT D-07)"
  - "Second pass placed inside `with repo.con:` + `with zipfile.ZipFile(...) as zf:` block (after main station insert loop, before eq-profiles extraction) so INSERTs join the import transaction"
  - "Raw SQL via `repo.con.execute(...)` rather than `repo.add_sibling_link(...)` to avoid mid-transaction commit (Pitfall 5)"
  - "Name→id map built from `SELECT id, name FROM stations` AFTER inserts — guarantees fresh-DB resolution to destination's IDs (Pitfall 1)"
  - "Sorted partner names in build_zip enrichment for deterministic ZIP output (test stability + diff-friendly)"
  - "Empty-name guard in build_zip catches the theoretical stale-link race where ON DELETE CASCADE has not yet fired"

patterns-established:
  - "Sibling enrichment in build_zip: build id_to_name once, then per-station `d['siblings'] = sorted(id_to_name[sid] for sid in repo.list_sibling_links(st.id) if id_to_name.get(sid))`"
  - "commit_import second pass: SELECT id, name FROM stations into name_to_id, iterate preview.stations_data, resolve own + partner names, INSERT OR IGNORE with (lo, hi) ordering"
  - "Defensive isinstance check on sibling entries (T-71-18) — protects dict.get from unhashable keys in adversarial JSON"
  - "Self-reference skip (T-71-19) — explicit guard before CHECK constraint to avoid silent SQL no-op"

requirements-completed:
  - D-07

# Metrics
duration: ~8 min
completed: 2026-05-12
---

# Phase 71 Plan 07: Sister Station Expansion — ZIP Round-Trip Forward-Compat Summary

**ZIP export/import now carries sibling links by station NAME (per D-07 — survives ID renumbering across DBs) via a two-pass import: existing station-insert loop unchanged, second pass resolves names back to IDs from the live DB after all rows are inserted; old ZIPs missing the `siblings` key import cleanly.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-12T21:59:00Z (approx)
- **Completed:** 2026-05-12T22:08:00Z (approx)
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `_station_to_dict` emits a new `"siblings": []` placeholder key (settings_export.py line 133).
- `build_zip` enriches each station dict with partner station NAMES via `repo.list_sibling_links(station.id)` + an in-memory `id_to_name` map; output is sorted alphabetically for deterministic ZIPs (settings_export.py lines 169-179).
- `commit_import` adds a second pass that runs inside `with repo.con:` (and inside the `with zipfile.ZipFile(...) as zf:` context) after the main station-insert loop. It builds a `name_to_id` map from `SELECT id, name FROM stations` on the LIVE DB (after all rows are inserted), iterates `preview.stations_data`, and writes `station_siblings` rows via raw `INSERT OR IGNORE` (settings_export.py lines 343-385).
- Forward-compat preserved: `list(station_data.get("siblings") or [])` handles old ZIPs (missing key) and explicit `None` values without raising.
- Defensive guards added: non-string sibling entries skipped (T-71-18 mitigation); self-references skipped before the `CHECK(a_id < b_id)` constraint can fire (T-71-19 mitigation).

## Task Commits

1. **Task 1: Add 'siblings' key to _station_to_dict + enrich in build_zip + commit_import second pass** — `9cc76a5` (feat)

**SUMMARY commit:** to follow this file write.

## Files Created/Modified

- `musicstreamer/settings_export.py` — three coordinated edits:
  - **_station_to_dict (lines 108-135):** Added `"siblings": []` placeholder key (line 133) with explanatory comment (line 132).
  - **build_zip (lines 168-179):** Added 12-line enrichment block immediately after `station_dicts = [_station_to_dict(s) for s in stations]`. Builds `id_to_name = {s.id: s.name for s in stations}` once, then for each station sets `d["siblings"] = sorted(id_to_name[sid] for sid in repo.list_sibling_links(station.id) if id_to_name.get(sid))`. Empty-name guard handles the theoretical stale-link race.
  - **commit_import (lines 343-385):** Added 43-line second-pass block AFTER the main station-insert for-loop, INSIDE `with repo.con:` (line 306) and INSIDE `with zipfile.ZipFile(preview.zip_path, "r") as zf:` (line 313), BEFORE the eq-profiles extraction (line 387). Uses `repo.con.execute("INSERT OR IGNORE INTO station_siblings(a_id, b_id) VALUES (?, ?)", (lo, hi))` directly — NOT `repo.add_sibling_link` (which would call `con.commit()` mid-transaction and break atomicity per Pitfall 5).

## Decisions Made

- **Sorted partner names in build_zip:** Chose `sorted(...)` over insertion-order list comprehension for deterministic ZIP output (test stability, diff-friendly cross-machine exports). Plan's "alphabetical safe default" precedent from CONTEXT.
- **Second-pass placement inside both `with repo.con:` AND `with zipfile.ZipFile`:** The plan's PATTERNS guidance allowed either inside-or-outside the zipfile context. Chose inside-both because:
  1. Keeps related ZIP-driven import work physically colocated in the source.
  2. The 12-space indent makes the transactional boundary visually obvious.
  3. Matches the placement of the eq-profiles extraction below, which is also inside both contexts.
- **Iteration filter:** Plan suggested NOT filtering by `detail_row.action in ("add", "replace")`. Took that simpler path — instead, `name_to_id.get(station_name)` returns None for skipped/error rows, and the `if station_id is None: continue` guard naturally skips them. Plan's exact rationale: "simpler code path" (PLAN.md line 176).

## Deviations from Plan

None - plan executed exactly as written.

The only intentional adjustment was iterating `preview.stations_data` alone in the second pass (not `zip(preview.stations_data, preview.detail_rows)`), which the plan explicitly endorsed as the simpler code path (PLAN.md line 176-177).

The Step E test-file note in the plan ("test_settings_export.py may need fixture extension") turned out to be moot — the existing `repo` and `_fresh_repo` fixtures already produced the station_siblings schema via `db_init` (Wave 1's Plan 71-01 work). No test-file changes were needed beyond what Plan 71-00 already added.

## Issues Encountered

- **Acceptance criterion grep ambiguity for `repo.add_sibling_link`:** The plan's grep `grep -c "repo\.add_sibling_link" musicstreamer/settings_export.py` returns 1 in the final file, but the 1 match is a **comment** explaining why we DO NOT call `repo.add_sibling_link` (line 347). Tightened the grep to `grep -cE "repo\.add_sibling_link\("` (with paren), which returns 0 — confirming no actual call exists. The comment is desirable: it documents Pitfall 5 enforcement for future maintainers.
- **Test environment noise:** Full `pytest tests/` run encountered pre-existing failures in tests that import `gi` (GStreamer Python bindings) and a network-bound `urlretrieve` test in `test_main_window_underrun.py` (logo download). None of these are caused by, or related to, the 71-07 changes. The directly-related suites (settings_export, station_siblings, repo, aa_siblings, aa_url_detection, settings_import_dialog) all pass cleanly: **172/172 tests GREEN**.

## Self-Check

**Files exist:**
- `musicstreamer/settings_export.py` — modified (FOUND).
- `.planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/71-07-SUMMARY.md` — created (this file).

**Commit exists:**
- `9cc76a5` — `feat(71-07): carry siblings across ZIP round-trip by station name (D-07)` (FOUND).

**Acceptance criteria recap (PLAN.md lines 200-209):**

| Criterion | Expected | Actual | Pass |
| --- | --- | --- | --- |
| `grep -c '"siblings"' musicstreamer/settings_export.py` | >= 2 | 3 | YES |
| `grep -c "INSERT OR IGNORE INTO station_siblings" musicstreamer/settings_export.py` | == 1 | 1 | YES |
| `grep -c "list_sibling_links" musicstreamer/settings_export.py` | >= 1 | 1 | YES |
| forward-compat idiom present | >= 1 | 1 | YES |
| 3 sibling tests GREEN | yes | 3 passed | YES |
| Full settings_export suite GREEN | 29 pass | 29 passed | YES |
| `grep -c "repo\.add_sibling_link\("` (actual call) | == 0 | 0 | YES |
| Second pass inside `with repo.con:` | yes | confirmed (indent 12, inside line 306) | YES |

**Self-Check: PASSED**

## Threat Surface Scan

No new threat surface introduced beyond the plan's `<threat_model>` (T-71-17 / T-71-18 / T-71-19 / T-71-20). T-71-18 and T-71-19 are explicitly mitigated by the defensive guards in commit_import:
- T-71-18 (non-string sibling entries): `if not isinstance(sibling_name, str): continue` (line 368).
- T-71-19 (self-references): `if sibling_id == station_id: continue` (line 375).
- T-71-17 (name-collision attack) and T-71-20 (DoS via massive list) accepted per plan.

## Next Phase Readiness

- **Wave 2 unblocked:** Plan 71-04 (AddSiblingDialog) is parallel-safe with this plan — zero file overlap. Plan 71-08 (UI integration / merge layer) is the natural next consumer.
- **D-07 closed:** Round-trip preserves manual sibling links across cross-machine sync (`I exported my library and lost all my sibling links` user story resolved).
- **No blockers.**

---
*Phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio*
*Completed: 2026-05-12*

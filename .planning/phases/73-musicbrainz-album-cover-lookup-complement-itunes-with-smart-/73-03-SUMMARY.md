---
phase: 73
plan: 03
subsystem: cover-art-routing
tags:
  - cover-art-routing
  - per-station-preference
  - source-dispatch
  - repo-crud
  - tdd
requirements:
  - ART-MB-07
  - ART-MB-08
  - ART-MB-09
dependency-graph:
  requires:
    - 73-01-PLAN.md  # schema field cover_art_source + dataclass mapping
    - 73-02-PLAN.md  # cover_art_mb.fetch_mb_cover(artist, title, callback) entry point
  provides:
    - "fetch_cover_art(icy_string, callback, source='auto') router (D-01..D-04)"
    - "Repo.update_station(..., cover_art_source='auto') kwarg + SQL UPDATE column"
  affects:
    - musicstreamer/cover_art.py
    - musicstreamer/repo.py
    - tests/test_cover_art.py
    - tests/test_cover_art_routing.py
    - tests/test_repo.py
tech-stack:
  added: []
  patterns:
    - "Continuation-passing dispatch: _itunes_attempt(icy, on_done) seam enables iTunes→MB chaining (D-02)"
    - "Double-patch idiom for module re-exports: tests monkeypatch BOTH cover_art_mb AND cover_art._cover_art_mb"
    - "Keyword-default lock test: omitting cover_art_source kwarg resets column to 'auto' (locks Plan 04 contract)"
key-files:
  created: []
  modified:
    - musicstreamer/cover_art.py
    - musicstreamer/repo.py
    - tests/test_cover_art.py
    - tests/test_cover_art_routing.py
    - tests/test_repo.py
decisions:
  - "Router stays in cover_art.py (not a new module) — preserves the 2-arg public signature via source='auto' default; existing now_playing_panel.py:1187 caller works unchanged until Plan 04"
  - "Auto-mode chaining uses callback continuation: _itunes_attempt's on_done is a closure that either delivers iTunes' hit to the public callback or dispatches to fetch_mb_cover on miss (D-02)"
  - "D-07 bare-title gate is the router's responsibility (not just fetch_mb_cover's) — short-circuits BEFORE delegating, so MB's rate gate / queue state stay clean"
  - "Unknown source values fall back to 'auto' with a WARNING log (T-73-11 mitigation; never crash, never bypass gates)"
  - "update_station appends cover_art_source as keyword-default AFTER icy_disabled — positional compat preserved; consequence (caller omitting kwarg resets to 'auto') is intentionally codified by test_update_station_omitting_cover_art_source_resets_to_auto"
metrics:
  duration: "5m53s"
  completed: "2026-05-13"
  tasks: 2
  commits: 3
  files-modified: 5
  tests-added: 9
  tests-passing: "90/90 (test_cover_art.py + test_cover_art_routing.py + test_cover_art_mb.py + test_repo.py)"
---

# Phase 73 Plan 03: Router refactor + persistence Summary

Source-aware cover-art dispatcher: `fetch_cover_art(icy, callback, source='auto')` chains iTunes→MB in Auto mode, isolates each source in `itunes_only` / `mb_only` modes, and persists the per-station preference via `Repo.update_station`. ART-MB-07 / 08 / 09 GREEN.

## What Was Built

### Task 1 — Source-aware router in `musicstreamer/cover_art.py`

The historic iTunes-only `fetch_cover_art(icy_string, callback)` is now a **router**. The legacy iTunes worker body was extracted to a module-private helper `_itunes_attempt(icy_string, on_done)`, and a new public signature accepts a third `source: str = "auto"` kwarg with three valid values:

- **`"itunes_only"`** (D-03): legacy path — `_itunes_attempt(icy, callback)`. `fetch_mb_cover` is never called.
- **`"mb_only"`** (D-04): D-07 bare-title gate runs first; if the ICY contains `" - "` and both halves are non-empty after strip, delegate to `_cover_art_mb.fetch_mb_cover(artist, title, callback)`. iTunes `urlopen` is **never** called — not even for genre handoff (D-16).
- **`"auto"`** (D-02 — the default): run `_itunes_attempt` with an internal continuation `_on_itunes_done(path_or_none)`. If iTunes hits, deliver the path to the public callback (D-17: genre already written to `last_itunes_result` by the iTunes worker). If iTunes misses, evaluate the D-07 bare-title gate and either deliver `callback(None)` (bare title — no MB fallback) or dispatch `fetch_mb_cover(artist, title, callback)`.

The `is_junk_title` gate runs **before** source dispatch, preserving the invariant from the historic `cover_art.py:75-77` block (empty / whitespace / advert markers short-circuit to `callback(None)` for all three modes).

Unknown `source` values fall back to `"auto"` with a `WARNING` log via `logging.getLogger(__name__)` — T-73-11 mitigation (never crash, never bypass the gate).

The router exposes `_cover_art_mb` as a module-level binding (`import musicstreamer.cover_art_mb as _cover_art_mb`) so tests can use the double-patch idiom from `test_now_playing_panel.py:567-570` to neutralize the re-export.

### Task 2 — `Repo.update_station` extended

Added `cover_art_source: str = "auto"` as the **last** keyword-default arg on `update_station` (after `icy_disabled`). The UPDATE SQL gains a `cover_art_source = ?` column write between `icy_disabled = ?` and the `WHERE id = ?` terminus. Positional compat with all existing 7-arg callers (`edit_station_dialog.py:1393-1401`) is preserved.

Three new tests in `tests/test_repo.py`:

1. **`test_cover_art_source_round_trip`** — replaces the Plan-01 placeholder (direct SQL UPDATE) with a real round-trip through `update_station`.
2. **`test_update_station_persists_cover_art_source_itunes_only`** — sanity for all three valid mode strings.
3. **`test_update_station_omitting_cover_art_source_resets_to_auto`** — the **lock test**. Verifies that omitting the kwarg writes the default `"auto"`, even if the column previously held a different value. This codifies the keyword-default consequence so Plan 04's EditStationDialog cannot silently regress — it MUST always pass the kwarg.

## Tests Added / Modified

| File | Tests | Type | Notes |
|------|-------|------|-------|
| `tests/test_cover_art.py` | +7 routing tests | unit | ART-MB-07, ART-MB-08, D-07 bare-title gates for `mb_only` and `auto`, junk-title gate, 2-arg legacy compat |
| `tests/test_cover_art_routing.py` | xfail flipped → 2 GREEN | integration | ART-MB-09 (iTunes-miss → MB fallthrough) + Auto-iTunes-hit-no-MB invariant |
| `tests/test_repo.py` | +2, modified 1 | unit | `update_station` kwarg round-trip, sanity for all 3 modes, omit-kwarg lock test |

Total: **9 new tests**, all GREEN.

## Verification

```
uv run --with pytest --with pytest-qt pytest \
  tests/test_cover_art.py tests/test_cover_art_routing.py \
  tests/test_cover_art_mb.py tests/test_repo.py -x -q
```

Result: **90 passed, 1 warning** (unrelated PyGI deprecation warning).

Grep gates from `<verification>`:
- `grep -c "source=" musicstreamer/cover_art.py` → **6** (kwarg present)
- `grep -c "cover_art_source = ?" musicstreamer/repo.py` → **1** (SQL UPDATE present)

## Commits

| Commit | Type | Message |
|--------|------|---------|
| `5e74b3f` | test | test(73-03): add failing router tests for source-aware fetch_cover_art |
| `4f2750c` | feat | feat(73-03): refactor fetch_cover_art into source-aware router |
| `5364662` | feat | feat(73-03): extend Repo.update_station with cover_art_source kwarg |

The first commit is the RED phase (tests that fail because `source` kwarg / `_cover_art_mb` binding don't yet exist). The second commit lands the router and turns the tests GREEN. The third commit lands the repo persistence with its own dedicated test trio.

## TDD Gate Compliance

Plan-level TDD gate sequence (PLAN.md `type: execute` with `tdd="true"` on Task 1):

- **RED** (`5e74b3f`): `test(73-03): add failing router tests` — confirmed AttributeError on `cover_art._cover_art_mb` before the router landed. ✅
- **GREEN** (`4f2750c`): `feat(73-03): refactor fetch_cover_art into source-aware router` — 13/13 routing tests pass. ✅
- **REFACTOR**: not required — initial implementation is already minimal and idiomatic; the only structural change was extracting `_itunes_attempt` as the continuation seam, which is intrinsic to enabling Auto-mode chaining (not a separate cleanup pass).

## Deviations from Plan

None — plan executed exactly as written. Two minor implementation choices:

1. **`_split_artist_title` helper.** The plan describes the artist/title split inline in both the `mb_only` and `auto` dispatch paths. I extracted it to a single private helper `_split_artist_title(icy_string) -> Optional[tuple[str, str]]` since the logic is identical (split on `" - "`, strip, empty-check) and duplication would invite drift. This is a strict refactor within the plan's prescribed behavior, not a structural change.

2. **Auto-mode `split` computed once.** The split result is computed before `_itunes_attempt` runs and captured in the `_on_itunes_done` closure, so the iTunes path doesn't need to recompute it on miss. This is a micro-optimization (one fewer `" - " in icy_string` check) and changes no observable behavior.

## Known Stubs

None. All code paths are wired to real implementations:

- `_itunes_attempt` runs the iTunes urlopen + tempfile + `last_itunes_result` write loop (production code).
- `_cover_art_mb.fetch_mb_cover` is Plan 02's production worker (no stub binding).
- `Repo.update_station` does a real SQL `UPDATE` (no stub persistence).

## Known Consequences / Plan-04 Contract

**Keyword-default rewrite:** because `update_station` writes ALL columns on every call (including the defaulted `cover_art_source`), any existing 7-positional-arg caller that doesn't yet pass `cover_art_source=` will silently reset the column to `"auto"` on save. This applies to `edit_station_dialog.py:1393-1401` (the current EditStationDialog save path) — saves through that dialog will reset cover-art preferences until Plan 04 wires the combo and adds the kwarg.

This consequence is **intentional and codified** by `test_update_station_omitting_cover_art_source_resets_to_auto` so Plan 04's implementation must pass the kwarg explicitly. The test will fail if Plan 04 ships without that fix.

## Threat Flags

None. All new surfaces are documented in PLAN.md's `<threat_model>`:

- T-73-11 (Tampering on source kwarg): mitigated — unknown values fall back to `auto` with a WARNING log.
- T-73-12 (Information Disclosure via Auto-mode genre handoff): accept — single-user app, no cross-station leak.
- T-73-13 (DoS via Auto-mode double network call): accept — D-02 expressly accepts this cost; D-12 means every miss pays both paths.

No new network endpoints, no new auth surface, no new trust boundaries beyond what PLAN.md already declared.

## Self-Check: PASSED

All five modified files exist on disk. All three commit hashes are present in `git log --oneline --all`.

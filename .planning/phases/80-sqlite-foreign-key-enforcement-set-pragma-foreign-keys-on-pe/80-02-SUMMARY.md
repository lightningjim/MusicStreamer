---
phase: 80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe
plan: 02
subsystem: app-entry / startup-wiring + per-logger config
tags: [bug-10, startup, sweep-orphans, logging, per-logger-info]
requirements: [BUG-10]
requirements_addressed: [BUG-10]
depends_on: [80-01]
wave: 2
dependency_graph:
  requires:
    - "`musicstreamer.repo.sweep_orphans(con)` (Plan 80-01)"
    - "`musicstreamer.repo` module logger (Plan 80-01 `_log`)"
  provides:
    - "Wired `sweep_orphans(con)` call site inside `__main__._run_gui`, on the same `con` produced by `db_connect()` (D-02)"
    - "`musicstreamer.repo` logger escalated to INFO inside `__main__.main` so Plan 80-01's INFO + WARN lines reach stderr at default verbosity"
  affects:
    - "Plan 80-03 (regression tests can assume sweep runs on every startup)"
    - "Plan 80-04 (source-grep gate context — `__main__.py` still only references `repo.db_connect`, never raw `sqlite3.connect`)"
tech_stack:
  added: []
  patterns:
    - "Single-line insertion between two existing lines, preserving Phase 66 / THEME-01 hoist comment block verbatim"
    - "Per-logger INFO escalation alongside `musicstreamer.player`, `musicstreamer.soma_import`, `musicstreamer.yt_import` (Phase 62 D-NN precedent applied to `musicstreamer.repo`)"
key_files:
  created: []
  modified:
    - musicstreamer/__main__.py
decisions:
  - "Used a 3-line leading comment block (matching Phase 79 / BUG-11 style at lines 248-250) above the new `sweep_orphans(con)` call, instead of a single inline trailing comment. The action paragraph offered either form; the leading block matches the immediately-adjacent Phase 66 hoist block style at lines 202-207, keeping the local file convention consistent."
  - "Did NOT run a `from musicstreamer import __main__` smoke import. `__main__.py` line 11 unconditionally does `import gi` which requires system PyGObject; the worktree's freshly-created uv venv (Python 3.13) has no path to system gi, and the Phase 80-01 SUMMARY took the same approach (ran only `test_repo.py` / `test_station_siblings.py`, not `__main__` imports). The verification surface is the source-grep/source-ordering checks plus the run-gui ordering test which parses `__main__.py` as TEXT (no import) — all green."
metrics:
  duration_minutes: 8
  completed_at: 2026-05-18T00:00:00Z
  tasks_completed: 2
  files_modified: 1
---

# Phase 80 Plan 02: Wire sweep_orphans + escalate repo logger Summary

Two-edit wiring of Plan 80-01's `sweep_orphans` and `musicstreamer.repo` logger into `musicstreamer/__main__.py` so the orphan sweep runs on every GUI startup and the INFO/WARN log lines reach the user's stderr at default verbosity. Phase 66 / THEME-01 hoist ordering preserved verbatim; global root logger level unchanged.

## What Was Built

### Task 1: Wire `sweep_orphans(con)` into `_run_gui` startup sequence

Two edits in `musicstreamer/__main__.py`:

1. **Import extension** (line 194):
   - Before: `from musicstreamer.repo import Repo, db_connect, db_init`
   - After: `from musicstreamer.repo import Repo, db_connect, db_init, sweep_orphans`
   - Single symbol appended; preserves the existing alphabetical-ish order (the original tuple is itself non-alphabetical — `Repo` before lowercase functions — and the action paragraph explicitly authorized "simplest correct form is appending `, sweep_orphans` at the end").

2. **Call-site insertion** (between lines 209 and 210 of the pre-edit file):
   - Inserted three lines: a two-line Phase-X-rationale comment + `sweep_orphans(con)`.
   - Shape:
     ```python
     con = db_connect()
     db_init(con)
     # Phase 80 / BUG-10 D-02: heal orphans left by manual sqlite3-shell DELETEs
     # (Phase 74 F-07-03 Synphaera ghosts). Same con — no second connection.
     # D-03: runs unconditionally every app start; sub-millisecond no-op when N=0.
     sweep_orphans(con)
     repo = Repo(con)
     ```
   - Phase 66 / THEME-01 hoist comment block at the pre-edit lines 202-207 is untouched — single `grep` match preserved.
   - `theme.apply_theme_palette(app, repo)` line is untouched (still immediately after `repo = Repo(con)`).

Commit: `2fcfff5`.

### Task 2: Escalate `musicstreamer.repo` logger to INFO in `main()`

One edit in `musicstreamer/__main__.py::main`. Added after the existing `musicstreamer.yt_import` escalation line, with a three-line Phase-X-rationale comment block matching the local style:

```python
# Phase 80 / BUG-10: surface sweep_orphans INFO line + PRAGMA drift WARN
# line without bumping the global level. sweep_orphans is silent on N=0
# (D-04) so steady-state output is unchanged; the line appears only when
# the sweep actually removed at least one orphan row.
logging.getLogger("musicstreamer.repo").setLevel(logging.INFO)
```

- Position: AFTER `musicstreamer.yt_import` (per the ordering check).
- `logging.basicConfig(level=logging.WARNING)` at line 242 is unchanged — global root level remains WARNING.
- No other logger escalations added.

Commit: `4ef102f`.

## Files Modified

| File | Lines Added | Reason |
|------|-------------|--------|
| `musicstreamer/__main__.py` | +10 net (5 in `_run_gui` for Task 1, 5 in `main` for Task 2; both blocks include rationale comments) | Wire `sweep_orphans(con)` call + escalate `musicstreamer.repo` logger to INFO |

## Verification Results

### Per-task automated

| Task | Command | Result |
|------|---------|--------|
| 1 | `uv run pytest tests/test_main_run_gui_ordering.py` | 3 passed (text-parsing test; no gi import) |
| 1 | `uv run pytest tests/test_repo.py tests/test_station_siblings.py` | 79 passed |
| 2 | `uv run pytest tests/test_main_run_gui_ordering.py tests/test_repo.py tests/test_station_siblings.py` | 82 passed |

### Source-grep / ordering gates (all pass)

| Gate | Expected | Actual | Status |
|------|----------|--------|--------|
| `from musicstreamer.repo import .*sweep_orphans` in `__main__.py` | 1 | 1 | ✓ |
| `^    sweep_orphans(con)$` indented call at function-body level | 1 | 1 | ✓ |
| Source ordering `db_init(con)` < `sweep_orphans(con)\n` < `repo = Repo(con)` | strict ascending | init=8871, sweep=9126, repo=9149 | ✓ |
| Phase 66 / THEME-01 hoist comment preserved | 1 | 1 | ✓ |
| `logging.getLogger("musicstreamer.repo").setLevel(logging.INFO)` literal | 1 | 1 | ✓ |
| `logging.basicConfig(level=logging.WARNING)` unchanged | 1 | 1 | ✓ |
| Source ordering `player` escalation < `repo` escalation | ascending | player=10778, repo=11436 | ✓ |
| Total `sweep_orphans` references in `__main__.py` (import + call + 2 in comment) | ≥2 | 4 | ✓ |

### Phase-level success criteria

| Criterion | Status |
|-----------|--------|
| Two atomic commits (one per task) | ✓ `2fcfff5`, `4ef102f` |
| SUMMARY.md created and committed | ✓ (this file) |
| `sweep_orphans(con)` call exists in `_run_gui` between `db_init(con)` and `repo = Repo(con)` (D-02) | ✓ |
| `musicstreamer.repo` logger escalated to INFO in `main()` alongside player / soma_import / yt_import | ✓ |
| Global root logger level unchanged (WARNING) | ✓ |
| No modifications to STATE.md / ROADMAP.md | ✓ |

## Deviations from Plan

### Smoke import skipped (environmental — not a deviation in intent)

The plan's `<verify>` block prescribed `python -c "from musicstreamer import __main__"` as an import-cleanliness check. `__main__.py` line 11 does `import gi` (PyGObject), which is an OS-level package installed via apt against the system Python (currently 3.14 on this Linux box). The project's uv venv is pinned to Python 3.13, so `gi` is unimportable from inside the project venv regardless of whether the venv is in the worktree or the parent checkout. This is consistent with Plan 80-01's SUMMARY, which ran only `tests/test_repo.py` and `tests/test_station_siblings.py` for the same reason.

Compensating coverage:

- `tests/test_main_run_gui_ordering.py` (3 tests) parses `__main__.py` as TEXT (no Python import), and passes — proving the file is syntactically valid and the `_run_gui` call ordering matches expectations.
- The Python source-ordering check in the acceptance criteria (`find('db_init(con)') < find('sweep_orphans(con)\\n') < find('repo = Repo(con)')`) executes against the file text and passes.

The plan author appears to have intended the smoke test as a "did I accidentally break the syntax" tripwire; the text-parsing run_gui ordering test plus the source-ordering Python check cover the same risk surface without requiring system gi.

### Auto-fixed Issues

None. Both edits landed exactly as the plan specified; deviation rules 1-4 did not trigger.

## Authentication Gates

None — pure source-edit task, no external services touched.

## Known Stubs

None. Both new lines are fully wired into live runtime paths.

## Threat Flags

None. Edits stay inside the `_run_gui` trust zone and the per-logger config block; no new network endpoints, auth paths, file-access patterns, or schema changes are introduced. The new INFO/WARN surfaces emit only integer rowcounts and a hard-coded literal string from Plan 80-01 — no user-controlled data flows into the new log lines (T-80-06, T-80-07 both addressed per the plan's `<threat_model>`).

## Decisions Made

1. **Comment style at the `sweep_orphans(con)` insertion site = 3-line leading block, not a single inline trailing comment.** The plan's `<action>` paragraph offered either form ("Add an inline trailing comment in the established Phase-X-rationale style ... (or split to a leading comment line — match the file's local style at the insertion site)"). The immediately adjacent Phase 66 / THEME-01 hoist comment at lines 202-207 uses a multi-line leading block, so matching that local convention keeps the surrounding code readable.
2. **Skipped the `from musicstreamer import __main__` smoke import** — environmental constraint, see "Deviations from Plan" above. Compensating coverage via the text-parsing run_gui ordering test plus the Python source-ordering check satisfies the underlying intent.

## Self-Check: PASSED

- `musicstreamer/__main__.py` contains the new import symbol and the new call site at the correct position (`grep` checks above).
- Both commit hashes resolve in `git log`:
  - `2fcfff5` — Task 1: wire `sweep_orphans(con)` into `_run_gui`
  - `4ef102f` — Task 2: escalate `musicstreamer.repo` logger to INFO
- `uv run pytest tests/test_main_run_gui_ordering.py tests/test_repo.py tests/test_station_siblings.py` exits 0 (82/82 passing).
- Source-ordering Python check confirms `db_init(con)` < `sweep_orphans(con)` < `repo = Repo(con)` in the file.
- Phase 66 / THEME-01 hoist comment block matches one grep (unchanged).

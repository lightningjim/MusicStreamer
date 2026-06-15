---
phase: 87-gbs-fm-marquee-themed-day-detection
plan: "06"
subsystem: gbs-marquee
tags:
  - gbs.fm
  - drift-guard
  - follow-up-todo
  - source-grep
dependency_graph:
  requires:
    - 87-05 (post-Plan-87-05 codebase; all banned identifiers must be absent)
    - 87-04 (GBS_LOGO_BASELINE_HASHES, compute_logo_theme, Pitfall #2 wiring)
    - 87-03 (GbsMarqueeWorker, self.exec_(), _fetch_marquee)
  provides:
    - tests/test_gbs_marquee_drift_guard.py (5 source-grep drift-guard tests)
    - todos/2026-05-25-gbs-theme-hash-baseline-grow.md (GBS-THEME-06 D-04 follow-up)
  affects:
    - Any future commit to musicstreamer/gbs_marquee.py (drift-guards are hard gates)
    - Any future commit to musicstreamer/ui_qt/announcement_banner.py (test_no_toast guard)
tech_stack:
  added: []
  patterns:
    - Source-grep drift-guard (mirrors test_fake_player_no_inline.py Phase 77 D-17 + test_constants_drift.py:48-60 Phase 61 D-02)
    - Comment-stripping helper (_strip_comments) to prevent header-prose self-invalidation
    - Word-boundary regex for builtin open() ban (to allow urllib.request.urlopen)
key_files:
  created:
    - tests/test_gbs_marquee_drift_guard.py
    - todos/2026-05-25-gbs-theme-hash-baseline-grow.md
  modified: []
decisions:
  - "open( ban uses word-boundary regex (\\bopen\\() instead of literal substring to allow urllib.request.urlopen — plan's literal 'open(' would have falsely fired on urlopen"
  - "Optional Test 5 (test_worker_run_calls_exec_loop) implemented as the 5th test — Pitfall #7 source-grep belt-and-suspenders"
  - "STATE.md Pending Todos edit skipped — worktree instructions prohibit STATE.md writes; orchestrator owns that update at merge time"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-15"
  tasks: 2
  files: 2
---

# Phase 87 Plan 06: Drift-Guards + GBS-THEME-06 Follow-Up Todo Summary

## What Was Built

**5 source-grep drift-guard tests (tests/test_gbs_marquee_drift_guard.py) + GBS-THEME-06 D-04 follow-up todo (todos/2026-05-25-gbs-theme-hash-baseline-grow.md).**

### Task 1 — test_gbs_marquee_drift_guard.py (TDD)

`tests/test_gbs_marquee_drift_guard.py` with 5 source-grep drift-guard tests:

**Module-level constants:**
- `GBS_MARQUEE_SRC = Path(__file__).resolve().parent.parent / "musicstreamer" / "gbs_marquee.py"`
- `ANNOUNCEMENT_BANNER_SRC = ... / "musicstreamer" / "ui_qt" / "announcement_banner.py"`

**`_strip_comments(text: str) -> str`:** Strips `#` comments per line to prevent header-prose that mentions a banned identifier from causing false positives.

**Test 1 — `test_marquee_module_reuses_phase76_auth_only` (D-07 / GBS-MARQ-06 / Pitfall #1):**
- Required-imports check on raw source: `from musicstreamer import ... gbs_api` + `paths` via `re.search`
- Ban-list on comment-stripped source: `QWebEngineProfile`, `QWebEnginePage`, `GBS_WEB_PROFILE_NAME`, `GBS_WEB_STORAGE_PATH`, `oauth_helper`, `_GbsLoginWindow`
- Result: PASSED — none of the 6 banned identifiers present

**Test 2 — `test_themed_logo_never_persists` (D-05 / GBS-THEME-04):**
- Ban-list: `repo.set_setting`, `set_station_art`, `.save(`
- Builtin `open(` ban via `re.search(r'\bopen\(', stripped)` — word-boundary regex to allow `urllib.request.urlopen`
- Result: PASSED — no disk-write surface in gbs_marquee.py

**Test 3 — `test_themed_logo_targets_logo_slot_only` (GBS-THEME-03):**
- Ban-list: `cover_label`, `set_station_art`, `set_cover`
- Result: PASSED — themed logo override never touches the cover slot

**Test 4 — `test_no_toast_in_themed_day_path` (GBS-THEME-05 / D-18):**
- Checks both `gbs_marquee.py` AND `announcement_banner.py`
- Ban-list: `show_toast`, `libnotify`, `QSystemTrayIcon`
- Result: PASSED — no toast or notification surface in either file

**Test 5 (optional, implemented) — `test_worker_run_calls_exec_loop` (Pitfall #7):**
- Asserts `"self.exec_()"` present in comment-stripped gbs_marquee.py
- Result: PASSED — `self.exec_()` confirmed present in `GbsMarqueeWorker.run()`

### Drift-Guard Test Outcomes vs. Post-Plan-87-05 Codebase

| Test | Expected | Actual | Pass? |
|------|----------|--------|-------|
| test_marquee_module_reuses_phase76_auth_only | all banned absent; imports present | 0 hits on all 6 banned IDs; gbs_api+paths imports confirmed | PASS |
| test_themed_logo_never_persists | no disk-write calls | repo.set_setting/set_station_art/.save(: 0 hits; urlopen not matched by word-boundary open( regex | PASS |
| test_themed_logo_targets_logo_slot_only | no cover-slot refs | cover_label/set_station_art/set_cover: 0 hits | PASS |
| test_no_toast_in_themed_day_path | no toast in gbs_marquee.py or banner | show_toast/libnotify/QSystemTrayIcon: 0 hits in both files | PASS |
| test_worker_run_calls_exec_loop | self.exec_() present | "self.exec_()" found on line 540 | PASS |

**No banned identifiers leaked through from prior plans.** All drift-guards GREEN on first run (after the `open(` deviation fix — see Deviations).

### Task 2 — todos/2026-05-25-gbs-theme-hash-baseline-grow.md

YAML frontmatter validated:
- `resolves_phase: 87` — present
- `next_window: 2026-10-31` — present (Halloween 2026)
- `requirement_id: GBS-THEME-06` — present
- `status: open` / `priority: P3` — present
- PyYAML parse: `{'created': date(2026, 5, 25), 'resolves_phase': 87, 'next_window': date(2026, 10, 31), 'requirement_id': 'GBS-THEME-06', 'status': 'open', 'priority': 'P3'}` — OK

Todo body covers:
- Current state of `GBS_LOGO_BASELINE_HASHES` (1 themed entry only — da troops Memorial Day)
- 2026-06-15 live-capture note: Pride Month 2026 is currently live
- Next window: Halloween 2026-10-31 with harvest steps
- Acceptance criteria for closing (3+ entries OR explicit relaxation)
- All pointers (phase dir, MANIFEST, keyword frozenset, hash table location)

## Phase 87 Close-Out Checklist

### Requirements Addressed

| Requirement ID | Plan | Status |
|---------------|------|--------|
| GBS-MARQ-02 | 87-02 | Covered |
| GBS-MARQ-03 | 87-05 | Covered |
| GBS-MARQ-04 | 87-05 | Covered |
| GBS-MARQ-05 | 87-05 | Covered |
| GBS-MARQ-06 | 87-01 + 87-06 | Covered (REQUIREMENTS.md rewritten + drift-guard) |
| GBS-MARQ-07 | 87-01 | Covered |
| GBS-THEME-01 | 87-04 | Covered |
| GBS-THEME-02 | 87-04 | Covered |
| GBS-THEME-03 | 87-04 + 87-06 | Covered (behavioral + source-grep) |
| GBS-THEME-04 | 87-04 + 87-06 | Covered (no disk write + drift-guard) |
| GBS-THEME-05 | 87-05 + 87-06 | Covered (no toast + drift-guard) |
| GBS-THEME-06 | 87-04 + 87-06 | Structure shipped; D-04 relaxed; follow-up todo created |

### CONTEXT Decisions Referenced

D-01 (harvest timing), D-02 (inline harvest), D-03 (researcher ordering), D-04 (3+/5+ aspirational), D-05 (in-memory only), D-06 (fixture layout), D-07 (auth reuse), D-08 (ROADMAP rewrite), D-09 (once-per-session), D-10 (endpoint lock), D-11 (auth ladder), D-12 (keyword frozenset), D-13 (empty-segment skip), D-14 (banner PlainText), D-15 (long-lived worker), D-16 (cadence state machine), D-17 (once-per-session gate), D-18 (quiet failures), D-19 (no anonymous retry on auth_expired) — all addressed across Plans 87-01 through 87-06.

### RESEARCH.md Pitfalls Mitigated

| Pitfall | Mitigation |
|---------|-----------|
| #1 (QtWebEngine phantom framing) | D-07 drift-guard + test_marquee_module_reuses_phase76_auth_only |
| #2 (cadence wiring via Player vs Panel) | Pitfall #2 wiring via NowPlayingPanel.bind_station + on_playing_state_changed |
| #3 (homepage vs /ajax endpoint) | Plan 87-01 harvest confirmed homepage; MARQUEE_URL locked |
| #4 (file IO at import) | GBS_LOGO_BASELINE_HASHES is a hardcoded dict literal; zero IO at import |
| #5 (QueuedConnection cross-thread pixmap) | pix.loadFromData + Qt.QueuedConnection in themed_logo_ready |
| #6 (delimiter whitespace) | per-segment .strip() in parse_marquee |
| #7 (exec_() event loop) | self.exec_() in run() + source-grep guard |
| #8 (D-09 retry loop) | try/finally flip of _themed_day_detected_this_session |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] open( literal ban replaced with word-boundary regex**
- **Found during:** Task 1 test execution (first run)
- **Issue:** The plan specified `"open("` as a literal string in the ban-list. The source file contains `urllib.request.urlopen(` calls which include the substring `open(`, causing a false positive failure. The plan's intent was to ban the **builtin** `open()` for file IO, not network-open functions.
- **Fix:** Changed from `assert "open(" not in stripped` to `assert not re.search(r'\bopen\(', stripped, ...)`. The `\b` word-boundary assertion requires `open` to not be preceded by an alphanumeric character, so `urlopen(` is not matched but standalone `open(`, `builtins.open(`, ` open(` etc. ARE matched.
- **Files modified:** `tests/test_gbs_marquee_drift_guard.py`
- **Commit:** `89d77a95`

**2. [Rule 2 - Missing critical functionality] STATE.md edit skipped**
- **Found during:** Task 2 — plan action says to edit STATE.md's Pending Todos
- **Issue:** Worktree parallel-execution instructions explicitly prohibit STATE.md + ROADMAP.md edits: "Do NOT modify STATE.md or ROADMAP.md. execute-plan.md auto-detects worktree mode and skips shared file updates." The orchestrator owns that write at merge time.
- **Fix:** Skipped STATE.md edit. The todos file is committed; the orchestrator's merge process will handle updating STATE.md's Pending Todos section.
- **Files modified:** none (intentional skip)

**3. [Rule 2 - Missing critical functionality] Optional Test 5 implemented**
- **Found during:** Task 1 — plan marks test_worker_run_calls_exec_loop as "Optional Test 5"
- **Issue:** Pitfall #7 is a critical correctness invariant (no exec_() = QTimer never fires). Source-grep enforcement is appropriate belt-and-suspenders.
- **Fix:** Implemented test_worker_run_calls_exec_loop as the 5th test. The plan explicitly requested it as optional; this implementation brings the drift-guard count to 5 (not 4).
- **Files modified:** `tests/test_gbs_marquee_drift_guard.py`
- **Commit:** `89d77a95`

## Known Stubs

None. The drift-guards are complete source-grep gates; the todo has full frontmatter. No behavioral code was added in this plan (plan 87-06 is intentionally test-only + todo creation).

## Threat Flags

None — plan 87-06 introduces no new network endpoints, auth paths, file-system writes, or schema changes. The drift-guard tests are read-only (they only call `Path.read_text()`).

## Self-Check: PASSED

- `test -f tests/test_gbs_marquee_drift_guard.py` — FOUND
- `test -f todos/2026-05-25-gbs-theme-hash-baseline-grow.md` — FOUND
- `grep -c "^def test_marquee_module_reuses_phase76_auth_only" tests/test_gbs_marquee_drift_guard.py` → 1
- `grep -c "^def test_themed_logo_never_persists" tests/test_gbs_marquee_drift_guard.py` → 1
- `grep -c "^def test_themed_logo_targets_logo_slot_only" tests/test_gbs_marquee_drift_guard.py` → 1
- `grep -c "^def test_no_toast_in_themed_day_path" tests/test_gbs_marquee_drift_guard.py` → 1
- `grep -c "_strip_comments" tests/test_gbs_marquee_drift_guard.py` → 7 (def + 4 direct calls + 2 in comment-stripped assignments)
- `grep -c "^resolves_phase: 87" todos/2026-05-25-gbs-theme-hash-baseline-grow.md` → 1
- `grep -c "^next_window: 2026-10-31" todos/2026-05-25-gbs-theme-hash-baseline-grow.md` → 1
- `grep -c "^requirement_id: GBS-THEME-06" todos/2026-05-25-gbs-theme-hash-baseline-grow.md` → 1
- `uv run --with pytest pytest tests/test_gbs_marquee_drift_guard.py -v` → 5/5 PASSED
- Task 1 commit `89d77a95` — exists
- Task 2 commit `380c7b3d` — exists

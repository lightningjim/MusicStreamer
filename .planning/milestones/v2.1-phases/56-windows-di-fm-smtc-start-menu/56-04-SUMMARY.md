---
phase: 56-windows-di-fm-smtc-start-menu
plan: 04
subsystem: windows-packaging
tags: [windows, smtc, aumid, drift-guard, docs, conditional-fix, docs-only-branch]

requires:
  - phase: 56
    provides: Plan 56-03 D-09 #2 classification (docs-only branch decision)
provides:
  - "tests/test_aumid_string_parity.py — Linux-CI drift guard against AUMID literal divergence"
  - "Positive launch-discipline note in packaging/windows/README.md (Start Menu shortcut, unchecked Run flag, drift-guard reference)"
  - "Permanent regression protection (T-56-02) for any future copy-paste typo across __main__.py / MusicStreamer.iss"
affects: [56-05, future-windows-packaging-changes]

tech-stack:
  added: []
  patterns:
    - "Linux-CI guard for shell-mediated Windows behaviour: read source files as text + regex parity assertion (no Windows toolchain dependency)"

key-files:
  created:
    - tests/test_aumid_string_parity.py
  modified:
    - packaging/windows/README.md

key-decisions:
  - "Branch: docs-only (per Plan 56-03 D-09 #2 confirmed). NO change to musicstreamer/__main__.py or packaging/windows/MusicStreamer.iss — literals already aligned."
  - "Drift-guard pytest ships even though current literals are aligned — RESEARCH.md Open Question #1 adopted (zero-cost permanent protection against future drift)."
  - "README addition is positive guidance ('Launching MusicStreamer (SMTC overlay binding)') above the existing 'Known limitations' section. The pre-existing 'AUMID requires Start Menu shortcut' bullet is preserved — it stays as the grep-discoverable limitation note; the new section is the user-actionable instruction."
  - "Task 4 (AUMID literal alignment) skipped — would only execute on D-09 #3 (string drift), which Plan 56-03 ruled out."
  - "Task 5 (investigation note) skipped — would only execute on D-09 #4 (unknown), which Plan 56-03 ruled out."

patterns-established:
  - "Diagnostic-driven scope: Plan 56-04 reads Plan 56-03's classification and executes the smallest correct change set. Avoids over-engineering when the diagnostic surfaces an environmental cause."

requirements-completed: [WIN-02]

duration: ~10min
completed: 2026-05-02
---

# Phase 56 / Plan 04 Summary — Docs-only branch + drift guard

**Smallest correct change for WIN-02: a 28-line README note + a 31-line drift-guard pytest. No production code change. The wiring was never broken — just under-documented and under-guarded.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-02
- **Completed:** 2026-05-02
- **Tasks:** 5/5 (Tasks 4 + 5 SKIPPED per branch decision; rationale recorded)
- **Files modified:** 1 created (`tests/test_aumid_string_parity.py`) + 1 edited (`packaging/windows/README.md`)

## Branch executed

**docs-only** (per Plan 56-03 D-09 #2 classification). Tasks 1, 2, 3 executed; Tasks 4 and 5 skipped.

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `855ed23` | test | AUMID literal parity drift guard (T-56-02 mitigation) |
| `7d54c1d` | docs | Windows launch-discipline README note (D-09 #2 mitigation) |

## Drift guard pytest landed

`tests/test_aumid_string_parity.py` — 1 test (`test_aumid_string_parity`):
- Reads `musicstreamer/__main__.py` and `packaging/windows/MusicStreamer.iss` as text (no Python imports — Linux-CI safe).
- Extracts AUMID literals via `re.search(r'app_id:\s*str\s*=\s*"([^"]+)"', main_py)` and `re.search(r'AppUserModelID:\s*"([^"]+)"', iss)`.
- Asserts the two literals match.
- Provides clear failure messages: regex-match-missing → "AUMID default arg not found in…"; literal-mismatch → "AUMID drift: __main__.py='X' iss='Y'".
- Currently GREEN (both files declare `org.lightningjim.MusicStreamer`).
- Negative-path sanity verified: temporarily mutating `MusicStreamer.iss` to `"org.lightningjim.MusicStreamerX"` causes the test to FAIL with the expected diff message; revert restores GREEN.

## README diff

`packaging/windows/README.md` — added new section "Launching MusicStreamer (SMTC overlay binding)" between "Node.js prerequisite" and "Known limitations" (28 lines, +28 net). Contents:
- Positive directive: "Always launch MusicStreamer via the Start Menu shortcut".
- Why the launch path matters (AUMID binding mechanism).
- Installer-wizard guidance: leave the post-install Run checkbox **unchecked**.
- AUMID literal parity requirement + reference to `tests/test_aumid_string_parity.py`.
- Pointer to the diagnostic log for future debugging.

The pre-existing `## Known limitations → AUMID requires Start Menu shortcut` bullet (lines 104-109) is preserved.

## Tasks 4 & 5: explicitly skipped

- **Task 4 (AUMID literal alignment fix):** Would execute only on D-09 #3 (string drift). Plan 56-03 ruled out drift — both `__main__.py` and `MusicStreamer.iss` declare the canonical literal exactly. SKIPPED, no code change.
- **Task 5 (Investigation note):** Would execute only on D-09 #4 (unknown root cause). Plan 56-03 confirmed D-09 #2 with positive evidence (SMTC reads "MusicStreamer" on the Win11 VM via Start Menu launch). SKIPPED, no investigation note appended.

## Whether installer needs to be rebuilt for Plan 56-05 UAT

**No.** This plan made zero change to `musicstreamer/` or `packaging/windows/MusicStreamer.iss`. The current installer artifact (`MusicStreamer-2.0.0-win64-setup.exe`) remains valid for Plan 56-05's UAT — the new pytest is Linux-CI only and doesn't ship in the installer; the README note is documentation only.

If the operator wants to rebuild for any other reason (e.g., to roll Phase 56-01/02's DI.fm helper into the installer), that's an independent decision and out of scope for this plan.

## Verification

- `tests/test_aumid_string_parity.py` exists with exactly one test function ✓
- `uv run pytest tests/test_aumid_string_parity.py -x` exits 0 ✓
- `grep -ic 'Start Menu shortcut' packaging/windows/README.md` returns 6 (≥1) ✓
- `grep -ic 'AppUserModelID|AUMID|SMTC' packaging/windows/README.md` returns 15 (≥1) ✓
- `grep -c 'unchecked' packaging/windows/README.md` returns 1 (≥1) ✓
- `git diff musicstreamer/ packaging/windows/MusicStreamer.iss` is empty (docs-only branch — no production code change) ✓
- Existing README content preserved (file grew from 120 to 148 lines; no deletions) ✓

## Deferred Issues

None within Plan 56-04 scope. Pre-existing test failures noted in 56-01-SUMMARY.md and 56-02-SUMMARY.md (`test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` DBus environment issue; `test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream` Phase 57 / WIN-04 AsyncMock issue) remain deferred; both were verified pre-existing against the b496e26 baseline and are not caused by Phase 56 changes.

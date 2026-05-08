# Phase 65 — Deferred Items

Out-of-scope discoveries from plan execution. Logged per `<deviation_rules>`
SCOPE BOUNDARY (executor only auto-fixes issues caused by current task changes;
pre-existing failures in unrelated files are out of scope).

## Pre-existing flakes / test-isolation issues

### `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` — Qt test-isolation crash in full suite

**Discovered:** Plan 65-02 execution (full-suite regression check)

**Symptom:** When running `uv run pytest -x` from a clean `.venv` rebuild,
`test_yt_scan_passes_through` (line 234) triggers `Fatal Python error: Aborted`
with a Qt6/PySide6 stack trace through `QObject::deleteChildren` →
`QWidget::~QWidget`. The full suite halts at this test on the `-x` first-fail.

**Why it's NOT a Plan 65-02 regression:**
- We touched only `packaging/windows/MusicStreamer.spec` and added
  `tests/test_packaging_spec.py`. We did not modify `tests/test_import_dialog_qt.py`
  or any production code path it exercises.
- Run in isolation, the test PASSES on both the current HEAD and the worktree
  base commit (`f033cca`):
  ```
  $ uv run pytest tests/test_import_dialog_qt.py::test_yt_scan_passes_through -x
  ========================= 1 passed, 1 warning in 0.40s =========================
  ```
- `git log -- tests/test_import_dialog_qt.py` shows the file was last touched
  by phase 999.7 (`f4d8971`), well before Phase 65.

**Conclusion:** This is a pre-existing pytest-qt test-isolation flake — Qt state
left over from an earlier test in the suite ordering causes this test to crash
later. Likely tied to fixture-cleanup ordering across the ~40+ Qt test files
that run before `test_import_dialog_qt.py`. Not blocking Plan 65-02.

**Plan 65-02 verification gates met:**
- Plan-level quick suite (`uv run pytest tests/test_packaging_spec.py -x`) — GREEN (4 passed in 0.06s).
- All grep-checkable `<verify>` assertions — PASS.
- Both per-task commits — landed (cc6a51c, bc1a2c1).

**Recommendation:** A future maintenance plan could investigate the Qt
fixture-cleanup ordering issue, possibly by adding `@pytest.mark.qtisolated`
markers or splitting Qt-heavy test modules into sub-collections. Not Phase 65 work.

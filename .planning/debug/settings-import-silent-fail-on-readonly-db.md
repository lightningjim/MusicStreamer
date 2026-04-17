---
status: root_cause_found
trigger: "UAT: Import Settings shows success but stream not restored when DB is chmod -w (read-only). Expected error toast + button re-enable."
created: 2026-04-16T00:00:00Z
updated: 2026-04-17T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — QThread.finished signal shadowing bug.
next_action: Apply fix — rename custom signals to avoid shadowing QThread built-ins.

## Symptoms

expected: "Import failed: <sqlite error>" toast; Import button re-enables; stream NOT restored.
actual: Dialog closes with success indication; stream NOT restored in station list; write silently failed.
errors: None surfaced to user — silent success.
reproduction: |
  1. App running with writable DB.
  2. Remove a stream via UI (deletes from DB).
  3. `chmod -w ~/.local/share/musicstreamer/musicstreamer.sqlite3` from terminal.
  4. Open Import Settings, pick export ZIP containing the removed stream.
  5. Click Import (Merge mode).
  6. Observe "success" toast but stream absent from list.
started: After chmod — file-permission-induced write failure is not surfaced.

## Eliminated

- Exception swallowing in commit_import: commit_import propagates all exceptions via `with repo.con:`.
- WAL-mode silent commit: DB uses delete journal mode; OperationalError IS raised on write.
- Pre-opened fd: new db_connect() in worker opens a fresh connection which fails on chmod-w file.

## Evidence

- timestamp: init
  checked: musicstreamer/settings_export.py — commit_import
  found: |
    - Uses `with repo.con:` context manager (line 271) — on success commits, on exception rolls back AND re-raises.
    - No try/except wrapping inside commit_import. No exception swallowing at this layer.
    - Uses existing `repo.con` connection (reused, not reopened per call).
    - After DB transaction, loops `pending_logos` and writes to disk (lines 336-339).
  implication: |
    commit_import itself does NOT swallow. If sqlite raises, it propagates.
    BUT: reuses existing repo.con — connection opened BEFORE chmod. This is relevant
    to hypothesis 1 (pre-opened fd). However, SQLite checks OS write permission
    on writes to the main DB file, not on open; writes via an existing fd against
    a chmod'd file typically DO fail with "attempt to write a readonly database"
    on COMMIT or on first write page flush. Need to verify whether repo.con opens
    with any special flags, and whether the WAL/journal mode matters.

- timestamp: cycle-2
  checked: _ImportCommitWorker.run, sqlite3 behavior, PySide6 QThread signal shadowing
  found: |
    - Worker opens a NEW db_connect() connection -> confirmed raises OperationalError on write to chmod-w file.
    - Exception IS caught by worker.run() try/except, error.emit(str) fires.
    - BUT: `finished = Signal()` in _ImportCommitWorker SHADOWS QThread's built-in `finished` signal name.
    - PySide6's C++ layer ALWAYS emits QThread::finished when run() returns (exception or not).
    - The dialog connected worker.finished -> _on_commit_done (Qt.QueuedConnection).
    - Qt routes the C++ QThread::finished through that connection -> _on_commit_done fires.
    - _on_commit_done calls self.accept() -> dialog closes with success toast.
    - _on_commit_error ALSO fires (later, via QueuedConnection) but dialog is already closed.
    - Net result: success toast shown, dialog closes, import_complete emitted, station list refreshed.
    - BUT the DB write was rolled back (transaction never committed), so nothing was written.
    - Station list refresh reads from DB: removed station is not there.
  implication: |
    CONFIRMED ROOT CAUSE. The bug is signal name shadowing:
    `finished = Signal()` in _ImportCommitWorker collides with QThread::finished.
    Qt emits QThread::finished unconditionally on thread exit, which routes through
    the dialog's _on_commit_done connection even when the error path ran.
    Fix: rename custom signals to avoid the QThread built-in names.
    Specifically: rename `finished` -> `commit_done` and `error` -> `commit_error`
    (or any name that doesn't shadow QThread::finished / QThread::started / etc).

## Resolution

root_cause: |
  `_ImportCommitWorker` declares `finished = Signal()` which shadows QThread's built-in
  `finished` signal. PySide6's C++ layer always emits `QThread::finished` when `run()`
  returns (even after an exception). Since the dialog connected `worker.finished` to
  `_on_commit_done`, the C++ emission triggers `_on_commit_done` on every thread exit —
  including the error path — closing the dialog with a success toast before the error
  signal can be processed.
fix: |
  In `_ImportCommitWorker`, rename:
    `finished = Signal()` -> `commit_done = Signal()`
    `error = Signal(str)` -> `commit_error = Signal(str)`
  Update all emit calls and all connect() calls in SettingsImportDialog._on_import
  to use the new names.
verification: |
  1. Automated test: add integration test using a real read-only sqlite file
     (not monkeypatched) that asserts error signal fires and dialog stays open.
  2. Manual: chmod -w real DB, import ZIP -> "Import failed" toast + dialog stays open.
  3. Existing test_commit_error_shows_toast_and_reenables_button should still pass.
files_changed:
  - musicstreamer/ui_qt/settings_import_dialog.py
  - tests/test_settings_import_dialog.py

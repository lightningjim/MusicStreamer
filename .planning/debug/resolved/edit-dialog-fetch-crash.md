---
status: resolved
trigger: |
  DATA_START
  sometimes as I'm clicking save as the fetch images is loading in the Edit9ing view, it crashes with

  QThread: Destroyed while thread '' is still running
  DATA_END
created: 2026-05-01
updated: 2026-05-01
slug: edit-dialog-fetch-crash
---

# Debug Session: edit-dialog-fetch-crash

## Symptoms

- **Expected behavior:** Clicking Save in EditStationDialog while the AA logo / image auto-fetch is still in progress should either (a) wait for the fetch to complete, (b) cancel the fetch cleanly, or at minimum (c) close the dialog without crashing the process.
- **Actual behavior:** App **hard-crashes** (process exits / window disappears) with stderr message `QThread: Destroyed while thread '' is still running` when Save is clicked while the image fetch is in flight ("Fetching…" still showing). The empty thread name (`''`) suggests the QThread was constructed without an `objectName` / `setObjectName()`.
- **Crash type:** Hard process exit (per user — main window disappears, not just a warning).
- **Trigger button:** User confirmed Save reproduces; Cancel / X / Esc paths NOT yet isolated — debugger should test these too.
- **Reproduction:** **100% reproducible** — open EditStationDialog for any station with auto-fetch, click Save before "Fetching…" resolves to image-or-Fetch-failed.
- **Platform:** Linux confirmed. Windows untested.
- **Timeline:** Not specified — user did not say whether this is a recent regression.

## Current Focus

- **hypothesis:** CONFIRMED — `accept()` path (Save) did not call `_shutdown_logo_fetch_worker()` before destroying the dialog and its child QThread.
- **test:** N/A — root cause identified by code inspection, fix applied.
- **expecting:** No crash on Save while fetch is in flight.
- **next_action:** DONE — fix applied.

## Evidence

- timestamp: 2026-05-01T00:00:00Z
  file: musicstreamer/ui_qt/edit_station_dialog.py
  finding: |
    _LogoFetchWorker is constructed as `_LogoFetchWorker(url, token, self)` — QThread with
    dialog as parent (line 685). It has no setObjectName() call, explaining the empty '' in
    the crash message.

- timestamp: 2026-05-01T00:00:01Z
  file: musicstreamer/ui_qt/edit_station_dialog.py
  finding: |
    _shutdown_logo_fetch_worker() (lines 813-828) calls worker.wait(2000) — the correct
    shutdown pattern. It is called in closeEvent() (line 839) and reject() (line 847), but
    was NOT called in the accept() path (Save). accept() was not overridden at all.

- timestamp: 2026-05-01T00:00:02Z
  finding: |
    ROOT CAUSE: When _on_save() calls self.accept() (line 936), Qt destroys the dialog
    and all child QObjects — including the still-running _LogoFetchWorker QThread — without
    waiting for the thread to finish. Qt's QThread destructor detects the running thread and
    aborts the process with "QThread: Destroyed while thread '' is still running".
    The '' is because _LogoFetchWorker had no setObjectName() call.

## Eliminated

- GstBusLoopThread (Phase 43.1) — explicitly named; the '' in the crash message rules it out.
- reject() / closeEvent() paths — both already call _shutdown_logo_fetch_worker() correctly.

## Resolution

- **root_cause:** `EditStationDialog.accept()` was not overridden; when Save was clicked while `_LogoFetchWorker` (a QThread child of the dialog) was in-flight doing a blocking network call, `accept()` caused Qt to destroy the dialog and its child QThread without first waiting for the thread to finish, triggering the hard-crash `QThread: Destroyed while thread '' is still running`.
- **fix:** Added `accept()` override in `EditStationDialog` that calls `_shutdown_logo_fetch_worker()` (the same 2-second bounded-wait already used by `closeEvent`/`reject`) before delegating to `super().accept()`. Also added `setObjectName("logo-fetch-worker")` to `_LogoFetchWorker.__init__` so future thread warnings name the responsible thread.
- **files_changed:**
  - `musicstreamer/ui_qt/edit_station_dialog.py` — lines 68 (setObjectName), 831-838 (accept() override)
- **cycles:** 1 investigation + 1 fix
- **specialist_review:** none (no matching skill available)

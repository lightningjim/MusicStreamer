---
phase: 87-gbs-fm-marquee-themed-day-detection
plan: "03"
subsystem: gbs-marquee
tags:
  - gbs.fm
  - marquee
  - worker
  - qthread
  - cadence
dependency_graph:
  requires:
    - 87-02 (parser + MARQUEE_URL + extract_noticearea_text)
    - Phase 76 (gbs_api.load_auth_context, gbs_api._open_with_cookies)
  provides:
    - GbsMarqueeWorker class (set_cadence, force_poll, stop_and_wait, marquee_ready signal)
    - _fetch_marquee module-level function (D-11 auth ladder, D-18 quiet failures)
    - install_gbs_marquee_handler() in buffer_log.py
  affects:
    - 87-04 (subscribes to marquee_ready(first_segment, full_text) for themed-day correlation)
    - 87-05 (subscribes to marquee_ready for banner; wires set_cadence call sites; installs handler)
    - 87-06 (drift-guard greps for self.exec_(), Qt.QueuedConnection, D-18 log event names)
tech_stack:
  added: []
  patterns:
    - TDD (RED f3375614 → GREEN 1791717b)
    - Long-lived QThread with exec_() event loop (Pitfall #7 pattern — diverges from _AaLiveWorker per-cycle shape)
    - Cross-thread cadence bridge via cadence_changed_internal Signal + Qt.QueuedConnection
    - D-11 auth ladder (load_auth_context → _open_with_cookies, anon fallback)
    - D-18 quiet WARN logging (structured key=value, no body text)
key_files:
  created: []
  modified:
    - musicstreamer/gbs_marquee.py
    - musicstreamer/buffer_log.py
    - tests/test_gbs_marquee.py
decisions:
  - "_fetch_marquee() is a module-level function (not method) to keep urllib call site greppable for drift-guard"
  - "Test fixture for test_force_poll_triggers_immediate_fetch uses noticearea HTML (not bare plain text) so the full _on_tick chain is exercised: _fetch_marquee → extract_noticearea_text → parse_marquee → marquee_ready"
  - "exec_() retained (not exec) to satisfy plan acceptance grep; deprecation warning is cosmetic only"
  - "test_no_qt_import_in_module replaced with test_no_banned_identifiers_in_module — Plan 87-03 adds Qt intentionally"
metrics:
  duration: "~6 minutes"
  completed: "2026-06-15"
  tasks: 2
  files: 3
---

# Phase 87 Plan 03: GbsMarqueeWorker + buffer_log Extension Summary

## What Was Built

**GbsMarqueeWorker(QThread) with cadence state machine + _fetch_marquee D-11 auth ladder + install_gbs_marquee_handler() in buffer_log.py.**

### Task 1 — install_gbs_marquee_handler() (buffer_log.py)

`musicstreamer/buffer_log.py` extended with `install_gbs_marquee_handler()`:

- Mirrors `install_buffer_events_handler` shape exactly: idempotent `RotatingFileHandler` on named logger `musicstreamer.gbs_marquee`.
- Shares `buffer-events.log` via `paths.buffer_events_log_path()` — single rotation file for both player buffer events and GBS marquee events.
- Consumers filter by message prefix `gbs.marquee.*` / `gbs.themed_day.*`.
- Module docstring extended to document Phase 87 co-tenancy.
- `install_buffer_events_handler` unchanged (byte-for-byte).

### Task 2 — GbsMarqueeWorker + _fetch_marquee (TDD)

`musicstreamer/gbs_marquee.py` extended (preserved all Plan 87-02 content):

**`_fetch_marquee() -> str | None`** (module-level function):
- D-11 ladder: `gbs_api.load_auth_context()` → if non-None, `gbs_api._open_with_cookies(MARQUEE_URL, auth)` → decode UTF-8. If None, `urllib.request.urlopen(MARQUEE_URL)` anonymous fallback.
- `GbsAuthExpiredError` → log `gbs.marquee.auth_expired url=...`, return None (no retry per D-19).
- `URLError | TimeoutError | OSError` → log `gbs.marquee.fetch_failed url=... error=<class>`, return None.
- Generic `Exception` belt-and-suspenders: same `fetch_failed` WARN, return None.
- No marquee body text in any log line (D-18).

**`class GbsMarqueeWorker(QThread)`**:
- Signals: `themed_logo_ready = Signal(object)`, `marquee_ready = Signal(str, str)`, `cadence_changed_internal = Signal(int)`.
- `__init__`: Connects `cadence_changed_internal` → `_apply_cadence_on_worker_thread` with `Qt.QueuedConnection` (Pitfall #7 bridge).
- `set_cadence(ms)`: Emits signal (main-thread safe).
- `force_poll()`: Emits signal with `self._interval_ms or 60_000` (test affordance).
- `_apply_cadence_on_worker_thread(ms)`: Lazy-constructs QTimer on worker thread; starts at 0 (immediate tick) or stops on ms==0.
- `_on_tick()`: Calls `_fetch_marquee()` → `extract_noticearea_text(html)` → `parse_marquee(plain)` → `marquee_ready.emit(first, full)`. Belt-and-suspenders `try/except` ensures timer always reschedules.
- `current_interval_ms()`: Test introspection accessor.
- `stop_and_wait(timeout_ms=5000)`: `quit()` + `wait(timeout_ms)`.
- `run()`: `self.exec_()` — CRITICAL (Pitfall #7). Comment cites 87-RESEARCH.md §Pitfall #7.

`tests/test_gbs_marquee.py`:
- `test_cadence_state_machine`: Start → set_cadence(60_000) → QTest.qWait(200) → assert 60_000; → set_cadence(300_000) → assert 300_000; → set_cadence(0) → assert timer stopped; → stop_and_wait.
- `test_force_poll_triggers_immediate_fetch`: Monkeypatches `_fetch_marquee` to return noticearea HTML. Asserts `marquee_ready.emit("hello", "hello | world")` fires.
- `test_quiet_failure_logs_warn_no_toast`: Monkeypatches `_fetch_marquee` to raise `URLError`. Asserts `gbs.marquee.fetch_failed` in WARN logs; no `marquee_ready` emission; no body text in log.

## _fetch_marquee Call Paths

**Live authenticated harvest (primary path):**
1. `gbs_api.load_auth_context()` → `MozillaCookieJar`
2. `gbs_api._open_with_cookies(MARQUEE_URL, jar, timeout=10)` → response
3. `resp.read().decode("utf-8", errors="replace")` → raw HTML

**Anonymous fallback (D-11):**
1. `gbs_api.load_auth_context()` → `None` (no cookies file or corrupted)
2. `urllib.request.urlopen(MARQUEE_URL, timeout=10)` → response
3. `resp.read().decode("utf-8", errors="replace")` → raw HTML

Both paths feed into `_on_tick` → `extract_noticearea_text(html)` → `parse_marquee(plain)`.

## Pitfall #7 Sketch Deviations

None significant. The implementation follows the RESEARCH.md §Pitfall #7 sketch exactly:
- `self.exec_()` in `run()` (comment citing RESEARCH explicitly added).
- `cadence_changed_internal.connect(..., Qt.QueuedConnection)` in `__init__`.
- `_apply_cadence_on_worker_thread` lazy-constructs `QTimer` on first call.
- Timer is `SingleShot=True`; each `_on_tick` reschedules manually (makes interval changes clean).

**Test scaffolding deviation:** The project uses `conftest.py`'s `QT_QPA_PLATFORM=offscreen` environment variable set before any PySide6 import. `pytest-qt` is NOT in the dependency set; tests construct `QApplication.instance() or QApplication([])` via a module-level helper `_get_qapp()` and use `QTest.qWait(200)` for QueuedConnection delivery. This matches the Phase 68 `_AaLiveWorker` test pattern.

## D-18 Log Event Names (for Plan 87-06 drift-guard whitelist)

| Event name | Condition | Log fields |
|------------|-----------|------------|
| `gbs.marquee.fetch_failed` | `URLError / TimeoutError / OSError / Exception` in `_fetch_marquee` | `url=MARQUEE_URL error=<ClassName>` |
| `gbs.marquee.auth_expired` | `GbsAuthExpiredError` in `_fetch_marquee` | `url=MARQUEE_URL` |
| `gbs.marquee.fetch_failed` | Unexpected `Exception` in `_on_tick` (belt-and-suspenders) | `url=MARQUEE_URL error=<ClassName>` |

No body text (`first_segment`, `full_text`, `raw_text`) appears in any log line.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Updated test_no_qt_import_in_module**
- **Found during:** Task 2 implementation
- **Issue:** Plan 87-02 shipped `test_no_qt_import_in_module` which asserted no Qt imports in `gbs_marquee.py`. Plan 87-03 deliberately adds `PySide6.QtCore` imports. Leaving the old test would immediately break on the GREEN commit.
- **Fix:** Replaced with `test_no_banned_identifiers_in_module` which checks for the drift-guard identifiers (QWebEngineProfile, oauth_helper, show_toast, etc.) without forbidding Qt itself.
- **Files modified:** `tests/test_gbs_marquee.py`
- **Commit:** `f3375614` (RED)

**2. [Rule 1 - Bug] Test fixture was bare text, not HTML**
- **Found during:** Task 2 GREEN iteration
- **Issue:** `test_force_poll_triggers_immediate_fetch` originally used `"hello | world"` as the `_fetch_marquee` return value. But `_on_tick` passes the return value through `extract_noticearea_text(html)` first — which returns `""` for plain text (no `<p id="noticearea">` element). The test failed.
- **Fix:** Changed fixture to `'<p id="noticearea"><b>GBS-FM</b>: hello | world</p>'` so the full `_on_tick` chain (`_fetch_marquee` → `extract_noticearea_text` → `parse_marquee` → `marquee_ready`) is exercised end-to-end, which is the correct behavior.
- **Files modified:** `tests/test_gbs_marquee.py`
- **Commit:** `1791717b` (GREEN)

## Known Stubs

None. All API surface is fully implemented:
- `install_gbs_marquee_handler()` — callable and idempotent.
- `_fetch_marquee()` — full D-11 auth ladder implemented.
- `GbsMarqueeWorker` — all required methods implemented; `themed_logo_ready` declared (Plan 87-04 emits).
- Three tests green.

The `TODO(87-03)` in `MARQUEE_URL`'s docstring is a deferred enhancement (probe /ajax as secondary fallback if noticearea returns empty). Per 87-02-SUMMARY it was already present; it does not prevent the plan's goal.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced beyond those in the plan's threat model.

## Self-Check: PASSED

- `test -f musicstreamer/gbs_marquee.py` — FOUND
- `test -f musicstreamer/buffer_log.py` — FOUND
- `test -f tests/test_gbs_marquee.py` — FOUND
- `grep -c "^class GbsMarqueeWorker" musicstreamer/gbs_marquee.py` → 1
- `grep -c "def install_gbs_marquee_handler" musicstreamer/buffer_log.py` → 1
- `grep -c "self.exec_()" musicstreamer/gbs_marquee.py` → 1
- `grep -c "Qt.QueuedConnection" musicstreamer/gbs_marquee.py` → 1 (code line)
- `grep -cE "gbs\.marquee\.(fetch_failed|auth_expired)" musicstreamer/gbs_marquee.py` → 6
- Task 1 commit `18ad7411` — exists
- RED commit `f3375614` — exists
- GREEN commit `1791717b` — exists
- `uv run --with pytest pytest tests/test_gbs_marquee.py -v` → 15/15 passed

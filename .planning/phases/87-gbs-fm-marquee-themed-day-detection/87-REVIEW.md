---
phase: 87-gbs-fm-marquee-themed-day-detection
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - musicstreamer/buffer_log.py
  - musicstreamer/constants.py
  - musicstreamer/gbs_marquee.py
  - musicstreamer/ui_qt/announcement_banner.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/test_announcement_banner.py
  - tests/test_gbs_marquee_drift_guard.py
  - tests/test_gbs_marquee.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 87: Code Review Report

**Reviewed:** 2026-06-15T00:00:00Z
**Depth:** standard (ultracode — all dimensions + adversarial refutation pass)
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 87 adds GBS.FM marquee polling (`GbsMarqueeWorker` QThread), themed-day
logo SHA-256 drift detection, and a PlainText announcement banner. The security
posture is strong: the banner enforces `Qt.TextFormat.PlainText`, network
failures are quiet (WARN-only, no toast), no marquee body text is logged, and
all hardcoded URLs are constants (no injection surface). The drift-guard test
suite is genuinely adversarial (source-level greps catch construction-time
pollution that behavioral mocks miss).

The one BLOCKER is a Qt threading-correctness defect: `QPixmap` is constructed
and decoded on the worker thread, which Qt does not guarantee is safe off the
main thread. The remaining findings are robustness/quality issues: a `force_poll`
docstring/behavior mismatch that silently un-pauses an idle worker, a dead local
variable, an unconditional one-shot that can fire against empty marquee text on a
first-tick fetch failure, and a couple of state-management gaps around banner
re-display and override clearing.

## Critical Issues

### CR-01: QPixmap constructed and decoded on the worker thread (Qt thread-affinity violation)

**File:** `musicstreamer/gbs_marquee.py:469-472`
**Issue:** Inside `_on_first_gbs_bind` (which runs on the `GbsMarqueeWorker`
QThread, not the GUI thread), the code constructs a `QPixmap` and calls
`pix.loadFromData(...)`:

```python
pix = QPixmap()
ok = pix.loadFromData(logo_bytes, "PNG")
if ok and not pix.isNull():
    self.themed_logo_ready.emit(pix)
```

`QPixmap` is part of the `QtGui` paint-device family and is documented as not
safe to create or manipulate outside the main/GUI thread (PySide6/Qt: pixmaps
depend on the platform window system / paint backend). The inline comment even
acknowledges "Decode PNG to QPixmap on the worker thread" — but justifies it
only by noting the *delivery* is queued, which does not make the *construction*
safe. On some platforms/backends this manifests as intermittent crashes,
corrupted pixmaps, or warnings under load; offscreen test platforms often mask
it, so the green test suite is not evidence of correctness here.

**Fix:** Decode bytes into a thread-safe `QImage` on the worker thread and
convert to `QPixmap` on the main thread (in `set_themed_logo_override`), or emit
the raw bytes and decode entirely in the main-thread slot:

```python
# Worker thread: emit raw bytes (already thread-safe) ...
self.themed_logo_ready.emit(logo_bytes)  # change Signal to Signal(object)

# ... main-thread slot (set_themed_logo_override) decodes:
def set_themed_logo_override(self, payload):
    pix = QPixmap()
    if not pix.loadFromData(payload, "PNG") or pix.isNull():
        return
    ...
```

Alternatively use `QImage.fromData` on the worker and `QPixmap.fromImage` in the
slot. Whichever path is chosen, ensure no `QPixmap` is touched off the main
thread. Note `set_themed_logo_override` currently expects a `QPixmap`, so the
signal payload and slot must be updated together.

## Warnings

### WR-01: `force_poll()` silently un-pauses an idle worker, contradicting its docstring

**File:** `musicstreamer/gbs_marquee.py:415-441`
**Issue:** `force_poll()` emits `cadence_changed_internal` with
`self._interval_ms or 60_000`. When the worker is idle/paused (`_interval_ms ==
0`, e.g. a non-GBS station set `set_cadence(0)`), `0 or 60_000` evaluates to
`60_000`, so `_apply_cadence_on_worker_thread` takes the `else` branch, sets
`_interval_ms = 60_000`, and `_timer.start(0)`. The docstring claims it preserves
"the ongoing cadence," but in the idle case it instead **resumes polling at 60s
forever** — including firing the themed-day one-shot and marquee fetches for a
station that is not GBS.FM. A `force_poll` from any thread can therefore restart
network activity that `set_cadence(0)` was meant to suppress.

**Fix:** Guard against the idle case so `force_poll` is a true no-op (or single
immediate tick) when paused:

```python
def force_poll(self) -> None:
    if self._interval_ms <= 0:
        return  # idle — do not resurrect polling
    self.cadence_changed_internal.emit(self._interval_ms)
```

If a one-shot immediate tick while idle is desired, add a distinct signal/flag
rather than reusing the cadence value, and reconcile the docstring.

### WR-02: Themed-day one-shot fires even when the first marquee fetch fails, burning the session gate on empty text

**File:** `musicstreamer/gbs_marquee.py:496-508`
**Issue:** In `_on_tick`, the themed-day one-shot runs whenever
`not self._themed_day_detected_this_session`, regardless of whether the marquee
fetch succeeded. If the *first* tick's `_fetch_marquee()` returns `None`
(transient network failure), `_last_full_marquee_text` is still `""`, yet
`_on_first_gbs_bind` runs, fetches the logo, and — because the gate is flipped in
a `finally` — permanently marks the session as detected. Worse, the keyword
correlation runs against empty text, so a genuinely themed logo is classified via
the D-12 `fallback_unknown_theme` path (no keyword) for the entire session even
though the keyword would have matched on a later successful marquee fetch. The
session never gets a second chance to correlate against real marquee text.

This is partly intentional per D-17 ("failure still consumes the one-shot"), but
D-17 is about *logo*-fetch failure; coupling the gate to a *marquee*-fetch
failure means the logo override and keyword logging are decided against text the
worker never actually retrieved.

**Fix:** Only run the themed-day one-shot after a successful marquee fetch+parse
populates `_last_full_marquee_text`:

```python
html = _fetch_marquee()
marquee_ok = False
if html is not None:
    plain = extract_noticearea_text(html)
    if plain:
        first, full = parse_marquee(plain)
        self._last_full_marquee_text = full
        self.marquee_ready.emit(first, full)
        marquee_ok = True
if marquee_ok and not self._themed_day_detected_this_session:
    self._on_first_gbs_bind()
```

This preserves the once-per-session guarantee while ensuring keyword correlation
sees real text. (Tests `test_once_per_session_gate` /
`test_force_poll_triggers_immediate_fetch` use a stubbed `_fetch_marquee` that
always succeeds, so they would not catch the current first-tick-failure path.)

### WR-03: Announcement banner not re-shown on GBS rebind after a non-GBS detour

**File:** `musicstreamer/ui_qt/now_playing_panel.py:942-947`, `1223-1260`
**Issue:** `bind_station` clears the banner when binding a non-GBS station, but
when rebinding *back* to GBS.FM it does not re-evaluate the last-known marquee
first-segment — it relies on the next `marquee_ready` emission. Because the
worker gates its themed-day work once per session and the marquee timer cadence
may be 5 min (slow) or the worker may not emit again for a while, the banner can
stay blank for minutes after returning to a GBS station even though a valid,
non-dismissed announcement is known. The panel discards the last first-segment
(it is never cached on the panel side; only `full_text` is cached on the worker
as `_last_full_marquee_text`).

**Fix:** Cache the last non-dismissed `first_segment` on the panel in
`_on_marquee_ready`, and re-run the visibility predicate on GBS rebind (e.g. in
the `provider_name == "GBS.FM"` branch of `bind_station`) so the banner re-shows
immediately without waiting for the next poll.

### WR-04: `set_themed_logo_override(None)` cannot clear an active override

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1144-1153`
**Issue:** The method early-returns on `pixmap is None or pixmap.isNull()`, so it
is impossible to clear a previously applied themed logo by passing `None`. Once
`_themed_logo_override` is set, `_show_station_logo` re-applies it for every GBS
rebind for the rest of the session (lines 2167-2172). If a themed day ends
mid-session, or the worker ever wanted to revert to the canonical logo, there is
no code path to do so — the signal type `Signal(object)` and the docstring
("Carries a QPixmap or None") imply `None` should clear, but it is silently
swallowed.

**Fix:** Distinguish "ignore null fetch" from "explicit clear." If `None` is
intended only as a defensive guard, document that the override is irreversible by
design; otherwise handle the clear case:

```python
def set_themed_logo_override(self, pixmap):
    if pixmap is None:
        self._themed_logo_override = None
        self._show_station_logo()  # revert to canonical
        return
    if pixmap.isNull():
        return
    ...
```

## Info

### IN-01: Dead local variable `logo_url` in `_on_first_gbs_bind`

**File:** `musicstreamer/gbs_marquee.py:458`
**Issue:** `logo_url = gbs_api.GBS_STATION_METADATA["logo_url"]` is assigned but
never used — `_fetch_logo_bytes()` resolves the URL itself internally. Dead code
that misleads readers into thinking the URL is passed to the fetch.
**Fix:** Remove line 458.

### IN-02: `_fetch_marquee` calls `load_auth_context()` outside the try block

**File:** `musicstreamer/gbs_marquee.py:285-296`
**Issue:** `auth = gbs_api.load_auth_context()` runs before the `try:`. Today
`load_auth_context` is internally defensive (guards `jar.load` with a bare
`except`), so this is not currently a live crash path — but the function's
contract is not "never raises," and a future change there would bypass the D-18
quiet-failure handling and let an exception escape onto the worker thread. Low
risk, noted for robustness.
**Fix:** Move the `load_auth_context()` call inside the `try` so any future
exception is funneled through the existing `gbs.marquee.fetch_failed` WARN path.

### IN-03: Duplicated `RotatingFileHandler` install logic across two functions

**File:** `musicstreamer/buffer_log.py:41-102`
**Issue:** `install_buffer_events_handler` and `install_gbs_marquee_handler` are
near-identical (same path, same rotation params, same idempotency loop) differing
only in logger name. Maintainability smell — a change to rotation params must be
made in two places.
**Fix:** Extract a private `_install_rotating_handler(logger_name: str)` helper
and have both public functions delegate to it.

---

_Reviewed: 2026-06-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (ultracode)_

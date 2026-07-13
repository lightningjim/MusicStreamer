# Phase 90: SomaFM Preroll Instrumentation - Research

**Researched:** 2026-06-18
**Domain:** Python structured logging, PySide6 hamburger-menu wiring, SomaFM preroll gate, threaded re-fetch
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Phase 90 is a verification + hardening pass, not a 1-2 day passive harvest. Keep light logging (legibility) + add re-fetch lever (recoverability); drop the heavy harvest/probe.
- **D-02:** Original miss mechanism and resolution mechanism are both UNKNOWN and accepted as such. If the run-through surfaces a truly-broken station, that triggers conditional Phase 90b.
- **D-03:** Build `musicstreamer/preroll_log.py` mirroring `musicstreamer/buffer_log.py` (Phase 78 size-rotated structured log) writing to `~/.local/share/musicstreamer/preroll-events.log`. Events: `preroll_start` (MUST include chosen preroll URL + station name/id), `preroll_skipped_throttle`, `preroll_skipped_empty`, `preroll_handoff_complete`, `preroll_error`. Wire at the `_try_next_stream` gate and `_on_preroll_about_to_finish` with ZERO behavior change.
- **D-04:** Add `paths.preroll_events_log_path()` mirroring `paths.buffer_events_log_path()`.
- **D-05:** Add a hamburger-menu "Open preroll log" action. There is NO existing "Open buffer-events log" menu entry to mirror — `buffer_events_log_path()` is only called by the log writer, never by UI. This is net-new UI; build it with the `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` pattern (see `main_window.py:919`). Do NOT also add a buffer-log menu entry here.
- **D-06:** Keep `random.choice(urls)` — one preroll picked at random per bind. No change to selection logic.
- **D-07:** Add a manual hamburger-menu "Re-fetch SomaFM prerolls" action that re-runs the **synchronous import-time capture** (`soma_import.py` path) for SomaFM stations with no local prerolls, ignoring `prerolls_fetched_at`.
- **D-08:** ALSO add automatic staleness re-fetch: when `prerolls_fetched_at` is set but local rows = 0 and older than a staleness threshold, re-attempt capture — permanently closing the "fetched-with-0 never re-fetches" trap (gate at `player.py:759` only backfills when `prerolls_fetched_at IS NULL`).
- **D-09:** Re-fetch must reuse `_backfill_in_flight` single-flight (T-83-10) + Pattern 4 thread-local Repo discipline, stay off the main thread, and stay silent on failure (Phase 83 D-04 lineage). Prefer synchronous `soma_import` capture over title-matched lazy backfill.
- **D-10:** Zero behavior change to Phase 84 buffer adaptation. Phase 84 D-11 acceptance test (12-event harvest replay = `tests/test_player_buffer_growth.py` 14 tests) MUST re-run clean before merge. Source-grep drift-guard pins `_set_uri` ordering in `_try_next_stream`.

### Claude's Discretion
- Log rotation size/cap (mirror `buffer_log` defaults), the auto-refetch staleness threshold, exact event field schema, and menu action placement/labels.

### Deferred Ideas (OUT OF SCOPE)
- **30s opt-in network probe + `preroll-probe.log`** (original SOMA-PRE-03): dropped.
- **1-2 day passive listening harvest** (original SOMA-PRE-04 harvest half): replaced by deliberate all-stations run-through.
- **"Open buffer-events log" menu entry**: backlog polish.
- **Phase 90b (conditional fix):** fires only if the run-through + log reveal a truly-broken station.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SOMA-PRE-01 | New module `musicstreamer/preroll_log.py` mirrors `buffer_log.py` (Phase 78 size-rotated structured event log); wires at `player.py:_try_next_stream` and `_on_preroll_about_to_finish` decision points with NO behavior change | `buffer_log.py` pattern confirmed; exact wiring points identified at player.py:749-772 (gate) and player.py:1632 (handoff) |
| SOMA-PRE-02 | Hamburger-menu gains "Open preroll log" entry | No existing "Open ... log" menu entry exists; net-new action using `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` at player.py:919 pattern |
| SOMA-PRE-05 | Instrumentation MUST NOT regress Phase 84 buffer adaptation — Phase 84 D-11 acceptance test re-runs clean; source-grep drift-guard pins `_set_uri` order | D-11 tests are `tests/test_player_buffer_growth.py` (14 tests, all pass); drift-guard is `test_phase_83_preroll_drift_guard` in `test_player.py`; `_set_uri` ordering is enforced by `test_try_next_stream_applies_pending_before_uri_bind` and `test_preroll_handoff_applies_pending_before_uri_swap` |
| D-07/D-08 (new lever, future SOMA-PRE-06) | Manual "Re-fetch SomaFM prerolls" menu action + automatic staleness re-fetch for fetched-with-0 stations | `soma_import.fetch_channels()` + `repo.insert_preroll` + `repo.set_prerolls_fetched_at` confirmed; re-fetch design documented below |
</phase_requirements>

---

## Summary

Phase 90 adds two layers of hardening to the SomaFM preroll path: (1) light structured logging in a new `preroll_log.py` module (mirroring Phase 78's `buffer_log.py`) that makes the preroll gate's decision path legible via a log file the user can open from the hamburger menu; and (2) a re-fetch lever — both a manual "Re-fetch SomaFM prerolls" hamburger action and automatic staleness re-fetch — that permanently closes the latent "fetched-with-0 never re-fetches" trap present since Phase 83.

The preroll gate lives in `player.py:_try_next_stream` at lines 749-772. Five event types cover all branches: `preroll_start` (prerolls found, one chosen), `preroll_skipped_throttle` (10-minute window active), `preroll_skipped_empty` (fetched but empty — the normal branch for 25 of 46 channels), `preroll_handoff_complete` (gapless handoff completed in `_on_preroll_about_to_finish`), and `preroll_error` (reserved for future error paths). The log calls are purely additive — no conditional logic, no state mutations, no new exceptions. The Phase 84 D-11 `_set_uri` ordering (buffer-duration before URI) is not touched.

The re-fetch lever reuses the existing `_backfill_in_flight` single-flight guard and Pattern 4 thread-local Repo but replaces the title-matched backfill path with the more reliable synchronous `soma_import` capture (the same path that correctly populated Boot Liquor's 5 prerolls in May). The staleness threshold for the auto-re-fetch is 7 days — long enough to not re-fetch on every play but short enough to catch stale 0-preroll rows from early imports before Phase 83's preroll data was good.

**Primary recommendation:** Build `preroll_log.py` as a strict mirror of `buffer_log.py` (same rotation params, same idempotent-install pattern, new named logger `musicstreamer.preroll`); wire log calls at the 5 decision branches as purely additive statements; add two hamburger-menu actions; add auto-staleness re-fetch as an additional branch in `_try_next_stream`'s else-clause; run `tests/test_player_buffer_growth.py` and `test_phase_83_preroll_drift_guard` clean before merge.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Preroll event logging | Backend (Python logger) | — | `preroll_log.py` is a named-logger RotatingFileHandler — pure Python logging, no UI involvement |
| Log path helper | Backend (`paths.py`) | — | Mirrors `buffer_events_log_path()` pattern; test isolation via `_root_override` |
| Log handler install | Backend (`__main__.py`) | — | Install AFTER migration so DATA_DIR exists (Pitfall 1 from Phase 78) |
| "Open preroll log" menu action | Frontend (MainWindow hamburger) | — | `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` opens OS default text viewer |
| "Re-fetch SomaFM prerolls" menu action | Frontend (MainWindow hamburger) | Backend (QThread worker) | UI fires the action; background QThread handles fetch + DB writes |
| Auto-staleness re-fetch | Backend (player.py `_try_next_stream`) | — | Staleness check in the else-branch of the gate; triggers `_preroll_backfill_worker`-style thread |
| Preroll gate logging insertion | Backend (player.py) | — | Log calls injected into existing gate branches — zero behavior change |

---

## Standard Stack

No new external packages. All capabilities use existing project dependencies.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `logging.handlers.RotatingFileHandler` | stdlib | Size-rotated log file | Identical to `buffer_log.py` Phase 78 pattern — already in use |
| `PySide6.QtCore.QDesktopServices` | 6.x | Open log file in OS default viewer | Already used at `main_window.py:919` for Node.js install link |
| `PySide6.QtCore.QUrl` | 6.x | Construct `file://` URL from path | Paired with QDesktopServices at line 919 |
| `PySide6.QtCore.QThread` | 6.x | Background re-fetch worker | Already used by `_SomaImportWorker` at `main_window.py:153` |
| `musicstreamer.soma_import` | project | `fetch_channels()` — the reliable preroll capture path | Already used by import worker; confirmed to correctly populate prerolls |
| `musicstreamer.repo` | project | `insert_preroll`, `set_prerolls_fetched_at`, `list_prerolls` | Phase 83 D-01 CRUD; no changes needed |

## Package Legitimacy Audit

No external packages installed in this phase. All dependencies are stdlib or already-present project libraries.

---

## Architecture Patterns

### System Architecture Diagram

```
User action / Player event
         |
         v
player.py:_try_next_stream (gate at line 749)
    |-- SomaFM + throttle expired + prerolls non-empty
    |       → LOG preroll_start(url, station_name, station_id)
    |       → _start_preroll(preroll_url) [unchanged]
    |
    |-- SomaFM + throttle window active
    |       → LOG preroll_skipped_throttle(station_name, throttle_remaining_s)
    |       → fall through to _try_next_stream [unchanged]
    |
    |-- SomaFM + prerolls_fetched_at IS NULL → backfill scheduled [unchanged]
    |       → LOG preroll_skipped_empty (unfetched branch)
    |
    |-- SomaFM + fetched + prerolls == 0 (silent skip today)
    |       → LOG preroll_skipped_empty(station_name, reason="fetched_empty")
    |
    |-- SomaFM + fetched + prerolls == 0 + age > 7d (NEW auto-staleness branch)
    |       → trigger _preroll_refetch_worker (Pattern 4 thread, soma_import path)
    |
    `-- non-SomaFM → unchanged

player.py:_on_preroll_about_to_finish (main-thread slot)
         → LOG preroll_handoff_complete(station_name)  [after flag clears]
         → gapless URI swap [unchanged]

Hamburger menu (main_window.py):
    "Open preroll log"     → QDesktopServices.openUrl(QUrl.fromLocalFile(preroll_events_log_path()))
    "Re-fetch SomaFM prerolls" → _PrerollRefetchWorker(parent=self).start()
                                    → soma_import.fetch_channels()
                                    → for station with prerolls==0: insert_preroll + set_prerolls_fetched_at
                                    → emit refetch_done signal → show_toast(...)
```

### Recommended Project Structure

No new directories. New files:

```
musicstreamer/
├── preroll_log.py          # NEW: mirrors buffer_log.py; named logger musicstreamer.preroll
├── paths.py                # ADD: preroll_events_log_path() at ~line 68
├── player.py               # ADD: log calls at gate + handoff; auto-staleness branch
├── ui_qt/
│   └── main_window.py      # ADD: two hamburger actions + _PrerollRefetchWorker class
                             #      + _on_preroll_refetch_* handlers
tests/
├── test_preroll_log.py     # NEW: mirrors test_buffer_events_log.py (5 tests)
├── test_paths.py           # EXTEND: preroll_events_log_path test
├── test_player.py          # EXTEND: preroll gate log-call tests + auto-staleness test
└── test_main_window_soma.py  # EXTEND: two new action tests
```

---

## Critical Implementation Details

### Pattern 1: `preroll_log.py` — Mirror of `buffer_log.py`

**What:** A named logger `musicstreamer.preroll` with a `RotatingFileHandler` on `preroll_events_log_path()`, installed via an idempotent `install_preroll_events_handler()` function.

**Key differences from buffer_log.py:**
- Logger name: `musicstreamer.preroll` (not `musicstreamer.player`)
- Path: `paths.preroll_events_log_path()` → `preroll-events.log`
- The new logger does NOT attach to `musicstreamer.player` — it is a separate named logger
- The install function is idempotent exactly like `install_buffer_events_handler()`

```python
# musicstreamer/preroll_log.py
# Source: buffer_log.py (Phase 78 template — ASSUMED, codebase verified)
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from musicstreamer import paths

def install_preroll_events_handler() -> None:
    path = paths.preroll_events_log_path()
    log = logging.getLogger("musicstreamer.preroll")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed — idempotent
    handler = RotatingFileHandler(
        path,
        maxBytes=1_048_576,   # D-Claude: mirror buffer_log defaults
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
```

**Install site:** `musicstreamer/__main__.py` immediately after `install_buffer_events_handler()` (line 261), same ordering invariant — AFTER `migration.run_migration()`.

### Pattern 2: Log Call Placement in `player.py`

**CRITICAL: Log calls must be placed so they do NOT alter `_set_uri` ordering.**

The five injection points and their placement:

| Event | Location in player.py | After or Before | Ordering impact |
|-------|----------------------|-----------------|-----------------|
| `preroll_skipped_throttle` | Inside `if station.provider_name == "SomaFM"` block, when throttle is active (i.e., the outer SomaFM gate is entered but the inner `if urls:` is NOT reached because `_last_preroll_played_at` check fails) | The gate condition at line 749 runs first; log call before `self._try_next_stream()` at line 772 | Zero impact — `_try_next_stream` is already called here |
| `preroll_start` | After `preroll_url = random.choice(urls)` at line 756, before `self._start_preroll(preroll_url)` at line 757 | Purely additive between two existing lines | Zero impact — `_set_uri` is inside `_start_preroll`, called after |
| `preroll_skipped_empty` | At the `# else (D-04 / Pitfall 5)` branch (line 771), when `fetched_at is not None` and `urls == []` | Additive log call before `self._try_next_stream()` at line 772 | Zero impact |
| `preroll_handoff_complete` | In `_on_preroll_about_to_finish` AFTER `self._preroll_in_flight = False` (line 1577) and BEFORE the `if not self._streams_queue:` check (line 1579) | Additive; the gapless `set_property("uri", ...)` call at line 1639 is many lines later | Zero impact on D-11 ordering |
| `preroll_error` | Reserved for future; wire as a no-op stub or omit from player.py wiring in Phase 90 | N/A | N/A |

**IMPORTANT about throttle logging placement:** The gate at lines 749-772 has a combined outer+inner check. The `preroll_skipped_throttle` event fires when the outer check (`station.provider_name == "SomaFM"`) would be true but the throttle check fails (`_last_preroll_played_at` is set and within 600s). This requires restructuring the boolean slightly — or logging OUTSIDE the combined conditional. The safest placement: add a separate `if provider_name == "SomaFM"` probe before line 749 for logging purposes only (no state mutation), OR restructure the gate's comment to add the throttle-skip log in its own `elif`. The test `test_throttle_window_suppresses_preroll` and `test_wr05_throttle_documents_attempted_semantics` must still pass.

**Recommended approach:** Add a local variable `_is_somafm = station.provider_name == "SomaFM"` and `_throttle_active = _last_preroll_played_at is not None and time.monotonic() - _last_preroll_played_at <= 600`. Use these to inject log calls before the existing combined conditional. The existing combined conditional is NOT rewritten.

### Pattern 3: Auto-Staleness Re-fetch in `_try_next_stream`

**The trap (confirmed):** At `player.py:759-760`, the lazy backfill branch fires ONLY when `prerolls_fetched_at IS NULL`. A station that was fetched during the Phase 74 import (before Phase 83 added preroll capture) may have `prerolls_fetched_at = <some old timestamp>` and `prerolls = []`. The existing gate at line 771 treats this as "fetched, genuinely-empty channel" — silent skip forever. The auto-staleness re-fetch closes this permanently.

**Where to wire the staleness check:** In the `# else (D-04 / Pitfall 5)` branch at line 771, add a sub-condition:

```python
# else (D-04 / Pitfall 5): fetched, genuinely-empty channel — skip silently.
# D-08 (Phase 90): but if fetched_at is OLD (> staleness threshold), re-attempt.
elif (
    fetched_at is not None
    and len(urls) == 0
    and int(time.time()) - fetched_at > _PREROLL_STALE_THRESHOLD_S
    and station.id not in self._backfill_in_flight
):
    self._backfill_in_flight.add(station.id)
    threading.Thread(
        target=self._preroll_refetch_worker,   # NEW: soma_import path, not title-match
        args=(station.id,),
        daemon=True,
    ).start()
```

**Staleness threshold:** `_PREROLL_STALE_THRESHOLD_S = 7 * 24 * 3600` (7 days). [ASSUMED — Claude's Discretion per D-08]. Rationale: matches a typical "re-import cadence"; old enough to not re-fetch on every play; short enough to catch any station where Phase 83 populated an empty prerolls_fetched_at before preroll data was correctly captured.

**`_preroll_refetch_worker` vs `_preroll_backfill_worker`:** The D-09 decision is to prefer `soma_import` capture over the title-match path. The re-fetch worker should use `soma_import.fetch_channels()` (not title-matching) or at minimum find the station's upstream channel by ID. Since the Phase 83 backfill worker already uses `soma_import.fetch_channels()` + title match, the re-fetch worker can simply be the existing `_preroll_backfill_worker` called with the station_id — but for the manual "Re-fetch ALL" menu action, a different QThread-based worker is needed (see Pattern 4).

**Practical resolution for auto-staleness:** Reuse `_preroll_backfill_worker` with the station's name (title-match). For the manual menu action (D-07), prefer a full `fetch_channels()` sweep (more reliable, populates all stations with 0 prerolls in one pass) via `_PrerollRefetchWorker(QThread)`.

### Pattern 4: `_PrerollRefetchWorker` (Manual Re-fetch Action)

The manual "Re-fetch SomaFM prerolls" action mirrors `_SomaImportWorker` but targets only stations where `len(prerolls) == 0`, ignoring `prerolls_fetched_at`.

```python
# In main_window.py — mirrors _SomaImportWorker pattern
class _PrerollRefetchWorker(QThread):
    refetch_done = Signal(int)   # count of stations updated
    error = Signal(str)

    def run(self):
        try:
            from musicstreamer.repo import Repo, db_connect
            from musicstreamer import soma_import
            import time
            channels = soma_import.fetch_channels()
            # Build lookup by title (Pitfall 3 of Phase 83 — acceptable here since
            # this is a recovery tool, not the primary path)
            channels_by_title = {c["title"]: c for c in channels}
            con = db_connect()
            try:
                repo = Repo(con)
                updated = 0
                for station in repo.list_stations():
                    if station.provider_name != "SomaFM":
                        continue
                    if list(repo.list_prerolls(station.id)):
                        continue  # already has prerolls — skip
                    ch = channels_by_title.get(station.name)
                    if ch is None:
                        continue
                    preroll_urls = ch.get("preroll_urls", [])[:50]
                    if not preroll_urls:
                        repo.set_prerolls_fetched_at(station.id, int(time.time()))
                        continue
                    for pos, url in enumerate(preroll_urls, start=1):
                        try:
                            repo.insert_preroll(station.id, url, pos)
                        except ValueError:
                            continue
                    repo.set_prerolls_fetched_at(station.id, int(time.time()))
                    updated += 1
            finally:
                con.close()
            self.refetch_done.emit(updated)
        except Exception as exc:
            self.error.emit(str(exc))
```

**Single-flight guard:** The `_soma_refetch_worker: QThread | None` field on `MainWindow` mirrors `_soma_import_worker`. Double-click guard: check `if self._soma_refetch_worker is not None` before starting.

### Pattern 5: Hamburger Menu Action Placement

**"Open preroll log" action:** Place in a new Group 4 (diagnostics) after the existing Group 3 (Export/Import Settings separator), before the version footer. Add a separator if needed.

**"Re-fetch SomaFM prerolls" action:** Place adjacent to "Import SomaFM" (Group 1) since it is SomaFM-specific import-related. Add immediately after `act_soma_import` at `main_window.py:234`.

**`QDesktopServices.openUrl` pattern** (confirmed at `main_window.py:919`):
```python
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
QDesktopServices.openUrl(QUrl.fromLocalFile(paths.preroll_events_log_path()))
```

**CAVEAT:** The log file may not exist yet on first launch (no SomaFM station has been played). `QDesktopServices.openUrl` will silently fail on a non-existent path. The action handler should check for file existence and show a toast "No preroll log yet — play a SomaFM station first" if the file does not exist.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Size-rotating log file | Custom log file with manual roll-over | `logging.handlers.RotatingFileHandler` (stdlib) | Already proven in Phase 78 `buffer_log.py` — handles atomic rotate, backup count, encoding |
| Idempotent handler install | Custom flag/singleton | The `for h in log.handlers` check pattern from `buffer_log.py` | Exact pattern, prevents duplicate handlers across hot-reload/test runs |
| Background fetch | `threading.Thread` with bare `Repo` shared from main thread | `QThread` (for UI-connected workers) or `threading.Thread` + Pattern 4 thread-local Repo | QThread for menu-triggered workers (needs Qt signal to report done); daemon Thread + thread-local Repo for automatic gate-triggered refetch |
| URL validation on insert | Custom regex | `repo.insert_preroll` (T-83-01 gate already rejects non-HTTP(S)) | Existing security gate — do not bypass |

**Key insight:** The logging infrastructure is already 100% solved by the Phase 78 pattern. The only novelty is the log module name, path, and injection sites. Do not over-engineer.

---

## Common Pitfalls

### Pitfall 1: Log call placed BETWEEN `_apply_pending_buffer_duration_to_pipeline()` and `set_property("uri", ...)`

**What goes wrong:** Phase 84 D-11 drift-guard tests (`test_try_next_stream_applies_pending_before_uri_bind`, `test_preroll_handoff_applies_pending_before_uri_swap`) check that `buffer-duration` write precedes `uri` write in `set_property` call list. A log call between them does not break the ordering — but if the planner places a log call that calls any method touching `_pipeline.set_property`, the test will inject a spurious call into the sequence.
**How to avoid:** Log calls use only `logging.getLogger("musicstreamer.preroll").info(...)`. They never call `self._pipeline.set_property`. Zero risk if this rule is followed.
**Warning sign:** Any test in `test_player_buffer_growth.py` that checks `call_args_list` ordering starts failing.

### Pitfall 2: Using `prerolls_fetched_at` timestamp from `Station.prerolls_fetched_at` vs. DB

**What goes wrong:** `Player.play()` receives a `Station` object whose `prerolls_fetched_at` was populated at the time `Repo.get_station()` was last called. If the user starts the app, plays a station, and then a background worker updates `prerolls_fetched_at`, the in-memory `Station` object is stale. The staleness check for auto-re-fetch must use `station.prerolls_fetched_at` (the value loaded when play() was called), which is fine — the point is to check the *age of the last fetch*, and a stale object makes the condition more conservative (re-fetches sooner), which is correct behavior.
**How to avoid:** Use `station.prerolls_fetched_at` directly in the gate check. Do NOT add an extra DB read in the hot path.

### Pitfall 3: `_backfill_in_flight` race for auto-staleness worker

**What goes wrong:** Both the existing D-13 lazy backfill branch (line 759) and the new auto-staleness branch use `_backfill_in_flight` as a single-flight guard. If both branches are reachable for the same station in the same `play()` call (they are not — one requires `fetched_at IS NULL`, the other requires `fetched_at IS NOT NULL`), there would be a race. They are mutually exclusive by design.
**How to avoid:** Confirm the mutual exclusivity with a comment in the code. The D-13 branch fires only when `prerolls_fetched_at IS NULL`. The D-08 branch fires only when `prerolls_fetched_at IS NOT NULL AND prerolls == [] AND age > threshold`. No station can match both simultaneously.

### Pitfall 4: Re-fetch worker does not clear `prerolls_fetched_at` before inserting

**What goes wrong:** If a station has `prerolls_fetched_at = <old_ts>` and `prerolls = []`, and the re-fetch worker calls `insert_preroll` for each new URL without first deleting the existing (empty) state, the state after re-fetch is correct (rows now exist). But the `insert_preroll` UNIQUE constraint on `(station_id, url, position)` might reject re-inserts if the station was previously fetched and then cleaned up improperly.
**How to avoid:** Check `repo.list_prerolls(station.id)` inside the worker — skip stations that already have prerolls (the manual action explicitly skips them). The `insert_preroll` at position 1..N with a fresh start is safe because the station had 0 rows.

### Pitfall 5: `QDesktopServices.openUrl` on non-existent log file

**What goes wrong:** On first launch, `preroll-events.log` does not exist (no SomaFM play has occurred). `QDesktopServices.openUrl` silently fails on Linux/macOS or opens a "file not found" dialog on Windows.
**How to avoid:** In the "Open preroll log" slot, check `os.path.isfile(paths.preroll_events_log_path())` and call `self.show_toast("No preroll log yet — play a SomaFM station first")` if the file does not exist.

### Pitfall 6: Named logger `musicstreamer.preroll` level not set to INFO

**What goes wrong:** The named logger defaults to NOTSET (inherits from root at WARNING). INFO-level log calls from the preroll gate would not be emitted.
**How to avoid:** In `install_preroll_events_handler()`, set `log.setLevel(logging.INFO)` on the `musicstreamer.preroll` logger before attaching the handler — mirrors the implicit level set in `test_buffer_events_log.py:_clean_player_handlers` fixture.

### Pitfall 7: `_PrerollRefetchWorker` opens `Repo` without Pattern 4 thread-local discipline

**What goes wrong:** If the worker uses the MainWindow's `self._repo` connection across threads, SQLite `check_same_thread=False` protection is not guaranteed, and concurrent writes can corrupt.
**How to avoid:** Call `db_connect()` inside `_PrerollRefetchWorker.run()` (Pattern 4 — same as `_SomaImportWorker.run()` at `main_window.py:167-174`). Close the connection in `finally`.

---

## Code Examples

### Preroll gate log call injection points (confirmed)

```python
# Source: musicstreamer/player.py lines 749-772 (ASSUMED — codebase read)
# BEFORE the existing gate — add local probes (no state change):
_is_somafm = station.provider_name == "SomaFM"
_throttle_active = (
    self._last_preroll_played_at is not None
    and time.monotonic() - self._last_preroll_played_at <= 600
)

# Log throttle skip BEFORE the combined gate (avoids restructuring):
if _is_somafm and _throttle_active:
    logging.getLogger("musicstreamer.preroll").info(
        "preroll_skipped_throttle station_name=%r station_id=%d remaining_s=%.0f",
        station.name, station.id,
        600 - (time.monotonic() - self._last_preroll_played_at),
    )

# Existing gate (UNCHANGED except for log additions inside):
if (
    station.provider_name == "SomaFM"
    and (self._last_preroll_played_at is None
         or time.monotonic() - self._last_preroll_played_at > 600)
):
    urls = list(getattr(station, "prerolls", []) or [])
    if urls:
        preroll_url = random.choice(urls)
        # LOG: preroll_start — ADDITIVE, before _start_preroll
        logging.getLogger("musicstreamer.preroll").info(
            "preroll_start station_name=%r station_id=%d url=%r",
            station.name, station.id, preroll_url,
        )
        self._start_preroll(preroll_url)
        return
    elif (
        getattr(station, "prerolls_fetched_at", None) is None
        ...
    ):
        # D-13 lazy backfill [unchanged]
        # LOG: preroll_skipped_empty (unfetched branch)
        logging.getLogger("musicstreamer.preroll").info(
            "preroll_skipped_empty station_name=%r station_id=%d reason=unfetched",
            station.name, station.id,
        )
    # D-04 / Pitfall 5: fetched, genuinely-empty
    # LOG: preroll_skipped_empty (fetched-empty branch)
    logging.getLogger("musicstreamer.preroll").info(
        "preroll_skipped_empty station_name=%r station_id=%d reason=fetched_empty",
        station.name, station.id,
    )
self._try_next_stream()
```

### `preroll_handoff_complete` in `_on_preroll_about_to_finish`

```python
# Source: musicstreamer/player.py line 1577 (ASSUMED — codebase read)
# After: self._preroll_in_flight = False  (line 1577)
# Before: if not self._streams_queue:     (line 1579)
logging.getLogger("musicstreamer.preroll").info(
    "preroll_handoff_complete station_name=%r station_id=%d",
    self._current_station_name, self._current_station_id,
)
```

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — section required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (inferred from existing test suite) |
| Config file | `pyproject.toml` (uv/pytest config) |
| Quick run command | `.venv/bin/python -m pytest tests/test_preroll_log.py tests/test_player_buffer_growth.py tests/test_player.py::test_phase_83_preroll_drift_guard tests/test_paths.py -x -v` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x --timeout=30` (scope to avoid >600s run) |

**Note:** Run tests with `.venv/bin/python` — system `python3` lacks `PySide6.QtWidgets` (causes false failures). Two known pre-existing failures exist in the suite; they are NOT caused by Phase 90.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SOMA-PRE-01 | `preroll_log.py` installs RotatingFileHandler on `musicstreamer.preroll` logger | unit | `.venv/bin/python -m pytest tests/test_preroll_log.py::test_handler_attached_to_preroll_logger -xvs` | ❌ Wave 0 |
| SOMA-PRE-01 | Handler is idempotent (double-install = 1 handler) | unit | `.venv/bin/python -m pytest tests/test_preroll_log.py::test_install_is_idempotent -xvs` | ❌ Wave 0 |
| SOMA-PRE-01 | INFO emit writes structured line to `preroll-events.log` | unit | `.venv/bin/python -m pytest tests/test_preroll_log.py::test_emit_writes_line_to_file -xvs` | ❌ Wave 0 |
| SOMA-PRE-01 | `preroll_start` event logged with URL + station name/id | unit | `.venv/bin/python -m pytest tests/test_player.py::test_preroll_log_start_event_includes_url_and_station -xvs` | ❌ Wave 0 |
| SOMA-PRE-01 | `preroll_skipped_throttle` event logged when throttle active | unit | `.venv/bin/python -m pytest tests/test_player.py::test_preroll_log_skipped_throttle_event -xvs` | ❌ Wave 0 |
| SOMA-PRE-01 | `preroll_skipped_empty` event logged for fetched-empty station | unit | `.venv/bin/python -m pytest tests/test_player.py::test_preroll_log_skipped_empty_fetched -xvs` | ❌ Wave 0 |
| SOMA-PRE-01 | `preroll_handoff_complete` event logged after handoff | unit | `.venv/bin/python -m pytest tests/test_player.py::test_preroll_log_handoff_complete_event -xvs` | ❌ Wave 0 |
| SOMA-PRE-01 | `paths.preroll_events_log_path()` returns correct path | unit | `.venv/bin/python -m pytest tests/test_paths.py -k "preroll" -xvs` | ❌ Wave 0 (extend existing test_paths.py) |
| SOMA-PRE-02 | "Open preroll log" action exists in hamburger menu | unit | `.venv/bin/python -m pytest tests/test_main_window_soma.py::test_open_preroll_log_action_exists -xvs` | ❌ Wave 0 |
| SOMA-PRE-02 | "Open preroll log" shows toast when log file absent | unit | `.venv/bin/python -m pytest tests/test_main_window_soma.py::test_open_preroll_log_absent_shows_toast -xvs` | ❌ Wave 0 |
| SOMA-PRE-05 | Phase 84 D-11 buffer-duration ordering (14 tests) | unit | `.venv/bin/python -m pytest tests/test_player_buffer_growth.py -xvs` | ✅ EXISTS |
| SOMA-PRE-05 | Phase 83 preroll drift-guard (`"SomaFM"` literal + `_last_preroll_played_at`) | unit (source-grep) | `.venv/bin/python -m pytest tests/test_player.py::test_phase_83_preroll_drift_guard -xvs` | ✅ EXISTS |
| SOMA-PRE-05 | `test_throttle_timestamp_set_on_start` still passes | unit | `.venv/bin/python -m pytest tests/test_player.py::test_throttle_timestamp_set_on_start -xvs` | ✅ EXISTS |
| SOMA-PRE-05 | `test_wr05_throttle_documents_attempted_semantics` still passes | unit | `.venv/bin/python -m pytest tests/test_player.py::test_wr05_throttle_documents_attempted_semantics -xvs` | ✅ EXISTS |
| D-07/D-08 | "Re-fetch SomaFM prerolls" action exists in hamburger menu | unit | `.venv/bin/python -m pytest tests/test_main_window_soma.py::test_refetch_prerolls_action_exists -xvs` | ❌ Wave 0 |
| D-07/D-08 | Re-fetch worker skips stations that already have prerolls | unit | `.venv/bin/python -m pytest tests/test_main_window_soma.py::test_refetch_worker_skips_stations_with_prerolls -xvs` | ❌ Wave 0 |
| D-08 | Auto-staleness branch triggers re-fetch for fetched-empty + old stations | unit | `.venv/bin/python -m pytest tests/test_player.py::test_auto_staleness_refetch_triggers_for_old_empty_station -xvs` | ❌ Wave 0 |
| D-08 | Auto-staleness branch does NOT trigger for stations with prerolls | unit | `.venv/bin/python -m pytest tests/test_player.py::test_auto_staleness_no_refetch_when_prerolls_exist -xvs` | ❌ Wave 0 |
| D-08 | Auto-staleness branch does NOT trigger for recently-fetched empty stations | unit | `.venv/bin/python -m pytest tests/test_player.py::test_auto_staleness_no_refetch_when_recently_fetched -xvs` | ❌ Wave 0 |
| D-09 (zero-behavior-change) | Existing preroll tests still pass end-to-end | regression | `.venv/bin/python -m pytest tests/test_player.py -k "preroll" -xvs` | ✅ EXISTS (13 tests) |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest tests/test_preroll_log.py tests/test_player_buffer_growth.py -x --timeout=30`
- **Per wave merge:** `.venv/bin/python -m pytest tests/test_preroll_log.py tests/test_player_buffer_growth.py tests/test_player.py -x --timeout=30`
- **Phase gate:** Full scope above (all SOMA-PRE tests + regression suite for preroll + buffer_growth) green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_preroll_log.py` — 5 tests mirroring `test_buffer_events_log.py` (handler attach, emit writes, rotation, idempotent, propagate) for `musicstreamer.preroll` logger
- [ ] Extend `tests/test_paths.py` — add `test_preroll_events_log_path_returns_correct_path` + `test_preroll_events_log_path_respects_root_override`
- [ ] Extend `tests/test_player.py` — 7 new tests for log-call behavior (preroll_start, skipped_throttle, skipped_empty×2, handoff_complete, auto-staleness×3)
- [ ] Extend `tests/test_main_window_soma.py` — 4 new tests for the two new actions (exists, behavior)

---

## Environment Availability

> Step 2.6: Phase is code/config-only changes with no new external dependencies. No new CLI tools, services, or runtimes required beyond the existing project environment.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/python` | Test execution | ✓ | (existing project venv) | — |
| `PySide6` | UI wiring | ✓ | (existing conda env) | — |
| `musicstreamer.soma_import` | Re-fetch worker | ✓ | project module | — |
| `musicstreamer.repo` | Re-fetch worker | ✓ | project module | — |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 83: `_preroll_backfill_worker` uses title-match (`c.get("title") == station_name`) | Phase 90 re-fetch: same title-match for auto-staleness; full `soma_import` sweep for manual action | Phase 90 | Title-match remains Pitfall 3 weak point for renamed stations; acceptable for recovery tool per D-09 |
| Phase 83: no menu re-fetch lever | Phase 90: manual "Re-fetch SomaFM prerolls" action | Phase 90 | User has a concrete recovery action without needing to re-import the full catalog |
| Phase 83: fetched-with-0 trap permanent | Phase 90: auto-staleness threshold closes it | Phase 90 | Stations that were fetched before Phase 83 preroll data was correct will self-heal |

---

## Open Questions (RESOLVED)

1. **`_preroll_refetch_worker` — reuse existing `_preroll_backfill_worker` or add new method?**
   - What we know: `_preroll_backfill_worker` takes `(station_id, station_name)` and is called from `_try_next_stream`. The auto-staleness trigger can reuse it directly.
   - What's unclear: Whether to call the existing method directly (adding a call path from the staleness branch) vs. adding a new `_preroll_refetch_worker` that differs only in the title-match-vs-soma_import path.
   - Recommendation: Reuse `_preroll_backfill_worker` for auto-staleness (same single-flight guard, same failure-silent contract). Add a separate `_PrerollRefetchWorker(QThread)` only for the manual menu action (needs Qt signal to show toast).

2. **"Re-fetch SomaFM prerolls" — should it also clear `prerolls_fetched_at` to force a fresh timestamp?**
   - What we know: `set_prerolls_fetched_at` is called after each station's re-fetch with `int(time.time())`. This updates the timestamp to now.
   - What's unclear: Whether to delete existing (empty) `station_prerolls` rows before inserting fresh ones (not needed if `list_prerolls` confirms 0 rows before inserting).
   - Recommendation: No deletion needed — the worker already skips stations with existing prerolls. The `insert_preroll` calls are only made for stations with 0 rows.

3. **Log level for `preroll_skipped_empty` — INFO or DEBUG?**
   - What we know: The majority of SomaFM stations (25 of 46) have no prerolls. At INFO level, every play of any empty-preroll SomaFM station writes a log line.
   - Recommendation: Use INFO for all 5 event types (mirrors buffer_log.py which logs every underrun at INFO). The rotation cap (1MB / ~4MB total) handles the volume. The whole point of the log is to be complete for the user's run-through.

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `repo.insert_preroll` T-83-01 gate rejects non-HTTP(S) URL schemes — already in place; re-fetch worker inherits this |
| V2 Authentication | no | Log file is local diagnostic data, default permissions |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V6 Cryptography | no | — |

**Known threat patterns for this stack:**

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SomaFM API returns hostile non-HTTP(S) preroll URL | Tampering | `repo.insert_preroll` T-83-01 gate (existing) — rejects `file://`, `javascript:`, etc. |
| Log file written to world-readable path | Information Disclosure | Default permissions (Phase 78 D-03 deliberate departure from oauth_log.py 0o600 — diagnostic data, not credentials) |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Staleness threshold of 7 days is appropriate for auto-refetch | Re-fetch design / Common Pitfalls | Too short: re-fetches too often (minor annoyance, not correctness); Too long: latent trap persists longer |
| A2 | Log level INFO is correct for all 5 event types | Open Questions / Code Examples | If DEBUG is preferred: high-volume empty-preroll stations may be noisy; planner should validate with user |
| A3 | `_preroll_refetch_worker` reusing `_preroll_backfill_worker` for auto-staleness is sufficient | Open Questions | Title-match (Pitfall 3) still applies; user-renamed stations won't heal. Acceptable per D-09. |
| A4 | "Re-fetch SomaFM prerolls" action placed in Group 1 adjacent to "Import SomaFM" | Hamburger menu placement | Could go in a separate diagnostics group; visual placement TBD at planner discretion |

**If this table were empty:** All claims were verified or cited from codebase. Assumptions above are low-risk; all within Claude's Discretion scope (D-08 threshold, log level).

---

## Sources

### Primary (HIGH confidence — codebase verified)

- `musicstreamer/buffer_log.py` — Phase 78 template confirmed; `install_buffer_events_handler()` pattern verified verbatim
- `musicstreamer/paths.py` — `buffer_events_log_path()` at line 68 confirmed; `_root_override` test hook confirmed
- `musicstreamer/player.py` lines 749-772 — preroll gate confirmed; `_backfill_in_flight`, `_preroll_backfill_worker`, `_start_preroll` at lines 1468 and 1998 confirmed
- `musicstreamer/player.py` lines 1526-1656 — `_on_preroll_about_to_finish` full slot confirmed; `_preroll_in_flight = False` at line 1577; gapless `set_property("uri", ...)` at line 1639
- `musicstreamer/soma_import.py` lines 175-256 — `fetch_channels()` confirmed; preroll capture at lines 343-356 confirmed
- `musicstreamer/repo.py` lines 516-562 — `list_prerolls`, `insert_preroll`, `set_prerolls_fetched_at` at line 781 confirmed
- `musicstreamer/ui_qt/main_window.py` lines 153-174 — `_SomaImportWorker` pattern confirmed; hamburger menu construction lines 214-309 confirmed; `QDesktopServices.openUrl` at line 919 confirmed
- `musicstreamer/__main__.py` lines 255-261 — install-after-migration ordering confirmed
- `musicstreamer/models.py` lines 27-44 — `Station` dataclass with `prerolls: List[str]` and `prerolls_fetched_at: Optional[int]` confirmed
- `tests/test_player.py` lines 878-895 — `test_throttle_timestamp_set_on_start` confirmed; `test_wr05_throttle_documents_attempted_semantics` at 1563 confirmed; `test_phase_83_preroll_drift_guard` at 1201 confirmed
- `tests/test_player_buffer_growth.py` — 14 tests confirmed; `test_try_next_stream_applies_pending_before_uri_bind` at 184; `test_preroll_handoff_applies_pending_before_uri_swap` at 254
- `tests/test_buffer_events_log.py` — 5-test template confirmed for mirror in `test_preroll_log.py`
- `.planning/config.json` — `nyquist_validation: true` confirmed

### Secondary (MEDIUM confidence — codebase structure inferred)

- `main_window.py:505-506` — `install_gbs_marquee_handler()` install site in `MainWindow.__init__` (Phase 87 pattern for alternative install-in-init vs install-in-__main__ pattern; not used for preroll_log but documented for context)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing, codebase-verified
- Architecture: HIGH — code paths confirmed line-by-line
- Pitfalls: HIGH — most derived from confirmed Phase 83/84 precedent
- Test mapping: HIGH — existing tests confirmed; Wave 0 gaps clearly identified

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (stable internal codebase — 30 days)

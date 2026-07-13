# Phase 90: SomaFM Preroll Instrumentation - Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 9 new/modified files
**Analogs found:** 8 / 9 (1 net-new UI, no analog)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/preroll_log.py` | utility (log installer) | event-driven | `musicstreamer/buffer_log.py` | exact |
| `musicstreamer/paths.py` (add `preroll_events_log_path`) | utility (path resolver) | transform | `musicstreamer/paths.py:buffer_events_log_path` (line 68–70) | exact |
| `musicstreamer/__main__.py` (install site) | config (startup wiring) | request-response | `musicstreamer/__main__.py:261` (`install_buffer_events_handler` call) | exact |
| `musicstreamer/player.py` (log calls at gate + auto-staleness branch) | service (preroll gate) | event-driven | `musicstreamer/player.py:749–772` (`_try_next_stream` SomaFM block) | self-analog (extend) |
| `musicstreamer/player.py` (`_on_preroll_about_to_finish` log call) | service (gapless handoff) | event-driven | `musicstreamer/player.py:1577` (`_preroll_in_flight = False`) | self-analog (extend) |
| `musicstreamer/ui_qt/main_window.py` (`_PrerollRefetchWorker` + "Re-fetch" action) | component (QThread worker + menu) | request-response | `musicstreamer/ui_qt/main_window.py:153–174` (`_SomaImportWorker`) | exact |
| `musicstreamer/ui_qt/main_window.py` ("Open preroll log" action) | component (menu action) | request-response | `musicstreamer/ui_qt/main_window.py:915–920` (`_on_node_install_clicked`) | partial (QDesktopServices pattern — net-new UI) |
| `tests/test_preroll_events_log.py` | test | event-driven | `tests/test_buffer_events_log.py` | exact |
| `tests/test_player_buffer_growth.py` (extend) | test | event-driven | `tests/test_player_buffer_growth.py:184,254` (D-11 ordering tests) | self-analog (extend) |

---

## Pattern Assignments

### `musicstreamer/preroll_log.py` (utility, event-driven)

**Analog:** `musicstreamer/buffer_log.py` (entire file — 103 lines)

**Imports pattern** (buffer_log.py lines 33–38):
```python
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from musicstreamer import paths
```

**Core idempotent-install pattern** (buffer_log.py lines 56–68 — copy verbatim, change 3 identifiers):
```python
def install_buffer_events_handler() -> None:
    path = paths.buffer_events_log_path()
    log = logging.getLogger("musicstreamer.player")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed — short-circuit
    handler = RotatingFileHandler(
        path,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
```

**Substitutions for preroll_log.py:**
- Function name: `install_preroll_events_handler`
- Path call: `paths.preroll_events_log_path()`
- Logger name: `"musicstreamer.preroll"`
- Add `log.setLevel(logging.INFO)` before `log.addHandler(handler)` (Pitfall 6 — named logger defaults to NOTSET, swallows INFO)

**Rotation parameters (D-02, confirmed):** `maxBytes=1_048_576`, `backupCount=3`, `encoding="utf-8"` — identical to buffer_log.py

**Propagate invariant:** Do NOT set `log.propagate = False`. Default `True` preserved (mirrors buffer_log.py — Pitfall 5 stderr-parity invariant).

---

### `musicstreamer/paths.py` — add `preroll_events_log_path()` (utility, transform)

**Analog:** `musicstreamer/paths.py` lines 68–70

**Exact pattern to copy (lines 68–70):**
```python
def buffer_events_log_path() -> str:
    """Phase 78 / BUG-09 D-03: path to the size-rotated buffer-event diagnostic log."""
    return os.path.join(_root(), "buffer-events.log")
```

**New function to add immediately after line 70:**
```python
def preroll_events_log_path() -> str:
    """Phase 90 D-04: path to the size-rotated preroll-event diagnostic log."""
    return os.path.join(_root(), "preroll-events.log")
```

**Test isolation:** `_root_override` (line 25) is the monkeypatch hook used by all path tests. No new mechanism needed — `monkeypatch.setattr(paths, "_root_override", str(tmp_path))` works identically for the new function.

---

### `musicstreamer/__main__.py` — install site (config, startup wiring)

**Analog:** `musicstreamer/__main__.py` lines 252–261

**Exact existing block to mirror (lines 252–261):**
```python
    # Phase 78 / BUG-09 Commit A: install rotating file handler on the
    # musicstreamer.player logger so buffer_underrun lines also land at
    # ~/.local/share/musicstreamer/buffer-events.log regardless of launch
    # context (.desktop vs terminal). MUST run AFTER migration.run_migration()
    # so DATA_DIR exists (Pitfall 1 — RotatingFileHandler opens eagerly). The
    # install function is idempotent so re-entry / hot-reload is safe. The
    # named-logger attach preserves Pitfall 5 (basicConfig WARNING is global
    # and stays untouched at __main__.py line 231).
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
```

**New block to add immediately after line 261:**
```python
    from musicstreamer.preroll_log import install_preroll_events_handler
    install_preroll_events_handler()
```

**Ordering invariant:** MUST come after `migration.run_migration()` (line 250) so `DATA_DIR` exists when `RotatingFileHandler` opens the file eagerly (Pitfall 1).

---

### `musicstreamer/player.py` — preroll gate log calls + auto-staleness branch (`_try_next_stream`)

**Analog:** `musicstreamer/player.py` lines 749–772 (the existing SomaFM gate — self-extend)

**Exact existing gate (lines 749–772):**
```python
        if (
            station.provider_name == "SomaFM"
            and (self._last_preroll_played_at is None
                 or time.monotonic() - self._last_preroll_played_at > 600)
        ):
            urls = list(getattr(station, "prerolls", []) or [])
            if urls:
                preroll_url = random.choice(urls)
                self._start_preroll(preroll_url)
                return  # _on_preroll_about_to_finish triggers _try_next_stream
            elif (
                getattr(station, "prerolls_fetched_at", None) is None
                and station.id not in self._backfill_in_flight
            ):
                # D-13 lazy backfill; non-blocking. Worker discards station.id from
                # _backfill_in_flight in its finally clause (T-83-10 single-flight).
                self._backfill_in_flight.add(station.id)
                threading.Thread(
                    target=self._preroll_backfill_worker,
                    args=(station.id, station.name),
                    daemon=True,
                ).start()
            # else (D-04 / Pitfall 5): fetched, genuinely-empty channel — skip silently.
        self._try_next_stream()
```

**Log call injection points (ZERO reordering — additive only):**

1. **`preroll_skipped_throttle`** — add a probe BEFORE the combined gate (line 749). The combined condition short-circuits when throttle is active; this separate probe fires only for the skip path:
```python
        # Phase 90 D-03: throttle-skip probe (additive — no state change).
        if (
            station.provider_name == "SomaFM"
            and self._last_preroll_played_at is not None
            and time.monotonic() - self._last_preroll_played_at <= 600
        ):
            logging.getLogger("musicstreamer.preroll").info(
                "preroll_skipped_throttle station_name=%r station_id=%d remaining_s=%.0f",
                station.name, station.id,
                600 - (time.monotonic() - self._last_preroll_played_at),
            )
```

2. **`preroll_start`** — add AFTER `preroll_url = random.choice(urls)` (line 756), BEFORE `self._start_preroll(preroll_url)` (line 757):
```python
                logging.getLogger("musicstreamer.preroll").info(
                    "preroll_start station_name=%r station_id=%d url=%r",
                    station.name, station.id, preroll_url,
                )
```

3. **`preroll_skipped_empty` (unfetched branch)** — add inside the `elif prerolls_fetched_at is None` branch (after line 762, before the `threading.Thread` call):
```python
                logging.getLogger("musicstreamer.preroll").info(
                    "preroll_skipped_empty station_name=%r station_id=%d reason=unfetched",
                    station.name, station.id,
                )
```

4. **`preroll_skipped_empty` (fetched-empty branch) + auto-staleness D-08** — replace the `# else (D-04 / Pitfall 5)` comment at line 771 with:
```python
            else:
                # D-04 / Pitfall 5: fetched, genuinely-empty channel.
                logging.getLogger("musicstreamer.preroll").info(
                    "preroll_skipped_empty station_name=%r station_id=%d reason=fetched_empty",
                    station.name, station.id,
                )
                # D-08 (Phase 90): close the "fetched-with-0 never re-fetches" trap.
                # Fires ONLY when fetched_at IS NOT NULL (mutually exclusive with D-13
                # branch above which requires fetched_at IS NULL).
                if (
                    getattr(station, "prerolls_fetched_at", None) is not None
                    and int(time.time()) - station.prerolls_fetched_at > _PREROLL_STALE_THRESHOLD_S
                    and station.id not in self._backfill_in_flight
                ):
                    self._backfill_in_flight.add(station.id)
                    threading.Thread(
                        target=self._preroll_backfill_worker,
                        args=(station.id, station.name),
                        daemon=True,
                    ).start()
```

**Module-level constant to add near top of player.py** (Claude's Discretion — 7 days per RESEARCH.md):
```python
_PREROLL_STALE_THRESHOLD_S: int = 7 * 24 * 3600  # Phase 90 D-08
```

**Critical D-11 ordering guard:** Log calls use only `logging.getLogger(...).info(...)`. They MUST NOT call `self._pipeline.set_property(...)`. The `buffer-duration` → `uri` ordering tested by `test_player_buffer_growth.py:184,254` is entirely upstream of all injection points.

---

### `musicstreamer/player.py` — `_on_preroll_about_to_finish` log call (`preroll_handoff_complete`)

**Analog:** `musicstreamer/player.py` lines 1577–1581 (the existing in-flight flag clear + empty-queue check)

**Exact context (lines 1577–1581):**
```python
        self._preroll_in_flight = False
        # Empty-queue defensive: fall back to legacy path (emits failover(None)).
        if not self._streams_queue:
            self._try_next_stream()
            return
```

**Injection point:** Add AFTER `self._preroll_in_flight = False` (line 1577), BEFORE the `if not self._streams_queue:` check (line 1579). The gapless `set_property("uri", ...)` at line 1639 is far downstream — no ordering risk:
```python
        self._preroll_in_flight = False
        # Phase 90 D-03: log handoff completion (additive — before queue check).
        logging.getLogger("musicstreamer.preroll").info(
            "preroll_handoff_complete station_name=%r station_id=%d",
            self._current_station_name, self._current_station_id,
        )
        # Empty-queue defensive: fall back to legacy path (emits failover(None)).
        if not self._streams_queue:
```

---

### `musicstreamer/ui_qt/main_window.py` — `_PrerollRefetchWorker` + "Re-fetch SomaFM prerolls" action

**Analog:** `musicstreamer/ui_qt/main_window.py` lines 153–174 (`_SomaImportWorker`), lines 1567–1608 (`_on_soma_import_clicked` + handlers)

**Worker class pattern (lines 153–174 — copy shape, change domain):**
```python
class _SomaImportWorker(QThread):
    """..."""
    import_finished = Signal(int, int)
    error = Signal(str)

    def run(self):
        try:
            from musicstreamer.repo import Repo
            from musicstreamer import soma_import
            channels = soma_import.fetch_channels()
            repo = Repo(db_connect())
            inserted, skipped = soma_import.import_stations(channels, repo)
            self.import_finished.emit(int(inserted), int(skipped))
        except Exception as exc:
            self.error.emit(str(exc))
```

**New `_PrerollRefetchWorker` mirrors this shape exactly.** Key differences:
- Signal: `refetch_done = Signal(int)` (count of stations updated)
- Pattern 4 discipline: `con = db_connect()` inside `run()`, closed in `finally` (mirrors `_preroll_backfill_worker` at lines 2023–2036 for the `con.close()` pattern)
- Skips stations already having prerolls (`repo.list_prerolls(station.id)` check before inserting)

**Worker field retention on MainWindow (line 365 — the SYNC-05 pattern):**
```python
        self._soma_import_worker: QThread | None = None
```
New field to add alongside: `self._soma_refetch_worker: QThread | None = None`

**Action wiring pattern (lines 1576–1583):**
```python
        if self._soma_import_worker is not None:
            self.show_toast("SomaFM import already in progress")
            return
        self.show_toast("Importing SomaFM…")
        self._soma_import_worker = _SomaImportWorker(parent=self)  # SYNC-05 retain
        self._soma_import_worker.import_finished.connect(self._on_soma_import_done)  # QA-05
        self._soma_import_worker.error.connect(self._on_soma_import_error)    # QA-05
        self._soma_import_worker.start()
```

**New `_on_preroll_refetch_clicked` handler mirrors this verbatim** (substitute `_soma_refetch_worker`, `_PrerollRefetchWorker`, `refetch_done` signal, `_on_preroll_refetch_done`, `_on_preroll_refetch_error`, toast messages).

**Menu placement** — add immediately after `act_soma_import` wiring at line 234:
```python
        # Phase 74 D-06 / SOMA-NN: SomaFM bulk-catalog import
        act_soma_import = self._menu.addAction("Import SomaFM")
        act_soma_import.triggered.connect(self._on_soma_import_clicked)  # QA-05 bound method

        # Phase 90 D-07: manual preroll re-fetch lever
        act_preroll_refetch = self._menu.addAction("Re-fetch SomaFM prerolls")
        act_preroll_refetch.triggered.connect(self._on_preroll_refetch_clicked)  # QA-05
```

---

### `musicstreamer/ui_qt/main_window.py` — "Open preroll log" action (net-new UI)

**Analog:** `musicstreamer/ui_qt/main_window.py` lines 915–920 (`_on_node_install_clicked` — `QDesktopServices.openUrl` pattern)

**Exact existing pattern (lines 915–920):**
```python
    def _on_node_install_clicked(self) -> None:
        """Phase 44 D-13: hamburger Node-missing indicator click handler.
        Opens nodejs.org in the user's default browser."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://nodejs.org/en/download"))
```

**New `_on_open_preroll_log_clicked` handler** adapts this with `QUrl.fromLocalFile(...)` instead of a bare `QUrl("https://...")` + existence check (Pitfall 5):
```python
    def _on_open_preroll_log_clicked(self) -> None:
        """Phase 90 D-05: open preroll-events.log in OS default viewer."""
        import os
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from musicstreamer import paths
        log_path = paths.preroll_events_log_path()
        if not os.path.isfile(log_path):
            self.show_toast("No preroll log yet — play a SomaFM station first")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(log_path))
```

**Note:** `QUrl.fromLocalFile(path)` (not bare `QUrl(path)`) is required for `file://` construction on all platforms. The `main_window.py:919` analog uses a plain HTTPS URL; this is the only difference.

**Menu placement** — add in a new diagnostics group after the Group 3 separator (after line 286, before the Node-missing conditional at line 296). Add a separator before it to delineate:
```python
        self._menu.addSeparator()
        act_open_preroll_log = self._menu.addAction("Open preroll log")
        act_open_preroll_log.triggered.connect(self._on_open_preroll_log_clicked)  # QA-05
```

---

### `tests/test_preroll_events_log.py` (NEW — mirrors `tests/test_buffer_events_log.py`)

**Analog:** `tests/test_buffer_events_log.py` (entire file — 146 lines)

**Fixture pattern (lines 21–45 — copy verbatim, substitute logger name):**
```python
@pytest.fixture(autouse=True)
def _clean_player_handlers():
    log = logging.getLogger("musicstreamer.player")
    saved_handlers = list(log.handlers)
    saved_level = log.level
    log.setLevel(logging.INFO)
    yield
    for h in list(log.handlers):
        if h not in saved_handlers:
            try:
                h.close()
            except Exception:
                pass
            log.removeHandler(h)
    log.setLevel(saved_level)
```
New fixture: `_clean_preroll_handlers` — substitute `"musicstreamer.preroll"` for `"musicstreamer.player"` throughout.

**5 tests to mirror (test names → new names):**

| Analog test | New test | Logger / file substitution |
|-------------|----------|---------------------------|
| `test_handler_attached_to_player_logger` | `test_handler_attached_to_preroll_logger` | `"musicstreamer.preroll"` / `"preroll-events.log"` |
| `test_emit_writes_line_to_file` | `test_emit_writes_line_to_file` | emit `"preroll_start ..."` message |
| `test_rotation_at_1mb` | `test_rotation_at_1mb` | log `"preroll_start bench=..."` |
| `test_never_creates_backup_4` | `test_never_creates_backup_4` | same substitution |
| `test_record_reaches_both_sinks` | `test_record_reaches_both_sinks` | assert `"musicstreamer.preroll".propagate is True` |

**Install function import:** `from musicstreamer.preroll_log import install_preroll_events_handler`
**Path call:** `paths.preroll_events_log_path()` → `tmp_path / "preroll-events.log"`

---

### `tests/test_player_buffer_growth.py` (EXTEND — D-11 ordering + zero-behavior-change assertions)

**Analog:** `tests/test_player_buffer_growth.py` lines 184–251 (`test_try_next_stream_applies_pending_before_uri_bind`) and lines 254–304 (`test_preroll_handoff_applies_pending_before_uri_swap`)

**Key pattern from line 184 test (lines 221–251):**
```python
    player._pipeline.set_property.reset_mock()
    player._try_next_stream()
    calls = player._pipeline.set_property.call_args_list
    # Assert buffer-duration write precedes uri write
    duration_indices = [i for i, c in enumerate(calls) if c.args[0] == "buffer-duration"]
    uri_indices = [i for i, c in enumerate(calls) if c.args[0] == "uri"]
    assert duration_indices and uri_indices
    assert duration_indices[0] < uri_indices[0], (
        f"buffer-duration write must precede uri "
        f"write ... duration_index={duration_indices[0]}, "
        f"uri_index={uri_indices[0]}, calls={calls}"
    )
```

**Zero-behavior-change extension:** The new tests added to this file are assertions that the Phase 90 log calls do NOT inject `set_property` calls between `buffer-duration` and `uri`. The existing tests already cover this by checking `call_args_list` ordering. The extension confirms the 14 existing tests continue to pass after the Phase 90 preroll gate modifications — no new test structure needed beyond running the existing suite clean.

**Drift-guard note:** `test_phase_83_preroll_drift_guard` in `tests/test_player.py` (line 1201) source-greps `player.py` for the literal string `"SomaFM"` and `_last_preroll_played_at` to confirm the gate hasn't drifted. The new throttle-probe conditional (Pattern section above) adds a second occurrence of `"SomaFM"` and `_last_preroll_played_at` in the source — the drift-guard test asserts existence (at least one match), not exact count, so it remains green.

---

## Shared Patterns

### Pattern 4 — Thread-local Repo (applies to `_PrerollRefetchWorker` and auto-staleness branch)

**Source:** `musicstreamer/player.py` lines 2023–2036 (`_preroll_backfill_worker`)

```python
            con = db_connect()
            try:
                repo = Repo(con)
                for pos, url in enumerate(preroll_urls, start=1):
                    try:
                        repo.insert_preroll(station_id, url, pos)
                    except ValueError:
                        continue
                repo.set_prerolls_fetched_at(station_id, int(time.time()))
            finally:
                con.close()
```

**Rule:** `db_connect()` is called INSIDE the worker `run()` / thread target, never passed from the main thread. `con.close()` in `finally`. The `_PrerollRefetchWorker.run()` must mirror this exactly.

### Silent-failure contract (D-04 lineage — applies to all background workers)

**Source:** `musicstreamer/player.py` lines 2037–2041 (`_preroll_backfill_worker`)

```python
        except Exception as exc:  # noqa: BLE001 — D-04 silent failure path
            _log.warning(
                "Phase 83 preroll backfill failed for station %d (%r): %s",
                station_id, station_name, exc,
            )
```

**`_PrerollRefetchWorker`** uses `self.error.emit(str(exc))` (Qt signal path) rather than `_log.warning` — the menu-triggered worker reports failure via toast (Signal → `show_toast`). Daemon thread workers (`threading.Thread`) follow the `_log.warning` swallow pattern.

### SYNC-05 worker retention (applies to `_PrerollRefetchWorker`)

**Source:** `musicstreamer/ui_qt/main_window.py` line 365

```python
        self._soma_import_worker: QThread | None = None
```

Analogous field: `self._soma_refetch_worker: QThread | None = None`. Set to the worker before `.start()`, cleared to `None` in both `_on_preroll_refetch_done` and `_on_preroll_refetch_error`. Prevents GC of a running QThread (Phase 60 D-02 precedent).

### Idempotent log-handler install (applies to `preroll_log.py`)

**Source:** `musicstreamer/buffer_log.py` lines 58–60

```python
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed — short-circuit
```

This `for` loop + exact `baseFilename` comparison is the canonical idempotency guard. Do not use `len(log.handlers) == 0` — multiple independent handlers may share the same logger.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| "Open preroll log" menu action (`_on_open_preroll_log_clicked`) | component (menu handler) | request-response | No existing "Open [log file]" menu action in `main_window.py` — `buffer_events_log_path()` is never exposed in UI. The `_on_node_install_clicked` pattern provides the `QDesktopServices.openUrl` idiom but uses a URL, not a local file. Build from QDesktopServices.openUrl + QUrl.fromLocalFile + os.path.isfile existence guard (Pitfall 5). |

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`
**Files scanned:** 9 (buffer_log.py, paths.py, __main__.py, player.py lines 740–772 + 1560–1650 + 1998–2042, main_window.py lines 145–310 + 915–920 + 1567–1608, test_buffer_events_log.py, test_player_buffer_growth.py lines 178–304)
**Pattern extraction date:** 2026-06-18

---
phase: 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
asvs_level: 1
block_on: high
threats_total: 9
threats_closed: 9
threats_open: 0
audit_result: SECURED
audited_at: 2026-06-15
---

# Phase 94 — Security Audit Report

**Phase:** 94 — Optimize Sidebar Logo Loading with Pre-Scaled Thumbnails
**ASVS Level:** 1
**Block-on:** high
**Result:** SECURED — 9/9 threats closed, 0 open

---

## Threat Verification Register

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-94-02 | Tampering — path traversal | mitigate | CLOSED | `_art_paths.py:55-62` — `_thumb_path_for` returns `os.path.join(os.path.dirname(abs_source_path), THUMB_FILENAME)`. `abs_source_path` derives exclusively from `abs_art_path(rel)` which joins under `paths.data_dir()` (`paths.py:34-35`). `THUMB_FILENAME = "station_art.thumb.png"` is a module constant (`_art_paths.py:39`). No attacker-controlled string component in the write path. Worker writes only to the precomputed `thumb_path` passed in at call time (`_art_paths.py:113-114`). |
| T-94-03 | DoS / Info disclosure — malformed PNG | mitigate | CLOSED | `_art_paths.py:96-99` — `img = QImage(source_path); if img.isNull(): callback(station_id, source_path, None); return`. Outer `except Exception` at `_art_paths.py:127-128` catches any other worker failure and calls `callback(..., None)`, guaranteeing no exception escapes the daemon thread. Fallback icon stays on the renderer side when `thumb_path` is `None` (`station_tree_model.py:196-197`). |
| T-94-04 | Info disclosure — torn thumbnail | mitigate | CLOSED | `_art_paths.py:109-123` — `tempfile.mkstemp(dir=thumb_dir, suffix=".thumb.tmp.png")` creates temp in the same directory as the destination, guaranteeing a same-filesystem rename. `os.replace(tmp, thumb_path)` at line 113 is POSIX-atomic. CR-01 fix verified: when `scaled.save(tmp, "PNG")` returns `False`, `os.unlink(tmp)` is called at line 117 (not only on exception). A second `os.unlink(tmp)` at line 123 covers the exception path. Reader sees old-complete or new-complete, never partial. |
| T-94-05 | Tampering — Qt PNG decoder on import-sourced bytes | accept | CLOSED | Accepted risk (see Accepted Risks section). Confirmed no new untrusted-at-render input path was added: `_generate_thumb` reads only from `source_path` which is the pre-existing `abs_art_path(station.station_art_path)` value computed on the main thread from importer-written local files. No new network input, no user-supplied bytes at render time. `now_playing_panel._load_scaled_pixmap` (`now_playing_panel.py:204-216`) uses the same Qt decoder on the same source. |
| T-94-06 | Tampering — QPixmap/QPixmapCache off UI thread | mitigate | CLOSED | `grep "QPixmap" station_tree_model.py` returns only `QPixmapCache` import (line 22) and a single `QPixmapCache.remove(...)` call inside `_on_thumb_landing` (line 200), which is a slot delivered via `Qt.QueuedConnection` (line 69), guaranteeing main-thread execution. Inside `_generate_thumb` the worker closure uses `QImage` only (`_art_paths.py:96-102`); no `QPixmap(` appears within the `_generate_thumb` function body. All `QPixmap` constructions in `_art_paths.py` are in `load_station_icon` (lines 180-214), which is called from the main thread. |
| T-94-07 | DoS — worker storm / duplicate threads | mitigate | CLOSED | `station_tree_model.py:138-140` — `if station_id in self._in_flight_thumbs: return` dedup guard fires before any `_generate_thumb` call. `self._in_flight_thumbs.add(station_id)` at line 140 adds the id before spawning. `_in_flight_thumbs.discard(station_id)` at line 195 clears it in `_on_thumb_landing` (main-thread slot). Test `test_in_flight_dedup` (`tests/test_station_thumb_async.py:139`) is present and covers this path. |
| T-94-08 | Tampering — stale QModelIndex across async boundary | mitigate | CLOSED | Only `station_id: int`, `source_path: str`, and `thumb_path: str` cross the async boundary (via `_pending_landings` SimpleQueue, `station_tree_model.py:145`). `_on_thumb_landing` re-derives a fresh index via `index_for_station_id(station_id)` at line 201; `dataChanged.emit` is guarded by `if idx.isValid():` at line 202. No `QModelIndex` is stored across the async boundary anywhere in the pipeline. |
| T-94-09 | Repudiation / Integrity — now_playing drift | mitigate | CLOSED | `now_playing_panel.py:204-216` — `_load_scaled_pixmap` function exists and contains zero references to `"station_art.thumb"` (grep confirmed empty output). The function reads `abs_art_path(path)` and constructs `QPixmap(resolved)` directly from the full-resolution source path. Drift-guard test `test_now_playing_panel_does_not_use_thumb` (`tests/test_station_thumb_async.py:196-216`) asserts both conditions via `inspect.getsource`. Phase-94 commits touched only `_art_paths.py` and `station_tree_model.py` — `now_playing_panel.py` has zero Phase-94 commits. |
| T-94-01 | Tampering — test fixture file writes | accept | CLOSED | Accepted risk (see Accepted Risks section). Test files write exclusively under `pytest tmp_path` via `paths._root_override` monkeypatch (`94-01-PLAN.md` threat register). No production paths touched. |
| T-94-SC | Tampering — npm/pip/cargo installs | mitigate (N/A) | CLOSED | Phase 94 adds zero external dependencies. Implementation adds only stdlib imports (`tempfile`, `threading`, `queue`) and intra-package imports. No `requirements*.txt`, `pyproject.toml`, `package.json`, or `Cargo.toml` changes appear in Phase-94 commits (39191ff7, 9acf0b39, 4644a880, d3da2db2, c835341e, dd10d8e0). |

---

## Accepted Risks

### T-94-05 — Qt PNG Decoder Robustness on Import-Sourced Bytes

**Risk:** Qt's built-in PNG decoder processes bytes written by the aa/soma/gbs importers. A malformed importer-produced PNG could trigger a Qt decoder bug.

**Rationale for acceptance (ASVS L1):**
- The PNG bytes originate from the importer download flow, not from user-supplied render-time input. The attack surface is the importer, not the thumbnail renderer.
- The same Qt PNG decoder is already used by `now_playing_panel._load_scaled_pixmap` on the same files; Phase 94 introduces no new decoder call surface beyond what already existed for the full-resolution path.
- `QImage.isNull()` guard plus outer `try/except` in `_generate_thumb` ensure a malformed PNG causes a no-op (fallback icon) rather than a crash.
- Accepted at plan time in `94-02-PLAN.md` threat register.

### T-94-01 — Test Fixture File Writes

**Risk:** Tests write PNG files to temporary directories.

**Rationale for acceptance (ASVS L1):**
- Test-scope only. All writes go under `pytest tmp_path` via `paths._root_override` monkeypatch. No production path is reachable from test fixture code.
- Accepted at plan time in `94-01-PLAN.md` threat register.

---

## Unregistered Threat Flags

**None.** The three SUMMARY files (`94-01-SUMMARY.md`, `94-02-SUMMARY.md`, `94-03-SUMMARY.md`) each declare "None" or equivalent under their Threat Flags sections. No new attack surface was identified by the executor during implementation beyond the pre-registered threats.

---

## Implementation Architecture Notes

The final implementation diverged from the original Signal-emission-from-daemon-thread design due to a PySide6 6.11 limitation (`QTest.qWait` does not process `QueuedConnection` events posted from Python daemon threads). The adopted bridge — `queue.SimpleQueue` written by the daemon callback + `QTimer._poll_pending_landings` draining the queue on the main thread, then emitting `_thumb_landing` from the main thread — satisfies the security properties declared in the threat register:

- T-94-06 (QPixmap off UI thread): the daemon callback does `pending.put(...)` only — zero Qt object access. The `_thumb_landing.emit` call at `station_tree_model.py:167` runs from `_poll_pending_landings`, a main-thread timer slot.
- T-94-08 (stale QModelIndex): the bridge carries only `(int, str, str)` — no Qt objects — making the original guarantee stronger, not weaker.
- T-94-07 (dedup): the dedup guard at `station_tree_model.py:138` fires before the queue interaction; the in-flight set and queue are both drained atomically on the main thread.

---

## Audit Trail

| Date | Auditor | Action |
|------|---------|--------|
| 2026-06-15 | Claude (claude-sonnet-4-6) | Initial audit — all 9 threats verified against live code with file:line evidence. SECURED. |

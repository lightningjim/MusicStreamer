---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
reviewed: 2026-05-14T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - musicstreamer/__main__.py
  - musicstreamer/soma_import.py
  - musicstreamer/ui_qt/main_window.py
  - tests/fixtures/soma_channels_3ch.json
  - tests/fixtures/soma_channels_with_dedup_hit.json
  - tests/test_constants_drift.py
  - tests/test_main_window_gbs.py
  - tests/test_main_window_soma.py
  - tests/test_soma_import.py
findings:
  critical: 5
  warning: 7
  info: 5
  total: 17
status: issues_found
---

# Phase 74: Code Review Report

**Reviewed:** 2026-05-14
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 74 ships a SomaFM bulk-import backend (`soma_import.py`) and a `_SomaImportWorker` QThread plus three handlers in `main_window.py`. Two follow-up plans (74-05, 74-06) have already landed in the diff under review: a URL-slug bitrate parser (`_bitrate_from_url`) and a rename of every worker's `finished` signal to `<verb>_finished` to stop shadowing the inherited `QThread.finished()`. Those two follow-ups DO close the previously-identified CR-01 (hardcoded MP3-highest bitrate) and WR-04 (signal-shadowing). They do NOT close the other Critical and Warning findings from the earlier review, several of which remain live in the merged code.

Re-reviewing the **current** state of the source files I find:

* **BLOCKER** — `_resolve_pls` still returns `[pls_url]` (the input PLS URL) on any fetch/parse failure (line 115). That bogus URL is then fed into `_bitrate_from_url(pls_url, default)` (line 153), persisted as an ICE relay URL, and the user gets a "station" whose only stream is a `.pls` file the player cannot decode. This is the same silent-data-corruption path called out in WR-03 of the prior review — still unfixed.
* **BLOCKER** — `urllib.request.urlopen` is called on three operator-API-controlled URL fields (`_API_URL`, `pls_url`, `image_url`) with no scheme allow-list. A compromised api.somafm.com or any MitM that survives TLS can return `image: "file:///etc/passwd"` and the import will read it, copy it into the station-art assets directory, and persist the path. CR-03 from the prior review — still unfixed.
* **BLOCKER** — `_download_logos._download_logo` opens a new `sqlite3` connection per logo via `Repo(db_connect())` (line 286) and never closes it. With `max_workers=8` against the full 80+ SomaFM catalog, dozens of unclosed connections pile up under WAL on Windows. CR-04 from the prior review — still unfixed.
* **BLOCKER** — `import_stations` per-channel `try/except` (lines 252-255) wraps the station insert AND the stream-insert loop. If `insert_stream` raises mid-loop (UNIQUE constraint, OperationalError, etc.) the station row remains in the DB with a partial stream set, the user is told `skipped += 1`, and any subsequent re-import dedups on the partial URLs and never repairs the row. WR-02 from the prior review elevated here because the symptom is silent permanent data corruption.
* **BLOCKER** — `_on_soma_import_error` slot DOES NOT call `_refresh_station_list()` (line 1519-1523), but `import_stations` is allowed to insert rows BEFORE raising (the worker's `try/except` is at line 165-174 around the whole `fetch_channels` + `import_stations` chain). If a malformed channel late in the list triggers an unhandled exception OUTSIDE the per-channel `try/except` (e.g., a `KeyboardInterrupt` or memory error during `_download_logos` post-loop), the user sees "SomaFM import failed: …" but the station list is stale — `imported` stations are in the DB and invisible until next refresh.

Beyond the five blockers there are seven warnings (silent logo-failure logging, double-click race, `_bitrate_from_url` accepts arbitrary digit run lengths, `urllib.error` unused import promoted from info because it betrays incomplete error-handling design, regression-test `db_connect` not mocked, `_re_import…` test relies on real fs/db side effects, codec literal "AAC" conflates LC and HE-AAC) and five info items.

## Critical Issues

### CR-01: `_resolve_pls` silently corrupts the import by returning the input PLS URL as if it were a stream URL

**File:** `musicstreamer/soma_import.py:113-115`
**Issue:**
```python
except Exception:  # noqa: BLE001
    pass
return [pls_url]
```
On any fetch failure (network blip, parse error, empty playlist) the function returns the input `.pls` URL inside a 1-element list. `fetch_channels` then iterates that list at line 152 as if it were a list of ICE relay URLs, calls `_bitrate_from_url(pls_url, default)` (line 153), persists the `.pls` URL as a `station_streams.url` row, and the SomaFM provider gets a "station" whose only stream is `https://api.somafm.com/groovesalad256.pls` — a playlist file, not an audio stream. The Player cannot decode it. Worse: on the next re-import `station_exists_by_url(".../groovesalad256.pls")` returns True and the WHOLE channel is dedup-skipped, so the broken station is never repaired.

The docstring at line 102-103 claims "Falls back to [pls_url] on any exception (mirrors AA; callers that need [0] continue to work against the fallback-on-error contract)" — but no current Phase 74 caller "needs [0]"; the AA-legacy contract has no place in the Phase 74 import path and produces silently-broken data for the SomaFM use case.

**Fix:** Return `[]` (empty list) on fetch failure or empty parse. The caller's `if not streams: continue` at line 161 already drops a channel that produces zero recognisable tiers, which is the correct behaviour:
```python
def _resolve_pls(pls_url: str, timeout: int = 10) -> list[str]:
    try:
        req = urllib.request.Request(pls_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
        from musicstreamer.playlist_parser import parse_playlist
        entries = parse_playlist(body, content_type=content_type, url_hint=pls_url)
        return [e["url"] for e in entries if e.get("url")]
    except Exception as exc:
        _log.warning("SomaFM PLS fetch failed for %s: %s", pls_url, exc)
        return []
```
If AA's `_resolve_pls` shares the same fallback contract, audit it separately — Phase 74 should not be the place to ripple the change.

### CR-02: SSRF / local-file-read via `urllib.request.urlopen` — no scheme allow-list on any of the three call sites

**File:** `musicstreamer/soma_import.py:106, 132, 278`
**Issue:** `urllib.request.urlopen` accepts `file://`, `ftp://`, and arbitrary `http://` URLs. Three call sites pass operator-API-controlled URL fields into it:

1. Line 132 — `urlopen(req)` where `req.full_url` is `_API_URL` (hardcoded HTTPS — safe today).
2. Line 106 — `urlopen(req, timeout=timeout)` where `pls_url` comes from `playlists[].url` in the SomaFM JSON response.
3. Line 278 — `urlopen(req, timeout=15)` where `image_url` comes from `channels[].image` in the SomaFM JSON response.

A compromised api.somafm.com (single bad CDN edge, single MitM in TLS chain, single hijacked DNS resolution) can return `{"image": "file:///etc/passwd", "playlists": [{"url": "http://127.0.0.1:9100/metrics", ...}]}`. The import will then (a) read local files into the user's station-art directory and persist the path in the DB, and (b) open arbitrary internal HTTP services from the user's workstation. On a future server-side bulk-import path (any Phase 7x cron / sync job) this is a hard SSRF pivot.

This matches Phase 74's "Mirror X" decision-citation rule from MEMORY.md — the only spec citation supporting `urllib.request.urlopen` is "AA does it this way", and AA carries the same surface; both deserve the fix.

**Fix:** Add a `_safe_urlopen` helper that rejects non-HTTPS schemes and empty netlocs. Replace all three call sites.
```python
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"https", "http"}  # 'http' retained for legacy SomaFM ICE relays on port 80

def _safe_urlopen(url: str, timeout: int):
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Refusing non-HTTP(S) URL scheme: {parsed.scheme!r}")
    if not parsed.netloc:
        raise ValueError(f"Refusing URL with empty netloc: {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)
```

### CR-03: SQLite connection leak in `_download_logos` — one connection per logo, never closed

**File:** `musicstreamer/soma_import.py:286-287`
**Issue:**
```python
art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
thread_repo = Repo(db_connect())
thread_repo.update_station_art(station_id, art_path)
```
`thread_repo` (and the underlying `sqlite3.Connection`) is local. There is no `con.close()` and no context-manager use. CPython's reference-counting GC will close the connection when `thread_repo` drops, but only after the `_download_logo` callable returns — for `ThreadPoolExecutor(max_workers=8)` running through 80+ channels this means dozens of connections held open across the executor's lifetime. On Windows SQLite WAL has been observed to hold journal locks across exactly this pattern (referenced in MEMORY.md `reference_musicstreamer_db_schema.md`). The corresponding bug in `aa_import.py:267` has the same shape; do not let Phase 74 reintroduce it.

**Fix:**
```python
art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
con = db_connect()
try:
    Repo(con).update_station_art(station_id, art_path)
finally:
    con.close()
```

### CR-04: `import_stations` per-channel try/except allows half-imported stations to persist permanently

**File:** `musicstreamer/soma_import.py:197-256`
**Issue:** The `try` block (line 198) wraps both `repo.insert_station(...)` (line 215) AND the per-stream loop (lines 224-248). If `insert_stream` raises on, say, the 7th of 20 streams (UNIQUE constraint from a prior crashed run, sqlite OperationalError on lock contention), the outer `except Exception` (line 252) increments `skipped`, the user is told "skipped 1 channel", and the half-imported station persists in the DB:
- 1 row in `stations` (created at line 215)
- 1 row in `station_streams` from `insert_station`'s implicit first-stream insert (repo.py:542)
- N additional rows in `station_streams` (where N is the count before the failure)

On the next re-import, `station_exists_by_url` returns True for the persisted partial URLs, the WHOLE channel is dedup-skipped (line 210), and the broken station is never repaired. The user has no UI affordance for "this station is missing 13 streams"; the only escape is a manual edit-station-streams round-trip.

This is silently permanent data corruption — strictly worse than the original symptom WR-02 in the prior review documented (which classified it as Warning).

**Fix:** Two-step approach. Cheap fix: roll back the station on any per-channel exception by tracking the inserted station_id and deleting it on failure. Repo already has `delete_station` (per the `_FakeRepo` test double). The Repo `delete_station` implementation should CASCADE-delete `station_streams` rows; verify before relying on it.
```python
for ch in channels:
    inserted_station_id: int | None = None
    try:
        if not ch.get("streams"):
            ...
        else:
            ...
            inserted_station_id = repo.insert_station(...)
            for s in ch["streams"]:
                ...
            imported += 1
            if ch.get("image_url"):
                logo_targets.append((inserted_station_id, ch["image_url"]))
    except Exception as exc:
        if inserted_station_id is not None:
            try:
                repo.delete_station(inserted_station_id)
            except Exception:
                _log.warning("Failed to roll back partial SomaFM station %s", inserted_station_id)
        _log.warning("SomaFM channel %s import skipped: %s", ch.get("id"), exc)
        skipped += 1
```
Long-term, add a `Repo.insert_station_with_streams(...)` atomic API so the whole channel is one SQLite transaction.

### CR-05: `_on_soma_import_error` skips `_refresh_station_list()` — UI silently stale after partial-import failure

**File:** `musicstreamer/ui_qt/main_window.py:1519-1523`
**Issue:**
```python
def _on_soma_import_error(self, msg: str) -> None:
    truncated = (msg[:80] + "…") if len(msg) > 80 else msg
    self.show_toast(f"SomaFM import failed: {truncated}")
    self._soma_import_worker = None
```
This branch does not refresh the station list. But `_SomaImportWorker.run()` wraps the ENTIRE `fetch_channels() + import_stations()` chain in one `try/except Exception` (line 165-174). `import_stations` is allowed to commit station rows BEFORE the failure propagates (e.g., the per-channel `try/except` does not catch `MemoryError`, `KeyboardInterrupt`, `SystemExit`; an exception during `_download_logos` after the loop will also propagate out of `import_stations` with stations already committed). The user then sees the failure toast, the worker reference is cleared, but `_refresh_station_list()` never runs — the StationListPanel is now lying about the library state until the next manual interaction.

Compare to `_on_soma_import_done` which DOES call `self._refresh_station_list()` at line 1516. The error path should mirror it.

**Fix:**
```python
def _on_soma_import_error(self, msg: str) -> None:
    truncated = (msg[:80] + "…") if len(msg) > 80 else msg
    self.show_toast(f"SomaFM import failed: {truncated}")
    self._refresh_station_list()    # partial inserts may exist; never trust the cached list
    self._soma_import_worker = None
```

## Warnings

### WR-01: `_download_logos` silently swallows ALL exceptions with no log line

**File:** `musicstreamer/soma_import.py:293-294`
**Issue:**
```python
except Exception:  # noqa: BLE001
    pass
```
The module registers a logger at INFO (`__main__.py:236`), but the bare-swallow `pass` eats every logo-download failure with zero diagnostic data. When a user reports "half my SomaFM stations have no art" the developer has nothing to grep for — was it a 404? a permission denied on the asset dir? a Pillow / `copy_asset_for_station` crash? Unknown.

**Fix:**
```python
except Exception as exc:
    _log.warning("SomaFM logo download failed for station %s (%s): %s",
                 station_id, image_url, exc)
```

### WR-02: Double-clicking "Import SomaFM" spawns parallel workers — no in-flight guard

**File:** `musicstreamer/ui_qt/main_window.py:1502-1508`
**Issue:** `_on_soma_import_clicked` unconditionally constructs a new `_SomaImportWorker` and assigns it to `self._soma_import_worker`, dropping the previous reference. A user who double-clicks the action gets two workers racing: both call `fetch_channels()` (~30s of network each), both call `Repo(db_connect())` from different threads, both try to import. `station_exists_by_url` checks race against each other's inserts. The first worker's `_on_soma_import_done` clears `self._soma_import_worker = None` while the second is still running, defeating the SYNC-05 retention rationale and exposing the second worker to mid-run GC.

The GBS analog (`_on_gbs_add_clicked`, line 1453-1464) has the same defect.

**Fix:** Guard at function head.
```python
def _on_soma_import_clicked(self) -> None:
    if self._soma_import_worker is not None:
        self.show_toast("SomaFM import already in progress")
        return
    self.show_toast("Importing SomaFM…")
    self._soma_import_worker = _SomaImportWorker(parent=self)
    self._soma_import_worker.import_finished.connect(self._on_soma_import_done)
    self._soma_import_worker.error.connect(self._on_soma_import_error)
    self._soma_import_worker.start()
```

### WR-03: `_bitrate_from_url` accepts arbitrary-length digit runs; no upper bound on parsed bitrate

**File:** `musicstreamer/soma_import.py:74, 77-88`
**Issue:** `_BITRATE_FROM_URL_RE = re.compile(r"-(\d+)-(?:mp3|aac|aacp)\b")` matches `\d+` with no length cap, then `int(m.group(1))` parses to a Python int (arbitrary precision). A SomaFM URL containing `-999999999999-mp3` (whether maliciously injected, copy-pasted, or simply a slug typo) is silently persisted as `bitrate_kbps=999999999999`. SQLite INTEGER column will store it; downstream UI sort/display logic that expects a small positive int may render garbage or trip range assertions.

This is also a minor DoS surface: an attacker who controls the SomaFM API response (CR-02 already establishes that is a realistic threat) can hand the parser a `\d{100000}-mp3` slug. The regex engine will scan it in linear time, but `int()` on a 100k-digit string is a CPython quadratic-time operation (PEP 651 / CVE-2020-10735 territory pre-CPython 3.11 hardening).

**Fix:** Cap the digit run and validate the parsed integer falls in `[8, 9999]` (the realistic ICE bitrate range):
```python
_BITRATE_FROM_URL_RE = re.compile(r"-(\d{1,5})-(?:mp3|aac|aacp)\b")

def _bitrate_from_url(url: str, default: int) -> int:
    m = _BITRATE_FROM_URL_RE.search(url)
    if m:
        try:
            value = int(m.group(1))
        except ValueError:
            return default
        if 8 <= value <= 9999:
            return value
    return default
```

### WR-04: `test_re_import_emits_no_changes_toast_via_real_thread` calls real `db_connect()` from a worker thread

**File:** `tests/test_main_window_soma.py:314-361`
**Issue:** The test stubs `soma_import.fetch_channels` and `soma_import.import_stations` but leaves `db_connect()` un-monkeypatched. `_SomaImportWorker.run()` (main_window.py:170) executes `repo = Repo(db_connect())` in the worker thread — that line runs the REAL `db_connect`, hitting the filesystem. On a CI runner with no XDG_DATA_HOME / no pre-created SQLite dir this is a real I/O dependency hidden inside a regression test, and on a developer's workstation it mutates the dev database (creates the file if missing, applies schema migrations). The test is also vulnerable to flakiness if `db_init` schema-migration takes >5s on a cold cache.

**Fix:** Monkeypatch `musicstreamer.ui_qt.main_window.db_connect` and `Repo` to in-memory fakes for the duration of the test:
```python
import sqlite3
monkeypatch.setattr("musicstreamer.ui_qt.main_window.db_connect",
                    lambda: sqlite3.connect(":memory:"))
monkeypatch.setattr("musicstreamer.ui_qt.main_window.Repo",
                    lambda con: MagicMock())  # import_stations is also stubbed
```
Or inject a fake `Repo` via the worker constructor (a small refactor, but it makes the worker testable in isolation).

### WR-05: `test_no_self_capturing_lambda_in_soma_action` parses source with `open(...)` and never closes the file

**File:** `tests/test_main_window_soma.py:304`
**Issue:**
```python
src = open("musicstreamer/ui_qt/main_window.py", encoding="utf-8").read()
```
The file handle is never closed; CPython reference-count GC closes it on next gc cycle, but it leaks an FD on Windows and trips `ResourceWarning` under `pytest -W error::ResourceWarning`. The sibling test `test_no_self_capturing_lambda_in_gbs_action` in `tests/test_main_window_gbs.py:234-236` has the same pattern.

**Fix:**
```python
from pathlib import Path
src = Path("musicstreamer/ui_qt/main_window.py").read_text(encoding="utf-8")
```

### WR-06: Codec literal "AAC" stored for both LC-AAC and HE-AAC (aacp) streams — DB cannot distinguish

**File:** `musicstreamer/soma_import.py:65-67`
**Issue:** The tier table maps `("aac", "highest") → codec="AAC"` AND `("aacp", "high") → codec="AAC"` AND `("aacp", "low") → codec="AAC"`. The comment block at line 60-62 acknowledges this and cites Phase 69 WIN-05's decision that "aacp" decodes via the same `aacparse + avdec_aac` chain — but the stored `codec` column now conflates two materially different codecs (HE-AAC v1 uses SBR; HE-AAC v2 adds Parametric Stereo). Any future UI or quality-map logic that displays "Codec: AAC" will mislead users on SomaFM 64 / 32 kbps tiers.

This is not a runtime bug today, but the DB schema has no `codec_subtype` column to recover the distinction later — the data loss is permanent at insert time. Flag it now while the codec literal is still grep-replaceable.

**Fix:** Either accept the precision loss and add a TODO in 74-LEARNINGS.md, or change the `aacp` tiers' codec to `"HE-AAC"` and verify the player's codec routing tolerates the new label (Phase 69 WIN-05 needs a tap before flipping the literal).

### WR-07: `urllib.error` imported but never used — betrays incomplete error-handling design

**File:** `musicstreamer/soma_import.py:26`
**Issue:** `import urllib.error` is at the top of the file but `urllib.error` is not referenced anywhere. Compare to `aa_import.py` which uses `urllib.error.HTTPError` to distinguish 401/403 (invalid listen key) from other failures and surface a re-auth toast. The SomaFM module collapses every network exception into the same `_log.warning(...)` + `pass` swallow (lines 113-114, 175 try/except, 252 try/except, 293 except). The missing distinction means the user gets the same opaque "SomaFM import failed: …" toast whether the failure is recoverable (network blip, single channel down) or operator-facing (SomaFM API returned 5xx, retry in 5 min).

**Fix:** Remove the import OR use it. The cleanest first step is to catch `urllib.error.HTTPError` separately in `fetch_channels` so a 5xx surfaces as `"SomaFM is temporarily unavailable — try again in a few minutes"` and a 4xx surfaces as `"SomaFM API rejected the request — please file a bug"`.

## Info

### IN-01: `_SomaImportWorker.__init__` is a no-op forward — drop it

**File:** `musicstreamer/ui_qt/main_window.py:162-163`
**Issue:**
```python
def __init__(self, parent=None):
    super().__init__(parent)
```
Adds zero behaviour over `QThread.__init__`. `_GbsImportWorker.__init__` (line 135-136) has the same dead override. PySide6 accepts `_SomaImportWorker(parent=self)` natively.

**Fix:** Delete the override.

### IN-02: `_bitrate_from_url` is dead-code-tested as a public API but underscore-prefixed

**File:** `musicstreamer/soma_import.py:77, tests/test_soma_import.py:498-522`
**Issue:** The new helper is named with a leading underscore (Python convention: module-private) but the test file calls it as `soma_import._bitrate_from_url(...)` from outside the module. This is allowed Python and is consistent with `_resolve_pls` testing in the same file, but the convention drift makes future grep "what depends on this private?" lie. Either drop the leading underscore (promote to module-public API since it's exercised by tests + has a 3-public-test contract) or keep the underscore and route the test via a thin public wrapper.

**Fix:** Rename to `bitrate_from_url` (no leading underscore) — its contract is now a tested invariant.

### IN-03: Three near-identical worker classes — `_ExportWorker`, `_ImportPreviewWorker`, `_GbsImportWorker`, `_SomaImportWorker`

**File:** `musicstreamer/ui_qt/main_window.py:88-174`
**Issue:** All four `QThread` subclasses follow the same shape: a `<verb>_finished` signal, an `error` signal, an `__init__(self, parent=None)` that just forwards, and a `run()` that calls one backend function in try/except. After the 74-06 rename the pattern is even more uniform. This is now a candidate for a single parametrised `_BackgroundWorker(QThread)` base class that takes the callable and emits a generic `done`/`error`. Not a defect — flagging because the duplication will rot the next time someone forgets to rename `finished` (root cause of CR-02 / WR-04 in the prior review).

**Fix:** Future refactor; out of scope for Phase 74 closeout.

### IN-04: `tests/test_constants_drift.py` regex-style baseline test inflates phase-completion risk

**File:** `tests/test_constants_drift.py:82-108`
**Issue:** `test_richtext_baseline_unchanged_by_phase_71` literally counts `setTextFormat(Qt.RichText)` occurrences and asserts equality to `EXPECTED_RICHTEXT_COUNT = 3`. Any addition of a legitimate new RichText QLabel will RED-fail an unrelated test in an unrelated phase. The test docstring acknowledges the test was RED for the entirety of Phase 71. Useful as a tripwire; brittle as a permanent CI gate.

**Fix:** Promote to a `# trip-wire / xfail-strict` annotation OR replace the strict equality with a documented upper-bound `assert count <= EXPECTED_RICHTEXT_COUNT`. Out of scope for Phase 74 but worth noting since Phase 74 added two new drift tests in the same file (lines 116-156).

### IN-05: `_log.warning` for swallowed channel exceptions includes only `ch.get("id")` — missing `title` for diagnostic correlation

**File:** `musicstreamer/soma_import.py:174, 254`
**Issue:**
```python
_log.warning("Skipping SomaFM channel %s: %s", ch.get("id"), exc)
_log.warning("SomaFM channel %s import skipped: %s", ch.get("id"), exc)
```
The SomaFM `id` is a short slug (`groovesalad`, `dronezone`); the `title` is the user-facing name. A user reporting "Boot Liquor is missing after import" gives the title, not the slug — the developer then has to grep the catalog to find which slug corresponds. Cheap to fix.

**Fix:**
```python
_log.warning("SomaFM channel %r (%s) import skipped: %s",
             ch.get("title"), ch.get("id"), exc)
```

---

_Reviewed: 2026-05-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

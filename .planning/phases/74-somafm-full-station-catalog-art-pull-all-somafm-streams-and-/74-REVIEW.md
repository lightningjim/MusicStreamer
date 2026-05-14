---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
reviewed: 2026-05-14T13:30:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - musicstreamer/soma_import.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/__main__.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 74: Code Review Report

**Reviewed:** 2026-05-14T13:30:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 74 adds a SomaFM bulk-import backend (`soma_import.py`) plus a `_SomaImportWorker` QThread + handler trio in `main_window.py`, with a logger registration in `__main__.py`. The shape mirrors the AudioAddict importer (`aa_import.py`) and the GBS worker (`_GbsImportWorker`), so the structural skeleton is sound.

The two UAT-surfaced issues are real and confirmed:

1. **Hardcoded MP3-highest bitrate (CR-01)** — `_TIER_BY_FORMAT_QUALITY` pins `(mp3, "highest")` to `bitrate_kbps=128`. SomaFM's catalog has channels whose `highest`-quality MP3 stream is 256 kbps (e.g. `synphaera-256-mp3`, `secretagent-128-mp3` is 128 but `bootliquor-128-mp3` is 128 — many are ≥ 192). The actual bitrate is encoded in the URL slug (`-NNN-mp3`) and is also exposed by `playlists[].url` plus the upstream API's per-playlist hints, but the import never reads them. Every imported MP3-highest stream lands in the DB with `bitrate_kbps=128`, which is wrong.

2. **Idempotent re-import emits "no changes" toast — but two adjacent defects can suppress it (CR-02 + WR-04)**. The `else:` branch in `_on_soma_import_done` is correctly written, so when it fires you DO get the toast. The cases where it does NOT fire (and which match the UAT report) are: (a) `_SomaImportWorker.finished = Signal(int, int)` SHADOWS `QThread.finished()`, the auto-emitted parent C++ signal — the same trapdoor the GBS worker has, but GBS gets re-imports rarely so the symptom never showed; and (b) on idempotent re-import `import_stations` returns `(0, N)` and `_download_logos([])` short-circuits, so the run completes faster than the network-fetch user expects, but this is fine. The actual user-visible regression is that on `inserted=0` with EVERY channel skipped via the per-channel try/except bumping `skipped`, the worker never reaches the manual `self.finished.emit(...)` call IF `fetch_channels` itself raises — and the error path's `_on_soma_import_error` runs instead of `_on_soma_import_done`. See CR-02 for the concrete trace.

Beyond the two known issues there are additional Critical/Warning findings: SSRF surface from un-validated `image_url` / `pls_url` schemes (CR-03), per-logo SQLite connection leak (CR-04), silent logo failures (WR-01), and several quality issues.

## Critical Issues

### CR-01: MP3-highest bitrate hardcoded to 128 — wrong for ~half the SomaFM catalog

**File:** `musicstreamer/soma_import.py:62-67`
**Issue:** `_TIER_BY_FORMAT_QUALITY[("mp3", "highest")]` returns `{"bitrate_kbps": 128, ...}` unconditionally, but SomaFM publishes 128 / 192 / 256 kbps as the `highest` MP3 tier per channel. Channels like `synphaera` (`https://ice2.somafm.com/synphaera-256-mp3`), `vaporwaves`, `groovesalad` (192), etc. all get persisted with the wrong bitrate. Downstream UI / quality-map logic that uses `bitrate_kbps` for sorting/labelling is now lying about the stream. This is the UAT-surfaced bug #1.

The bitrate is recoverable from at least three places: (a) the URL slug `-(\d+)-mp3`, (b) the SomaFM `playlists[]` entry doesn't expose bitrate directly but the channel JSON has a `highestpls`/`fastpls`/`slowpls` set with explicit kbps fields, (c) parsing the icy headers from each ICE relay (heavyweight; do not).

**Fix:** Parse the bitrate from the relay URL slug after `_resolve_pls`, then override the table default per stream. Keep the table default as a fallback only:

```python
import re

_BITRATE_FROM_URL_RE = re.compile(r"-(\d+)-(?:mp3|aac|aacp)\b")

def _bitrate_from_url(url: str, default: int) -> int:
    """Extract bitrate from SomaFM ICE URL slug like ice2.somafm.com/foo-256-mp3."""
    m = _BITRATE_FROM_URL_RE.search(url)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return default

# Then in fetch_channels at the streams.append site:
for relay_index, relay_url in enumerate(relay_urls, start=1):
    parsed_bitrate = _bitrate_from_url(relay_url, tier_meta["bitrate_kbps"])
    streams.append({
        "url": relay_url,
        "quality": tier_meta["quality"],
        "position": tier_meta["tier_base"] * 10 + relay_index,
        "codec": tier_meta["codec"],
        "bitrate_kbps": parsed_bitrate,
    })
```

Also add a unit test fixture asserting `synphaera`'s `hi`-tier streams persist as 256 kbps and `groovesalad` as 192 (or whatever the live data shows).

### CR-02: `_SomaImportWorker` swallows fatal `fetch_channels` errors as toast-failed; on partial-failure the per-channel try/except in `import_stations` masks the failure and emits `(0, 0)` — no toast either way

**File:** `musicstreamer/ui_qt/main_window.py:165-174` and `musicstreamer/soma_import.py:120-155, 175-240`
**Issue:** This is the root cause of UAT bug #2 ("no toast at all on idempotent re-import"). The flow has two interacting bugs:

1. `_SomaImportWorker.run()` wraps the entire `fetch_channels()` + `import_stations()` chain in a single `try/except Exception`. If `fetch_channels` raises (network blip, DNS, SomaFM 5xx), the worker calls `self.error.emit(str(exc))` — `_on_soma_import_error` then shows "SomaFM import failed: …". OK so far.

2. But `fetch_channels` itself has a per-channel `try/except` (line 120-153) that swallows ALL exceptions (including `_resolve_pls` returning the fallback `[pls_url]`, which is THEN treated as a valid stream URL). `_resolve_pls` ALSO swallows all exceptions and returns `[pls_url]` — the input PLS URL — as if it were a real ICE relay URL. So a SomaFM-side outage that 502s the per-channel `.pls` fetches yields a channel with `streams=[{"url": "https://somafm.com/foo.pls", ...}]`. On re-import, `station_exists_by_url("...foo.pls")` returns False (no prior PLS-URL stream exists), the channel is "imported" with a non-streamable URL, and the user sees `"SomaFM import: 80 stations added"` with stations that never play.

3. The `_on_soma_import_done` slot itself is correct. The reason the UAT saw "no toast at all" is that the `finished` signal — `Signal(int, int)` — SHADOWS the parent `QThread.finished()` (no-arg). When the C++ side auto-emits `finished()` with no args at thread end, PySide6 dispatches into the Python signal slot `_on_soma_import_done(inserted, skipped)` with the wrong arity, which raises `TypeError: _on_soma_import_done() missing 2 required positional arguments` *inside the Qt event dispatcher*, swallowed by Qt and printed only to stderr. The result: no toast. The GBS worker has the identical bug (line 124-150) but it has not surfaced because GBS imports are rare.

**Fix:** Two changes are needed.

(a) Rename the Phase 74 worker's signal so it does not shadow `QThread.finished`:

```python
class _SomaImportWorker(QThread):
    import_finished = Signal(int, int)   # (inserted, skipped) — NOT 'finished'
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

And update the connect at `main_window.py:1506`:

```python
self._soma_import_worker.import_finished.connect(self._on_soma_import_done)
```

Apply the same rename to `_GbsImportWorker.finished` → `_GbsImportWorker.import_finished` (and its caller at `main_window.py:1462`), and `_ExportWorker.finished` / `_ImportPreviewWorker.finished` if they have the same shape (they do — `main_window.py:101, 107, 119`). This clears the latent bug across all four workers.

(b) Make `_resolve_pls` distinguish "fetched OK but empty" from "fetch failed", and stop returning the input PLS URL as if it were a relay URL. Caller-side (`fetch_channels`) should treat a fetch failure as a recoverable per-channel error that contributes to `skipped`:

```python
def _resolve_pls(pls_url: str, timeout: int = 10) -> list[str] | None:
    """Returns None on fetch failure, [] on empty playlist, list[str] otherwise."""
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
        return None
```

In `fetch_channels`, treat `None` as a hard failure for that tier (skip the tier; do NOT silently substitute the input URL):

```python
relay_urls = _resolve_pls(pl["url"])
if not relay_urls:
    continue   # tier failed — drop this tier, channel may still have other tiers
```

Note: this is a behavioural change for AA-style callers, so audit `aa_import._resolve_pls` callers before applying the same fix there.

### CR-03: SSRF / local-file-read via `urllib.request.urlopen(image_url)` — no scheme allow-list

**File:** `musicstreamer/soma_import.py:255` (and `:84` for PLS, `:111` for the channels API)
**Issue:** `urllib.request.urlopen` accepts `file://`, `ftp://`, and arbitrary `http://` URLs. The `image_url` and `pl["url"]` values come from the SomaFM API response, and while api.somafm.com is reasonably trusted, a single compromised CDN entry or a MitM in the api.somafm.com TLS chain can serve `{"image": "file:///etc/passwd"}` or `{"image": "http://internal-corp-host:8080/admin"}`. The ThreadPoolExecutor then opens `file:///etc/passwd`, reads the bytes, copies them into the user's station-art directory, and persists the path in the DB. On a developer workstation that's a leak; on a future server-side bulk-import (Phase 7x) it's an SSRF pivot into the internal network.

The api endpoint `_API_URL` is hardcoded HTTPS (good), but `urlopen` does not enforce that the URL passed to `Request(...)` is HTTPS. There is no scheme validation anywhere in this module.

**Fix:** Add a strict scheme check before every `urlopen`. A 4-line helper covers all three call sites:

```python
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"https", "http"}   # 'http' kept for ICE relays that 80/tcp some legacy SomaFM mirrors

def _safe_urlopen(url: str, timeout: int):
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Refusing non-HTTP(S) URL scheme: {parsed.scheme!r}")
    if not parsed.netloc:
        raise ValueError(f"Refusing URL with empty netloc: {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)
```

Then replace every `urllib.request.urlopen(req, ...)` site with `_safe_urlopen(url, timeout)`. The mitigation should also propagate to `aa_import.py` (same surface, same trust level).

### CR-04: SQLite connection leak in `_download_logos` — one new connection per logo, never closed

**File:** `musicstreamer/soma_import.py:264-265`
**Issue:** `_download_logo` does `thread_repo = Repo(db_connect())` for every logo target. The connection is referenced by `thread_repo` for the duration of the `update_station_art` call and then dropped. CPython will eventually GC the `Repo` and close the underlying sqlite connection, but only on a future GC cycle — and inside a `ThreadPoolExecutor(max_workers=8)` running through the full ~80-channel SomaFM catalog this means ~80 connections are opened in quick succession with no deterministic close. On Windows (Phase 74's deployment target per spike findings) sqlite WAL files have been observed to lock under exactly this pattern, and a worker thread holding an unclosed connection across a `update_station_art` is a known Phase 67 footgun (referenced in your project memory).

The AA importer (`aa_import.py:267`) has the same bug — but Phase 74 surfaces it more sharply because SomaFM has 80 channels vs AA's smaller per-network sets.

**Fix:** Close the connection deterministically with `try/finally` or use the connection as a context manager:

```python
def _download_logo(station_id: int, image_url: str) -> None:
    try:
        req = urllib.request.Request(image_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        suffix = os.path.splitext(image_url.split("?")[0])[1] or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
            con = db_connect()
            try:
                Repo(con).update_station_art(station_id, art_path)
            finally:
                con.close()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as exc:
        _log.warning("SomaFM logo download failed for %s: %s", image_url, exc)
```

(See WR-01 for the related `except Exception: pass` swallowing.)

## Warnings

### WR-01: `_download_logos` silently swallows ALL exceptions — no log line, no telemetry

**File:** `musicstreamer/soma_import.py:271-272`
**Issue:** `except Exception: pass` (bare-bones, not even a `noqa` comment justifying it). The docstring claims "best-effort" and "silently swallowed", but for a 280-line file that registers a logger at INFO level (per `__main__.py:236`), eating every logo failure with no log line is a debugging dead-end. When a user reports "half my SomaFM stations have no art", you have zero diagnostic data — was it a 404? a permission denied on the asset dir? a `copy_asset_for_station` raise? Unknown.

**Fix:** Log the exception at WARNING. The "non-fatal" contract is preserved; you just gain diagnostics:

```python
except Exception as exc:
    _log.warning("SomaFM logo download failed for station %s (%s): %s",
                 station_id, image_url, exc)
```

### WR-02: `import_stations` per-channel try/except can mark a successfully-half-imported channel as "skipped"

**File:** `musicstreamer/soma_import.py:175-233`
**Issue:** The channel body inserts the station, then iterates streams and calls `insert_stream` per stream. If `insert_stream` raises on, say, the 5th stream of 20 (UNIQUE constraint on `url` from a prior partial run), the channel is half-imported (1 station + 4 streams in the DB) but the outer `except Exception` increments `skipped` and the user is told "skipped 1". A subsequent re-import will then see that stream URL exists, skip the WHOLE channel, and the half-imported station is permanently broken (1 station with 4 streams, never repaired).

**Fix:** Wrap the station/stream insert in a single transaction so a stream failure rolls back the station. The repo currently auto-commits after each `insert_stream`. Either:

(a) Add `repo.delete_station(station_id)` in the `except` branch when partway through stream inserts, OR

(b) Restructure to validate all streams first (no DB writes), then do all inserts inside a single transaction. The latter is cleaner but requires a `repo.insert_station_with_streams` API.

The minimal short-term fix is (a):

```python
station_id = None
try:
    # ... existing logic ...
    station_id = repo.insert_station(...)
    # ... insert_stream loop ...
    imported += 1
except Exception as exc:
    if station_id is not None:
        try:
            repo.delete_station(station_id)
        except Exception:
            _log.warning("Failed to roll back partial SomaFM station %s", station_id)
    _log.warning("SomaFM channel %s import skipped: %s", ch.get("id"), exc)
    skipped += 1
```

### WR-03: `_resolve_pls` returns input PLS URL as a "relay URL" on any fetch failure — silently corrupts the import

**File:** `musicstreamer/soma_import.py:92-94`
**Issue:** Already covered structurally in CR-02, but worth its own finding because it is a localised bug independent of the worker-shadowing issue. The `return [pls_url]` fallback hands the upstream caller a list containing the `.pls` playlist URL itself, which is then persisted as if it were a `https://ice2.somafm.com/...` ICE relay URL. The `Player` cannot decode a PLS file as a stream — playback will fail at runtime with an obscure pipeline error.

The docstring says "callers that need [0] continue to work against the fallback-on-error contract" — but no current Phase 74 caller "needs [0]"; the fallback only existed for AA's legacy callers. In the SomaFM path it produces silently broken data.

**Fix:** Change the fallback to `return []` (empty list — no streams for this tier). The caller in `fetch_channels` already has `if not streams: continue` (line 139) so the channel with no recognisable tiers is dropped. See CR-02's deeper fix for `None` vs `[]` semantics.

### WR-04: `_SomaImportWorker.finished` shadows `QThread.finished` — latent slot-arity TypeError eats the toast

**File:** `musicstreamer/ui_qt/main_window.py:159`
**Issue:** Already covered structurally in CR-02 part (3). Filed as its own warning so the fix can be applied in isolation if CR-02 part 1+2 are deferred. The PySide6 idiom for "I want a worker thread with a typed completion signal" is to declare a NEW signal name, not to redeclare `finished`. Same warning applies to `_GbsImportWorker.finished` (line 132) and any other `QThread` subclass in this file that re-declares `finished`.

**Fix:** Rename to `import_finished`. See CR-02 fix snippet.

### WR-05: `_on_soma_import_clicked` does not disable the menu action while the import runs — double-click spawns parallel workers

**File:** `musicstreamer/ui_qt/main_window.py:1502-1508`
**Issue:** A user who double-clicks "Import SomaFM" gets two `_SomaImportWorker` instances started in sequence. Both call `Repo(db_connect())` from their respective threads, both run `fetch_channels()` (~30 s of network), and both attempt to import. The second one's `station_exists_by_url` checks will see the first's inserts (race-dependent), so most channels are skipped, but logo downloads happen TWICE for any channel the second one observes as "newly inserted between its existence-check and its `insert_station` call". And `self._soma_import_worker = _SomaImportWorker(...)` overwrites the reference to the first worker — the first becomes orphaned (still parented to MainWindow so it survives, but the `_on_soma_import_done` for it will set `self._soma_import_worker = None` while the second is still running, defeating the SYNC-05 retention rationale).

The GBS analog has the same bug (`_on_gbs_add_clicked`).

**Fix:** Disable the menu action while a worker is in flight, and re-enable in both `_on_soma_import_done` and `_on_soma_import_error`. Or guard with `if self._soma_import_worker is not None: return` at the top of `_on_soma_import_clicked` (and show a "import already running" toast).

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

## Info

### IN-01: `_SomaImportWorker.__init__` is a no-op forward — drop it

**File:** `musicstreamer/ui_qt/main_window.py:162-163`
**Issue:** `def __init__(self, parent=None): super().__init__(parent)` adds zero behaviour over `QThread.__init__`. It's also misleading because Python tooling (mypy / pyright) will flag it as override-without-effect. The `_GbsImportWorker` has the same redundant override (line 135-136).

**Fix:** Delete the `__init__` block entirely; PySide6 / `QThread` accept `_SomaImportWorker(parent=self)` natively.

### IN-02: `urllib.error` import is unused

**File:** `musicstreamer/soma_import.py:25`
**Issue:** `import urllib.error` is imported but never referenced. The error handling uses bare `except Exception:` everywhere. (This module differs from `aa_import.py` which DOES use `urllib.error.HTTPError` for the 401/403 invalid-key path.)

**Fix:** Remove the import line, or use it in `_resolve_pls` / `_download_logo` to distinguish HTTP errors from other failures (would also satisfy WR-01's diagnostic-line goal).

### IN-03: `_TIER_BY_FORMAT_QUALITY` codec annotation drift — `aacp` is HE-AAC v1 (or v2), not vanilla AAC

**File:** `musicstreamer/soma_import.py:62-67`
**Issue:** The comment block correctly notes "Codec for 'aacp' (HE-AAC) is 'AAC' — Phase 69 WIN-05 verified it decodes via aacparse + avdec_aac chain. 'AAC+' is intentionally absent (SOMA-15 / T-74-02)." But this means the `codec` field in the DB carries "AAC" for both true LC-AAC streams AND HE-AAC v1/v2 streams. Any future UI that displays "Codec: AAC" misleads the user. Not a runtime bug today, but a known truthiness gap.

**Fix:** No code change required; document the limitation in the SUMMARY for Phase 74 and add a TODO for a future `codec_subtype` field. If a code change is desired, change the `codec` literal to `"HE-AAC"` for the `aacp` tiers and verify the player's codec-routing tolerates the new label (Phase 69 WIN-05 may need re-verification).

---

_Reviewed: 2026-05-14T13:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

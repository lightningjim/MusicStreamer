---
phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-
reviewed: 2026-05-14T01:51:56Z
fixed: 2026-05-14T03:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - musicstreamer/cover_art.py
  - musicstreamer/cover_art_mb.py
  - musicstreamer/models.py
  - musicstreamer/repo.py
  - musicstreamer/settings_export.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/test_cover_art.py
  - tests/test_cover_art_mb.py
  - tests/test_cover_art_routing.py
  - tests/test_edit_station_dialog.py
  - tests/test_now_playing_panel.py
  - tests/test_repo.py
  - tests/test_settings_export.py
  - tests/fixtures/mb_recording_search_503_body.json
  - tests/fixtures/mb_recording_search_bootleg_only.json
  - tests/fixtures/mb_recording_search_clean_album_hit.json
  - tests/fixtures/mb_recording_search_no_tags.json
  - tests/fixtures/mb_recording_search_score_79.json
  - tests/fixtures/mb_recording_search_score_85.json
findings:
  critical: 0
  warning: 4
  info: 8
  total: 12
fix_results:
  fixed: 7
  skipped: 5
  attempted_reverted: 0
status: fixes_applied
---

# Phase 73: Code Review Report

**Reviewed:** 2026-05-14T01:51:56Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 73 adds MusicBrainz + Cover Art Archive as a per-station, additive cover-art source complementing iTunes. The implementation is generally tight: the locked decisions D-01..D-20 are honored, the documented threat-model mitigations (T-73-01 Lucene injection, T-73-05 timeout, T-73-06 UA literal) are present and unit-tested, and the cross-file contract between Plan 03 (router) and Plan 04 (dialog + panel) is enforced by source-grep gates.

The most material finding is a worker-thread wedge risk (WR-01): if anything escapes `_run_one_job` before `_worker` re-enters the inflight-lock, the `_in_flight` flag is never cleared and the MB pipeline becomes permanently inert until process restart. Two other warnings concern silent kwarg-default writes that could re-bite Phase 73 from unintended callers (WR-02), and a stored-but-unvalidated `cover_art_source` value at the repo layer (WR-03) that diverges from the `Literal` type hint on the dataclass. Info-level items are mostly hygiene (unused import, unused fixture, two redundant in-worker imports) plus minor robustness suggestions.

No security regressions. No D-04 (MB-only-never-calls-iTunes) violations. No User-Agent leaks of the email contact form. CAA URL correctly pinned to `/front-250`. Lucene escape is correct including the two-char `&&`/`||` operator handling.

## Warnings

### WR-01: `_in_flight` flag can become permanently stuck on unhandled worker exception

**File:** `musicstreamer/cover_art_mb.py:372-397`
**Issue:** `_worker` runs `_run_one_job(job)` BEFORE entering the `_inflight_lock` to clear `_in_flight`. `_run_one_job` has a defensive bare `except Exception`, but any exception from logging itself (e.g., `_log.warning("MB worker failed: %r %r", artist, title, exc_info=True)` — the format spec evaluates `repr(artist)` which is safe for str but not for arbitrary objects if the job tuple is later widened), or any exception raised between `_run_one_job` returning and the worker re-entering the lock (none today, but the surface is unprotected), would escape the worker thread WITHOUT clearing the flag. From that point on, every `fetch_mb_cover` submission sees `_in_flight=True`, drops jobs into `_pending`, and never spawns a new worker — the MB pipeline is permanently inert for the rest of the process lifetime. D-20 says the worker never raises out; honoring that in spirit means also guaranteeing the in-flight flag is always cleared on worker exit, not just on the happy path.
**Fix:** Wrap the loop in a `try/finally` that guarantees the flag is cleared on any exit path:
```python
def _worker(initial_job: tuple) -> None:
    global _in_flight
    job = initial_job
    try:
        while True:
            _run_one_job(job)
            with _inflight_lock:
                try:
                    job = _pending.get_nowait()
                    continue
                except queue.Empty:
                    _in_flight = False
                    return
    except BaseException:
        # Defense-in-depth: never leave the in-flight flag stuck.
        with _inflight_lock:
            _in_flight = False
        _log.warning("MB worker exited unexpectedly", exc_info=True)
        raise  # let daemon-thread default handler log it; flag now clear
```

**Status:** Fixed in daa7329

### WR-02: `repo.update_station` silently writes `cover_art_source='auto'` when kwarg omitted; only one in-tree caller is gated

**File:** `musicstreamer/repo.py:380-413`
**Issue:** The keyword-default design (`cover_art_source: str = "auto"`) means *every* `update_station` call that omits the kwarg resets the user's per-station preference to "auto". This is intentional per Plan 03 — locked by `test_update_station_omitting_cover_art_source_resets_to_auto` — and `test_every_update_station_call_passes_cover_art_source_kwarg` source-greps `edit_station_dialog.py` to catch regressions there. However, that grep is scoped to ONE file. Future callers added elsewhere in the codebase (e.g., a bulk-edit dialog, an import workflow, a debug fixup script) would silently regress every user's preference without a single failing test. Today the only callers are `edit_station_dialog.py:1428` (gated) and `tests/test_repo.py` (intentional). The contract relies on convention, not enforcement.
**Fix:** Make the grep apply across the entire `musicstreamer/` package, or — preferable — drop the default and require `cover_art_source` as a positional/required arg so omitting it is a `TypeError` at import time, not a silent data loss at save time:
```python
def update_station(
    self, station_id, name, provider_id, tags,
    station_art_path, album_fallback_path,
    icy_disabled,
    cover_art_source,  # required, no default
):
```
Or, if the keyword-default ergonomic must stay, broaden the source-grep test to scan every `*.py` under `musicstreamer/` (`importlib.resources.files("musicstreamer")` + recursive walk) so the gate covers the whole package, not just `edit_station_dialog.py`.

**Status:** Fixed in aa09650 (broadened source-grep test; kept keyword-default for backward compat with the locked test_update_station_omitting_cover_art_source_resets_to_auto contract).

### WR-03: `cover_art_source` value is not validated at the repo write boundary

**File:** `musicstreamer/repo.py:380-413` and `musicstreamer/models.py:36`
**Issue:** `Station.cover_art_source` is typed `Literal["auto", "itunes_only", "mb_only"]`, but `repo.update_station` accepts `cover_art_source: str = "auto"` — no runtime validation. A caller passing `"itunes-only"` (hyphen instead of underscore), `"ITunes_Only"` (wrong case), or any other typo persists silently. The router (`cover_art.py:200-204`) defends against unknown values at the consumer side by falling back to "auto" with a warning, but the stored DB value remains the typo'd string forever — `get_station` returns it verbatim and the dialog's `setCurrentIndex` loop on line 552-556 falls through without matching any entry, leaving the combo at index 0 (which happens to be "auto"), making the user think their preference is auto when it's actually an unparseable string. Surfaces as a bug only when a future feature (e.g., a settings-validation routine, a CSV export) tries to interpret the field.
**Fix:** Validate at the write boundary:
```python
_VALID_COVER_ART_SOURCES = {"auto", "itunes_only", "mb_only"}

def update_station(self, ..., cover_art_source="auto"):
    if cover_art_source not in _VALID_COVER_ART_SOURCES:
        # Either raise, or coerce + log.
        raise ValueError(
            f"cover_art_source must be one of {_VALID_COVER_ART_SOURCES}; "
            f"got {cover_art_source!r}"
        )
    ...
```
Apply the same check in `settings_export._insert_station` and `_replace_station` so a malformed ZIP cannot inject a bad value.

**Status:** Fixed in e468ef8 (repo raises ValueError; settings_export coerces unknown values to 'auto' so a malformed ZIP cannot abort the entire import).

### WR-04: Auto-mode chains iTunes worker into MB on miss without checking that the iTunes worker actually ran the search

**File:** `musicstreamer/cover_art.py:212-226`
**Issue:** `_on_itunes_done` is the iTunes worker's `on_done` continuation. The router treats `path_or_none is None` as "iTunes missed → try MB". But the iTunes worker also delivers `None` on:
  - JSON parse failure (truncated payload, malformed response)
  - Network error / timeout
  - Tempfile write failure (disk-full)
  - Any other exception caught by the bare `except` on cover_art.py:125

In all those non-miss failure cases, Auto mode now silently falls through to a SECOND network call (MB), doubling the request load on every transient iTunes failure. iTunes hit-rate is high enough that this is mostly latent, but: (a) a flaky network burns 2× the requests, (b) every iTunes 503 (rate-limit, outage) triggers an MB call that wouldn't be needed if iTunes succeeded normally, (c) for stations explicitly configured `source='auto'` precisely because iTunes works well, a transient iTunes outage now hits MB's 1-req/sec gate, queueing all subsequent fetches behind the wasted MB call. The current router can't distinguish "iTunes searched and found nothing" from "iTunes failed to run." D-02 doesn't strictly forbid the fallthrough on failure, but the spirit ("MB fallback on miss") differs from the implementation ("MB fallback on any non-success").
**Fix:** Distinguish iTunes-miss from iTunes-error by having `_itunes_attempt` pass an explicit sentinel:
```python
ITUNES_MISS = object()  # genuine "no results"
ITUNES_ERROR = object()  # network/parse/disk failure

def _itunes_attempt(icy, on_done):
    def _worker():
        try:
            ...
            if artwork_url is None:
                on_done(ITUNES_MISS)
                return
            ...
            on_done(temp_path)
        except Exception:
            on_done(ITUNES_ERROR)
    ...
```
Then `_on_itunes_done` falls through to MB only on `ITUNES_MISS`, calls `callback(None)` on `ITUNES_ERROR`. (Or keep current behavior but document it explicitly as a design choice in the Plan 03 SUMMARY so a future maintainer doesn't tighten this and break the latent fail-open.)

**Status:** Skipped (design choice aligned with strict D-02 reading: "If iTunes returns no result … try MB" — an error counts as no result. Introducing an ITUNES_MISS / ITUNES_ERROR sentinel would split the auto-mode fall-open behavior and require updates to both Plan 03 SUMMARY and existing tests. Defer to a future phase if the 2× request load becomes user-visible.)

## Info

### IN-01: Unused import `urllib.error` in `cover_art_mb.py`

**File:** `musicstreamer/cover_art_mb.py:59`
**Issue:** `import urllib.error` is present but no code path references `urllib.error.HTTPError` or anything from that namespace (the `except Exception` catches HTTPError as a base-class-of-OSError catch). Test file uses it (raises `HTTPError` in mock); module file doesn't.
**Fix:** Remove the unused import. If the intent was to keep it as documentation that 503/429 are anticipated, replace with a comment.

**Status:** Fixed in 6da6ba1

### IN-02: Unused test fixture `mb_recording_search_503_body.json`

**File:** `tests/fixtures/mb_recording_search_503_body.json`
**Issue:** The fixture exists in the repo but no test imports or loads it. The 503 test (`test_mb_503_falls_through_to_callback_none`) raises an `HTTPError` directly via `urllib.error.HTTPError(...)` — it does not read this fixture body. The fixture is dead weight; either delete it or wire it into the 503 test.
**Fix:** Either delete the fixture file or use it in the 503 test:
```python
def fake_urlopen_503(req, timeout=None):
    body = (FIXTURES_DIR / "mb_recording_search_503_body.json").read_bytes()
    raise urllib.error.HTTPError(url=..., code=503, msg="Service Unavailable",
                                  hdrs=None, fp=io.BytesIO(body))
```

**Status:** Skipped (review presents two equally-valid options — delete or wire. Neither is unambiguously better, and the 503 test currently constructs its own HTTPError without consuming a body. Leaving the fixture as documentation of the expected payload shape.)

### IN-03: Two redundant in-function imports of `musicstreamer.cover_art`

**File:** `musicstreamer/cover_art.py:109` and `musicstreamer/cover_art_mb.py:355`
**Issue:** Both worker bodies do an `import musicstreamer.cover_art as _self_module` / `as _cover_art_module` inside the function to obtain the module object for `last_itunes_result` write. The comment explains why (mutate the module attribute, not a local binding) — but the import is repeated on every worker invocation. Since `cover_art.py` is already loaded by the time any worker runs, this works but is unnecessary churn through `sys.modules` lookup on every call. The cleaner idiom is `import musicstreamer.cover_art as _self_module` at module level (or in `cover_art_mb.py` use a deferred reference via `sys.modules["musicstreamer.cover_art"]` once), but the inline import does avoid the circular-import problem at module load. Trade-off accepted; documenting only.
**Fix:** No action required. Optionally, hoist to a module-level lazy property or add a once-per-process cache.

**Status:** Skipped (review explicitly says "No action required.")

### IN-04: `last_itunes_result` is a module-level mutable dict with no concurrency guard

**File:** `musicstreamer/cover_art.py:61` and `musicstreamer/cover_art_mb.py:357-360`
**Issue:** Multiple fetch operations can in principle race on `last_itunes_result` writes. The MB-side has a 1-req/sec gate and single-slot queue, so MB cannot race against itself. iTunes-side spawns a fresh daemon thread per call with no gate — back-to-back station switches could fly two iTunes workers in parallel, racing on `last_itunes_result`. Read-side is the Favorites flow (genre column at favorite-add time) which only fires on user action. Pre-existing condition not introduced by Phase 73, but expanded surface (MB writes are new). Worth noting because the genre-handoff channel is the documented D-15 contract and racy writes can cause genre mismatch on the next favorite-add.
**Fix:** Wrap writes in a `threading.Lock`, or change the data flow to thread the genre alongside the path through the callback rather than via a module global.

**Status:** Skipped (pre-existing concurrency surface, not introduced by Phase 73. Adding a lock or rethreading the genre channel through callbacks would require new abstractions and touch D-15 contracts. Defer to a dedicated concurrency-hardening phase.)

### IN-05: `_USER_AGENT` computed at import time can fail entire module load

**File:** `musicstreamer/cover_art_mb.py:72-75`
**Issue:** `_pkg_version('musicstreamer')` is called at module import; if the package is not installed (e.g., raw-source deployment, broken egg-info, PyInstaller frozen bundle with stripped metadata), `PackageNotFoundError` propagates out of the import and prevents `musicstreamer.cover_art_mb` from loading at all, which in turn breaks `cover_art.py` (because it eagerly imports `cover_art_mb`). The same pattern exists in `__main__.py`, so this is an accepted project convention — but on the cover-art path the failure mode is worse: the entire cover-art feature becomes unreachable rather than degrading to a missing version string.
**Fix:** Wrap the version lookup defensively:
```python
try:
    _MS_VERSION = _pkg_version("musicstreamer")
except Exception:
    _MS_VERSION = "0.0.0"
_USER_AGENT = f"MusicStreamer/{_MS_VERSION} (https://github.com/lightningjim/MusicStreamer)"
```

**Status:** Fixed in a64309a

### IN-06: `_genre_from_tags` may raise on malformed MB payload with `count=None`

**File:** `musicstreamer/cover_art_mb.py:230`
**Issue:** `key=lambda t: (-int(t.get("count", 0)), t.get("name", ""))` — `t.get("count", 0)` returns `0` if the key is missing, but returns `None` if the key is present with explicit-null value (which MB does NOT produce in practice, but the parser does no schema-validation). `int(None)` raises `TypeError`. The exception is caught by `_run_one_job`'s bare `except` and degrades to `callback(None)`, so D-20 is honored — but the user silently loses the genre and the cover image both, when only the genre lookup was malformed. The release-selection ladder ran successfully and would have produced a valid image.
**Fix:** Coerce defensively:
```python
key=lambda t: (-int(t.get("count") or 0), t.get("name") or "")
```
Apply the same to `_pick_recording`'s `(r.get("score") or 0) >= 80` (already done — good — so the pattern is established; just propagate to tags).

**Status:** Fixed in d486359

### IN-07: `release_mbid` is interpolated into the CAA URL without UUID-shape validation

**File:** `musicstreamer/cover_art_mb.py:268` and `:356`
**Issue:** `release_mbid` comes from MB JSON — `r["id"]` — and is f-stringed directly into the CAA URL. MBIDs are UUIDs in practice, but a malicious or corrupted MB response (extremely unlikely over HTTPS) containing path separators like `../../../foo` would synthesize a URL `https://coverartarchive.org/release/../../../foo/front-250` that `urlopen` resolves server-side. CAA would return 404 in practice, so impact is bounded; still, a defensive UUID-shape check before fetching costs nothing and would also catch any future bug that mis-populates `release_mbid` from the wrong JSON path.
**Fix:** Validate before use:
```python
import re
_UUID_RE = re.compile(r"^[0-9a-f-]{36}$", re.IGNORECASE)

def _pick_release_mbid(...) -> Optional[str]:
    ...
    candidate_id = candidates[0]["id"]
    if not _UUID_RE.match(candidate_id):
        return None
    return candidate_id
```

**Status:** Fixed in 2f86c90 (regex applied to BOTH D-10 ladder steps via helper).

### IN-08: `is_junk_title` list does not cover common ad markers

**File:** `musicstreamer/cover_art.py:32-43`
**Issue:** `JUNK_TITLES` covers `""`, `"advertisement"`, `"advert"`, `"commercial"`, `"commercial break"`. Real-world streams also produce: `"unknown"`, `"radio break"`, `"station id"`, `"sweeper"`, `"underwriting"`, `"ad break"`. None of these will trigger the gate today, so MB+CAA gets queried for "Unknown - Unknown" and similar. Pre-existing scope but worth flagging since Phase 73 now spends an MB rate-gate slot on each such call. Not a regression, just a place where the existing junk list is thin.
**Fix:** Extend the set if there's user demand; otherwise document the scope. No action required for ship.

**Status:** Skipped (review explicitly says "No action required for ship.")

---

_Reviewed: 2026-05-14T01:51:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

_Fixes applied: 2026-05-14_
_Fixer: Claude Opus 4.7 (1M context)_
_Fix scope: --fix --all_
_Result: 7 fixed (WR-01, WR-02, WR-03, IN-01, IN-05, IN-06, IN-07); 5 skipped (WR-04, IN-02, IN-03, IN-04, IN-08)_

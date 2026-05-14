"""Cover art fetching via MusicBrainz + Cover Art Archive (D-07..D-20).

This module is the bulk of Phase 73's new code. It exposes a single public
entry point — `fetch_mb_cover(artist, title, callback)` — that orchestrates a
two-leg HTTP pipeline:

    1. MusicBrainz recording search (rate-gated to 1 req/sec per D-13/D-14/D-19).
    2. Cover Art Archive front-250 image fetch (NOT rate-gated, per D-19).

Architecture (see RESEARCH §"Architecture Patterns" diagram):

    fetch_mb_cover(artist, title, cb)
        |
        v
    [_pending queue, maxsize=1, latest-wins per D-13]
        |
        v
    _spawn_worker(target=_worker, args=(job,))   # pinned test seam (ART-MB-06)
        |
        v
    _worker(job)
        - _GATE.wait_then_mark()  # 1-req/sec floor on MB API only
        - _do_mb_search(artist, title) -> dict | None
        - _pick_recording(data)            # score >= 80 + earliest-first (Pitfall 1)
        - _pick_release_mbid(recording)    # D-10 ladder, steps 1+2 only (step 3 deferred)
        - _fetch_caa_image(release_mbid)   # bytes | None
        - tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        - musicstreamer.cover_art.last_itunes_result = {artwork_url, genre}
        - callback(temp_path)

Locked decisions referenced here:
    - D-07: caller responsible for ' - ' split (this module's fetch_mb_cover
      short-circuits to callback(None) when title is bare).
    - D-09: MB score >= 80 acceptance.
    - D-10 (revised 2026-05-13): release ladder steps 1+2 only;
      step 3 (CAA-art existence probe) deferred per RESEARCH OQ-1 RESOLVED.
    - D-11: CAA endpoint /front-250 (smallest variant for 160x160 slot @ DPR=1.0).
    - D-12: NO caching. Each call hits the network.
    - D-13: latest-wins single-slot queue; max 1 in-flight + 1 queued.
    - D-14: rate gate uses time.monotonic floor (see _MbGate below).
    - D-15: highest-count MB tag wins; '' on no tags (Pitfall 3).
    - D-16: NO iTunes call from this module under any circumstance.
    - D-18: User-Agent literal `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)`.
    - D-19: 1-req/sec gate applies to MB API only, not CAA.
    - D-20: bare `except Exception` in worker -> callback(None); never raise out.

Threading note (RESEARCH Pitfall 5): the worker is a raw `threading.Thread`,
NOT a `QThread`. Cross-thread delivery to Qt happens at the caller via a
queued Signal (now_playing_panel.cover_art_ready). This module does NOT
import Qt and MUST NOT call QTimer.singleShot — that silently drops on
non-QThread threads.
"""
import json
import logging
import queue
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from importlib.metadata import version as _pkg_version
from typing import Callable, Optional

_log = logging.getLogger(__name__)


# D-18 (locked): UA literal MUST contain "MusicStreamer/" and the GitHub URL.
# ART-MB-15 source-grep gate asserts both substrings are present in this file.
# VER-02 convention: pull the version via importlib.metadata (auto-bumps via
# phase-complete hook). Do NOT hardcode the version literal like gbs_api.py:77.
# IN-05: tolerate PackageNotFoundError so a raw-source / stripped-metadata
# deployment cannot prevent the cover_art_mb module from importing — which
# would in turn break cover_art.py (it eagerly imports cover_art_mb) and
# render the entire cover-art feature unreachable.
try:
    _MS_VERSION = _pkg_version("musicstreamer")
except Exception:
    _MS_VERSION = "0.0.0"
_USER_AGENT = (
    f"MusicStreamer/{_MS_VERSION} "
    f"(https://github.com/lightningjim/MusicStreamer)"
)

# RESEARCH Pitfall 10: Lucene special chars. We escape these with a single-pass
# iteration; two-char operators (&&, ||) are handled before single-char checks.
LUCENE_SPECIAL_CHARS: str = '+-!(){}[]^"~*?:\\/'


def _escape_lucene(s: str) -> str:
    """Escape Lucene query syntax special characters with a backslash prefix.

    Special chars per Lucene 4.x docs: + - && || ! ( ) { } [ ] ^ " ~ * ? : \\ /
    Single-pass iteration avoids the double-escape trap (Pitfall 10) that bites
    naive two-pass `.replace()` solutions (\\ inserted in pass 1 gets re-escaped
    in pass 2).

    Mitigates T-73-01 (Lucene injection from untrusted ICY metadata).
    """
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        # Two-char operators first.
        if ch == "&" and i + 1 < n and s[i + 1] == "&":
            out.append("\\&\\&")
            i += 2
            continue
        if ch == "|" and i + 1 < n and s[i + 1] == "|":
            out.append("\\|\\|")
            i += 2
            continue
        if ch in LUCENE_SPECIAL_CHARS:
            out.append("\\" + ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _build_mb_query(artist: str, title: str) -> str:
    """Compose the MB recording-search URL for (artist, title).

    Returns the full URL. Per RESEARCH OQ-4 RESOLVED: limit=10 — larger than
    D-08's 5 to catch canonical-album hits beyond the top-5 noise band; smaller
    than 25 to keep payload manageable.
    """
    artist_esc = _escape_lucene(artist)
    title_esc = _escape_lucene(title)
    q = f'artist:"{artist_esc}" AND recording:"{title_esc}"'
    return (
        f"https://musicbrainz.org/ws/2/recording/?query="
        f"{urllib.parse.quote(q, safe='')}&fmt=json&limit=10"
    )


class _MbGate:
    """1-req/sec gate for musicbrainz.org/ws/2/* (D-13, D-14, D-19).

    Holds a `_next_allowed_at` floor measured against time.monotonic(). Each
    `wait_then_mark()` call sleeps until the floor is reached, then advances
    the floor by 1.0 seconds.

    Note: time.sleep is called under the lock. This is acceptable here because
    (a) sleeps are bounded by 1 second, (b) the worker is a daemon thread that
    exits on interpreter shutdown, and (c) the alternative (drop the lock to
    sleep) opens a race where two callers both read the same _next_allowed_at
    and both proceed. The RESEARCH §"Anti-Patterns" entry calls this out
    explicitly as the right tradeoff for a 1-second gate.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0  # time.monotonic() floor

    def wait_then_mark(self) -> None:
        """Block until the gate is open, then push the floor 1.0s into the future."""
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed_at:
                time.sleep(self._next_allowed_at - now)
            self._next_allowed_at = time.monotonic() + 1.0


# Module-level singleton — shared across all fetch_mb_cover calls so the
# 1-req/sec gate survives station changes (RESEARCH "Alternatives Considered":
# per-request threading cannot share _next_allowed_at cleanly).
_GATE = _MbGate()


def _pick_recording(data: dict) -> Optional[dict]:
    """Pick the canonical recording from an MB search response.

    D-09: filter score >= 80. RESEARCH Pitfall 1: top-5 may all have score=100
    but contain bootlegs; sort by first-release-date ascending so the earliest
    (= canonical) release wins. Pitfall 2: `first-release-date` may be None,
    '', 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD' — sort with `... or "9999"` sentinel.

    Returns the first accepted recording dict, or None on total miss.
    """
    recordings = data.get("recordings", []) or []
    accepted = [r for r in recordings if (r.get("score") or 0) >= 80]
    if not accepted:
        return None
    accepted.sort(key=lambda r: r.get("first-release-date") or "9999")
    return accepted[0]


def _pick_release_mbid(recording: dict) -> Optional[str]:
    """Pick a release MBID from a recording's releases[] per D-10 ladder.

    D-10 (revised 2026-05-13) implements steps 1+2 only. Step 3 (any release
    with CAA art on HEAD probe) is DEFERRED per RESEARCH OQ-1 RESOLVED.

    Step 1: status == "Official" AND release-group.primary-type == "Album",
            earliest `date` first.
    Step 2: any status == "Official", earliest `date` first.
    Else:   None.

    Pitfall 2: `date` may be None/''/'YYYY'/'YYYY-MM'/'YYYY-MM-DD' — sort
    using `... or "9999"` sentinel.
    """
    releases = recording.get("releases", []) or []

    # Step 1: Official + Album, earliest date.
    candidates = [
        r for r in releases
        if r.get("status") == "Official"
        and (r.get("release-group") or {}).get("primary-type") == "Album"
    ]
    candidates.sort(key=lambda r: r.get("date") or "9999")
    if candidates:
        return candidates[0]["id"]

    # Step 2: any Official, earliest date.
    candidates = [r for r in releases if r.get("status") == "Official"]
    candidates.sort(key=lambda r: r.get("date") or "9999")
    if candidates:
        return candidates[0]["id"]

    # Step 3 deferred — return None on total miss.
    return None


def _genre_from_tags(recording: dict) -> str:
    """Return the highest-count tag name from a recording, or '' on no tags.

    D-15: highest-count tag wins; stable sort by name for determinism on ties.
    Pitfall 3: `tags` key may be entirely absent (not just empty) — handled by
    `.get("tags") or []`.
    """
    tags = recording.get("tags") or []
    if not tags:
        return ""
    tags_sorted = sorted(
        tags,
        key=lambda t: (-int(t.get("count", 0)), t.get("name", "")),
    )
    return tags_sorted[0].get("name", "")


def _do_mb_search(artist: str, title: str) -> Optional[dict]:
    """Single MB API call. Returns parsed JSON dict, or None on any failure.

    Calls `_GATE.wait_then_mark()` FIRST to honor the 1-req/sec gate (D-19:
    applies to MB API only). On any exception (network error, HTTPError 503/429,
    JSON parse error, anything) — log at WARNING and return None (D-20).

    %r format specifier preserves quote canary on ICY-echoed strings — matches
    Phase 62 T-62-01 mitigation.
    """
    _GATE.wait_then_mark()
    url = _build_mb_query(artist, title)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = resp.read()
        return json.loads(payload)
    except Exception:
        _log.warning("MB search failed: %r %r", artist, title, exc_info=True)
        return None


def _fetch_caa_image(release_mbid: str) -> Optional[bytes]:
    """Single CAA GET. Returns image bytes, or None on any failure.

    D-11: front-250 variant (smallest variant that scales cleanly to 160x160
    on DPR=1.0 Wayland — assumption A1 in RESEARCH).
    D-19: NO gate call here — only the MB API is rate-gated.
    D-18: User-Agent literal applied to BOTH MB API and CAA requests.

    urllib follows the 307 redirect from CAA to archive.org transparently
    (verified live 2026-05-13; RESEARCH Pitfall 4).
    """
    url = f"https://coverartarchive.org/release/{release_mbid}/front-250"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read()
    except Exception:
        _log.warning("CAA fetch failed: %r", release_mbid, exc_info=True)
        return None


# Latest-wins single-slot queue (D-13, RESEARCH Pattern 2).
# The queue holds at most ONE PENDING job. The `_in_flight` flag guards
# against spawning duplicate workers — if a worker is already running, new
# submissions only update the pending slot, and the in-flight worker will
# drain it after its current call completes. This delivers D-13's
# "max 1 in-flight + 1 queued" with NO wasted spawns under rapid bursts.
_pending: queue.Queue = queue.Queue(maxsize=1)
_inflight_lock = threading.Lock()
_in_flight = False  # True while a worker thread is processing (or about to)


def _reset_queue_for_tests() -> None:
    """Drain `_pending` AND reset the in-flight flag so tests start fresh.

    Test-only helper. Plan 02 Task 1 step 15 exposes this for ART-MB-06.
    """
    global _in_flight
    try:
        while True:
            _pending.get_nowait()
    except queue.Empty:
        pass
    with _inflight_lock:
        _in_flight = False


# Last-spawned-thread handle, exposed for failure-path tests that need to join
# the worker before asserting on the callback. Production code does NOT read
# this. The token-guard at the Qt slot is the production sync mechanism.
_last_thread: Optional[threading.Thread] = None


def _spawn_worker(target: Callable, args: tuple) -> None:
    """Single call site for daemon-thread creation — seam Plan 01 RED scaffold monkeypatches for ART-MB-06.

    The latest-wins enqueue path in `fetch_mb_cover` MUST route through this
    function and MUST NOT create+start a thread inline anywhere else in the
    module. This guarantees the test scaffold's monkeypatch fully neutralizes
    thread spawning.

    See PLAN 73-02 Task 1 step 18 for the pinned contract.
    """
    global _last_thread
    th = threading.Thread(target=target, args=args, daemon=True)
    _last_thread = th
    th.start()


def _run_one_job(job: tuple) -> None:
    """Run a single (artist, title, callback) job through the MB+CAA pipeline.

    Bare `except Exception` ensures D-20 holds: no exception escapes.
    """
    artist, title, callback = job
    try:
        data = _do_mb_search(artist, title)
        if data is None:
            callback(None)
            return
        recording = _pick_recording(data)
        if recording is None:
            callback(None)
            return
        release_mbid = _pick_release_mbid(recording)
        if release_mbid is None:
            callback(None)
            return
        image_bytes = _fetch_caa_image(release_mbid)
        if image_bytes is None:
            callback(None)
            return
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            temp_path = tmp.name
        # D-15 genre handoff: write to cover_art.last_itunes_result. Import the
        # module (not `from ... import last_itunes_result`) so we mutate the
        # module attribute, not a local binding. Matches cover_art.py:82 idiom.
        import musicstreamer.cover_art as _cover_art_module
        caa_url = f"https://coverartarchive.org/release/{release_mbid}/front-250"
        _cover_art_module.last_itunes_result = {
            "artwork_url": caa_url,
            "genre": _genre_from_tags(recording),
        }
        callback(temp_path)
    except Exception:
        # D-20: never raise out of worker; mirrors cover_art.py:98.
        _log.warning("MB worker failed: %r %r", artist, title, exc_info=True)
        try:
            callback(None)
        except Exception:
            # Callback itself raised — swallow to honor the never-raise contract.
            _log.warning("MB worker callback raised", exc_info=True)


def _worker(initial_job: tuple) -> None:
    """Worker thread body — runs the initial job then drains queued successors.

    The worker holds the `_in_flight` flag for its entire lifetime. After
    completing each job, it checks `_pending` for a newer (superseded) job
    and runs it instead of returning. This implements D-13 latest-wins:
    rapid bursts collapse into "first arrival processes; last arrival wins
    the queued slot; everything in between is dropped."

    The flag is cleared atomically when the worker exits, AFTER the final
    queue check shows empty — preventing the lost-wakeup race where a new
    submission arrives between "queue empty" and "flag cleared".

    WR-01 defense-in-depth: the outer try/except guarantees `_in_flight` is
    cleared on ANY exit path, including unexpected exceptions escaping
    `_run_one_job` (which has its own bare-except, but logging or future
    code edits could still raise). Without this finally-style guarantee, a
    stuck `_in_flight=True` would render the MB pipeline permanently inert
    until process restart.
    """
    global _in_flight
    job = initial_job
    try:
        while True:
            _run_one_job(job)
            # Look for a superseded successor under the lock to close the
            # "submitter saw _in_flight=True but worker already finished" race.
            with _inflight_lock:
                try:
                    job = _pending.get_nowait()
                    continue  # drained a superseded job; process it
                except queue.Empty:
                    _in_flight = False
                    return
    except BaseException:
        # WR-01: never leave the in-flight flag stuck if anything escapes
        # the inner loop (D-20 spirit: worker never raises out, but also
        # never wedges the pipeline). Clear the flag, log, and re-raise so
        # the daemon-thread default handler can report it.
        with _inflight_lock:
            _in_flight = False
        _log.warning("MB worker exited unexpectedly", exc_info=True)
        raise


def fetch_mb_cover(
    icy_or_artist: str,
    title_or_callback,
    callback: Optional[Callable[[Optional[str]], None]] = None,
) -> None:
    """Fetch MB+CAA cover for an artist/title pair (D-07..D-20).

    Two call shapes are supported for backward compatibility with the Wave 0
    RED scaffold (which calls `fetch_mb_cover(icy_string, callback)`):

        fetch_mb_cover("Artist - Title", callback)       # legacy/scaffold shape
        fetch_mb_cover("Artist", "Title", callback)      # explicit split shape

    Plan 03 (router) will call the legacy shape with the full ICY string; this
    function does the ' - ' split itself for that case. Bare-title ICY (no
    ' - ') short-circuits to callback(None) per D-07.

    On hit: writes `musicstreamer.cover_art.last_itunes_result = {artwork_url, genre}`
    (D-15 genre handoff channel) and invokes `callback(temp_jpg_path)`.

    On any miss (no recording, no release, CAA 404, network error, HTTP 503,
    JSON parse error, anything): `callback(None)`. Never raises out per D-20.

    Submits via `_pending` (queue.Queue maxsize=1) per D-13 latest-wins —
    superseded queued submissions are dropped before the worker sees them.
    """
    try:
        # Disambiguate call shape.
        if callback is None:
            # Legacy shape: fetch_mb_cover(icy_string, callback)
            icy_string = icy_or_artist
            cb = title_or_callback
            if " - " not in icy_string:
                # D-07: bare-title ICY skips MB entirely.
                cb(None)
                return
            artist, title = icy_string.split(" - ", 1)
        else:
            # Explicit-split shape: fetch_mb_cover(artist, title, callback)
            artist = icy_or_artist
            title = title_or_callback
            cb = callback

        artist = (artist or "").strip()
        title = (title or "").strip()
        if not artist or not title:
            cb(None)
            return

        job = (artist, title, cb)
        # D-13 latest-wins: only spawn a new worker if none is already in flight.
        # The submitter and worker coordinate via _inflight_lock + _pending so
        # rapid bursts collapse to "1 in-flight (running) + 1 queued (the latest)".
        global _in_flight
        with _inflight_lock:
            if _in_flight:
                # A worker is already running — drop any older queued job and
                # leave the new one for the worker to pick up after its current
                # call returns. NO new spawn.
                try:
                    _pending.get_nowait()
                except queue.Empty:
                    pass
                try:
                    _pending.put_nowait(job)
                except queue.Full:
                    pass  # race against worker dequeue; safe to drop
                return
            # No worker in flight — claim the in-flight slot and spawn one.
            _in_flight = True
        # Spawn via the pinned seam — never inline thread creation.
        _spawn_worker(target=_worker, args=(job,))
    except Exception:
        # D-20: never raise out. Best effort callback(None).
        _log.warning("fetch_mb_cover failed pre-spawn", exc_info=True)
        try:
            if callback is not None:
                callback(None)
            elif callable(title_or_callback):
                title_or_callback(None)
        except Exception:
            _log.warning("fetch_mb_cover callback raised", exc_info=True)

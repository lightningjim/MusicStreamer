"""Unit tests for musicstreamer.cover_art_mb module — Wave 0 RED scaffolds.

Plan 73-01 creates this file with xfail-marked tests. Plans 73-02/03/04 flip
them GREEN by landing `musicstreamer.cover_art_mb` and its consumers. The
xfail marks are intentional: pytest must COLLECT these tests now (for
--collect-only gating) but treat the failures as expected until the module
exists.

Coverage:
- ART-MB-01: User-Agent on MB API request (Plan 02)
- ART-MB-02: User-Agent on CAA image request (Plan 02)
- ART-MB-03: 1 req/sec gate with monotonic-floor (Plan 02)
- ART-MB-04: score-threshold acceptance (Plan 02)
- ART-MB-05: Release-selection ladder (Plan 02)
- ART-MB-06: Latest-wins queue (Plan 02)
- ART-MB-13: MB tags -> genre (Plan 02)
- ART-MB-14: HTTP 503 -> callback(None) (Plan 02)
- ART-MB-15: Source-grep gate, UA literal (Plan 02)
- ART-MB-16: Source-grep gate, time.monotonic (Plan 02)
"""
import json
import os
import re
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a JSON fixture from tests/fixtures/."""
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# ART-MB-01: User-Agent header literal on MB API request
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; cover_art_mb module not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_mb_request_carries_user_agent(monkeypatch):
    """ART-MB-01: D-18 User-Agent on MB API request — RESEARCH Pitfall 6 header case."""
    from musicstreamer import cover_art_mb  # noqa: F401 — RED until Plan 02 lands the module

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        resp = MagicMock()
        resp.read.return_value = b'{"recordings": []}'
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp

    monkeypatch.setattr(
        "musicstreamer.cover_art_mb.urllib.request.urlopen", fake_urlopen
    )
    cover_art_mb._do_mb_search("Daft Punk", "One More Time")
    ua = captured["req"].get_header("User-agent")  # Pitfall 6: 'User-agent', not 'User-Agent'
    assert ua is not None
    assert ua.startswith("MusicStreamer/")
    assert "https://github.com/lightningjim/MusicStreamer" in ua


# ---------------------------------------------------------------------------
# ART-MB-02: User-Agent header literal on CAA image request
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; cover_art_mb CAA path not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_caa_request_carries_user_agent(monkeypatch):
    """ART-MB-02: D-18 User-Agent on CAA image request — symmetric with MB API."""
    from musicstreamer import cover_art_mb  # noqa: F401 — RED until Plan 02

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured.setdefault("reqs", []).append(req)
        resp = MagicMock()
        # CAA returns the image bytes (or a redirect followed transparently by urllib)
        resp.read.return_value = b"fake_jpeg_bytes"
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp

    monkeypatch.setattr(
        "musicstreamer.cover_art_mb.urllib.request.urlopen", fake_urlopen
    )
    cover_art_mb._fetch_caa_image("b9ddde22-fca3-4d94-aee9-f964b34166ce")
    # Assert at least the CAA request carries the UA
    caa_reqs = [r for r in captured["reqs"] if "coverartarchive.org" in r.full_url]
    assert caa_reqs, "Expected at least one CAA request"
    ua = caa_reqs[0].get_header("User-agent")
    assert ua is not None
    assert ua.startswith("MusicStreamer/")
    assert "https://github.com/lightningjim/MusicStreamer" in ua


# ---------------------------------------------------------------------------
# ART-MB-03: 1 req/sec gate with monotonic-floor
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; _MbGate not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_mb_gate_serializes_with_1s_floor(monkeypatch):
    """ART-MB-03: D-14 rate gate — 5 sequential MB calls must space ≥ 1s apart.

    Strategy: deterministic clock via monkeypatched time.monotonic + recorded
    time.sleep durations. Mirrors Phase 62 _BufferUnderrunTracker test pattern.
    """
    from musicstreamer import cover_art_mb  # RED until Plan 02

    fake_now = [0.0]
    sleeps: list = []
    monkeypatch.setattr(cover_art_mb.time, "monotonic", lambda: fake_now[0])
    monkeypatch.setattr(cover_art_mb.time, "sleep", lambda s: sleeps.append(s))

    gate = cover_art_mb._MbGate()
    gate.wait_then_mark()
    fake_now[0] = 0.3  # second call only 0.3s after first
    gate.wait_then_mark()

    # First call: no wait (now=0, next_allowed=0). Second call: sleep 0.7 to reach 1.0.
    assert sleeps == [pytest.approx(0.7)]


# ---------------------------------------------------------------------------
# ART-MB-04: Score threshold — reject < 80, accept >= 80, bare-title short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; _pick_recording not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_score_threshold_rejects_below_80_accepts_at_or_above_80():
    """ART-MB-04: D-09 score >= 80 acceptance, plus D-07 bare-title short-circuit.

    Cases:
      - score=79 fixture → rejected (returns None)
      - score=85 fixture → accepted (returns the recording dict)
      - bare-title ICY "Just A Title" (no " - ") → never even queries MB
    """
    from musicstreamer import cover_art_mb  # RED until Plan 02

    score_79 = _load_fixture("mb_recording_search_score_79.json")
    score_85 = _load_fixture("mb_recording_search_score_85.json")

    assert cover_art_mb._pick_recording(score_79) is None, (
        "D-09: score=79 must be rejected"
    )
    accepted = cover_art_mb._pick_recording(score_85)
    assert accepted is not None
    assert accepted["id"] == "85858585-8585-8585-8585-858585858585"

    # D-07: bare-title ICY (no ' - ') must short-circuit before any MB call.
    # The exact API for this short-circuit is Plan 02's design; expected shape
    # is fetch_mb_cover("Just A Title", cb) → cb invoked with None synchronously
    # (or the helper returns a sentinel — Plan 02 picks).
    cb_calls: list = []
    cover_art_mb.fetch_mb_cover("Just A Title", lambda p: cb_calls.append(p))
    assert cb_calls == [None], "D-07: bare-title ICY must short-circuit to callback(None)"


# ---------------------------------------------------------------------------
# ART-MB-05: Release-selection ladder picks Official+Album over Bootleg
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; _pick_release_mbid not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_release_selection_ladder_picks_official_album_over_bootleg():
    """ART-MB-05: D-10 release-selection ladder.

    - bootleg_only fixture (all Bootleg/Promotion, no Official+Album) → None
    - clean_album_hit fixture → the Daft Punk MBID b9ddde22-...
    """
    from musicstreamer import cover_art_mb  # RED until Plan 02

    bootleg_only = _load_fixture("mb_recording_search_bootleg_only.json")
    clean_hit = _load_fixture("mb_recording_search_clean_album_hit.json")

    # Pitfall 1: top-5 Bootlegs with score=100 must be rejected by the ladder.
    bootleg_rec = bootleg_only["recordings"][0]
    assert cover_art_mb._pick_release_mbid(bootleg_rec) is None, (
        "D-10: no Official+Album in bootleg-only releases"
    )

    # Daft Punk shape — Official + Album → release MBID picked.
    clean_rec = clean_hit["recordings"][0]
    assert (
        cover_art_mb._pick_release_mbid(clean_rec)
        == "b9ddde22-fca3-4d94-aee9-f964b34166ce"
    )


# ---------------------------------------------------------------------------
# ART-MB-06: Latest-wins queue — 5 rapid jobs collapse to ≤2 worker spawns
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; fetch_mb_cover + _spawn_worker seam not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_latest_wins_queue_drops_superseded_jobs(monkeypatch):
    """ART-MB-06: D-13 latest-wins, max 1 in-flight + 1 queued.

    Pinned seam: `musicstreamer.cover_art_mb._spawn_worker(target, args)` is the
    SOLE call site that wraps `threading.Thread`. Monkeypatching it lets us
    capture every spawn attempt without ever creating a real thread. Plan 02's
    Task 1 step 18 implements this seam exactly.

    Assertion: 5 rapid ICY arrivals must produce ≤2 spawn calls (1 in-flight +
    1 final). The middle 3 are queued, then collapsed: only the latest survives.
    """
    from musicstreamer import cover_art_mb  # RED until Plan 02

    spawned: list = []

    def recording_stub(target, args):
        """Record the spawn without actually starting a thread."""
        spawned.append({"target": target, "args": args})
        # Intentionally do NOT call target() — the queue logic is what's under test.

    # MUST monkeypatch the exact pinned attribute name — see plan note.
    monkeypatch.setattr(cover_art_mb, "_spawn_worker", recording_stub)

    # Submit 5 rapid ICY titles.
    for i in range(5):
        cover_art_mb.fetch_mb_cover(f"Artist {i} - Title {i}", lambda _p: None)

    # D-13: at most 2 worker spawns (1 in-flight + 1 final).
    assert len(spawned) <= 2, (
        f"D-13: latest-wins queue should produce ≤2 spawns; got {len(spawned)}"
    )


# ---------------------------------------------------------------------------
# ART-MB-13: Genre from MB tags — highest count wins; no-tags → ""
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; _genre_from_tags not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_genre_from_tags_picks_highest_count():
    """ART-MB-13: D-15 highest-count tag wins; absent 'tags' key (Pitfall 3) → ""."""
    from musicstreamer import cover_art_mb  # RED until Plan 02

    clean_hit = _load_fixture("mb_recording_search_clean_album_hit.json")
    no_tags = _load_fixture("mb_recording_search_no_tags.json")

    clean_rec = clean_hit["recordings"][0]
    no_tags_rec = no_tags["recordings"][0]

    # 'house' (count=5) beats 'dance' (count=1).
    assert cover_art_mb._genre_from_tags(clean_rec) == "house"

    # Pitfall 3: 'tags' key entirely absent → empty string, not KeyError.
    assert "tags" not in no_tags_rec, "Fixture invariant: no_tags must omit the key"
    assert cover_art_mb._genre_from_tags(no_tags_rec) == ""


# ---------------------------------------------------------------------------
# ART-MB-14: HTTP 503 from MB → callback(None), no raise
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; D-20 fall-through not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError),
)
def test_mb_503_falls_through_to_callback_none(monkeypatch):
    """ART-MB-14: D-20 — 503 rate-limit MUST NOT escape the worker.

    Strategy: monkeypatch urlopen to raise HTTPError(503). Assert callback gets
    None and no exception propagates. Mirrors cover_art.py:98 bare except idiom.
    """
    from musicstreamer import cover_art_mb  # RED until Plan 02

    def fake_urlopen_503(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url if hasattr(req, "full_url") else "http://test",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        "musicstreamer.cover_art_mb.urllib.request.urlopen", fake_urlopen_503
    )

    cb_calls: list = []
    # Synchronous call (or the worker stub) — Plan 02 chooses the test seam.
    cover_art_mb.fetch_mb_cover("Daft Punk - One More Time", lambda p: cb_calls.append(p))

    # callback invoked exactly once with None; no exception raised.
    assert cb_calls == [None]


# ---------------------------------------------------------------------------
# ART-MB-15: Source-grep gate — UA literal present in cover_art_mb.py
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; cover_art_mb.py not yet created",
    raises=(FileNotFoundError, AssertionError, ImportError, ModuleNotFoundError),
)
def test_user_agent_string_literals_present():
    """ART-MB-15: D-18 — source-grep guarantees the literal strings exist.

    Mirrors the memory `feedback_gstreamer_mock_blind_spot.md` lesson:
    protocol-required strings must be testable at the source level, not just
    behaviorally (since mocked HTTP would happily pass any UA string).
    """
    import importlib.resources

    src = importlib.resources.files("musicstreamer").joinpath("cover_art_mb.py").read_text()
    assert "MusicStreamer/" in src, "UA literal 'MusicStreamer/' must appear in source"
    assert "https://github.com/lightningjim/MusicStreamer" in src, (
        "UA contact URL must appear in source verbatim per D-18"
    )


# ---------------------------------------------------------------------------
# ART-MB-16: Source-grep gate — time.monotonic actually referenced (not just commented)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 02 — RED scaffold; cover_art_mb.py not yet created",
    raises=(FileNotFoundError, AssertionError, ImportError, ModuleNotFoundError),
)
def test_rate_gate_uses_monotonic():
    """ART-MB-16: D-14 — rate gate must actually call time.monotonic, not just claim to.

    Hygiene per plan instructions: a bare `'time.monotonic' in src` substring
    check would pass on a comment-only mention. Use a non-comment line-anchored
    regex so a docstring or `# time.monotonic` comment alone is not enough.
    """
    import importlib.resources

    src = importlib.resources.files("musicstreamer").joinpath("cover_art_mb.py").read_text()
    # Find any non-comment line referencing time.monotonic — strip lines whose
    # first non-whitespace char is '#'.
    pattern = re.compile(r"^[^#]*\btime\.monotonic\b", re.MULTILINE)
    assert pattern.search(src), (
        "time.monotonic must appear on a non-comment line in cover_art_mb.py"
    )

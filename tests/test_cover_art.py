"""Unit tests for musicstreamer.cover_art module."""
import json
import unittest
from unittest.mock import MagicMock

import musicstreamer.cover_art as cover_art_mod
from musicstreamer.cover_art import (
    fetch_cover_art,
    is_junk_title,
    _build_itunes_query,
    _parse_artwork_url,
)


class TestIsJunkTitle(unittest.TestCase):
    def test_is_junk_title(self):
        self.assertTrue(is_junk_title(""))
        self.assertTrue(is_junk_title("   "))
        self.assertTrue(is_junk_title("Advertisement"))
        self.assertTrue(is_junk_title("commercial break"))
        self.assertTrue(is_junk_title("Advert"))
        self.assertTrue(is_junk_title("Commercial"))
        self.assertFalse(is_junk_title("Bohemian Rhapsody"))


class TestBuildItunesQuery(unittest.TestCase):
    def test_build_itunes_query_artist_title(self):
        url = _build_itunes_query("Queen - Bohemian Rhapsody")
        self.assertIn("term=Queen+Bohemian+Rhapsody", url)
        self.assertIn("media=music", url)
        self.assertIn("limit=1", url)

    def test_build_itunes_query_title_only(self):
        url = _build_itunes_query("Bohemian Rhapsody")
        self.assertIn("term=Bohemian+Rhapsody", url)
        self.assertIn("media=music", url)
        self.assertIn("limit=1", url)


class TestParseArtworkUrl(unittest.TestCase):
    def test_parse_artwork_url(self):
        sample = {
            "resultCount": 1,
            "results": [
                {
                    "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/abc/100x100bb.jpg"
                }
            ]
        }
        result = _parse_artwork_url(json.dumps(sample).encode())
        self.assertIsNotNone(result)
        self.assertIn("160x160", result)
        self.assertNotIn("100x100", result)

    def test_parse_artwork_url_empty(self):
        sample = {"resultCount": 0, "results": []}
        result = _parse_artwork_url(json.dumps(sample).encode())
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Phase 73 Plan 03 — source-aware router tests
#
# These exercise the `source` kwarg on fetch_cover_art (D-01..D-04, D-07, D-16).
# The router intentionally lives in cover_art.py (not a new module) so existing
# 2-arg call sites in now_playing_panel keep working via the `source='auto'`
# default. ART-MB-07 / ART-MB-08 / ART-MB-09 are flipped GREEN by Plan 03.
#
# Pattern: monkeypatch BOTH iTunes urllib.request.urlopen AND the cover_art_mb
# module's fetch_mb_cover. We don't go through Plan 02's real worker thread —
# the routing layer should call fetch_mb_cover directly, and we assert call
# counts on a synchronous spy.
# ---------------------------------------------------------------------------


def _itunes_miss_urlopen() -> MagicMock:
    """Build a urlopen spy that returns an empty iTunes resultCount=0 payload."""
    spy = MagicMock()
    resp = MagicMock()
    resp.read.return_value = b'{"resultCount": 0, "results": []}'
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda *a: None
    spy.return_value = resp
    return spy


def test_mb_only_mode_does_not_call_itunes_urlopen(monkeypatch):
    """ART-MB-07 / D-04: source='mb_only' MUST NOT call iTunes urlopen at all.

    The test monkeypatches iTunes urlopen to a spy that records calls; any
    invocation is a routing bug. D-16 also forbids the side iTunes call for
    genre — MB-only is strict.
    """
    # iTunes urlopen MUST NOT fire. Use a side_effect to make any call loud.
    itunes_spy = MagicMock(side_effect=AssertionError(
        "iTunes urlopen called in MB-only mode (violates D-04 / D-16)"
    ))
    monkeypatch.setattr(cover_art_mod.urllib.request, "urlopen", itunes_spy)

    # MB-side: monkeypatch fetch_mb_cover to a synchronous spy (don't spawn
    # the real Plan 02 worker thread — keeps the test fast and deterministic).
    import musicstreamer.cover_art_mb as cover_art_mb_mod

    mb_spy = MagicMock()
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    # The router imports cover_art_mb at module-load — also patch the symbol
    # as it was bound at import time (matches the double-patch idiom from
    # test_now_playing_panel.py:567-570 for re-exported symbols).
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    cb = MagicMock()
    fetch_cover_art("Daft Punk - One More Time", cb, source="mb_only")

    assert itunes_spy.call_count == 0, "MB-only must not touch iTunes urlopen"
    assert mb_spy.call_count == 1, "MB-only must invoke fetch_mb_cover once"
    args, _kwargs = mb_spy.call_args
    # fetch_mb_cover supports two call shapes; the router uses the explicit
    # (artist, title, callback) split per the contract documented in Plan 02.
    assert args[0] == "Daft Punk"
    assert args[1] == "One More Time"
    assert args[2] is cb


def test_mb_only_bare_title_short_circuits(monkeypatch):
    """D-07: bare-title ICY (no ' - ') skips MB entirely in MB-only mode.

    Expected: callback(None) is invoked; neither iTunes urlopen nor MB is
    touched. This is the strict MB-only bare-title gate (the router must
    detect the bare title BEFORE delegating to fetch_mb_cover — even though
    fetch_mb_cover would also short-circuit, the router's gate avoids the
    fetch_mb_cover call entirely so its rate-gate / queue state is untouched).
    """
    itunes_spy = MagicMock(side_effect=AssertionError(
        "iTunes urlopen called for bare-title in MB-only mode"
    ))
    monkeypatch.setattr(cover_art_mod.urllib.request, "urlopen", itunes_spy)

    import musicstreamer.cover_art_mb as cover_art_mb_mod
    mb_spy = MagicMock()
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    cb_calls = []
    fetch_cover_art("Just A Song", lambda p: cb_calls.append(p), source="mb_only")

    assert itunes_spy.call_count == 0
    assert mb_spy.call_count == 0, "Bare title must not reach fetch_mb_cover"
    assert cb_calls == [None], f"Expected single callback(None); got {cb_calls!r}"


def test_itunes_only_mode_does_not_call_mb(monkeypatch):
    """ART-MB-08 / D-03: source='itunes_only' MUST NOT call cover_art_mb.

    The iTunes path runs normally; we stub its urlopen to return resultCount=0
    so the legacy worker terminates cleanly with callback(None). The MB spy
    must record zero calls.

    The iTunes path spawns a daemon thread, so we join it (via the module's
    private last-thread handle) before asserting on the MB spy to avoid a
    race between the worker thread finishing and the assertion.
    """
    itunes_spy = _itunes_miss_urlopen()
    monkeypatch.setattr(cover_art_mod.urllib.request, "urlopen", itunes_spy)

    import musicstreamer.cover_art_mb as cover_art_mb_mod
    mb_spy = MagicMock(side_effect=AssertionError(
        "fetch_mb_cover called in iTunes-only mode (violates D-03)"
    ))
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    cb_calls: list = []
    cb_event = __import__("threading").Event()

    def _cb(p):
        cb_calls.append(p)
        cb_event.set()

    fetch_cover_art("Daft Punk - One More Time", _cb, source="itunes_only")

    # Wait for the iTunes worker thread to deliver callback(None).
    assert cb_event.wait(timeout=2.0), "iTunes worker did not invoke callback"
    assert cb_calls == [None]
    assert mb_spy.call_count == 0, "iTunes-only must never invoke fetch_mb_cover"


def test_auto_bare_title_after_itunes_miss_does_not_fall_through_to_mb(monkeypatch):
    """D-07: bare-title ICY in Auto mode tries iTunes only — no MB fallback.

    Auto mode CAN run iTunes for bare titles (some streams produce them and
    iTunes can still match). But on iTunes miss, the router MUST NOT call MB
    for a bare title because MB requires artist+title (D-07).
    """
    itunes_spy = _itunes_miss_urlopen()
    monkeypatch.setattr(cover_art_mod.urllib.request, "urlopen", itunes_spy)

    import musicstreamer.cover_art_mb as cover_art_mb_mod
    mb_spy = MagicMock(side_effect=AssertionError(
        "fetch_mb_cover called for bare-title in Auto mode (violates D-07)"
    ))
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    cb_calls: list = []
    cb_event = __import__("threading").Event()

    def _cb(p):
        cb_calls.append(p)
        cb_event.set()

    fetch_cover_art("Just A Song", _cb, source="auto")

    assert cb_event.wait(timeout=2.0), "iTunes worker did not invoke callback"
    assert cb_calls == [None]
    assert mb_spy.call_count == 0, "Bare title in Auto mode must not call MB"


def test_junk_title_short_circuits_regardless_of_source(monkeypatch):
    """is_junk_title gate runs FIRST regardless of source — preserves the
    existing cover_art.py:75-77 invariant for both routing paths.
    """
    itunes_spy = MagicMock(side_effect=AssertionError("junk should skip iTunes"))
    monkeypatch.setattr(cover_art_mod.urllib.request, "urlopen", itunes_spy)
    import musicstreamer.cover_art_mb as cover_art_mb_mod
    mb_spy = MagicMock(side_effect=AssertionError("junk should skip MB"))
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    for src in ("auto", "itunes_only", "mb_only"):
        cb_calls: list = []
        fetch_cover_art("", lambda p: cb_calls.append(p), source=src)
        assert cb_calls == [None], f"source={src!r}: expected callback(None) on junk"
        fetch_cover_art("Advertisement", lambda p: cb_calls.append(p), source=src)

    assert itunes_spy.call_count == 0
    assert mb_spy.call_count == 0


def test_auto_mode_legacy_two_arg_callsite_still_works(monkeypatch):
    """Compat: existing 2-arg callers (now_playing_panel.py:1187 today) must
    continue to function with source='auto' default. This guards the brief
    Plan-03 → Plan-04 window when the panel hasn't yet been updated to pass
    `source=` explicitly.
    """
    itunes_spy = _itunes_miss_urlopen()
    monkeypatch.setattr(cover_art_mod.urllib.request, "urlopen", itunes_spy)
    import musicstreamer.cover_art_mb as cover_art_mb_mod
    mb_spy = MagicMock()  # iTunes miss + non-bare title → MB IS called in auto
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    cb = MagicMock()
    # 2-arg shape — no source kwarg.
    fetch_cover_art("Daft Punk - One More Time", cb)

    # Wait briefly for the iTunes worker thread to chain into MB.
    import time
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and mb_spy.call_count == 0:
        time.sleep(0.02)

    assert mb_spy.call_count == 1, (
        "Default source='auto' must chain iTunes miss → MB fallback"
    )


if __name__ == "__main__":
    unittest.main()

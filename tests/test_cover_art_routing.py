"""Integration tests for Phase 73 cover-art routing.

Plan 73-01 created this file with xfail-marked tests. Plan 73-03 lands the
auto-mode fallthrough (iTunes miss → MB called) and turns this GREEN.

Coverage:
- ART-MB-09: Auto mode fallthrough — iTunes miss triggers MB lookup; the
  final outer callback receives the MB-sourced image path.
"""
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# ART-MB-09: Auto mode — iTunes miss falls through to MB
# ---------------------------------------------------------------------------


def test_auto_mode_falls_through_to_mb_when_itunes_misses(monkeypatch):
    """ART-MB-09: D-02 Auto semantics — iTunes first, MB fallback on miss.

    Pattern: double-patch idiom from test_now_playing_panel.py:567-570 — when
    a consumer does `from musicstreamer.cover_art import fetch_cover_art`, the
    symbol must be patched in BOTH the source module AND the consumer. Here we
    don't have a Qt consumer in scope (Plan 04 lands the panel wiring); we
    directly call cover_art.fetch_cover_art with source='auto' and assert the
    router chains iTunes → MB on iTunes miss.

    Test seam: we monkeypatch fetch_mb_cover to a synchronous spy that invokes
    its callback with a known path. This avoids spawning Plan 02's daemon
    worker thread (which has a 1-req/sec gate) — keeps the test fast and
    deterministic.

    Assertions:
      - iTunes urlopen called at least once (the miss attempt).
      - fetch_mb_cover called exactly once (the fallback after iTunes miss).
      - The outer callback receives the MB-sourced path.
    """
    import musicstreamer.cover_art as cover_art_mod
    import musicstreamer.cover_art_mb as cover_art_mb_mod

    # iTunes side: urlopen returns resultCount=0 → iTunes worker delivers None.
    itunes_urlopen_spy = MagicMock()
    itunes_resp = MagicMock()
    itunes_resp.read.return_value = b'{"resultCount": 0, "results": []}'
    itunes_resp.__enter__ = lambda s: s
    itunes_resp.__exit__ = lambda *a: None
    itunes_urlopen_spy.return_value = itunes_resp
    monkeypatch.setattr(
        cover_art_mod.urllib.request, "urlopen", itunes_urlopen_spy
    )

    # MB side: synchronous spy that invokes callback with a dummy path.
    def _fake_fetch_mb(artist, title, callback):
        callback("/tmp/fake_mb_cover.jpg")

    mb_spy = MagicMock(side_effect=_fake_fetch_mb)
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    # Re-bind on the router's imported reference too (double-patch idiom).
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    cb_calls: list = []
    import threading
    cb_event = threading.Event()

    def _cb(path):
        cb_calls.append(path)
        cb_event.set()

    cover_art_mod.fetch_cover_art(
        "Daft Punk - One More Time",
        _cb,
        source="auto",
    )

    # The iTunes worker runs on a daemon thread; wait for it to complete and
    # chain into the MB spy → callback.
    assert cb_event.wait(timeout=2.0), "Outer callback never invoked"

    assert itunes_urlopen_spy.call_count >= 1, (
        "iTunes must be tried first in auto mode (D-02)"
    )
    assert mb_spy.call_count == 1, (
        "MB must be tried as fallback after iTunes miss (D-02)"
    )
    # ART-MB-09: the MB-sourced path reaches the outer callback.
    assert cb_calls == ["/tmp/fake_mb_cover.jpg"], (
        f"Expected MB path; got {cb_calls!r}"
    )


def test_auto_mode_itunes_hit_does_not_call_mb(monkeypatch):
    """D-02 inverse: when iTunes returns a result, MB MUST NOT be called.

    iTunes wins; this is the "no double network call when first source hits"
    invariant. The MB spy must record zero calls.
    """
    import musicstreamer.cover_art as cover_art_mod
    import musicstreamer.cover_art_mb as cover_art_mb_mod

    # iTunes side: return a hit. cover_art's iTunes worker then fetches the
    # 160x160 image bytes via a second urlopen call — we serve a tiny fake
    # JPEG-byte payload for that. urlopen is called twice (search + image).
    itunes_search_payload = (
        b'{"resultCount": 1, "results": [{'
        b'"artworkUrl100": "https://x.example/art/100x100bb.jpg",'
        b'"primaryGenreName": "Electronic"'
        b'}]}'
    )
    fake_image_bytes = b"\xFF\xD8\xFF\xE0fakejpeg"

    call_log: list = []

    def _fake_urlopen(url_or_req, timeout=None):
        # The first call is the search JSON; the second is the image GET.
        target = url_or_req if isinstance(url_or_req, str) else url_or_req.full_url
        call_log.append(target)
        resp = MagicMock()
        if "itunes.apple.com/search" in target:
            resp.read.return_value = itunes_search_payload
        else:
            resp.read.return_value = fake_image_bytes
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp

    monkeypatch.setattr(
        cover_art_mod.urllib.request, "urlopen", MagicMock(side_effect=_fake_urlopen)
    )

    mb_spy = MagicMock(side_effect=AssertionError(
        "fetch_mb_cover called even though iTunes returned a hit (violates D-02)"
    ))
    monkeypatch.setattr(cover_art_mb_mod, "fetch_mb_cover", mb_spy)
    monkeypatch.setattr(cover_art_mod, "_cover_art_mb", cover_art_mb_mod)

    cb_calls: list = []
    import threading
    cb_event = threading.Event()

    def _cb(path):
        cb_calls.append(path)
        cb_event.set()

    cover_art_mod.fetch_cover_art(
        "Daft Punk - One More Time",
        _cb,
        source="auto",
    )

    assert cb_event.wait(timeout=2.0), "Outer callback never invoked"
    # iTunes hit → callback receives the temp-file path (not None, not the MB path).
    assert cb_calls and cb_calls[0] is not None
    assert mb_spy.call_count == 0, (
        "Auto mode must not call MB after iTunes hits"
    )

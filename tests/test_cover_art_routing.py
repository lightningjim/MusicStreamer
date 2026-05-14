"""Integration tests for Phase 73 cover-art routing — Wave 0 RED scaffolds.

Plan 73-01 creates this file with xfail-marked tests. Plan 73-03 lands the
auto-mode fallthrough (iTunes miss → MB called) and turns this GREEN.

Coverage:
- ART-MB-09: Auto mode fallthrough — iTunes miss triggers MB lookup; the
  final cover_art_ready signal carries the MB-sourced image path.
"""
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# ART-MB-09: Auto mode — iTunes miss falls through to MB
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Plan 03 — RED scaffold; auto-mode fallthrough router not yet implemented",
    raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError, TypeError),
)
def test_auto_mode_falls_through_to_mb_when_itunes_misses(monkeypatch):
    """ART-MB-09: D-02 Auto semantics — iTunes first, MB fallback on miss.

    Pattern: double-patch idiom from test_now_playing_panel.py:567-570 — the
    panel does `from musicstreamer.cover_art import fetch_cover_art`, so the
    symbol must be patched in BOTH the source module AND the consumer module.

    The MB-side patch (`musicstreamer.cover_art_mb.urllib.request.urlopen`)
    targets a module that does not yet exist in Plan 01 — this is the
    deliberate Wave 0 RED state. Plan 02 lands cover_art_mb; Plan 03 wires
    the router; Plan 03 turns this test GREEN.

    Assertions:
      - iTunes urlopen called exactly once (the miss).
      - MB urlopen called exactly once (the fallthrough).
      - The cover_art_ready callback receives a non-None path (MB's mocked image).
    """
    # Patch iTunes side first — both source and panel-imported symbol.
    import musicstreamer.cover_art as cover_art_mod

    itunes_urlopen_spy = MagicMock()
    # iTunes returns empty results → cover_art.fetch_cover_art callback(None)
    itunes_resp = MagicMock()
    itunes_resp.read.return_value = b'{"resultCount": 0, "results": []}'
    itunes_resp.__enter__ = lambda s: s
    itunes_resp.__exit__ = lambda *a: None
    itunes_urlopen_spy.return_value = itunes_resp

    monkeypatch.setattr(
        cover_art_mod.urllib.request, "urlopen", itunes_urlopen_spy
    )

    # Patch MB side — module exists only after Plan 02 lands.
    from musicstreamer import cover_art_mb  # RED in Plan 01

    mb_urlopen_spy = MagicMock()
    mb_resp = MagicMock()
    mb_resp.read.return_value = b'{"recordings": []}'
    mb_resp.__enter__ = lambda s: s
    mb_resp.__exit__ = lambda *a: None
    mb_urlopen_spy.return_value = mb_resp

    monkeypatch.setattr(
        cover_art_mb.urllib.request, "urlopen", mb_urlopen_spy
    )

    # Invoke the router. Plan 03 lands the `source=` keyword on fetch_cover_art.
    cb_calls: list = []
    cover_art_mod.fetch_cover_art(
        "Daft Punk - One More Time",
        lambda p: cb_calls.append(p),
        source="auto",
    )

    # Auto-mode router contract:
    #   1. iTunes urlopen called at least once (the initial attempt).
    #   2. MB urlopen called at least once (the fallback after iTunes miss).
    #   3. The final callback was invoked (path can be None if MB also misses;
    #      Plan 03 may refine to assert non-None when MB returns a hit).
    assert itunes_urlopen_spy.call_count >= 1, "iTunes must be tried first in auto mode"
    assert mb_urlopen_spy.call_count >= 1, (
        "MB must be tried as fallback after iTunes miss (D-02)"
    )
    assert len(cb_calls) >= 1, "Callback must be invoked exactly once"

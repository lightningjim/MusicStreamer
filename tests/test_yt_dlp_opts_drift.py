"""Phase 79 / BUG-11 drift-guard: both yt-dlp call sites must use the shared
`yt_dlp_opts.build_js_runtimes(` helper. A regression that re-introduces the
inline `{'node': {'path': None}}` literal at either site is the exact bug
Phase 79 fixed — see commit `a06549f` context."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "musicstreamer"


def test_player_uses_build_js_runtimes():
    """Player._youtube_resolve_worker must route js_runtimes through
    yt_dlp_opts.build_js_runtimes() — the inline {"node": {"path": None}}
    literal at player.py:1063 is the exact bug Phase 79 / BUG-11 fixed."""
    src = (ROOT / "player.py").read_text()
    assert src.count("build_js_runtimes(") == 1, (
        "musicstreamer/player.py must call yt_dlp_opts.build_js_runtimes(...) "
        "exactly once (inside _youtube_resolve_worker's opts dict). A "
        "regression that re-introduces the inline {{'node': {{'path': None}}}} "
        "literal here is the exact bug Phase 79 / BUG-11 fixed — see commit "
        "a06549f (2026-04-25 first-half: Node detection) and Plan 79-02 "
        "(second-half: thread the resolved path through to yt-dlp's "
        "js_runtimes opt). Current count: {actual}".format(
            actual=src.count("build_js_runtimes(")
        )
    )


def test_yt_import_uses_build_js_runtimes():
    """yt_import.scan_playlist must route js_runtimes through
    yt_dlp_opts.build_js_runtimes() — single source of truth invariant (D-10).
    Per Pitfall 2 this is an INSERTION into the scan opts dict, not a
    substitution; count must be exactly 1, not 0."""
    src = (ROOT / "yt_import.py").read_text()
    assert src.count("build_js_runtimes(") == 1, (
        "musicstreamer/yt_import.py must call yt_dlp_opts.build_js_runtimes(...) "
        "exactly once (inside scan_playlist's opts dict). D-10 single-source-of-"
        "truth invariant: both yt-dlp call sites (player._youtube_resolve_worker "
        "and yt_import.scan_playlist) must route js_runtimes through the shared "
        "helper. Per Pitfall 2 this is an INSERTION not a SUBSTITUTION — "
        "scan_playlist had no inline js_runtimes literal before Phase 79. "
        "Current count: {actual}".format(actual=src.count("build_js_runtimes("))
    )

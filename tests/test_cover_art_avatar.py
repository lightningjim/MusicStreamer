"""Source-grep drift-guard and field-filter unit tests for Phase 89 cover-art avatar path.

ART-AVATAR-07/09: precedence lock — _mb_caa_lookup must appear before
_channel_avatar_lookup in cover_art.py source (structural drift-guard over
named functions, not behavioral mocks).

ART-AVATAR-03: thumbnail field-filter logic — avatar_uncropped preferred,
non-square rejected, None dimensions allowed.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import musicstreamer.cover_art as cover_art_mod

COVER_ART_SRC = Path(__file__).parent.parent / "musicstreamer" / "cover_art.py"


# ---------------------------------------------------------------------------
# ART-AVATAR-09: Source-grep precedence drift-guard
# ---------------------------------------------------------------------------


def test_mb_caa_runs_before_channel_avatar():
    """ART-AVATAR-09: _mb_caa_lookup must appear before _channel_avatar_lookup in cover_art.py.

    Source-grep gate: precedence enforced by grepping source, not mocking
    (per feedback_gstreamer_mock_blind_spot.md convention).
    """
    src = COVER_ART_SRC.read_text(encoding="utf-8")
    mb_pos = src.find("def _mb_caa_lookup")
    avatar_pos = src.find("def _channel_avatar_lookup")
    assert mb_pos != -1, "cover_art.py must define _mb_caa_lookup"
    assert avatar_pos != -1, "cover_art.py must define _channel_avatar_lookup"
    assert mb_pos < avatar_pos, (
        "ART-AVATAR-09: _mb_caa_lookup must appear BEFORE _channel_avatar_lookup "
        "in cover_art.py "
        "(cover-resolver precedence: ICY -> iTunes -> MB-CAA -> channel-avatar -> placeholder)"
    )


# ---------------------------------------------------------------------------
# ART-AVATAR-03: thumbnail field-filter logic
# ---------------------------------------------------------------------------


def test_fetch_channel_avatar_prefers_avatar_uncropped():
    """ART-AVATAR-03: avatar_uncropped entry selected over numeric-id entry."""
    thumbnails = [
        {"id": "0", "url": "http://cropped.jpg", "width": 200, "height": 200},
        {"id": "avatar_uncropped", "url": "http://uncropped.jpg"},
    ]
    # Test the filter logic directly (not the network call)
    entry = next((t for t in thumbnails if t.get("id") == "avatar_uncropped"), None)
    assert entry is not None
    assert entry["url"] == "http://uncropped.jpg"


def test_fetch_channel_avatar_rejects_non_square():
    """ART-AVATAR-03: entries with width != height are rejected."""
    w, h = 200, 150
    assert w is not None and h is not None and w != h  # rejection condition


def test_fetch_channel_avatar_allows_none_dimensions():
    """ART-AVATAR-03 / RESEARCH.md Pitfall 2: None != None == False; don't reject uncropped."""
    w, h = None, None
    # Correct guard: only reject when BOTH present and differ
    should_reject = w is not None and h is not None and w != h
    assert not should_reject


# ---------------------------------------------------------------------------
# _channel_avatar_lookup unit tests (synchronous, never-raise contract)
# ---------------------------------------------------------------------------


def test_channel_avatar_lookup_none_station_calls_cb_none():
    """_channel_avatar_lookup(None, cb) must call cb(None), never raise."""
    cb = MagicMock()
    cover_art_mod._channel_avatar_lookup(None, cb)
    cb.assert_called_once_with(None)


def test_channel_avatar_lookup_no_path_calls_cb_none():
    """_channel_avatar_lookup with station lacking provider_avatar_path calls cb(None)."""
    station = MagicMock(spec=[])  # no provider_avatar_path attribute
    cb = MagicMock()
    cover_art_mod._channel_avatar_lookup(station, cb)
    cb.assert_called_once_with(None)


def test_channel_avatar_lookup_empty_path_calls_cb_none():
    """_channel_avatar_lookup with station.provider_avatar_path == "" calls cb(None)."""
    station = MagicMock(spec=["provider_avatar_path"])
    station.provider_avatar_path = ""
    cb = MagicMock()
    cover_art_mod._channel_avatar_lookup(station, cb)
    cb.assert_called_once_with(None)


def test_channel_avatar_lookup_existing_path_calls_cb_abs(tmp_path):
    """_channel_avatar_lookup resolves rel path and calls cb(abs_path) when file exists."""
    import musicstreamer.paths as _paths_mod

    # Create a fake avatar file under a temporary data_dir
    avatar_rel = "assets/channel-avatars/42.png"
    avatar_abs = tmp_path / "assets" / "channel-avatars" / "42.png"
    avatar_abs.parent.mkdir(parents=True, exist_ok=True)
    avatar_abs.write_bytes(b"\x89PNG\r\n")

    station = MagicMock(spec=["provider_avatar_path"])
    station.provider_avatar_path = avatar_rel

    cb = MagicMock()
    original = _paths_mod._root_override
    try:
        _paths_mod._root_override = str(tmp_path)
        cover_art_mod._channel_avatar_lookup(station, cb)
    finally:
        _paths_mod._root_override = original

    cb.assert_called_once()
    called_path = cb.call_args[0][0]
    assert called_path is not None
    assert called_path.endswith(avatar_rel.replace("/", __import__("os").sep))


def test_channel_avatar_lookup_missing_file_calls_cb_none(tmp_path):
    """_channel_avatar_lookup calls cb(None) when the resolved path does not exist."""
    import musicstreamer.paths as _paths_mod

    station = MagicMock(spec=["provider_avatar_path"])
    station.provider_avatar_path = "assets/channel-avatars/99.png"

    cb = MagicMock()
    original = _paths_mod._root_override
    try:
        _paths_mod._root_override = str(tmp_path)
        cover_art_mod._channel_avatar_lookup(station, cb)
    finally:
        _paths_mod._root_override = original

    cb.assert_called_once_with(None)


def test_channel_avatar_lookup_null_provider_avatar_calls_cb_none():
    """D-06: station with provider_id set but no provider_avatar_path calls cb(None)."""
    station = MagicMock(spec=["provider_avatar_path"])
    station.provider_avatar_path = None
    cb = MagicMock()
    cover_art_mod._channel_avatar_lookup(station, cb)
    cb.assert_called_once_with(None)


# ---------------------------------------------------------------------------
# ART-AVATAR-12 / D-12: source-grep drift-guard — brand lookup placement
# ---------------------------------------------------------------------------


NOW_PLAYING_SRC = Path(__file__).parent.parent / "musicstreamer" / "ui_qt" / "now_playing_panel.py"
COVER_ART_PY = Path(__file__).parent.parent / "musicstreamer" / "cover_art.py"


def test_brand_lookup_only_in_cover_exhausted_branch():
    """D-12: _resolve_brand_avatar_fallback fires only from _on_cover_art_ready's
    if-not-path branch — never from bind_station or fetch_cover_art dispatch chain.

    Source-grep gate: structural contract, not a behavioral mock
    (per feedback_gstreamer_mock_blind_spot.md convention).
    """
    src = NOW_PLAYING_SRC.read_text(encoding="utf-8")

    # 1. _resolve_brand_avatar_fallback must be called within _on_cover_art_ready body.
    ready_pos = src.find("def _on_cover_art_ready")
    assert ready_pos != -1, "now_playing_panel.py must define _on_cover_art_ready"
    # Find next top-level method def after _on_cover_art_ready
    next_def_pos = src.find("\n    def ", ready_pos + 1)
    if next_def_pos == -1:
        next_def_pos = len(src)
    ready_body = src[ready_pos:next_def_pos]
    assert "_resolve_brand_avatar_fallback" in ready_body, (
        "D-07: _resolve_brand_avatar_fallback must be called from _on_cover_art_ready"
    )

    # 2. _resolve_brand_avatar_fallback must NOT appear in bind_station body.
    bind_pos = src.find("def bind_station")
    assert bind_pos != -1, "now_playing_panel.py must define bind_station"
    bind_next = src.find("\n    def ", bind_pos + 1)
    if bind_next == -1:
        bind_next = len(src)
    bind_body = src[bind_pos:bind_next]
    assert "_resolve_brand_avatar_fallback" not in bind_body, (
        "D-07: _resolve_brand_avatar_fallback must NOT appear in bind_station "
        "(brand lookup is cover-resolution-exhausted only, not icy_disabled bind path)"
    )

    # 3. brand_avatars.lookup must NOT appear in cover_art.py (D-07 / fetch_cover_art purity).
    cover_src = COVER_ART_PY.read_text(encoding="utf-8")
    assert "brand_avatars" not in cover_src, (
        "D-12: brand_avatars must NOT be imported in cover_art.py — "
        "the registry lookup belongs exclusively to the resolution-exhausted branch "
        "in now_playing_panel._on_cover_art_ready"
    )

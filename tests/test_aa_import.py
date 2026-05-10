import json
import urllib.error
from unittest.mock import MagicMock, patch, call

import pytest

from musicstreamer.aa_import import _resolve_pls
from musicstreamer.aa_import import fetch_channels_multi, import_stations_multi


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_channel_json(name: str, key: str) -> bytes:
    return json.dumps([{"name": name, "key": key}]).encode()


def _urlopen_factory(data: bytes, content_type: str = "audio/x-scpls"):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    # Provide a real headers.get so _resolve_pls can extract Content-Type
    # without receiving a MagicMock string that breaks parse_playlist dispatch.
    # Default "audio/x-scpls" matches what AA servers return for PLS responses.
    headers_mock = MagicMock()
    headers_mock.get = MagicMock(return_value=content_type)
    cm.headers = headers_mock
    return cm


def _make_http_error(code: int):
    return urllib.error.HTTPError(url="http://test", code=code, msg="err", hdrs=None, fp=None)


# ---------------------------------------------------------------------------
# _resolve_pls tests
# ---------------------------------------------------------------------------

def test_resolve_pls():
    """_resolve_pls fetches a PLS URL and returns ALL File= stream URLs (gap-06)."""
    pls_content = b"[playlist]\nNumberOfEntries=2\nFile1=http://prem1.di.fm:80/ambient_hi?key\nFile2=http://prem4.di.fm:80/ambient_hi?key\n"

    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(pls_content)):
        result = _resolve_pls("https://listen.di.fm/premium_high/ambient.pls?listen_key=key")

    # gap-06: _resolve_pls now returns a list of ALL File= URLs (primary + fallback).
    assert result == [
        "http://prem1.di.fm:80/ambient_hi?key",
        "http://prem4.di.fm:80/ambient_hi?key",
    ]


def test_resolve_pls_fallback_on_error():
    """_resolve_pls returns [original URL] as a single-element list if resolution fails (gap-06)."""
    pls_url = "https://listen.di.fm/premium_high/ambient.pls?listen_key=key"

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=Exception("network error")):
        result = _resolve_pls(pls_url)

    # gap-06: list-form fallback preserves prior behavior for callers that take [0].
    assert result == [pls_url]


# ---------------------------------------------------------------------------
# _normalize_aa_image_url tests
# ---------------------------------------------------------------------------

def test_normalize_aa_image_url():
    from musicstreamer.aa_import import _normalize_aa_image_url
    raw = "//cdn-images.audioaddict.com/abc/file.png{?size,height,width,quality,pad}"
    assert _normalize_aa_image_url(raw) == "https://cdn-images.audioaddict.com/abc/file.png"


def test_normalize_aa_image_url_already_https():
    from musicstreamer.aa_import import _normalize_aa_image_url
    raw = "https://cdn-images.audioaddict.com/abc/file.png"
    assert _normalize_aa_image_url(raw) == "https://cdn-images.audioaddict.com/abc/file.png"


# ---------------------------------------------------------------------------
# _fetch_image_map tests
# ---------------------------------------------------------------------------

def _api_image_map_json(channels: list[dict]) -> bytes:
    """Build an AA /v1/<slug>/channels response body from a list of channel dicts."""
    return json.dumps(channels).encode()


def test_fetch_image_map_prefers_default_over_square():
    """When both `default` and `square` are present, `default` wins.

    Regression for late-night-jazz-wrong-logo: AudioAddict's JazzRadio API serves
    the same `square` image URL for both `latenightjazz` and `trumpetjazz` (upstream
    data bug). The `default` images are channel-correct. We must prefer `default`.
    """
    from musicstreamer.aa_import import _fetch_image_map
    api_data = _api_image_map_json([
        {
            "name": "Late Night Jazz",
            "key": "latenightjazz",
            "images": {
                "default": "//cdn-images.audioaddict.com/correct/latenight.png",
                "square": "//cdn-images.audioaddict.com/collided/shared.jpg",
            },
        },
        {
            "name": "Trumpet Jazz",
            "key": "trumpetjazz",
            "images": {
                "default": "//cdn-images.audioaddict.com/correct/trumpet.png",
                "square": "//cdn-images.audioaddict.com/collided/shared.jpg",
            },
        },
    ])
    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(api_data)):
        result = _fetch_image_map("jazzradio")

    assert result["latenightjazz"] == "https://cdn-images.audioaddict.com/correct/latenight.png"
    assert result["trumpetjazz"] == "https://cdn-images.audioaddict.com/correct/trumpet.png"
    assert result["latenightjazz"] != result["trumpetjazz"]


def test_fetch_image_map_falls_back_to_square_when_default_absent():
    """Backward compatibility: fixtures and channels with only `square` still resolve."""
    from musicstreamer.aa_import import _fetch_image_map
    api_data = _api_image_map_json([
        {"name": "Ambient", "key": "ambient",
         "images": {"square": "//cdn-images.audioaddict.com/abc/ambient.png"}},
    ])
    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(api_data)):
        result = _fetch_image_map("di")

    assert result == {"ambient": "https://cdn-images.audioaddict.com/abc/ambient.png"}


def test_fetch_image_map_logs_warning_on_collision(caplog):
    """When two channel keys map to the same normalized image URL, log a WARNING.

    Defensive guard: catches future upstream collisions (analogous to the JazzRadio
    `square` collision) before they silently surface as misreads to the user.
    """
    import logging
    from musicstreamer.aa_import import _fetch_image_map
    api_data = _api_image_map_json([
        {"name": "ChanA", "key": "chana",
         "images": {"default": "//cdn-images.audioaddict.com/dup/shared.png"}},
        {"name": "ChanB", "key": "chanb",
         "images": {"default": "//cdn-images.audioaddict.com/dup/shared.png"}},
    ])
    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(api_data)), \
         caplog.at_level(logging.WARNING, logger="musicstreamer.aa_import"):
        result = _fetch_image_map("jazzradio")

    assert "chana" in result
    assert "chanb" in result
    collision_records = [
        r for r in caplog.records
        if "collision" in r.getMessage() and "jazzradio" in r.getMessage()
    ]
    assert len(collision_records) == 1
    msg = collision_records[0].getMessage()
    assert "chana" in msg and "chanb" in msg


def test_fetch_image_map_no_warning_when_unique(caplog):
    """No collision warning when every channel has a distinct image URL."""
    import logging
    from musicstreamer.aa_import import _fetch_image_map
    api_data = _api_image_map_json([
        {"name": "ChanA", "key": "chana",
         "images": {"default": "//cdn-images.audioaddict.com/unique/a.png"}},
        {"name": "ChanB", "key": "chanb",
         "images": {"default": "//cdn-images.audioaddict.com/unique/b.png"}},
    ])
    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(api_data)), \
         caplog.at_level(logging.WARNING, logger="musicstreamer.aa_import"):
        _fetch_image_map("jazzradio")

    collision_records = [r for r in caplog.records if "collision" in r.getMessage()]
    assert collision_records == []


# ---------------------------------------------------------------------------
# fetch_channels_multi tests
# ---------------------------------------------------------------------------

def test_fetch_channels_multi_returns_streams():
    """fetch_channels_multi returns channels with hi/med/low streams."""
    channel_data = _mock_channel_json("Ambient", "ambient")

    def urlopen_side(url, timeout=None):
        if "api.audioaddict.com" in url:
            return _urlopen_factory(json.dumps([]).encode())
        return _urlopen_factory(channel_data)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=urlopen_side), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: [url]):
        result = fetch_channels_multi("testkey123")

    assert isinstance(result, list)
    assert len(result) > 0
    for ch in result:
        assert "streams" in ch
        assert len(ch["streams"]) == 3
        qualities = {s["quality"] for s in ch["streams"]}
        assert qualities == {"hi", "med", "low"}


def test_fetch_channels_multi_stream_has_quality():
    """Each stream dict in channel['streams'] has url, quality, position keys."""
    channel_data = _mock_channel_json("Jazz", "jazz")

    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(json.dumps([]).encode())
               if "api.audioaddict.com" in url else _urlopen_factory(channel_data)), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: [url]):
        result = fetch_channels_multi("testkey123")

    for ch in result:
        for s in ch["streams"]:
            assert "url" in s
            assert "quality" in s
            assert "position" in s


def test_fetch_channels_multi_positions():
    """Position scheme: tier_base * 10 + pls_index (gap-06).

    With a mocked _resolve_pls returning [url] (single entry, pls_index=1),
    hi -> 11, med -> 21, low -> 31. The gap-06 scheme preserves tier ordering
    (hi < med < low) and leaves room within each tier for primary=*1 and
    fallback=*2 when real PLS files have 2 File= entries.
    """
    channel_data = _mock_channel_json("Jazz", "jazz")

    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(json.dumps([]).encode())
               if "api.audioaddict.com" in url else _urlopen_factory(channel_data)), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: [url]):
        result = fetch_channels_multi("testkey123")

    for ch in result:
        pos_map = {s["quality"]: s["position"] for s in ch["streams"]}
        assert pos_map == {"hi": 11, "med": 21, "low": 31}
        # Invariant: all positions unique and sort tier-first
        positions = [s["position"] for s in ch["streams"]]
        assert len(positions) == len(set(positions))


def test_fetch_channels_multi_invalid_key():
    """fetch_channels_multi raises ValueError('invalid_key') on 401/403."""
    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=_make_http_error(403)):
        with pytest.raises(ValueError, match="invalid_key"):
            fetch_channels_multi("badkey")


def test_fetch_channels_multi_no_channels():
    """fetch_channels_multi raises ValueError('no_channels') when empty."""
    empty_data = json.dumps([]).encode()
    with patch("musicstreamer.aa_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(empty_data)):
        with pytest.raises(ValueError, match="no_channels"):
            fetch_channels_multi("testkey123")


def test_import_multi_creates_streams():
    """import_stations_multi creates one station with 3 stream rows."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 42
    mock_repo.list_streams.return_value = [MagicMock(id=100)]

    channels = [{
        "title": "Ambient",
        "provider": "DI.fm",
        "image_url": None,
        "streams": [
            {"url": "http://hi.stream", "quality": "hi", "position": 1, "codec": "AAC"},
            {"url": "http://med.stream", "quality": "med", "position": 2, "codec": "MP3"},
            {"url": "http://low.stream", "quality": "low", "position": 3, "codec": "MP3"},
        ],
    }]
    imported, skipped = import_stations_multi(channels, mock_repo)
    assert imported == 1
    assert skipped == 0
    mock_repo.insert_station.assert_called_once()
    # Should have called insert_stream for the 2 additional streams (first was auto-created)
    assert mock_repo.insert_stream.call_count == 2


def test_import_multi_skips_existing():
    """import_stations_multi skips channel if any stream URL already exists."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = True

    channels = [{
        "title": "Ambient", "provider": "DI.fm", "image_url": None,
        "streams": [{"url": "http://hi.stream", "quality": "hi", "position": 1, "codec": "AAC"}],
    }]
    imported, skipped = import_stations_multi(channels, mock_repo)
    assert imported == 0
    assert skipped == 1
    mock_repo.insert_station.assert_not_called()


def test_import_multi_calls_progress():
    """on_progress is called after each channel."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 10
    mock_repo.list_streams.return_value = [MagicMock(id=1)]

    channels = [
        {
            "title": "Ambient", "provider": "DI.fm", "image_url": None,
            "streams": [{"url": "http://a.stream", "quality": "hi", "position": 1, "codec": "AAC"}],
        },
        {
            "title": "Jazz", "provider": "DI.fm", "image_url": None,
            "streams": [{"url": "http://b.stream", "quality": "hi", "position": 1, "codec": "AAC"}],
        },
    ]
    progress_calls = []
    import_stations_multi(channels, mock_repo, on_progress=lambda imp, skip: progress_calls.append((imp, skip)))
    assert len(progress_calls) == 2


# ---------------------------------------------------------------------------
# PB-12: bitrate_kbps tier mapping + threading through import (Phase 47-03)
# ---------------------------------------------------------------------------


def test_fetch_channels_multi_bitrate_kbps():
    """PB-12: fetch_channels_multi populates bitrate_kbps per DI.fm tier (hi=320, med=128, low=64)."""
    channel_data = _mock_channel_json("Ambient", "ambient")

    def urlopen_side(url, timeout=None):
        if "api.audioaddict.com" in url:
            return _urlopen_factory(json.dumps([]).encode())
        return _urlopen_factory(channel_data)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=urlopen_side), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: [url]):
        result = fetch_channels_multi("testkey123")

    assert len(result) > 0
    for ch in result:
        bitrates_by_quality = {s["quality"]: s["bitrate_kbps"] for s in ch["streams"]}
        assert bitrates_by_quality == {"hi": 320, "med": 128, "low": 64}


def test_import_multi_threads_bitrate_kbps():
    """PB-12: import_stations_multi passes bitrate_kbps kwarg to insert_stream and update_stream."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 42
    mock_repo.list_streams.return_value = [MagicMock(id=100)]

    channels = [{
        "title": "Ambient",
        "provider": "DI.fm",
        "image_url": None,
        "streams": [
            {"url": "http://hi.stream", "quality": "hi", "position": 1, "codec": "AAC", "bitrate_kbps": 320},
            {"url": "http://med.stream", "quality": "med", "position": 2, "codec": "MP3", "bitrate_kbps": 128},
            {"url": "http://low.stream", "quality": "low", "position": 3, "codec": "MP3", "bitrate_kbps": 64},
        ],
    }]
    import_stations_multi(channels, mock_repo)

    # update_stream called once for the auto-created first stream (hi=320)
    assert mock_repo.update_stream.call_count == 1
    upd_kwargs = mock_repo.update_stream.call_args.kwargs
    assert upd_kwargs.get("bitrate_kbps") == 320

    # insert_stream called twice (med, low) with bitrate_kbps kwarg
    assert mock_repo.insert_stream.call_count == 2
    bitrates_seen = {
        call.kwargs.get("bitrate_kbps") for call in mock_repo.insert_stream.call_args_list
    }
    assert bitrates_seen == {128, 64}


# ---------------------------------------------------------------------------
# Gap-closure (UAT gap 2): PLS primary + fallback server extraction
# ---------------------------------------------------------------------------


def test_resolve_pls_returns_all_entries():
    """_resolve_pls must return ALL File= entries in PLS file order.

    AA PLS files contain File1=<primary> + File2=<fallback>; the fallback
    is critical for failover redundancy within a tier.
    """
    from musicstreamer.aa_import import _resolve_pls

    pls_body = (
        "[playlist]\n"
        "numberofentries=2\n"
        "File1=http://primary.di.fm:8000/listen\n"
        "File2=http://fallback.di.fm:8000/listen\n"
        "Length1=-1\n"
        "Length2=-1\n"
        "Version=2\n"
    )

    with patch(
        "musicstreamer.aa_import.urllib.request.urlopen",
        side_effect=lambda *a, **kw: _urlopen_factory(pls_body.encode()),
    ):
        result = _resolve_pls("http://any.pls")

    assert result == [
        "http://primary.di.fm:8000/listen",
        "http://fallback.di.fm:8000/listen",
    ]


def test_resolve_pls_single_entry():
    """A PLS with only File1= returns a one-element list."""
    from musicstreamer.aa_import import _resolve_pls

    pls_body = (
        "[playlist]\n"
        "numberofentries=1\n"
        "File1=http://only.di.fm:8000/listen\n"
    )

    with patch(
        "musicstreamer.aa_import.urllib.request.urlopen",
        side_effect=lambda *a, **kw: _urlopen_factory(pls_body.encode()),
    ):
        result = _resolve_pls("http://any.pls")

    assert result == ["http://only.di.fm:8000/listen"]


def test_resolve_pls_delegates_to_playlist_parser():
    """Phase 58 / D-10: _resolve_pls delegates to playlist_parser.parse_playlist."""
    pls_url = "http://host/playlist.pls"
    pls_content = b"[playlist]\nFile1=http://s1.example/stream\nTitle1=Stream 128k MP3\n"
    mock_entries = [
        {"url": "http://s1.example/stream", "title": "Stream 128k MP3",
         "bitrate_kbps": 128, "codec": "MP3"},
    ]

    with patch(
        "musicstreamer.aa_import.urllib.request.urlopen",
        side_effect=lambda url, timeout=None: _urlopen_factory(pls_content),
    ), patch(
        "musicstreamer.playlist_parser.parse_playlist",
        return_value=mock_entries,
    ) as mock_pp:
        result = _resolve_pls(pls_url)

    assert result == ["http://s1.example/stream"]
    mock_pp.assert_called_once()
    # Body is the decoded string, content_type pulled from resp headers,
    # url_hint is the original pls_url.
    call_args = mock_pp.call_args
    assert isinstance(call_args.args[0], str)
    assert "File1=" in call_args.args[0]
    assert "url_hint" in call_args.kwargs
    assert call_args.kwargs["url_hint"] == pls_url
    assert "content_type" in call_args.kwargs


def test_resolve_pls_falls_back_when_parse_playlist_returns_empty():
    """Phase 58 / D-10: empty parse -> [pls_url] fallback preserved."""
    pls_url = "http://host/empty.pls"

    with patch(
        "musicstreamer.aa_import.urllib.request.urlopen",
        side_effect=lambda url, timeout=None: _urlopen_factory(b"[playlist]\n"),
    ), patch(
        "musicstreamer.playlist_parser.parse_playlist",
        return_value=[],
    ):
        result = _resolve_pls(pls_url)

    assert result == [pls_url]


def test_resolve_pls_falls_back_on_urlopen_exception():
    """Phase 58 / D-10: urlopen failure -> [pls_url] fallback preserved."""
    pls_url = "http://host/unreachable.pls"

    with patch(
        "musicstreamer.aa_import.urllib.request.urlopen",
        side_effect=urllib.error.URLError("Connection refused"),
    ):
        result = _resolve_pls(pls_url)

    assert result == [pls_url]


def test_fetch_channels_multi_preserves_primary_and_fallback():
    """Each tier's PLS has 2 server entries -> each tier produces 2 stream
    dicts in fetch_channels_multi output (6 streams total for hi/med/low).
    """
    channel_data = _mock_channel_json("Ambient", "ambient")

    pls_body_template = (
        "[playlist]\n"
        "File1=http://primary.{tier}.di.fm/listen\n"
        "File2=http://fallback.{tier}.di.fm/listen\n"
    )

    def urlopen_side(url, timeout=None):
        if "api.audioaddict.com" in url:
            return _urlopen_factory(json.dumps([]).encode())
        # PLS request — return tier-labeled primary+fallback body.
        # Order of tier checks matters: premium_high + premium_medium must be
        # matched before bare "premium" (which is the med tier).
        if ".pls?" in url or url.endswith(".pls"):
            if "premium_high" in url:
                return _urlopen_factory(pls_body_template.replace("{tier}", "hi").encode())
            if "premium_medium" in url:
                return _urlopen_factory(pls_body_template.replace("{tier}", "low").encode())
            if "premium" in url:
                return _urlopen_factory(pls_body_template.replace("{tier}", "med").encode())
        # Channel-list JSON request (non-PLS, non-api)
        return _urlopen_factory(channel_data)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=urlopen_side):
        result = fetch_channels_multi("testkey123")

    assert len(result) > 0
    for ch in result:
        # Expect 6 streams: 2 per tier (primary + fallback) x 3 tiers
        assert len(ch["streams"]) == 6, (
            f"expected 6 streams (primary + fallback x 3 tiers) for "
            f"{ch['title']}, got {len(ch['streams'])}"
        )
        # Every tier should have exactly 2 streams
        by_quality = {}
        for s in ch["streams"]:
            by_quality.setdefault(s["quality"], []).append(s)
        assert set(by_quality.keys()) == {"hi", "med", "low"}
        for q, entries in by_quality.items():
            assert len(entries) == 2
            # Bitrate identical across primary + fallback in the same tier
            assert len({e["bitrate_kbps"] for e in entries}) == 1
            # URLs differ between primary and fallback
            assert len({e["url"] for e in entries}) == 2
            # Position ordering: primary < fallback within the tier
            positions = [e["position"] for e in entries]
            assert positions == sorted(positions), (
                f"{q} tier positions {positions} must sort primary before fallback"
            )
            # Primary URL appears first in PLS (contains "primary.")
            primary = [e for e in entries if "primary." in e["url"]][0]
            fallback = [e for e in entries if "fallback." in e["url"]][0]
            assert primary["position"] < fallback["position"]


# ---------------------------------------------------------------------------
# Gap-closure (UAT gap 3): ground-truth codec mapping for paid AA tiers
# Source: user-verified AA hardware-player settings UI — hi=MP3, med=AAC, low=AAC
# ---------------------------------------------------------------------------


def test_fetch_channels_multi_codec_map_ground_truth():
    """Paid AA tier -> codec mapping: hi=MP3, med=AAC, low=AAC.

    This asserts the GROUND TRUTH from the AA hardware-player settings UI
    (consistent across all paid AA networks per user verification in UAT
    gap 3). The previous inline ternary produced the inverted mapping
    hi=AAC, med=MP3, low=MP3 — which is the bug this gap-closure closes.

    Bitrate values (hi=320, med=128, low=64) are already correct.
    """
    channel_data = _mock_channel_json("Jazz", "jazz")

    def urlopen_side(url, timeout=None):
        if "api.audioaddict.com" in url:
            return _urlopen_factory(json.dumps([]).encode())
        return _urlopen_factory(channel_data)

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=urlopen_side), \
         patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: ["http://mock"]):
        result = fetch_channels_multi("testkey123")

    assert len(result) > 0
    for ch in result:
        # Both primary + fallback entries per quality have identical codec,
        # so dict-comprehension de-duplication is safe.
        codec_by_quality = {s["quality"]: s["codec"] for s in ch["streams"]}
        # Ground truth — user-verified against AA hardware-player settings UI
        assert codec_by_quality["hi"] == "MP3", (
            f"hi tier codec must be MP3 (320 MP3 per ground truth), got {codec_by_quality['hi']}"
        )
        assert codec_by_quality["med"] == "AAC", (
            f"med tier codec must be AAC (128 AAC per ground truth), got {codec_by_quality['med']}"
        )
        assert codec_by_quality["low"] == "AAC", (
            f"low tier codec must be AAC (64 AAC per ground truth), got {codec_by_quality['low']}"
        )

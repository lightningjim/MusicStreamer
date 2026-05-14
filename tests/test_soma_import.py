"""Phase 74 / Wave 0: RED contract for musicstreamer.soma_import.

Eleven failing tests that encode the SomaFM importer spec (RESEARCH validation
tests #1–9 + #14–#15). All tests RED-fail on collection until Plan 02 creates
musicstreamer/soma_import.py. Once Plan 02 lands they must ALL turn GREEN.

SOMA-NN traceability:
  test 1: SOMA-01, SOMA-02, SOMA-04, SOMA-05 (fetch + parse shape)
  test 2: SOMA-02, SOMA-04 (4-tier × 5-relay + codec multiset)
  test 3: SOMA-03 (position numbering tier_base*10+relay_index)
  test 4: SOMA-04, T-74-02 (codec normalization: no AAC+ stored)
  test 5: SOMA-05, T-74-03 (PLS resolved to ice*.somafm.com direct URLs)
  test 6: SOMA-06, SOMA-07 (dedup-by-URL skip; insert_station not called)
  test 7: SOMA-01 (provider_name='SomaFM'; 3 stations × 20 streams = 57 insert_stream)
  test 8: SOMA-08, T-74-04 (logo failure non-fatal; update_station_art not called)
  test 9: SOMA-09, T-74-05 (per-channel exception skips only that channel)
  test 10: SOMA-15, T-74-02 (source-grep: no AAC+ codec literal in source)
  test 11: SOMA-13, SOMA-14, T-74-01 (source-grep: UA literals present in source)
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from musicstreamer import soma_import  # RED: ImportError until Plan 02 ships


# ---------------------------------------------------------------------------
# Helpers (lifted verbatim from tests/test_aa_import.py with module-path rename)
# ---------------------------------------------------------------------------

def _urlopen_factory(data: bytes, content_type: str = "audio/x-scpls"):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    # Provide a real headers.get so _resolve_pls can extract Content-Type
    # without receiving a MagicMock string that breaks parse_playlist dispatch.
    headers_mock = MagicMock()
    headers_mock.get = MagicMock(return_value=content_type)
    cm.headers = headers_mock
    return cm


def _make_http_error(code: int):
    return urllib.error.HTTPError(url="http://test", code=code, msg="err", hdrs=None, fp=None)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> bytes:
    """Load a JSON fixture from tests/fixtures/ as bytes."""
    fixture_dir = Path(__file__).parent / "fixtures"
    return (fixture_dir / name).read_bytes()


def _make_pls_body(channel_id: str, bitrate: str, ext: str, relay_count: int = 5) -> bytes:
    """Build a PLS body with relay_count File= entries for ice1..iceN.somafm.com."""
    lines = ["[playlist]", f"NumberOfEntries={relay_count}"]
    for i in range(1, relay_count + 1):
        lines.append(f"File{i}=https://ice{i}.somafm.com/{channel_id}-{bitrate}-{ext}")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _make_resolve_pls_stub(channel_id: str):
    """Return a _resolve_pls stub that returns 5 deterministic ICE relay URLs per PLS URL.

    Detects the quality tier from the PLS URL filename and returns appropriate URLs.
    """
    def _stub(pls_url: str, timeout: int = 10) -> list[str]:
        if "256" in pls_url or ("mp3" in pls_url.lower()):
            bitrate, ext = "128", "mp3"
        elif "130" in pls_url:
            bitrate, ext = "128", "aac"
        elif "64" in pls_url:
            bitrate, ext = "64", "aac"
        elif "32" in pls_url:
            bitrate, ext = "32", "aac"
        else:
            # Try to infer from URL
            bitrate, ext = "128", "mp3"
        return [f"https://ice{i}.somafm.com/{channel_id}-{bitrate}-{ext}" for i in range(1, 6)]
    return _stub


def _make_any_resolve_pls_stub():
    """Return a _resolve_pls stub that handles any channel by parsing the PLS filename."""
    def _stub(pls_url: str, timeout: int = 10) -> list[str]:
        # Extract channel_id from URL like https://api.somafm.com/groovesalad256.pls
        import re
        m = re.search(r'/([a-z]+)(\d+)\.pls', pls_url)
        if m:
            channel_id = m.group(1)
            bitrate = m.group(2)
            if int(bitrate) >= 200:  # 256 = mp3
                ext = "mp3"
                bitrate = "128"
            elif int(bitrate) == 130:
                ext = "aac"
                bitrate = "128"
            elif int(bitrate) == 64:
                ext = "aac"
            elif int(bitrate) == 32:
                ext = "aac"
            else:
                ext = "mp3"
            return [f"https://ice{i}.somafm.com/{channel_id}-{bitrate}-{ext}" for i in range(1, 6)]
        return [pls_url]
    return _stub


# ---------------------------------------------------------------------------
# Tests #1–#9 + #14–#15 (RESEARCH validation matrix)
# ---------------------------------------------------------------------------

def test_fetch_channels_parses_canonical_blob():
    """SOMA-01/02/04/05: fetch_channels returns list of dicts with correct shape.

    Monkeypatches urlopen to return soma_channels_3ch.json bytes and
    _resolve_pls to return 5 deterministic ICE relay URLs per tier.
    Asserts the returned list has 3 channels each with keys: id, title,
    description, image_url, streams.
    """
    fixture_bytes = _load_fixture("soma_channels_3ch.json")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    assert len(channels) == 3
    for ch in channels:
        assert "id" in ch, f"Channel missing 'id': {ch.keys()}"
        assert "title" in ch, f"Channel missing 'title': {ch.keys()}"
        assert "description" in ch, f"Channel missing 'description': {ch.keys()}"
        assert "image_url" in ch, f"Channel missing 'image_url': {ch.keys()}"
        assert "streams" in ch, f"Channel missing 'streams': {ch.keys()}"


def test_fetch_channels_maps_four_tiers_twenty_streams_per_channel():
    """SOMA-02/04: each channel has exactly 20 streams with the correct codec/quality/bitrate multiset.

    Asserts multiset: {('MP3','hi',128):5, ('AAC','hi2',128):5, ('AAC','med',64):5, ('AAC','low',32):5}
    Maps to CONTEXT D-03 LOCKED 4-tier × 5-relay scheme.
    """
    from collections import Counter
    fixture_bytes = _load_fixture("soma_channels_3ch.json")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    first_ch = channels[0]
    streams = first_ch["streams"]
    assert len(streams) == 20, f"Expected 20 streams, got {len(streams)}"

    multiset = Counter((s["codec"], s["quality"], s["bitrate_kbps"]) for s in streams)
    expected = {
        ("MP3", "hi", 128): 5,
        ("AAC", "hi2", 128): 5,
        ("AAC", "med", 64): 5,
        ("AAC", "low", 32): 5,
    }
    assert multiset == expected, f"Stream multiset mismatch: got {dict(multiset)}"


def test_fetch_channels_position_numbering_tier_base_times_ten():
    """SOMA-03: position = tier_base*10 + relay_index for each tier.

    tier_base = {hi:1, hi2:2, med:3, low:4}, relay_index = 1..5.
    Maps to CONTEXT D-03 position numbering (mirrors aa_import._POSITION_MAP).
    """
    fixture_bytes = _load_fixture("soma_channels_3ch.json")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    first_ch = channels[0]
    streams = first_ch["streams"]

    tier_base_map = {"hi": 1, "hi2": 2, "med": 3, "low": 4}
    for quality, tier_base in tier_base_map.items():
        tier_positions = sorted(s["position"] for s in streams if s["quality"] == quality)
        expected_positions = sorted(tier_base * 10 + relay for relay in range(1, 6))
        assert tier_positions == expected_positions, (
            f"Quality '{quality}' positions {tier_positions} != expected {expected_positions}"
        )


def test_aacp_codec_maps_to_AAC_not_aacplus():
    """SOMA-04/T-74-02: codec field for 'aacp' format is 'AAC', never 'AAC+'.

    Collects all codec values across streams; asserts codec set == {'MP3', 'AAC'}
    with no 'AAC+' literal. Maps to CONTEXT D-03 + Phase 69 WIN-05.
    """
    fixture_bytes = _load_fixture("soma_channels_3ch.json")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    all_codecs = {s["codec"] for s in channels[0]["streams"]}
    assert "AAC+" not in all_codecs, (
        "SOMA-04 violation: 'AAC+' must not appear as a stored codec value. "
        f"Found codecs: {all_codecs}"
    )
    assert all_codecs == {"MP3", "AAC"}, (
        f"Expected codec set {{'MP3', 'AAC'}}, got {all_codecs}"
    )


def test_resolve_pls_returns_all_five_direct_urls():
    """SOMA-05/T-74-03: _resolve_pls returns 5 direct ice*.somafm.com URLs, NOT the .pls URL.

    Uses a PLS body with 5 File= entries (per RESEARCH Operation 2 shape).
    Asserts ALL returned URLs start with 'https://ice' and none equals the input .pls URL.
    """
    pls_url = "https://api.somafm.com/groovesalad256.pls"
    # RESEARCH §"Operation 2" example PLS body (5 ICE relay entries)
    pls_body = (
        b"[playlist]\n"
        b"NumberOfEntries=5\n"
        b"File1=https://ice1.somafm.com/groovesalad-128-mp3\n"
        b"File2=https://ice2.somafm.com/groovesalad-128-mp3\n"
        b"File3=https://ice3.somafm.com/groovesalad-128-mp3\n"
        b"File4=https://ice4.somafm.com/groovesalad-128-mp3\n"
        b"File5=https://ice5.somafm.com/groovesalad-128-mp3\n"
    )

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda url, timeout=None: _urlopen_factory(pls_body, "audio/x-scpls")):
        result = soma_import._resolve_pls(pls_url)

    assert isinstance(result, list), "Expected a list of URLs"
    assert len(result) == 5, f"Expected 5 relay URLs, got {len(result)}"
    for url in result:
        assert url.startswith("https://ice"), (
            f"T-74-03: stored URL must start with 'https://ice', got {url!r}"
        )
    assert pls_url not in result, (
        "T-74-03: .pls URL must not appear in resolved URL list"
    )


def test_import_skips_when_url_exists():
    """SOMA-06/07: import_stations skips entire channel if ANY stream URL already exists.

    Loads soma_channels_with_dedup_hit.json; uses repo stub with station_exists_by_url=True.
    Asserts (inserted, skipped) == (0, 1) and insert_station never called. Maps to D-05 + D-09.
    """
    fixture_bytes = _load_fixture("soma_channels_with_dedup_hit.json")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = True

    inserted, skipped = soma_import.import_stations(channels, mock_repo)
    assert (inserted, skipped) == (0, 1), (
        f"Expected (0, 1) for full dedup-skip, got ({inserted}, {skipped})"
    )
    mock_repo.insert_station.assert_not_called()


def test_import_three_channels_full_path_creates_stations_and_streams():
    """SOMA-01: import_stations inserts 3 stations with provider_name='SomaFM'.

    Each channel produces 20 streams (4 tiers × 5 relays). The first stream per
    channel is auto-created by insert_station; the remaining 19 are inserted via
    insert_stream. Total insert_stream calls = 3 × 19 = 57.
    Maps to D-02 (provider_name='SomaFM' CamelCase) + D-03 (20 streams/station).
    """
    fixture_bytes = _load_fixture("soma_channels_3ch.json")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    # Return incrementing station IDs
    mock_repo.insert_station.side_effect = [42, 43, 44]
    mock_repo.list_streams.side_effect = [
        [MagicMock(id=100)],  # groovesalad first stream
        [MagicMock(id=200)],  # dronezone first stream
        [MagicMock(id=300)],  # bootliquor first stream
    ]

    inserted, skipped = soma_import.import_stations(channels, mock_repo)
    assert (inserted, skipped) == (3, 0), (
        f"Expected (3, 0) for 3-channel insert, got ({inserted}, {skipped})"
    )
    assert mock_repo.insert_station.call_count == 3, (
        f"Expected 3 insert_station calls, got {mock_repo.insert_station.call_count}"
    )
    assert mock_repo.insert_stream.call_count == 57, (
        f"Expected 57 insert_stream calls (3 × 19), got {mock_repo.insert_stream.call_count}"
    )
    # Verify provider_name='SomaFM' on all insert_station calls (D-02)
    for call in mock_repo.insert_station.call_args_list:
        kwargs = call.kwargs
        provider = kwargs.get("provider_name", call.args[2] if len(call.args) > 2 else None)
        assert provider == "SomaFM", (
            f"SOMA-01 violation: provider_name must be 'SomaFM', got {provider!r}"
        )


def test_logo_failure_is_non_fatal():
    """SOMA-08/T-74-04: when logo download fails, station + streams survive; update_station_art NOT called.

    Uses a one-channel inline fixture. Patches urlopen to raise Exception for logo GETs.
    Asserts (inserted, skipped) == (1, 0) and update_station_art never called.
    Maps to D-11 (logo failure is non-fatal).
    """
    one_channel_data = {
        "channels": [{
            "id": "groovesalad",
            "title": "Groove Salad",
            "description": "A nicely chilled plate.",
            "dj": "Rusty Hodge",
            "djmail": "rusty@somafm.com",
            "genre": "ambient",
            "image": "https://api.somafm.com/img/groovesalad120.png",
            "largeimage": "https://api.somafm.com/logos/256/groovesalad256.png",
            "xlimage": "https://api.somafm.com/logos/512/groovesalad512.png",
            "twitter": "SomaFM",
            "updated": "1747167600",
            "listeners": "1444",
            "lastPlaying": "Sine - Take Me Higher",
            "playlists": [
                {"url": "https://api.somafm.com/groovesalad256.pls", "format": "mp3", "quality": "highest"},
                {"url": "https://api.somafm.com/groovesalad130.pls", "format": "aac", "quality": "highest"},
                {"url": "https://api.somafm.com/groovesalad64.pls", "format": "aacp", "quality": "high"},
                {"url": "https://api.somafm.com/groovesalad32.pls", "format": "aacp", "quality": "low"},
            ],
        }]
    }
    fixture_bytes = json.dumps(one_channel_data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 99
    mock_repo.list_streams.return_value = [MagicMock(id=200)]

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=Exception("network error")), \
         patch("musicstreamer.soma_import.db_connect"), \
         patch("musicstreamer.soma_import.Repo") as mock_repo_cls:
        mock_thread_repo = MagicMock()
        mock_repo_cls.return_value = mock_thread_repo
        inserted, skipped = soma_import.import_stations(channels, mock_repo)

    assert (inserted, skipped) == (1, 0), (
        f"SOMA-08: station must survive logo failure. Got ({inserted}, {skipped})"
    )
    mock_thread_repo.update_station_art.assert_not_called()


def test_per_channel_exception_skips_only_that_channel():
    """SOMA-09/T-74-05: a bad channel increments skipped; import continues with remaining channels.

    Three channels in fixture; second channel given playlists=None to force KeyError
    inside the import loop. Asserts (inserted, skipped) == (2, 1) and insert_station
    called exactly twice. Maps to D-15 (per-channel best-effort).
    """
    channels = [
        {
            "id": "groovesalad",
            "title": "Groove Salad",
            "description": "Ambient.",
            "image_url": "https://api.somafm.com/img/groovesalad120.png",
            "streams": [
                {"url": f"https://ice{i}.somafm.com/groovesalad-128-mp3",
                 "quality": "hi", "position": 10 + i, "codec": "MP3", "bitrate_kbps": 128}
                for i in range(1, 6)
            ],
        },
        {
            "id": "dronezone",
            "title": "Drone Zone",
            "description": None,  # Malformed — will cause exception in importer
            "image_url": None,
            "streams": None,  # Force a per-channel exception (None streams triggers error)
        },
        {
            "id": "bootliquor",
            "title": "Boot Liquor",
            "description": "Americana.",
            "image_url": "https://api.somafm.com/img/bootliquor120.png",
            "streams": [
                {"url": f"https://ice{i}.somafm.com/bootliquor-128-mp3",
                 "quality": "hi", "position": 10 + i, "codec": "MP3", "bitrate_kbps": 128}
                for i in range(1, 6)
            ],
        },
    ]

    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.side_effect = [42, 44]
    mock_repo.list_streams.side_effect = [
        [MagicMock(id=100)],
        [MagicMock(id=300)],
    ]

    inserted, skipped = soma_import.import_stations(channels, mock_repo)
    assert (inserted, skipped) == (2, 1), (
        f"SOMA-09: bad channel must be skipped, rest continue. Got ({inserted}, {skipped})"
    )
    assert mock_repo.insert_station.call_count == 2, (
        f"Expected 2 insert_station calls (skipping the bad channel), "
        f"got {mock_repo.insert_station.call_count}"
    )


def test_no_aacplus_codec_literal_in_source():
    """SOMA-15/T-74-02: 'AAC+' must not appear as a stored codec literal in soma_import.py.

    Reads musicstreamer/soma_import.py source via importlib.resources.
    Strips comment lines (lines whose first non-whitespace char is '#') before
    checking — mandatory per feedback_gstreamer_mock_blind_spot.md to avoid
    self-invalidating the gate via a comment that mentions 'AAC+'.
    Maps to SOMA-15 + CONTEXT D-03 + Phase 69 WIN-05 closure.
    """
    import importlib.resources

    src = importlib.resources.files("musicstreamer").joinpath("soma_import.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    # Strip Python comment lines before checking (Nyquist hygiene)
    non_comment_lines = [ln for ln in lines if not ln.lstrip().startswith("#")]
    stripped = "\n".join(non_comment_lines)

    assert '"AAC+"' not in stripped, (
        "SOMA-15 violation: '\"AAC+\"' must not appear as a stored codec literal in "
        "soma_import.py (excluding comments). The codec for 'aacp' format is 'AAC'."
    )


def test_user_agent_literal_present_in_source():
    """SOMA-13/14/T-74-01: UA literals 'MusicStreamer/' and GitHub URL must appear in soma_import.py.

    Source-grep gate — behavioral tests cannot catch UA regressions since mocked
    urlopen happily passes any string. Per feedback_gstreamer_mock_blind_spot.md.
    Maps to SOMA-13 (UA on outbound requests) + SOMA-14 (source-grep gate).
    """
    import importlib.resources

    src = importlib.resources.files("musicstreamer").joinpath("soma_import.py").read_text(encoding="utf-8")
    assert "MusicStreamer/" in src, (
        "SOMA-14 / T-74-01: UA literal 'MusicStreamer/' must appear in "
        "musicstreamer/soma_import.py source"
    )
    assert "https://github.com/lightningjim/MusicStreamer" in src, (
        "SOMA-14 / T-74-01: UA contact URL 'https://github.com/lightningjim/MusicStreamer' "
        "must appear in musicstreamer/soma_import.py source verbatim"
    )

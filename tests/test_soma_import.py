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


# ---------------------------------------------------------------------------
# Phase 74.1 / Plan 74-05 / G-02 / SOMA-02 / CR-01 / UAT F-01:
# Bitrate URL-slug parser (_bitrate_from_url) — RED tests for gap closure.
# ---------------------------------------------------------------------------

def test_bitrate_from_url_parses_256_mp3_slug():
    """SOMA-02 / G-02 / CR-01: _bitrate_from_url extracts 256 from a Synphaera-style URL.

    Synphaera Radio's MP3-highest stream is ``ice2.somafm.com/synphaera-256-mp3``;
    the URL slug encodes the actual bitrate (256), so the helper must return 256
    instead of the table default (128).
    """
    assert soma_import.bitrate_from_url(
        "https://ice2.somafm.com/synphaera-256-mp3", default=128
    ) == 256


def test_bitrate_from_url_parses_192_mp3_slug():
    """SOMA-02 / G-02 / CR-01: _bitrate_from_url extracts 192 from a Groove Salad 192k relay URL."""
    assert soma_import.bitrate_from_url(
        "https://ice1.somafm.com/groovesalad-192-mp3", default=128
    ) == 192


def test_bitrate_from_url_falls_back_to_default_for_unparseable_slug():
    """SOMA-02 / G-02 / CR-01: _bitrate_from_url returns the default for missing or non-numeric slugs.

    Two cases:
      1. URL with no -NN-codec slug at all -> default.
      2. URL with the codec marker but a non-numeric bitrate (e.g. ``-XYZ-mp3``) -> default.
    """
    assert soma_import.bitrate_from_url(
        "https://example.com/no-slug-here", default=128
    ) == 128
    assert soma_import.bitrate_from_url(
        "https://ice1.somafm.com/foo-XYZ-mp3", default=128
    ) == 128


def test_fetch_channels_overrides_bitrate_from_relay_url_slug():
    """SOMA-02 / G-02 / CR-01 / UAT F-01: fetch_channels overrides bitrate_kbps from the relay URL.

    Integration shape (mirrors test_fetch_channels_maps_four_tiers_twenty_streams_per_channel):
    patch urlopen with the 3-channel fixture and patch _resolve_pls with a stub that
    returns ``-256-mp3`` URLs for the MP3-highest tier (PLS URLs that contain "256")
    and delegates to _make_any_resolve_pls_stub for the other tiers. Assert the
    first channel's streams include exactly 5 entries where quality=="hi" AND
    bitrate_kbps == 256 (not the table default of 128).
    """
    fixture_bytes = _load_fixture("soma_channels_3ch.json")
    fallback_stub = _make_any_resolve_pls_stub()

    def _stub(pls_url: str, timeout: int = 10) -> list[str]:
        # MP3-highest PLS URLs contain "256" (e.g. groovesalad256.pls). Force
        # the relay URLs to carry the -256-mp3 slug so the override path executes.
        if "256" in pls_url:
            # Extract channel id from URL like https://api.somafm.com/groovesalad256.pls
            import re as _re
            m = _re.search(r"/([a-z]+)256\.pls", pls_url)
            channel_id = m.group(1) if m else "synphaera"
            return [
                f"https://ice{i}.somafm.com/{channel_id}-256-mp3"
                for i in range(1, 6)
            ]
        return fallback_stub(pls_url, timeout)

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=_stub):
        channels = soma_import.fetch_channels()

    hi_streams = [s for s in channels[0]["streams"] if s["quality"] == "hi"]
    assert len(hi_streams) == 5, f"Expected 5 hi-tier streams, got {len(hi_streams)}"
    for s in hi_streams:
        assert s["bitrate_kbps"] == 256, (
            f"SOMA-02 / G-02 violation: hi-tier stream must store bitrate_kbps=256 "
            f"(from URL slug), got {s['bitrate_kbps']} for url={s['url']!r}"
        )


# ---------------------------------------------------------------------------
# Phase 83 / Plan 83-02: preroll capture + insert + D-04 marker + per-channel cap
# + CASCADE-rollback. Eight new tests anchored to VALIDATION.md row names
# verbatim. The D-04 canonical test
# (`test_import_sets_prerolls_fetched_at_for_empty_preroll`) is required by
# VALIDATION.md row 47 and pinned by the source-grep done-criterion in
# 83-02-PLAN.md.
# ---------------------------------------------------------------------------

import logging

from musicstreamer.repo import Repo


def _make_channel_with_preroll(
    channel_id: str,
    title: str,
    preroll: list[str] | None = None,
) -> dict:
    """Build a single SomaFM channel dict in the upstream `channels.json` shape.

    The four-tier `playlists` block mirrors the structure in
    `tests/fixtures/soma_channels_3ch.json`. ``preroll=None`` omits the key
    entirely (the legitimately-empty channel — 25 of 46 channels per RESEARCH);
    ``preroll=[]`` writes an explicit empty list.
    """
    ch: dict = {
        "id": channel_id,
        "title": title,
        "description": f"{title} description",
        "image": f"https://api.somafm.com/img/{channel_id}120.png",
        "playlists": [
            {"url": f"https://api.somafm.com/{channel_id}256.pls",
             "format": "mp3", "quality": "highest"},
            {"url": f"https://api.somafm.com/{channel_id}130.pls",
             "format": "aac", "quality": "highest"},
            {"url": f"https://api.somafm.com/{channel_id}64.pls",
             "format": "aacp", "quality": "high"},
            {"url": f"https://api.somafm.com/{channel_id}32.pls",
             "format": "aacp", "quality": "low"},
        ],
    }
    if preroll is not None:
        ch["preroll"] = preroll
    return ch


def test_fetch_channels_returns_preroll_urls_when_upstream_has_preroll():
    """Phase 83 D-02: fetch_channels surfaces `preroll[]` verbatim as `preroll_urls`.

    Uses Beat Blender's real shape (3 preroll m4a URLs per live SomaFM API
    audit 2026-05-22). The returned channel dict carries the same list in
    the same order under the `preroll_urls` key.
    """
    preroll_list = [
        "https://somafm.com/prerolls/beatblender/BeatBlenderID1.m4a",
        "https://somafm.com/prerolls/beatblender/BeatBlenderID2.m4a",
        "https://somafm.com/prerolls/beatblender/BeatBlenderID3.m4a",
    ]
    data = {"channels": [_make_channel_with_preroll(
        "beatblender", "Beat Blender", preroll=preroll_list,
    )]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    assert len(channels) == 1
    assert "preroll_urls" in channels[0], "fetch_channels must surface preroll_urls"
    assert channels[0]["preroll_urls"] == preroll_list, (
        f"Phase 83 D-02 violation: expected verbatim preroll list, got "
        f"{channels[0]['preroll_urls']!r}"
    )


def test_fetch_channels_returns_empty_preroll_urls_for_channels_without_preroll():
    """Phase 83 D-02: fetch_channels defaults preroll_urls to [] when upstream omits the key.

    25 of 46 live SomaFM channels have no `preroll` field at all (per RESEARCH §
    Sources). The importer must default to an empty list, not raise KeyError.
    """
    data = {"channels": [_make_channel_with_preroll("7soul", "Seven Inch Soul", preroll=None)]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    assert len(channels) == 1
    assert channels[0]["preroll_urls"] == [], (
        f"Phase 83 D-02: channels with no upstream `preroll` key must default "
        f"to []; got {channels[0]['preroll_urls']!r}"
    )


def test_fetch_channels_preserves_url_encoded_spaces_in_preroll():
    """Phase 83 Pitfall 7: preroll URLs are stored VERBATIM — no %20 decode.

    SomaFM-style preroll filenames sometimes contain `%20` (URL-encoded space).
    The importer never normalizes; playbin3 + souphttpsrc handles encoded
    URLs correctly. Decoding here would create a mismatch between what's
    stored and what plays.
    """
    encoded_url = "https://somafm.com/prerolls/bootliquor/Boot%20Liquor%20ID1.m4a"
    data = {"channels": [_make_channel_with_preroll(
        "bootliquor", "Boot Liquor", preroll=[encoded_url],
    )]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    assert channels[0]["preroll_urls"] == [encoded_url], (
        f"Phase 83 Pitfall 7 violation: URL must be stored verbatim. "
        f"Got {channels[0]['preroll_urls']!r}"
    )
    # Belt-and-suspenders: the raw %20 token survives unchanged.
    assert "%20" in channels[0]["preroll_urls"][0], (
        "Phase 83 Pitfall 7: %20 sequence must NOT be decoded to ' '"
    )


def test_import_calls_insert_preroll_per_url_in_position_order():
    """Phase 83 D-02: insert_preroll fires per URL, position monotone from 1.

    3-channel fixture: channel 1 has 2 prerolls; channels 2 and 3 have no
    preroll key. Assert insert_preroll is called only for channel 1, with
    (station_id=101, url1, position=1) and (101, url2, 2) — never for the
    empty channels.
    """
    preroll_list = [
        "https://somafm.com/prerolls/groovesalad/GrooveSaladID1.m4a",
        "https://somafm.com/prerolls/groovesalad/GrooveSaladID2.m4a",
    ]
    data = {"channels": [
        _make_channel_with_preroll("groovesalad", "Groove Salad", preroll=preroll_list),
        _make_channel_with_preroll("dronezone", "Drone Zone", preroll=None),
        _make_channel_with_preroll("bootliquor", "Boot Liquor", preroll=None),
    ]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    mock_repo = MagicMock(spec=Repo)
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.side_effect = [101, 102, 103]
    mock_repo.list_streams.side_effect = [
        [MagicMock(id=1010)],
        [MagicMock(id=1020)],
        [MagicMock(id=1030)],
    ]

    inserted, skipped = soma_import.import_stations(channels, mock_repo)

    assert (inserted, skipped) == (3, 0)
    # insert_preroll fires exactly twice — only for channel 1.
    assert mock_repo.insert_preroll.call_count == 2, (
        f"Expected 2 insert_preroll calls (only channel 1), got "
        f"{mock_repo.insert_preroll.call_count}"
    )
    # Positional args: (station_id, url, position) — monotone from 1.
    actual_calls = [
        (c.args[0], c.args[1], c.args[2])
        for c in mock_repo.insert_preroll.call_args_list
    ]
    assert actual_calls == [
        (101, preroll_list[0], 1),
        (101, preroll_list[1], 2),
    ], f"Phase 83 D-02 ordering violation: got {actual_calls!r}"


def test_import_sets_prerolls_fetched_at_for_empty_preroll():
    """Phase 83 D-04 (canonical anchor — name matches VALIDATION.md verbatim).

    Single-channel fixture where the channel has NO `preroll` key
    (legitimately-empty — 25 of 46 channels in the live API).
    set_prerolls_fetched_at MUST be called exactly once even though no
    insert_preroll fires — without this marker, the throttle gate would
    re-fetch on every Play, hammering the SomaFM API.
    """
    data = {"channels": [_make_channel_with_preroll(
        "7soul", "Seven Inch Soul", preroll=None,
    )]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    mock_repo = MagicMock(spec=Repo)
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 42
    mock_repo.list_streams.return_value = [MagicMock(id=420)]

    inserted, skipped = soma_import.import_stations(channels, mock_repo)

    assert (inserted, skipped) == (1, 0)
    assert mock_repo.set_prerolls_fetched_at.call_count == 1, (
        "Phase 83 D-04 violation: set_prerolls_fetched_at must fire even for "
        "legitimately-empty channels (otherwise throttle gate re-fetches "
        f"forever). Got call_count={mock_repo.set_prerolls_fetched_at.call_count}"
    )
    assert mock_repo.insert_preroll.call_count == 0, (
        "Empty preroll list must NOT call insert_preroll. Got "
        f"{mock_repo.insert_preroll.call_count} calls."
    )
    # Verify the call shape: (station_id, epoch_seconds:int).
    call = mock_repo.set_prerolls_fetched_at.call_args
    assert call.args[0] == 42, f"Expected station_id=42, got {call.args[0]!r}"
    assert isinstance(call.args[1], int), (
        f"epoch arg must be int (from int(time.time())); got {type(call.args[1])}"
    )


def test_import_sets_prerolls_fetched_at_for_every_imported_channel():
    """Phase 83 D-04 companion guard: every IMPORTED channel gets the marker.

    3-channel fixture: channel 1 populated (2 prerolls); channels 2 and 3
    empty. Assert set_prerolls_fetched_at.call_count == 3 — the marker
    fires for populated AND empty alike. Defends against regression where
    a future refactor scopes the call to `if preroll_urls:` only.
    """
    data = {"channels": [
        _make_channel_with_preroll("groovesalad", "Groove Salad", preroll=[
            "https://somafm.com/prerolls/groovesalad/GrooveSaladID1.m4a",
            "https://somafm.com/prerolls/groovesalad/GrooveSaladID2.m4a",
        ]),
        _make_channel_with_preroll("dronezone", "Drone Zone", preroll=None),
        _make_channel_with_preroll("bootliquor", "Boot Liquor", preroll=[]),
    ]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    mock_repo = MagicMock(spec=Repo)
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.side_effect = [201, 202, 203]
    mock_repo.list_streams.side_effect = [
        [MagicMock(id=2010)],
        [MagicMock(id=2020)],
        [MagicMock(id=2030)],
    ]

    inserted, skipped = soma_import.import_stations(channels, mock_repo)

    assert (inserted, skipped) == (3, 0)
    assert mock_repo.set_prerolls_fetched_at.call_count == 3, (
        "Phase 83 D-04 companion guard: marker must fire for populated AND "
        f"empty channels alike. Got call_count="
        f"{mock_repo.set_prerolls_fetched_at.call_count}"
    )
    # Each call should target a distinct station_id (201, 202, 203 in order).
    station_ids = [c.args[0] for c in mock_repo.set_prerolls_fetched_at.call_args_list]
    assert station_ids == [201, 202, 203], (
        f"Marker must target the imported station_ids in order; got {station_ids!r}"
    )


def test_import_caps_preroll_at_50_per_channel_and_emits_warning(caplog):
    """Phase 83 T-83-02 / DoS hardening: importer caps preroll inserts at 50 per channel.

    A hostile / compromised SomaFM response with 55 preroll entries for a
    single channel must result in exactly 50 insert_preroll calls AND a
    single _log.warning citing the original length. The channel still
    imports cleanly (the warning is non-fatal).
    """
    preroll_list = [
        f"https://somafm.com/prerolls/bigchannel/ID{i:03d}.m4a"
        for i in range(1, 56)
    ]
    assert len(preroll_list) == 55
    data = {"channels": [_make_channel_with_preroll(
        "bigchannel", "Big Channel", preroll=preroll_list,
    )]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    mock_repo = MagicMock(spec=Repo)
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 777
    mock_repo.list_streams.return_value = [MagicMock(id=7770)]

    with caplog.at_level(logging.WARNING, logger="musicstreamer.soma_import"):
        inserted, skipped = soma_import.import_stations(channels, mock_repo)

    # Channel still imports (warning is non-fatal).
    assert (inserted, skipped) == (1, 0), (
        f"Channel exceeding 50 prerolls must still import; got ({inserted}, {skipped})"
    )
    # Cap enforced: exactly 50 calls, never 55.
    assert mock_repo.insert_preroll.call_count == 50, (
        f"T-83-02 violation: insert_preroll must be capped at 50 per channel. "
        f"Got {mock_repo.insert_preroll.call_count} calls."
    )
    # Positions 1..50 in order.
    positions = [c.args[2] for c in mock_repo.insert_preroll.call_args_list]
    assert positions == list(range(1, 51)), (
        f"Positions must be 1..50 monotone after cap; got {positions[:3]}...{positions[-3:]}"
    )
    # Warning emitted once with the original length in the message.
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    cap_warnings = [r for r in warning_records if "capping at 50" in r.getMessage()]
    assert len(cap_warnings) == 1, (
        f"Expected exactly one cap-truncation warning; got {len(cap_warnings)}. "
        f"All warnings: {[r.getMessage() for r in warning_records]}"
    )
    msg = cap_warnings[0].getMessage()
    assert "55" in msg, (
        f"Cap warning must cite original length (55); got: {msg!r}"
    )
    # The marker still fires for this channel.
    assert mock_repo.set_prerolls_fetched_at.call_count == 1


def test_import_rolls_back_prerolls_via_cascade_when_stream_insert_raises_mid_channel():
    """Phase 83 Pitfall 4 ordering invariant: preroll INSERTs happen AFTER stream INSERTs.

    2-channel fixture: channel 1 imports cleanly (with 2 prerolls); channel 2
    raises mid-streams-loop. Assertions:
      - channel 1 prerolls are inserted normally.
      - channel 2: insert_preroll NEVER called (the streams loop raised
        BEFORE the preroll block).
      - channel 2: delete_station was called with channel 2's station_id
        (rollback fired; CASCADE on station_prerolls is the real-DB cleanup
        path — verified separately in test_repo.py).

    The MagicMock cannot replicate FK CASCADE, but this test proves the
    structural invariant that makes Pitfall 4 mitigation correct: prerolls
    are written INSIDE the rollback window, after streams.
    """
    preroll_ch1 = [
        "https://somafm.com/prerolls/groovesalad/GrooveSaladID1.m4a",
        "https://somafm.com/prerolls/groovesalad/GrooveSaladID2.m4a",
    ]
    preroll_ch2 = [
        "https://somafm.com/prerolls/dronezone/DroneZoneID1.m4a",
    ]
    data = {"channels": [
        _make_channel_with_preroll("groovesalad", "Groove Salad", preroll=preroll_ch1),
        _make_channel_with_preroll("dronezone", "Drone Zone", preroll=preroll_ch2),
    ]}
    fixture_bytes = json.dumps(data).encode("utf-8")
    resolve_stub = _make_any_resolve_pls_stub()

    with patch("musicstreamer.soma_import.urllib.request.urlopen",
               side_effect=lambda *a, **kw: _urlopen_factory(fixture_bytes, "application/json")), \
         patch("musicstreamer.soma_import._resolve_pls", side_effect=resolve_stub):
        channels = soma_import.fetch_channels()

    # Channel 1 needs 19 successful insert_stream calls (20 streams - 1 auto).
    # Channel 2's first insert_stream raises.
    insert_stream_side_effects: list = [None] * 19 + [RuntimeError("simulated DB error on ch2")]

    mock_repo = MagicMock(spec=Repo)
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.side_effect = [501, 502]
    mock_repo.list_streams.side_effect = [
        [MagicMock(id=5010)],
        [MagicMock(id=5020)],
    ]
    mock_repo.insert_stream.side_effect = insert_stream_side_effects

    inserted, skipped = soma_import.import_stations(channels, mock_repo)

    # Channel 1 succeeded, channel 2 skipped.
    assert (inserted, skipped) == (1, 1), (
        f"Phase 83 Pitfall 4: ch1 imports, ch2 rolls back. Got ({inserted}, {skipped})"
    )
    # Channel 2 rollback fired with its station_id.
    mock_repo.delete_station.assert_called_once_with(502)
    # Channel 1's prerolls were inserted normally (station_id=501, monotone positions).
    ch1_preroll_calls = [
        c for c in mock_repo.insert_preroll.call_args_list
        if c.args[0] == 501
    ]
    assert len(ch1_preroll_calls) == 2, (
        f"Channel 1 must have 2 preroll inserts; got {len(ch1_preroll_calls)}"
    )
    # Channel 2's prerolls were NEVER inserted (streams loop raised first).
    ch2_preroll_calls = [
        c for c in mock_repo.insert_preroll.call_args_list
        if c.args[0] == 502
    ]
    assert ch2_preroll_calls == [], (
        f"Phase 83 Pitfall 4 ordering invariant violated: ch2 preroll inserts "
        f"happened before the streams-loop raise. Found: {ch2_preroll_calls!r}"
    )
    # Channel 1 also got the D-04 marker; channel 2 did NOT (raised before the
    # marker line).
    marker_station_ids = [
        c.args[0] for c in mock_repo.set_prerolls_fetched_at.call_args_list
    ]
    assert marker_station_ids == [501], (
        f"Only the cleanly-imported channel should get the D-04 marker; got "
        f"{marker_station_ids!r}"
    )

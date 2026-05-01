"""Tests for musicstreamer.playlist_parser — Phase 58 / STR-15 / D-09..D-19.

Pure parser tests. No Qt, no I/O patching — fixtures are body literals
passed directly into parse_playlist.
"""
from __future__ import annotations

import pytest

from musicstreamer.playlist_parser import (
    parse_playlist,
    _extract_bitrate,
    _extract_codec,
)


# ---------------------------------------------------------------------------
# Fixture body strings (module-level constants — match RESEARCH §Q1 examples)
# ---------------------------------------------------------------------------

_PLS_BASIC = """\
[playlist]
NumberOfEntries=2
File1=http://prem1.di.fm:80/ambient_hi?key
Title1=Ambient 320k AAC+
File2=http://prem4.di.fm:80/ambient_hi?key
Title2=Ambient 320k AAC+ (fallback)
Length1=-1
Length2=-1
Version=2
"""

_PLS_OUT_OF_ORDER = """\
[playlist]
File2=http://second.example/stream
Title2=Second 192k MP3
File1=http://first.example/stream
Title1=First 320k AAC
"""

_PLS_MISSING_TITLE = """\
[playlist]
File1=http://s1.example/stream
File2=http://s2.example/stream
Title2=Has Title 96k OGG
"""

_PLS_CASE_VARIANT = "[playlist]\nfile1=http://lower.example\nTITLE1=Lowercase File 64k AAC\n"

_PLS_BOM = "﻿[playlist]\nFile1=http://bom.example\nTitle1=BOM 128k MP3\n"

_PLS_CRLF = "[playlist]\r\nFile1=http://crlf.example\r\nTitle1=CRLF 64k MP3\r\n"

_M3U_WITH_EXTINF = """\
#EXTM3U
#EXTINF:-1,Station One 128k AAC
http://stream1.example/aac
#EXTINF:-1,Station Two 64k OGG
http://stream2.example/ogg
"""

_M3U_NO_HEADER = "#EXTINF:-1,Plain M3U 96k MP3\nhttp://plain.example\n"

_M3U_NO_EXTINF = "http://no-meta.example/stream\n"

_M3U_EXTENDED_ATTRS = '#EXTINF:-1 tvg-id="x" tvg-name="y",Display Name 320k FLAC\nhttp://ext-attr.example\n'

_M3U_OTHER_DIRECTIVES = """\
#EXTM3U
#EXTINF:-1,Real Display 128k AAC
#EXT-X-STREAM-INF:BANDWIDTH=128000
http://hls.example/stream.m3u8
"""

_XSPF_BASIC = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<playlist version="1" xmlns="http://xspf.org/ns/0/">\n'
    b'  <trackList>\n'
    b'    <track>\n'
    b'      <location>http://xspf1.example/stream</location>\n'
    b'      <title>XSPF Track 96k OGG</title>\n'
    b'    </track>\n'
    b'    <track>\n'
    b'      <location>http://xspf2.example/stream</location>\n'
    b'      <title>XSPF Track 2 192k MP3</title>\n'
    b'    </track>\n'
    b'  </trackList>\n'
    b'</playlist>'
)

_XSPF_NO_LOCATION = (
    b'<?xml version="1.0"?>'
    b'<playlist xmlns="http://xspf.org/ns/0/">'
    b'<trackList>'
    b'<track><title>No Location 128k AAC</title></track>'
    b'</trackList>'
    b'</playlist>'
)

_XSPF_NO_TITLE = (
    b'<?xml version="1.0"?>'
    b'<playlist xmlns="http://xspf.org/ns/0/">'
    b'<trackList>'
    b'<track><location>http://no-title.example</location></track>'
    b'</trackList>'
    b'</playlist>'
)

_XSPF_MALFORMED = b'<not-xml-at-all'


# ---------------------------------------------------------------------------
# PLS tests
# ---------------------------------------------------------------------------

def test_parse_pls_single_entry():
    """Basic single-entry PLS: dict with title, bitrate, codec extracted from title."""
    body = "[playlist]\nFile1=http://s.mp3\nTitle1=Test 128k MP3\n"
    result = parse_playlist(body, url_hint="http://host/playlist.pls")
    assert result == [{
        "url": "http://s.mp3",
        "title": "Test 128k MP3",
        "bitrate_kbps": 128,
        "codec": "MP3",
    }]


def test_parse_pls_multiple_entries_file_order():
    """Out-of-numeric-order FileN entries are returned in numeric N order (gap-06)."""
    result = parse_playlist(_PLS_OUT_OF_ORDER, url_hint="x.pls")
    assert len(result) == 2
    # File1 must come first even though it appears second in the body (gap-06)
    assert result[0]["url"] == "http://first.example/stream"
    assert result[1]["url"] == "http://second.example/stream"


def test_parse_pls_missing_title():
    """FileN without matching TitleN yields title='', bitrate=0, codec=''."""
    result = parse_playlist(_PLS_MISSING_TITLE, url_hint="x.pls")
    assert len(result) == 2
    assert result[0]["title"] == ""
    assert result[0]["bitrate_kbps"] == 0
    assert result[0]["codec"] == ""
    # File2 has a title
    assert result[1]["title"] == "Has Title 96k OGG"
    assert result[1]["bitrate_kbps"] == 96
    assert result[1]["codec"] == "OGG"


def test_parse_pls_case_variant_keys():
    """`file1=` and `FILE1=` both parsed (re.IGNORECASE)."""
    result = parse_playlist(_PLS_CASE_VARIANT, url_hint="x.pls")
    assert len(result) == 1
    assert result[0]["url"] == "http://lower.example"
    assert result[0]["title"] == "Lowercase File 64k AAC"
    assert result[0]["bitrate_kbps"] == 64
    assert result[0]["codec"] == "AAC"


def test_parse_pls_bom_prefix():
    """Body with U+FEFF BOM prefix on first line is parsed correctly (BOM stripped)."""
    result = parse_playlist(_PLS_BOM, url_hint="x.pls")
    assert len(result) == 1
    assert result[0]["url"] == "http://bom.example"
    assert result[0]["title"] == "BOM 128k MP3"


def test_parse_pls_crlf_line_endings():
    """Body with \\r\\n line endings is parsed correctly."""
    result = parse_playlist(_PLS_CRLF, url_hint="x.pls")
    assert len(result) == 1
    assert result[0]["url"] == "http://crlf.example"
    assert result[0]["title"] == "CRLF 64k MP3"


def test_parse_pls_accepts_bytes():
    """body=bytes is decoded internally (D-17)."""
    body_bytes = b"[playlist]\nFile1=http://bytes.example\nTitle1=Bytes 64k MP3\n"
    result = parse_playlist(body_bytes, url_hint="x.pls")
    assert len(result) == 1
    assert result[0]["url"] == "http://bytes.example"
    assert result[0]["bitrate_kbps"] == 64
    assert result[0]["codec"] == "MP3"


# ---------------------------------------------------------------------------
# M3U tests (D-12)
# ---------------------------------------------------------------------------

def test_parse_m3u_with_extinf():
    """Standard #EXTM3U + #EXTINF + URL -> one entry with title from #EXTINF."""
    result = parse_playlist(_M3U_WITH_EXTINF, url_hint="x.m3u")
    assert len(result) == 2
    assert result[0]["url"] == "http://stream1.example/aac"
    assert result[0]["title"] == "Station One 128k AAC"
    assert result[0]["bitrate_kbps"] == 128
    assert result[0]["codec"] == "AAC"
    assert result[1]["url"] == "http://stream2.example/ogg"
    assert result[1]["title"] == "Station Two 64k OGG"


def test_parse_m3u_no_extinf_header():
    """Plain M3U without #EXTM3U header still parses URLs."""
    result = parse_playlist(_M3U_NO_HEADER, url_hint="x.m3u")
    assert len(result) == 1
    assert result[0]["url"] == "http://plain.example"
    assert result[0]["title"] == "Plain M3U 96k MP3"


def test_parse_m3u_url_no_preceding_extinf():
    """URL line with no preceding #EXTINF -> title=''."""
    result = parse_playlist(_M3U_NO_EXTINF, url_hint="x.m3u")
    assert len(result) == 1
    assert result[0]["url"] == "http://no-meta.example/stream"
    assert result[0]["title"] == ""
    assert result[0]["bitrate_kbps"] == 0
    assert result[0]["codec"] == ""


def test_parse_m3u_extended_attributes():
    """`#EXTINF:-1 attr1="v",Display Name` -> title is text after first comma (D-12)."""
    result = parse_playlist(_M3U_EXTENDED_ATTRS, url_hint="x.m3u")
    assert len(result) == 1
    assert result[0]["title"] == "Display Name 320k FLAC"
    assert result[0]["bitrate_kbps"] == 320
    assert result[0]["codec"] == "FLAC"


def test_parse_m3u_skips_other_directives():
    """#EXT-X-STREAM-INF lines do NOT clear prev_extinf; title is preserved."""
    result = parse_playlist(_M3U_OTHER_DIRECTIVES, url_hint="x.m3u")
    assert len(result) == 1
    # Despite the #EXT-X-STREAM-INF directive between #EXTINF and the URL,
    # the prev_extinf should still be paired with the URL.
    assert result[0]["title"] == "Real Display 128k AAC"
    assert result[0]["url"] == "http://hls.example/stream.m3u8"


def test_parse_m3u8_via_extension():
    """url_hint='x.m3u8' routes to _parse_m3u."""
    body = "#EXTM3U\n#EXTINF:-1,HLS Stream 320k AAC\nhttp://hls.example/stream\n"
    result = parse_playlist(body, url_hint="x.m3u8")
    assert len(result) == 1
    assert result[0]["title"] == "HLS Stream 320k AAC"
    assert result[0]["codec"] == "AAC"


# ---------------------------------------------------------------------------
# XSPF tests (D-13)
# ---------------------------------------------------------------------------

def test_parse_xspf_basic():
    """Well-formed XSPF with default namespace -> one entry per <track>."""
    result = parse_playlist(_XSPF_BASIC, url_hint="playlist.xspf")
    assert len(result) == 2
    assert result[0]["url"] == "http://xspf1.example/stream"
    assert result[0]["title"] == "XSPF Track 96k OGG"
    assert result[0]["bitrate_kbps"] == 96
    assert result[0]["codec"] == "OGG"
    assert result[1]["url"] == "http://xspf2.example/stream"
    assert result[1]["title"] == "XSPF Track 2 192k MP3"


def test_parse_xspf_track_without_location_skipped():
    """<track> with no <location> is skipped (not a crash)."""
    result = parse_playlist(_XSPF_NO_LOCATION, url_hint="x.xspf")
    assert result == []


def test_parse_xspf_missing_title():
    """<track> with <location> but no <title> -> title=''."""
    result = parse_playlist(_XSPF_NO_TITLE, url_hint="x.xspf")
    assert len(result) == 1
    assert result[0]["url"] == "http://no-title.example"
    assert result[0]["title"] == ""
    assert result[0]["bitrate_kbps"] == 0
    assert result[0]["codec"] == ""


def test_parse_xspf_malformed_returns_empty():
    """Invalid XML body -> returns [] (not a crash) (D-13 ET.ParseError catch)."""
    result = parse_playlist(_XSPF_MALFORMED, url_hint="x.xspf")
    assert result == []


def test_parse_xspf_accepts_bytes_input():
    """body=bytes parses correctly (D-17 — XSPF passes bytes to ET.fromstring)."""
    result = parse_playlist(_XSPF_BASIC, url_hint="x.xspf")
    assert len(result) == 2
    assert result[0]["url"] == "http://xspf1.example/stream"


def test_parse_xspf_accepts_str_input():
    """body=str is encoded to bytes and parses correctly (D-17)."""
    body_str = _XSPF_BASIC.decode("utf-8")
    result = parse_playlist(body_str, url_hint="x.xspf")
    assert len(result) == 2
    assert result[0]["url"] == "http://xspf1.example/stream"


# ---------------------------------------------------------------------------
# Format dispatch tests (D-19)
# ---------------------------------------------------------------------------

def test_dispatch_unknown_format_returns_empty():
    """url_hint='x.txt', content_type='text/plain' -> [] (no body sniffing per D-19)."""
    result = parse_playlist("anything", url_hint="x.txt", content_type="text/plain")
    assert result == []


def test_dispatch_extension_takes_precedence():
    """url_hint extension wins over content_type: url_hint=.pls + content_type=xspf -> PLS parsed."""
    # Empty PLS body returns [] (no FileN entries) even though content_type says xspf
    result = parse_playlist("", url_hint="x.pls", content_type="application/xspf+xml")
    assert result == []  # empty PLS body, but PLS dispatch was used (not XSPF)


def test_dispatch_extension_pls_vs_xspf_content():
    """url_hint=.pls with an XSPF body: PLS parser gets called, not XSPF parser."""
    xspf_str = _XSPF_BASIC.decode("utf-8")
    # This should use PLS parser (which won't find FileN lines) -> []
    result = parse_playlist(xspf_str, url_hint="playlist.pls", content_type="application/xspf+xml")
    assert result == []  # PLS parser sees no FileN= entries


def test_dispatch_content_type_fallback_pls():
    """url_hint='' + content_type='audio/x-scpls' -> PLS parsed."""
    body = "[playlist]\nFile1=http://scpls.example\nTitle1=SCPLS 128k MP3\n"
    result = parse_playlist(body, url_hint="", content_type="audio/x-scpls")
    assert len(result) == 1
    assert result[0]["url"] == "http://scpls.example"


def test_dispatch_content_type_with_charset():
    """content_type='audio/x-scpls; charset=utf-8' -> PLS parsed (substring match)."""
    body = "[playlist]\nFile1=http://charset.example\nTitle1=Charset 64k AAC\n"
    result = parse_playlist(body, content_type="audio/x-scpls; charset=utf-8")
    assert len(result) == 1
    assert result[0]["url"] == "http://charset.example"


def test_dispatch_content_type_fallback_m3u():
    """content_type='application/vnd.apple.mpegurl' -> M3U parsed."""
    body = "#EXTM3U\n#EXTINF:-1,Apple HLS 96k AAC\nhttp://apple.example/stream\n"
    result = parse_playlist(body, content_type="application/vnd.apple.mpegurl")
    assert len(result) == 1
    assert result[0]["title"] == "Apple HLS 96k AAC"


def test_dispatch_content_type_fallback_xspf():
    """content_type='application/xspf+xml' -> XSPF parsed."""
    result = parse_playlist(_XSPF_BASIC, content_type="application/xspf+xml")
    assert len(result) == 2


def test_dispatch_no_body_sniffing():
    """[playlist] body with url_hint=x.txt content_type=text/plain -> [] (no body sniffing per D-19)."""
    body = "[playlist]\nFile1=http://x"
    result = parse_playlist(body, url_hint="x.txt", content_type="text/plain")
    assert result == []


# ---------------------------------------------------------------------------
# Bitrate / codec extraction tests (D-11 / D-15)
# ---------------------------------------------------------------------------

def test_extract_bitrate_basic_cases():
    """Various bitrate string forms all extract correctly; no match -> 0."""
    cases = [
        ("HE-AAC 64kbps", 64),
        ("Radio Paradise 320 kbps MP3", 320),
        ("DI.fm 64kb", 64),
        ("OGG 96K stream", 96),
        ("BBC Radio (No bitrate)", 0),
        ("Jazz 192 Kbps", 192),
        ("FLAC 1000kbps", 1000),
    ]
    for title, expected in cases:
        assert _extract_bitrate(title) == expected, f"Failed: {title!r}"


def test_extract_codec_priority_order():
    """HE-AAC matched before AAC; AAC+ matched before AAC (priority order)."""
    # HE-AAC must be matched before AAC (priority order; "HE-AAC" contains "AAC" substring)
    assert _extract_codec("DI.fm 64kbps HE-AAC") == "HE-AAC"
    assert _extract_codec("AAC+ 96k station") == "AAC+"
    assert _extract_codec("Plain 128k AAC") == "AAC"


def test_extract_codec_no_match_returns_empty_string():
    """No recognized token in title -> '' (D-15: never 'unknown', never None)."""
    result = _extract_codec("BBC Radio")
    assert result == ""
    assert result is not None
    # Ensure type is exactly str
    assert isinstance(result, str)


def test_extract_codec_known_gap_heaacv2():
    """RESEARCH Finding 3: HEAACv2 contains substring 'AAC' (not 'HE-AAC') — known acceptable."""
    # HEAACv2 does not match "HE-AAC" (substring check fails because "HE-AAC" != "HEAAC")
    # but it does match "AAC" — same codec family for ordering, acceptable per RESEARCH.
    assert _extract_codec("HEAACv2 64k") == "AAC"


def test_extract_codec_known_gap_vorbis():
    """RESEARCH Finding 4: VORBIS returns '' — not in v1 token list per D-11."""
    assert _extract_codec("VORBIS 128k") == ""


def test_extract_bitrate_case_insensitive():
    """Bitrate regex is case-insensitive (D-11)."""
    assert _extract_bitrate("HE-AAC 64KBPS") == 64
    assert _extract_bitrate("128Kb") == 128
    assert _extract_bitrate("64KBps station") == 64


def test_extract_codec_ogg_flac_opus():
    """OGG, FLAC, and OPUS tokens all recognized."""
    assert _extract_codec("OGG 64k stream") == "OGG"
    assert _extract_codec("FLAC lossless 1000k") == "FLAC"
    assert _extract_codec("OPUS 96k experimental") == "OPUS"


def test_extract_codec_wma_mp3():
    """WMA and MP3 tokens recognized."""
    assert _extract_codec("WMA 64k Windows") == "WMA"
    assert _extract_codec("Classic MP3 128k") == "MP3"

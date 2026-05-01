"""Phase 51 / BUG-02: pure unit tests for find_aa_siblings.

Modeled on tests/test_aa_url_detection.py — no Qt, no fixtures, one assertion
per test. Tests assert the contract of
find_aa_siblings(stations, current_station_id, current_first_url)
-> list[tuple[network_slug, station_id, station_name]].
"""
from musicstreamer.models import Station, StationStream
from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html


def _mk(id_, name, url):
    """Factory: a minimal Station with one StationStream at `url`."""
    return Station(
        id=id_,
        name=name,
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[StationStream(id=id_ * 10, station_id=id_, url=url, position=1)],
    )


def test_finds_zenradio_sibling_for_difm_ambient():
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _mk(2, "Ambient", "http://prem4.zenradio.com/zrambient?listen_key=abc")
    siblings = find_aa_siblings([di, zr], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == [("zenradio", 2, "Ambient")]


def test_finds_jazzradio_sibling():
    """JazzRadio + ZenRadio cross-network match — zr prefix stripped from candidate."""
    jz = _mk(1, "AfroJazz", "http://prem1.jazzradio.com:80/afrojazz?listen_key=abc")
    zr = _mk(2, "AfroJazz", "http://prem1.zenradio.com:80/zrafrojazz?listen_key=abc")
    siblings = find_aa_siblings([jz, zr], current_station_id=1, current_first_url=jz.streams[0].url)
    assert siblings == [("zenradio", 2, "AfroJazz")]


def test_excludes_self_by_id():
    """Current station must never be in the result, even if a duplicate-id station shares the key."""
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    siblings = find_aa_siblings([di], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == []


def test_excludes_same_network_same_key():
    """Two DI.fm stations with the same channel_key — not siblings (must be cross-network)."""
    di1 = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    di2 = _mk(2, "Ambient (other)", "http://prem2.di.fm:80/ambient_hi?listen_key=abc")
    siblings = find_aa_siblings([di1, di2], current_station_id=1, current_first_url=di1.streams[0].url)
    assert siblings == []


def test_excludes_non_aa_candidates():
    """YouTube and Radio-Browser stations must be silently filtered."""
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    yt = _mk(2, "YT Ambient", "https://www.youtube.com/watch?v=abc")
    rb = _mk(3, "RB Ambient", "http://radiobrowser.example/ambient")
    siblings = find_aa_siblings([di, yt, rb], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == []


def test_excludes_candidate_with_unparseable_url():
    """Candidate whose first URL has no path segment is filtered, no exception raised."""
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    bad = _mk(2, "Ambient", "http://di.fm")  # AA domain but no path → no key
    siblings = find_aa_siblings([di, bad], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == []


def test_returns_empty_when_current_is_non_aa():
    """Non-AA current URL → returns [] (D-04 enforcement at helper level)."""
    di = _mk(2, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    siblings = find_aa_siblings([di], current_station_id=1, current_first_url="https://www.youtube.com/watch?v=abc")
    assert siblings == []


def test_returns_empty_when_current_url_has_no_channel_key():
    """AA domain but empty path → channel_key is None → returns [] gracefully."""
    di = _mk(2, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    siblings = find_aa_siblings([di], current_station_id=1, current_first_url="http://di.fm")
    assert siblings == []


def test_returns_empty_when_current_station_has_no_streams():
    """Caller passes empty current_first_url → returns [] (no AA gate match)."""
    di = _mk(2, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    siblings = find_aa_siblings([di], current_station_id=1, current_first_url="")
    assert siblings == []


def test_sort_order_matches_networks_declaration():
    """Multiple siblings sort by NETWORKS index: di < radiotunes < jazzradio < rockradio < classicalradio < zenradio."""
    current = _mk(1, "Classical", "http://prem1.di.fm:80/classical_hi?listen_key=abc")
    cr = _mk(2, "Classical", "http://prem1.classicalradio.com/classical_hi")
    zr = _mk(3, "Classical", "http://prem1.zenradio.com/zrclassical")
    rt = _mk(4, "Classical", "http://prem1.radiotunes.com/classical_hi")
    jz = _mk(5, "Classical", "http://prem1.jazzradio.com/classical")
    rr = _mk(6, "Classical", "http://prem1.rockradio.com/classical_hi")
    # Pass candidates in scrambled order to prove the helper sorts them.
    siblings = find_aa_siblings([current, cr, zr, rt, jz, rr], current_station_id=1, current_first_url=current.streams[0].url)
    assert [t[0] for t in siblings] == ["radiotunes", "jazzradio", "rockradio", "classicalradio", "zenradio"]


def test_link_text_payload_is_station_name():
    """When sibling station's name differs, the helper returns the sibling's actual name in tuple[2] (D-08 — rendering decides display)."""
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _mk(2, "Zen Ambient Vibes", "http://prem4.zenradio.com/zrambient?listen_key=abc")
    siblings = find_aa_siblings([di, zr], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == [("zenradio", 2, "Zen Ambient Vibes")]


# --- Cross-network identity: same channel concept, different per-network API keys ---

def test_finds_sibling_via_cross_network_identity_spacedreams():
    """DI.fm 'Space Dreams' has API key 'spacemusic'; ZenRadio 'Space Dreams' has key
    'spacedreams'. _AA_CROSS_NETWORK_KEYS normalizes both to 'spacedreams' so
    find_aa_siblings still pairs them as cross-network siblings.
    """
    di = _mk(1, "Space Dreams", "http://prem1.di.fm:80/spacemusic_hi?listen_key=abc")
    zr = _mk(2, "Space Dreams", "http://prem4.zenradio.com:80/zrspacedreams?listen_key=abc")
    siblings = find_aa_siblings([di, zr], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == [("zenradio", 2, "Space Dreams")]


def test_finds_sibling_via_cross_network_identity_alternativerock():
    """RadioTunes 'Alternative Rock' API key 'altrock' vs RockRadio 'alternativerock'."""
    rt = _mk(1, "Alternative Rock", "http://prem1.radiotunes.com:80/altrock_hi?listen_key=abc")
    rr = _mk(2, "Alternative Rock", "http://prem1.rockradio.com:80/alternativerock_hi?listen_key=abc")
    siblings = find_aa_siblings([rt, rr], current_station_id=1, current_first_url=rt.streams[0].url)
    assert siblings == [("rockradio", 2, "Alternative Rock")]


def test_finds_sibling_via_cross_network_identity_baroque():
    """ClassicalRadio 'Baroque Period' key 'baroqueperiod' vs RadioTunes 'baroque'."""
    cr = _mk(1, "Baroque Period", "http://prem1.classicalradio.com:80/baroqueperiod_hi?listen_key=abc")
    rt = _mk(2, "Baroque Period", "http://prem1.radiotunes.com:80/baroque_hi?listen_key=abc")
    siblings = find_aa_siblings([cr, rt], current_station_id=1, current_first_url=cr.streams[0].url)
    assert siblings == [("radiotunes", 2, "Baroque Period")]


def test_finds_sibling_via_cross_network_identity_romantic():
    """ClassicalRadio 'Romantic Period' key 'romanticperiod' vs RadioTunes 'romantic'."""
    cr = _mk(1, "Romantic Period", "http://prem1.classicalradio.com:80/romanticperiod_hi?listen_key=abc")
    rt = _mk(2, "Romantic Period", "http://prem1.radiotunes.com:80/romantic_hi?listen_key=abc")
    siblings = find_aa_siblings([cr, rt], current_station_id=1, current_first_url=cr.streams[0].url)
    assert siblings == [("radiotunes", 2, "Romantic Period")]


def test_finds_sibling_via_radiotunes_rt_prefix_stripping():
    """RadioTunes URLs may carry an 'rt' prefix (e.g. /rtambient). Sibling
    detection must work whether the candidate or the current station is the
    rt-prefixed one. Here current is RT, candidate is DI.
    """
    rt = _mk(1, "Ambient", "http://prem1.radiotunes.com:80/rtambient_hi?listen_key=abc")
    di = _mk(2, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    siblings = find_aa_siblings([rt, di], current_station_id=1, current_first_url=rt.streams[0].url)
    assert siblings == [("di", 2, "Ambient")]


def test_excludes_candidate_with_empty_streams_list():
    """Candidate Station with streams=[] is filtered, no IndexError."""
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    empty = Station(
        id=2,
        name="Ambient",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[],
    )
    siblings = find_aa_siblings([di, empty], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == []


# ---------------------------------------------------------------------------
# Phase 64 / D-03: render_sibling_html (promoted from EditStationDialog)
# ---------------------------------------------------------------------------


def test_render_sibling_html_basic_link():
    """Phase 64 / D-03 / Phase 51 D-07, D-08: single same-name sibling renders
    'Also on: <a href="sibling://{id}">{network_display}</a>' (network-only)."""
    siblings = [("zenradio", 2, "Ambient")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert out == 'Also on: <a href="sibling://2">ZenRadio</a>'


def test_render_sibling_html_uses_em_dash_when_names_differ():
    """Phase 64 / D-03 / Phase 51 D-08: name mismatch -> 'Network — Name'
    with literal U+2014 EM DASH between network and name."""
    siblings = [("zenradio", 2, "Ambient (Sleep)")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert "ZenRadio — Ambient (Sleep)" in out
    assert "—" in out  # U+2014 EM DASH literal in the output
    assert 'href="sibling://2"' in out


def test_render_sibling_html_html_escapes_station_name():
    """Phase 64 / D-03 / T-39-01 deviation mitigation preserved: malicious
    sibling name with HTML metachars must be escaped — raw '<script>'
    must NOT appear in the output."""
    siblings = [("zenradio", 2, "<script>alert(1)</script>")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "alert(1)" in out  # the text content survives escaping


def test_render_sibling_html_uses_bullet_separator_for_multiple():
    """Phase 64 / D-03 / Phase 51 D-07: multiple siblings joined with ' • '
    (literal U+2022 BULLET surrounded by single spaces)."""
    siblings = [("jazzradio", 2, "Ambient"), ("zenradio", 3, "Ambient")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert " • " in out  # U+2022 BULLET surrounded by spaces
    assert out.count("<a ") == 2
    assert 'href="sibling://2"' in out
    assert 'href="sibling://3"' in out


def test_render_sibling_html_unknown_slug_falls_back_to_slug_literal():
    """Phase 64 / D-03 defensive: a slug not in NETWORKS renders as the slug
    string itself (dict.get fallback). Should not crash; should not raise."""
    siblings = [("not_a_real_slug", 9, "Ambient")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert "not_a_real_slug" in out
    assert 'href="sibling://9"' in out

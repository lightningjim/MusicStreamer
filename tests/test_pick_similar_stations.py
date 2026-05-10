"""Phase 67: pure unit tests for pick_similar_stations + render_similar_html.

Modeled on tests/test_aa_siblings.py — no Qt, no fixtures, one assertion
per test. Tests assert the contract of:

    pick_similar_stations(
        stations: list[Station],
        current_station: Station,
        *, sample_size: int = 5, rng: random.Random | None = None
    ) -> tuple[list[Station], list[Station]]

    render_similar_html(
        stations: list[Station],
        *, show_provider: bool, href_prefix: str = "similar://"
    ) -> str
"""
import random
import time
from musicstreamer.models import Station, StationStream
from musicstreamer.url_helpers import pick_similar_stations, render_similar_html


def _mk(id_, name, url, *, provider_id=None, provider_name=None, tags=""):
    """Factory: a minimal Station with one StationStream at `url`.

    Extends tests/test_aa_siblings.py:12-23 _mk with three keyword args
    for Phase 67's provider/tag-aware pool derivation tests.
    """
    return Station(
        id=id_,
        name=name,
        provider_id=provider_id,
        provider_name=provider_name,
        tags=tags,
        station_art_path=None,
        album_fallback_path=None,
        streams=[StationStream(id=id_ * 10, station_id=id_, url=url, position=1)],
    )


# ---------------------------------------------------------------------------
# SIM-04: Same provider pool
# ---------------------------------------------------------------------------


def test_same_provider_pool_excludes_self_aa_and_no_provider():
    """Phase 67 / SIM-04 / T-04: same-provider pool excludes self, AA siblings,
    and no-provider candidates (T-04a/b/d)."""
    # current = SomaFM station (non-AA URL so no AA siblings)
    current = _mk(1, "Drone Zone", "http://somafm.com/droneZone.pls",
                  provider_id=1, provider_name="SomaFM", tags="ambient")
    somafm_other = _mk(2, "Space Station Soma", "http://somafm.com/spaceStation.pls",
                       provider_id=1, provider_name="SomaFM", tags="ambient")
    other_provider = _mk(3, "Jazz Station", "http://other.fm/jazz",
                         provider_id=2, provider_name="OtherFM", tags="jazz")
    no_provider_station = _mk(4, "Unknown", "http://unknown.fm/stream",
                              provider_id=None, provider_name=None, tags="ambient")
    stations = [current, somafm_other, other_provider, no_provider_station]
    same_provider, _ = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert same_provider == [somafm_other]


def test_same_provider_pool_lt_5_returns_all():
    """Phase 67 / SIM-04 / R-05: pool of 3 candidates returns all 3 (no padding)."""
    current = _mk(1, "Drone Zone", "http://somafm.com/droneZone.pls",
                  provider_id=1, provider_name="SomaFM", tags="ambient")
    s2 = _mk(2, "Spa", "http://somafm.com/spa.pls", provider_id=1, provider_name="SomaFM")
    s3 = _mk(3, "Lush", "http://somafm.com/lush.pls", provider_id=1, provider_name="SomaFM")
    s4 = _mk(4, "Groove", "http://somafm.com/grooveSalad.pls", provider_id=1, provider_name="SomaFM")
    stations = [current, s2, s3, s4]
    same_provider, _ = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert len(same_provider) == 3


def test_same_provider_pool_empty_when_current_provider_id_is_none():
    """Phase 67 / SIM-04 / T-04d: current.provider_id=None -> same_provider list is empty."""
    current = _mk(1, "Drone Zone", "http://somafm.com/droneZone.pls",
                  provider_id=None, provider_name=None, tags="ambient")
    other = _mk(2, "Spa", "http://somafm.com/spa.pls",
                provider_id=1, provider_name="SomaFM", tags="ambient")
    stations = [current, other]
    same_provider, _ = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert same_provider == []


# ---------------------------------------------------------------------------
# SIM-05: Same tag pool
# ---------------------------------------------------------------------------


def test_same_tag_pool_union_semantics():
    """Phase 67 / SIM-05 / T-01: union semantics — candidates with any overlapping
    tag qualify; no-overlap and empty-tag candidates are excluded."""
    current = _mk(1, "Current", "http://example.com/current",
                  provider_id=1, provider_name="P1", tags="ambient, electronic")
    ambient_only = _mk(2, "Ambient", "http://example.com/a",
                       provider_id=2, provider_name="P2", tags="ambient")
    electronic_downtempo = _mk(3, "Elec", "http://example.com/b",
                               provider_id=2, provider_name="P2", tags="electronic, downtempo")
    rock = _mk(4, "Rock", "http://example.com/c",
               provider_id=2, provider_name="P2", tags="rock")
    empty_tags = _mk(5, "NoTags", "http://example.com/d",
                     provider_id=2, provider_name="P2", tags="")
    stations = [current, ambient_only, electronic_downtempo, rock, empty_tags]
    _, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert set(s.id for s in same_tag) == {2, 3}


def test_same_tag_pool_lt_5_returns_all():
    """Phase 67 / SIM-05 / R-06: pool of 2 candidates returns all 2."""
    current = _mk(1, "Current", "http://example.com/c",
                  provider_id=1, provider_name="P1", tags="ambient")
    s2 = _mk(2, "A", "http://example.com/a", provider_id=2, provider_name="P2", tags="ambient")
    s3 = _mk(3, "B", "http://example.com/b", provider_id=2, provider_name="P2", tags="ambient")
    stations = [current, s2, s3]
    _, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert len(same_tag) == 2


def test_same_tag_pool_uses_normalize_tags():
    """Phase 67 / SIM-05: normalize_tags is applied — case-folded matching active
    so 'AMBIENT' matches current tag 'Ambient'."""
    current = _mk(1, "Current", "http://example.com/c",
                  provider_id=1, provider_name="P1", tags="Ambient, Electronic")
    candidate = _mk(2, "Cand", "http://example.com/a",
                    provider_id=2, provider_name="P2", tags="AMBIENT")
    stations = [current, candidate]
    _, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert candidate in same_tag


# ---------------------------------------------------------------------------
# Combined behavior
# ---------------------------------------------------------------------------


def test_pools_allow_cross_pool_duplicates():
    """Phase 67 / T-03: a station qualifying in BOTH pools appears in both
    (no cross-pool dedup performed)."""
    current = _mk(1, "Current", "http://example.com/current",
                  provider_id=1, provider_name="P1", tags="ambient")
    # Both same provider AND same tag as current
    both = _mk(2, "Both", "http://example.com/both",
               provider_id=1, provider_name="P1", tags="ambient")
    stations = [current, both]
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert both in same_provider
    assert both in same_tag


def test_seeded_rng_reproducibility():
    """Phase 67 / R-05/R-06: two calls with same seed produce identical output."""
    current = _mk(1, "Current", "http://example.com/c",
                  provider_id=1, provider_name="P1", tags="rock")
    stations = [current] + [
        _mk(i, f"S{i}", f"http://example.com/{i}",
            provider_id=1, provider_name="P1", tags="rock")
        for i in range(2, 12)
    ]
    result1 = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    result2 = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert result1 == result2


def test_aa_siblings_excluded_from_both_pools():
    """Phase 67 / T-04b: AA cross-network sibling excluded from both pools."""
    # current is DI.fm; zr is a ZenRadio cross-network sibling (same channel key)
    # Both share provider_id=1 and tags="ambient" so they would qualify in both pools
    # but the AA sibling should be excluded via find_aa_siblings
    current = _mk(1, "Ambient", "http://prem1.di.fm:80/di_ambient_hi?listen_key=abc",
                  provider_id=1, provider_name="AudioAddict", tags="ambient")
    zr_sibling = _mk(2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc",
                     provider_id=1, provider_name="AudioAddict", tags="ambient")
    stations = [current, zr_sibling]
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert zr_sibling not in same_provider
    assert zr_sibling not in same_tag


def test_empty_library_returns_empty_pools():
    """Phase 67 / SIM-04+05: library with only the current station returns empty pools."""
    current = _mk(1, "Current", "http://example.com/c",
                  provider_id=1, provider_name="P1", tags="ambient")
    stations = [current]
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert same_provider == []
    assert same_tag == []


def test_no_provider_no_tags_returns_empty_pools():
    """Phase 67 / T-04: current with no provider_id and no tags returns empty pools."""
    current = _mk(1, "Current", "http://example.com/c",
                  provider_id=None, provider_name=None, tags="")
    other = _mk(2, "Other", "http://example.com/o",
                provider_id=1, provider_name="P1", tags="ambient")
    stations = [current, other]
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert same_provider == []
    assert same_tag == []


def test_perf_500_stations_under_50ms():
    """Phase 67 / SIM-04+05: 500-station library returns in < 50ms."""
    # Mix: 250 same-provider candidates, 250 different-provider, varied tags
    current = _mk(0, "Current", "http://example.com/current",
                  provider_id=1, provider_name="P1", tags="rock, pop")
    stations = [current]
    for i in range(1, 251):
        stations.append(_mk(i, f"S{i}", f"http://example.com/{i}",
                            provider_id=1, provider_name="P1", tags="rock"))
    for i in range(251, 501):
        stations.append(_mk(i, f"S{i}", f"http://example.com/{i}",
                            provider_id=2, provider_name="P2", tags="pop"))
    start = time.perf_counter()
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    delta = time.perf_counter() - start
    assert delta < 0.050, f"pick_similar_stations took {delta*1000:.1f}ms (budget 50ms)"


def test_pick_similar_stations_handles_current_with_empty_streams():
    """Phase 67 / RESEARCH Pitfall 11: current.streams=[] skips AA exclusion
    silently — does not raise IndexError."""
    # Create a station with empty streams
    current = Station(
        id=1,
        name="Current",
        provider_id=1,
        provider_name="P1",
        tags="ambient",
        station_art_path=None,
        album_fallback_path=None,
        streams=[],
    )
    other = _mk(2, "Other", "http://example.com/o",
                provider_id=1, provider_name="P1", tags="ambient")
    stations = [current, other]
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert other in same_provider


# ---------------------------------------------------------------------------
# SIM-09: render_similar_html
# ---------------------------------------------------------------------------


def test_render_similar_html_provider_section_no_provider_in_text():
    """Phase 67 / SIM-09: show_provider=False renders only station name."""
    s = _mk(1, "Drone Zone", "http://somafm.com/d", provider_id=1, provider_name="SomaFM")
    out = render_similar_html([s], show_provider=False)
    assert ">Drone Zone</a>" in out
    assert "(SomaFM)" not in out


def test_render_similar_html_tag_section_includes_provider():
    """Phase 67 / SIM-09: show_provider=True renders '{Name} ({Provider})'."""
    s = _mk(1, "Drone Zone", "http://somafm.com/d", provider_id=1, provider_name="SomaFM")
    out = render_similar_html([s], show_provider=True)
    assert ">Drone Zone (SomaFM)</a>" in out


def test_render_similar_html_escapes_name():
    """Phase 67 / T-39-01 / T-67-02-01: malicious station name is HTML-escaped."""
    s = _mk(1, "<script>alert(1)</script>", "http://example.com/s",
            provider_id=1, provider_name="P1")
    out = render_similar_html([s], show_provider=False)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "alert(1)" in out


def test_render_similar_html_escapes_provider():
    """Phase 67 / RESEARCH Pitfall 7 / T-67-02-02: malicious provider_name is
    HTML-escaped (NEW for Phase 67 — Phase 64 only escaped name)."""
    s = _mk(1, "Station", "http://example.com/s",
            provider_id=1, provider_name="<script>alert(1)</script>")
    out = render_similar_html([s], show_provider=True)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_similar_html_uses_br_separator():
    """Phase 67 / D-03: three stations joined with exactly two '<br>' separators."""
    s1 = _mk(1, "A", "http://example.com/a", provider_id=1, provider_name="P1")
    s2 = _mk(2, "B", "http://example.com/b", provider_id=1, provider_name="P1")
    s3 = _mk(3, "C", "http://example.com/c", provider_id=1, provider_name="P1")
    out = render_similar_html([s1, s2, s3], show_provider=False)
    assert out.count("<br>") == 2


def test_render_similar_html_href_uses_similar_prefix():
    """Phase 67 / RESEARCH Pitfall 8: href always uses 'similar://', never 'sibling://'."""
    s = _mk(1, "A", "http://example.com/a", provider_id=1, provider_name="P1")
    out = render_similar_html([s], show_provider=False)
    assert 'href="similar://' in out
    assert "sibling://" not in out


def test_render_similar_html_href_payload_is_integer_only():
    """Phase 67 / T-67-02-03: href payload is integer-only (Station.id from SQLite)."""
    s = _mk(42, "Station", "http://example.com/s", provider_id=1, provider_name="P1")
    out = render_similar_html([s], show_provider=False)
    assert 'href="similar://42"' in out


def test_render_similar_html_empty_stations_returns_empty_string():
    """Phase 67 / SIM-09: empty stations list returns '' (no leading/trailing <br>)."""
    out = render_similar_html([], show_provider=False)
    assert out == ""


def test_render_similar_html_provider_none_safe():
    """Phase 67 / SIM-09 / T-67-02-02: show_provider=True with provider_name=None
    is handled gracefully via 'provider_name or \"\"'."""
    s = _mk(1, "Station", "http://example.com/s", provider_id=1, provider_name=None)
    out = render_similar_html([s], show_provider=True)
    assert "()" in out or "( )" in out or "Station ()" in out

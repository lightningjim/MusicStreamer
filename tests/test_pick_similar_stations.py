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
# SIM-04: Same-provider pool exclusion rules
# ---------------------------------------------------------------------------

def test_same_provider_pool_excludes_self_aa_and_no_provider():
    """Phase 67 / SIM-04 / T-04: same-provider pool excludes self id, AA sibling,
    and candidates with no provider_id (T-04a/b/d)."""
    # current: SomaFM "Drone Zone", provider_id=1
    current = _mk(1, "Drone Zone", "http://example.com/drone-zone", provider_id=1, provider_name="SomaFM", tags="ambient")
    # same provider, different id — should appear
    somafm_other = _mk(2, "Space Station", "http://example.com/space-station", provider_id=1, provider_name="SomaFM", tags="ambient")
    # AA cross-network sibling (same channel key, different network) — excluded by T-04b
    zenradio_aa_sibling = _mk(3, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc", provider_id=2, provider_name="ZenRadio", tags="ambient")
    # current AA station to pair with sibling
    di_current = _mk(1, "Drone Zone", "http://prem1.di.fm:80/ambient_hi?listen_key=abc", provider_id=1, provider_name="SomaFM", tags="ambient")
    # no provider — excluded by T-04d
    no_provider_station = _mk(4, "Unknown FM", "http://example.com/unknown", provider_id=None, provider_name=None, tags="ambient")

    # Use AA-flavored URLs so sibling detection works
    stations = [di_current, somafm_other, zenradio_aa_sibling, no_provider_station]
    same_provider, _ = pick_similar_stations(stations, di_current, sample_size=5, rng=random.Random(42))
    assert same_provider == [somafm_other]


def test_same_provider_pool_lt_5_returns_all():
    """Phase 67 / SIM-04 / R-05: pool of 3 same-provider candidates returns all 3 (no padding)."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="rock")
    a = _mk(2, "Station A", "http://example.com/a", provider_id=1, provider_name="P1", tags="rock")
    b = _mk(3, "Station B", "http://example.com/b", provider_id=1, provider_name="P1", tags="pop")
    c = _mk(4, "Station C", "http://example.com/c", provider_id=1, provider_name="P1", tags="jazz")
    stations = [current, a, b, c]
    same_provider, _ = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert len(same_provider) == 3


def test_same_provider_pool_empty_when_current_provider_id_is_none():
    """Phase 67 / SIM-04 / T-04d: current.provider_id=None → same_provider list is empty."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=None, provider_name=None, tags="rock")
    other = _mk(2, "Station A", "http://example.com/a", provider_id=1, provider_name="P1", tags="rock")
    stations = [current, other]
    same_provider, _ = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert same_provider == []


# ---------------------------------------------------------------------------
# SIM-05: Same-tag pool semantics
# ---------------------------------------------------------------------------

def test_same_tag_pool_union_semantics():
    """Phase 67 / SIM-05 / T-01: union match — candidate matches if it shares
    ANY tag with current (OR-within-candidate-tags). Excludes self, empty-tag,
    and no-overlap candidates."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="ambient, electronic")
    amb_match = _mk(2, "Ambient Match", "http://example.com/amb", provider_id=2, provider_name="P2", tags="ambient")
    elec_match = _mk(3, "Elec Match", "http://example.com/elec", provider_id=2, provider_name="P2", tags="electronic, downtempo")
    rock_nomatch = _mk(4, "Rock", "http://example.com/rock", provider_id=2, provider_name="P2", tags="rock")
    empty_tag = _mk(5, "No Tags", "http://example.com/empty", provider_id=2, provider_name="P2", tags="")
    stations = [current, amb_match, elec_match, rock_nomatch, empty_tag]
    _, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert set(s.id for s in same_tag) == {2, 3}


def test_same_tag_pool_lt_5_returns_all():
    """Phase 67 / SIM-05 / R-05: pool of 2 same-tag candidates returns all 2 (no padding)."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="jazz")
    a = _mk(2, "A", "http://example.com/a", provider_id=2, provider_name="P2", tags="jazz")
    b = _mk(3, "B", "http://example.com/b", provider_id=2, provider_name="P2", tags="jazz, blues")
    stations = [current, a, b]
    _, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert len(same_tag) == 2


def test_same_tag_pool_uses_normalize_tags():
    """Phase 67 / SIM-05 / T-01: normalize_tags case-folding applied — candidate
    with 'AMBIENT' matches current 'Ambient, Electronic' (case-insensitive)."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="Ambient, Electronic")
    candidate = _mk(2, "Cand", "http://example.com/cand", provider_id=2, provider_name="P2", tags="AMBIENT")
    stations = [current, candidate]
    _, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert candidate in same_tag


# ---------------------------------------------------------------------------
# Combined behavior tests
# ---------------------------------------------------------------------------

def test_pools_allow_cross_pool_duplicates():
    """Phase 67 / T-03: a candidate matching BOTH same-provider AND same-tag
    appears in BOTH returned lists (no cross-pool deduplication)."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="rock")
    both_match = _mk(2, "Both", "http://example.com/both", provider_id=1, provider_name="P1", tags="rock")
    stations = [current, both_match]
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert both_match in same_provider
    assert both_match in same_tag


def test_seeded_rng_reproducibility():
    """Phase 67 / R-06: two calls with rng=random.Random(42) produce identical output."""
    current = _mk(0, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="rock, pop")
    stations = [current]
    for i in range(1, 11):
        stations.append(_mk(i, f"S{i}", f"http://example.com/{i}", provider_id=1, provider_name="P1", tags="rock"))
    call1 = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    call2 = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert call1 == call2


def test_aa_siblings_excluded_from_both_pools():
    """Phase 67 / T-04b: AA cross-network sibling excluded from BOTH pools.

    DI.fm 'Ambient' is current; ZenRadio 'Ambient' shares the same AA channel
    key (cross-network sibling) — find_aa_siblings identifies it and it must
    NOT appear in either returned pool.
    """
    current = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc",
                  provider_id=1, provider_name="DI.fm", tags="ambient, electronic")
    zr_sibling = _mk(2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc",
                     provider_id=1, provider_name="ZenRadio", tags="ambient")
    stations = [current, zr_sibling]
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    assert zr_sibling not in same_provider
    assert zr_sibling not in same_tag


def test_empty_library_returns_empty_pools():
    """Phase 67 / T-04: library = [current only] → both pools empty."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="rock")
    same_provider, same_tag = pick_similar_stations([current], current, sample_size=5, rng=random.Random(42))
    assert same_provider == []
    assert same_tag == []


def test_no_provider_no_tags_returns_empty_pools():
    """Phase 67 / T-04c/d: current.provider_id=None, current.tags='' → both pools empty."""
    current = _mk(1, "Current", "http://example.com/current", provider_id=None, provider_name=None, tags="")
    other = _mk(2, "Other", "http://example.com/other", provider_id=1, provider_name="P1", tags="rock")
    same_provider, same_tag = pick_similar_stations([current, other], current, sample_size=5, rng=random.Random(42))
    assert same_provider == []
    assert same_tag == []


def test_perf_500_stations_under_50ms():
    """Phase 67 / SIM-04+05: 500-station library returns in < 50ms."""
    # Mix: 250 same-provider candidates, 250 different-provider, varied tags
    current = _mk(0, "Current", "http://example.com/current", provider_id=1, provider_name="P1", tags="rock, pop")
    stations = [current]
    for i in range(1, 251):
        stations.append(_mk(i, f"S{i}", f"http://example.com/{i}", provider_id=1, provider_name="P1", tags="rock"))
    for i in range(251, 501):
        stations.append(_mk(i, f"S{i}", f"http://example.com/{i}", provider_id=2, provider_name="P2", tags="pop"))
    start = time.perf_counter()
    same_provider, same_tag = pick_similar_stations(stations, current, sample_size=5, rng=random.Random(42))
    delta = time.perf_counter() - start
    assert delta < 0.050, f"pick_similar_stations took {delta*1000:.1f}ms (budget 50ms)"


def test_pick_similar_stations_handles_current_with_empty_streams():
    """Phase 67 / RESEARCH Pitfall 11: current.streams=[] must not raise IndexError.

    AA sibling exclusion is skipped silently when streams is empty (no URL to
    pass to find_aa_siblings). Same-provider and same-tag pools still derived.
    """
    current = Station(
        id=1,
        name="Current",
        provider_id=1,
        provider_name="P1",
        tags="rock",
        station_art_path=None,
        album_fallback_path=None,
        streams=[],
    )
    other = _mk(2, "Other", "http://example.com/other", provider_id=1, provider_name="P1", tags="rock")
    # Should not raise IndexError; AA exclusion silently skipped
    same_provider, same_tag = pick_similar_stations([current, other], current, sample_size=5, rng=random.Random(42))
    assert other in same_provider


# ---------------------------------------------------------------------------
# SIM-09: render_similar_html renderer tests
# ---------------------------------------------------------------------------

def test_render_similar_html_provider_section_no_provider_in_text():
    """Phase 67 / SIM-09 / D-03: show_provider=False → link text is just 'Name' (no provider)."""
    s = _mk(1, "Drone Zone", "http://example.com/dz", provider_id=1, provider_name="SomaFM", tags="ambient")
    out = render_similar_html([s], show_provider=False)
    assert ">Drone Zone</a>" in out
    assert "(SomaFM)" not in out


def test_render_similar_html_tag_section_includes_provider():
    """Phase 67 / SIM-09 / D-03: show_provider=True → link text is 'Name (Provider)'."""
    s = _mk(1, "Drone Zone", "http://example.com/dz", provider_id=1, provider_name="SomaFM", tags="ambient")
    out = render_similar_html([s], show_provider=True)
    assert ">Drone Zone (SomaFM)</a>" in out


def test_render_similar_html_escapes_name():
    """Phase 67 / SIM-09 / T-67-01-01: raw '<script>' in name must be escaped.

    html.escape ensures '<script>' never appears verbatim; '&lt;script&gt;'
    must be present; alert(1) text content survives escaping.
    """
    s = _mk(1, "<script>alert(1)</script>", "http://example.com/x",
            provider_id=1, provider_name="Safe", tags="")
    out = render_similar_html([s], show_provider=False)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "alert(1)" in out


def test_render_similar_html_escapes_provider():
    """Phase 67 / SIM-09 / T-67-01-01 / RESEARCH Pitfall 7: provider_name XSS
    lock — show_provider=True passes provider through html.escape too."""
    s = _mk(1, "Station", "http://example.com/x",
            provider_id=1, provider_name="<script>alert(1)</script>", tags="")
    out = render_similar_html([s], show_provider=True)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_similar_html_uses_br_separator():
    """Phase 67 / SIM-09 / D-03: vertical layout — n stations produce n-1 '<br>' separators."""
    a = _mk(1, "A", "http://example.com/a", provider_id=1, provider_name="P1", tags="")
    b = _mk(2, "B", "http://example.com/b", provider_id=1, provider_name="P1", tags="")
    c = _mk(3, "C", "http://example.com/c", provider_id=1, provider_name="P1", tags="")
    out = render_similar_html([a, b, c], show_provider=False)
    assert out.count("<br>") == 2


def test_render_similar_html_href_uses_similar_prefix():
    """Phase 67 / SIM-09 / RESEARCH Pitfall 8: href MUST use 'similar://' NOT 'sibling://'."""
    s = _mk(1, "Station", "http://example.com/x", provider_id=1, provider_name="P1", tags="")
    out = render_similar_html([s], show_provider=False)
    assert 'href="similar://' in out
    assert "sibling://" not in out


def test_render_similar_html_href_payload_is_integer_only():
    """Phase 67 / SIM-09 / T-67-01-02: href payload is strictly integer — 'similar://{id}'."""
    s = _mk(42, "Station", "http://example.com/x", provider_id=1, provider_name="P1", tags="")
    out = render_similar_html([s], show_provider=False)
    assert 'href="similar://42"' in out


def test_render_similar_html_empty_stations_returns_empty_string():
    """Phase 67 / SIM-09: empty station list → empty string output."""
    out = render_similar_html([], show_provider=False)
    assert out == ""


def test_render_similar_html_provider_none_safe():
    """Phase 67 / SIM-09 / RESEARCH Pitfall 7: provider_name=None with show_provider=True
    must not raise; renders empty parens '()' or similar."""
    s = Station(
        id=1,
        name="Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[StationStream(id=10, station_id=1, url="http://example.com/x", position=1)],
    )
    # Should not raise TypeError; renders provider_name or "" fallback
    out = render_similar_html([s], show_provider=True)
    assert "()" in out or "Station" in out
    # Critically: must not raise

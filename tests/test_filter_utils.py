from musicstreamer.filter_utils import normalize_tags, matches_filter, matches_filter_multi
from musicstreamer.models import Station


def make_station(name="Test Station", provider_name="Soma.FM", tags=""):
    return Station(
        id=1,
        name=name,
        url="http://example.com/stream",
        provider_id=1,
        provider_name=provider_name,
        tags=tags,
        station_art_path=None,
        album_fallback_path=None,
    )


# --- normalize_tags ---

def test_normalize_tags_comma_separated():
    assert normalize_tags("Lofi, Chill") == ["Lofi", "Chill"]


def test_normalize_tags_bullet_separated():
    assert normalize_tags("lofi \u2022 chill \u2022 Jazz") == ["lofi", "chill", "Jazz"]


def test_normalize_tags_dedup_case_insensitive():
    result = normalize_tags("Lofi, lofi, LOFI")
    assert result == ["Lofi"]


def test_normalize_tags_empty_string():
    assert normalize_tags("") == []


def test_normalize_tags_whitespace_only():
    assert normalize_tags("  , , ") == []


def test_normalize_tags_mixed_delimiters_dedup():
    result = normalize_tags("Rock \u2022 ,  Blues , Rock")
    assert result == ["Rock", "Blues"]


def test_normalize_tags_strips_whitespace():
    assert normalize_tags("  Rock  ,  Jazz  ") == ["Rock", "Jazz"]


# --- matches_filter ---

def test_matches_filter_no_filters():
    station = make_station()
    assert matches_filter(station, "", None, None) is True


def test_matches_filter_search_text_match():
    station = make_station(name="Soma Groove")
    assert matches_filter(station, "soma", None, None) is True


def test_matches_filter_search_text_no_match():
    station = make_station(name="DI.fm Lounge")
    assert matches_filter(station, "soma", None, None) is False


def test_matches_filter_search_case_insensitive():
    station = make_station(name="SOMA Groove")
    assert matches_filter(station, "soma", None, None) is True


def test_matches_filter_provider_match():
    station = make_station(provider_name="Soma.FM")
    assert matches_filter(station, "", "Soma.FM", None) is True


def test_matches_filter_provider_no_match():
    station = make_station(provider_name="DI.fm")
    assert matches_filter(station, "", "Soma.FM", None) is False


def test_matches_filter_tag_match():
    station = make_station(tags="Lofi, Chill")
    assert matches_filter(station, "", None, "lofi") is True


def test_matches_filter_tag_no_match():
    station = make_station(tags="Rock, Blues")
    assert matches_filter(station, "", None, "lofi") is False


def test_matches_filter_tag_case_insensitive():
    station = make_station(tags="LoFi, Chill")
    assert matches_filter(station, "", None, "LOFI") is True


def test_matches_filter_all_filters_match():
    station = make_station(name="Soma Groove", provider_name="Soma.FM", tags="Lofi, Chill")
    assert matches_filter(station, "groove", "Soma.FM", "lofi") is True


def test_matches_filter_name_matches_provider_does_not():
    station = make_station(name="Soma Groove", provider_name="DI.fm", tags="Lofi, Chill")
    assert matches_filter(station, "groove", "Soma.FM", "lofi") is False


def test_matches_filter_empty_provider_filter_inactive():
    station = make_station(provider_name="DI.fm")
    assert matches_filter(station, "", "", None) is True


def test_matches_filter_empty_tag_filter_inactive():
    station = make_station(tags="Rock")
    assert matches_filter(station, "", None, "") is True


def test_matches_filter_none_provider_inactive():
    station = make_station(provider_name=None)
    assert matches_filter(station, "", None, None) is True


def test_matches_filter_bullet_tags():
    station = make_station(tags="lofi \u2022 chill \u2022 Jazz")
    assert matches_filter(station, "", None, "chill") is True


# --- matches_filter_multi ---

def test_matches_filter_multi_all_empty():
    """Empty provider_set + empty tag_set + empty search -> True for any station."""
    station = make_station()
    assert matches_filter_multi(station, "", set(), set()) is True


def test_matches_filter_multi_provider_match():
    """provider_set containing station's provider -> True."""
    station = make_station(provider_name="Soma.FM")
    assert matches_filter_multi(station, "", {"Soma.FM"}, set()) is True


def test_matches_filter_multi_provider_no_match():
    """provider_set not containing station's provider -> False."""
    station = make_station(provider_name="DI.fm")
    assert matches_filter_multi(station, "", {"Soma.FM"}, set()) is False


def test_matches_filter_multi_provider_or_logic():
    """Multiple providers -> OR within providers (D-08)."""
    station = make_station(provider_name="DI.fm")
    assert matches_filter_multi(station, "", {"Soma.FM", "DI.fm"}, set()) is True


def test_matches_filter_multi_tag_match_case_insensitive():
    """tag_set member matches station tag case-insensitively."""
    station = make_station(tags="Lofi, Chill")
    assert matches_filter_multi(station, "", set(), {"lofi"}) is True


def test_matches_filter_multi_tag_no_match():
    """tag_set not matching any station tag -> False."""
    station = make_station(tags="Rock, Blues")
    assert matches_filter_multi(station, "", set(), {"lofi"}) is False


def test_matches_filter_multi_tag_or_logic():
    """Multiple tags -> OR within tags (D-09)."""
    station = make_station(tags="Rock, Blues")
    assert matches_filter_multi(station, "", set(), {"lofi", "rock"}) is True


def test_matches_filter_multi_and_composition_both_pass():
    """provider_set + tag_set both matching -> True (AND between dimensions, D-10)."""
    station = make_station(provider_name="Soma.FM", tags="Lofi, Chill")
    assert matches_filter_multi(station, "", {"Soma.FM"}, {"lofi"}) is True


def test_matches_filter_multi_and_composition_provider_fails():
    """provider_set + tag_set, provider fails -> False."""
    station = make_station(provider_name="DI.fm", tags="Lofi, Chill")
    assert matches_filter_multi(station, "", {"Soma.FM"}, {"lofi"}) is False


def test_matches_filter_multi_and_composition_tag_fails():
    """provider_set + tag_set, tag fails -> False."""
    station = make_station(provider_name="Soma.FM", tags="Lofi, Chill")
    assert matches_filter_multi(station, "", {"Soma.FM"}, {"rock"}) is False


def test_matches_filter_multi_search_and_provider():
    """search_text + provider_set -> station must match both."""
    station = make_station(name="Soma Groove", provider_name="Soma.FM")
    assert matches_filter_multi(station, "groove", {"Soma.FM"}, set()) is True
    station2 = make_station(name="Soma Groove", provider_name="DI.fm")
    assert matches_filter_multi(station2, "groove", {"Soma.FM"}, set()) is False


def test_matches_filter_multi_bullet_tags():
    """Bullet-separated tags work with tag_set matching."""
    station = make_station(tags="lofi \u2022 chill \u2022 Jazz")
    assert matches_filter_multi(station, "", set(), {"chill"}) is True


def test_matches_filter_multi_provider_none():
    """Station with provider_name=None and non-empty provider_set -> False."""
    station = make_station(provider_name=None)
    assert matches_filter_multi(station, "", {"Soma.FM"}, set()) is False

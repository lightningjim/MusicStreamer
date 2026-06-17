"""Registry unit tests and source-grep drift-guards for Phase 89c brand-avatar fallback.

ART-AVATAR-11: brand_avatars.lookup() maps the 7 exact provider_name strings
to bundled PNG paths; absent files and unknown keys return None (never raise).

ART-AVATAR-12 / D-11: source-grep drift-guards pin _last_brand_avatar to the
_apply_art_tier 4th branch and confirm bind_station resets it — structural
gates, not behavioral mocks (per feedback_gstreamer_mock_blind_spot.md).
"""
from pathlib import Path
from unittest.mock import patch

NOW_PLAYING_SRC = Path(__file__).parent.parent / "musicstreamer" / "ui_qt" / "now_playing_panel.py"


# ---------------------------------------------------------------------------
# Registry unit tests — ART-AVATAR-11
# ---------------------------------------------------------------------------


def test_lookup_registered_providers(tmp_path, monkeypatch):
    """All 7 exact provider_name keys resolve to a path when stub PNG present."""
    d = tmp_path / "musicstreamer" / "ui_qt" / "brand-avatars"
    d.mkdir(parents=True)
    provider_names = [
        "SomaFM",
        "DI.fm",
        "RadioTunes",
        "JazzRadio",
        "RockRadio",
        "ClassicalRadio",
        "ZenRadio",
    ]
    for name in provider_names:
        (d / f"{name}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    import musicstreamer.brand_avatars as ba
    monkeypatch.setattr(ba._res, "files", lambda pkg: tmp_path / pkg.replace(".", "/"))

    for name in provider_names:
        result = ba.lookup(name)
        assert result is not None, f"lookup({name!r}) returned None, expected a path"
        assert result.endswith(f"{name}.png"), f"Expected path ending in {name}.png, got {result!r}"


def test_lookup_gbs_returns_none(tmp_path, monkeypatch):
    """D-01: GBS.FM is NOT in the registry — lookup returns None."""
    d = tmp_path / "musicstreamer" / "ui_qt" / "brand-avatars"
    d.mkdir(parents=True)
    (d / "GBS.FM.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    import musicstreamer.brand_avatars as ba
    monkeypatch.setattr(ba._res, "files", lambda pkg: tmp_path / pkg.replace(".", "/"))

    result = ba.lookup("GBS.FM")
    assert result is None, "GBS.FM must NOT be registered (D-01)"


def test_lookup_missing_file_returns_none(tmp_path, monkeypatch):
    """D-04: registered provider whose PNG is absent returns None (graceful missing-asset)."""
    d = tmp_path / "musicstreamer" / "ui_qt" / "brand-avatars"
    d.mkdir(parents=True)
    # Do NOT create SomaFM.png — the file is absent

    import musicstreamer.brand_avatars as ba
    monkeypatch.setattr(ba._res, "files", lambda pkg: tmp_path / pkg.replace(".", "/"))

    result = ba.lookup("SomaFM")
    assert result is None, "lookup must return None when registered PNG file is absent (D-04)"


def test_lookup_unknown_provider_returns_none(tmp_path, monkeypatch):
    """Unknown provider_name not in registry returns None."""
    import musicstreamer.brand_avatars as ba
    result = ba.lookup("totally unknown provider")
    assert result is None, "Unknown provider must return None"


def test_lookup_never_raises():
    """lookup() must never raise for any string input."""
    import musicstreamer.brand_avatars as ba
    try:
        ba.lookup("")
        ba.lookup("SomaFM")
        ba.lookup("GBS.FM")
        ba.lookup("some very weird string with special chars: <>&;")
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"lookup() raised unexpectedly: {exc!r}") from exc


# ---------------------------------------------------------------------------
# Source-grep drift-guards — ART-AVATAR-12 / D-11 / D-12
# (These go RED until Task 2 adds the wiring to now_playing_panel.py)
# ---------------------------------------------------------------------------


def test_apply_art_tier_has_brand_avatar_branch():
    """D-11: _last_brand_avatar must appear within the _apply_art_tier body in now_playing_panel.py.

    Source-grep gate: structural contract, not a behavioral mock
    (per feedback_gstreamer_mock_blind_spot.md convention).
    """
    src = NOW_PLAYING_SRC.read_text(encoding="utf-8")
    tier_pos = src.find("def _apply_art_tier")
    assert tier_pos != -1, "now_playing_panel.py must define _apply_art_tier"
    # find next top-level def after _apply_art_tier
    next_def_pos = src.find("\n    def ", tier_pos + 1)
    if next_def_pos == -1:
        next_def_pos = len(src)
    tier_body = src[tier_pos:next_def_pos]
    assert "_last_brand_avatar" in tier_body, (
        "D-11: _last_brand_avatar must appear within _apply_art_tier body "
        "(4th branch between _last_avatar_path and the logo else)"
    )


def test_bind_station_resets_brand_avatar():
    """D-11: _last_brand_avatar = None must appear within the bind_station body.

    Source-grep gate: stale-station bleed guard must be in bind_station
    alongside _last_avatar_path = None.
    """
    src = NOW_PLAYING_SRC.read_text(encoding="utf-8")
    bind_pos = src.find("def bind_station")
    assert bind_pos != -1, "now_playing_panel.py must define bind_station"
    # find next top-level def after bind_station
    next_def_pos = src.find("\n    def ", bind_pos + 1)
    if next_def_pos == -1:
        next_def_pos = len(src)
    bind_body = src[bind_pos:next_def_pos]
    assert "_last_brand_avatar = None" in bind_body, (
        "D-11: _last_brand_avatar = None must appear within bind_station body "
        "(stale-station bleed guard, Phase 89c Pitfall 3)"
    )

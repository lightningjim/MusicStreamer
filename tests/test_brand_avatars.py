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


# ---------------------------------------------------------------------------
# D-09 / D-09a drift-guard — Wave 2 (edit_station_dialog.py picker)
# ---------------------------------------------------------------------------

EDIT_STATION_SRC = Path(__file__).parent.parent / "musicstreamer" / "ui_qt" / "edit_station_dialog.py"


def test_choose_brand_image_uses_provider_keyed_persist():
    """D-09/D-09a: _on_choose_brand_image must exist in edit_station_dialog.py and its
    body must reference write_provider_avatar and update_provider_avatar_path (non-silent-
    reset persist, Pitfall 5), contain a provider_id is None guard (Pitfall 7), and must
    NOT reference _AvatarFetchWorker (D-09a — synchronous, not the network worker).

    Source-grep drift-guard: structural contract over live source.
    """
    src = EDIT_STATION_SRC.read_text(encoding="utf-8")

    # Locate the method definition
    method_start = src.find("def _on_choose_brand_image")
    assert method_start != -1, (
        "edit_station_dialog.py must define _on_choose_brand_image (D-09)"
    )

    # Extract method body up to next top-level def at the same indent
    next_def_pos = src.find("\n    def ", method_start + 1)
    if next_def_pos == -1:
        next_def_pos = len(src)
    method_body = src[method_start:next_def_pos]

    assert "write_provider_avatar" in method_body, (
        "D-09: _on_choose_brand_image body must call write_provider_avatar "
        "(provider-keyed atomic write, Pitfall 6)"
    )
    assert "update_provider_avatar_path" in method_body, (
        "D-09: _on_choose_brand_image body must call update_provider_avatar_path "
        "(non-silent-reset single-column persist, Pitfall 5)"
    )
    assert "provider_id is None" in method_body, (
        "D-09 Pitfall-7: _on_choose_brand_image body must guard against "
        "provider_id is None before any write (never write None.png)"
    )
    assert "_AvatarFetchWorker" not in method_body, (
        "D-09a: _on_choose_brand_image must NOT reference _AvatarFetchWorker "
        "(pick is synchronous, disjoint from YouTube/Twitch auto-fetch path)"
    )


# ---------------------------------------------------------------------------
# Code-review fix drift-guards (89C-REVIEW.md WR-01 / WR-02)
# ---------------------------------------------------------------------------


def test_resolve_brand_avatar_fallback_clears_stale_trackers():
    """WR-01: the cover-resolution-exhausted path must clear ALL three tier-replay
    trackers so a later _apply_art_tier resize cannot re-render a prior track's
    cover or override-avatar over the current fallback.

    Source-grep gate: _resolve_brand_avatar_fallback body must reset
    _last_cover_path, _last_avatar_path, and _last_brand_avatar to None.
    """
    src = NOW_PLAYING_SRC.read_text(encoding="utf-8")
    pos = src.find("def _resolve_brand_avatar_fallback")
    assert pos != -1, "now_playing_panel.py must define _resolve_brand_avatar_fallback"
    next_def_pos = src.find("\n    def ", pos + 1)
    if next_def_pos == -1:
        next_def_pos = len(src)
    body = src[pos:next_def_pos]
    for tracker in ("_last_cover_path = None", "_last_avatar_path = None", "_last_brand_avatar = None"):
        assert tracker in body, (
            f"WR-01: _resolve_brand_avatar_fallback must reset '{tracker}' up front "
            "so a prior track's render state cannot bleed through _apply_art_tier on resize"
        )


def test_choose_brand_image_never_raises():
    """WR-02: _on_choose_brand_image is a Qt slot and must never raise — the
    file-read + write + DB persist must be wrapped in try/except.

    Source-grep gate: the method body must contain both 'try:' and 'except'.
    """
    src = EDIT_STATION_SRC.read_text(encoding="utf-8")
    pos = src.find("def _on_choose_brand_image")
    assert pos != -1, "edit_station_dialog.py must define _on_choose_brand_image"
    next_def_pos = src.find("\n    def ", pos + 1)
    if next_def_pos == -1:
        next_def_pos = len(src)
    body = src[pos:next_def_pos]
    assert "try:" in body and "except" in body, (
        "WR-02: _on_choose_brand_image must wrap file-read/write/persist in try/except "
        "(slots-never-raise contract)"
    )


# ---------------------------------------------------------------------------
# Gap-closure drift-guard (89c-03 — UAT Test 5 / Phase 89.1 D-07 reuse-on-open)
# ---------------------------------------------------------------------------


def test_populate_refreshes_avatar_preview():
    """Phase 89.1 D-07 reuse-on-open: _populate() must invoke _refresh_avatar_preview()
    so that a persisted provider_avatar_path renders in the dialog preview on open.

    Source-grep drift-guard: structural contract over live source (closes 89c UAT Test 5).
    """
    src = EDIT_STATION_SRC.read_text(encoding="utf-8")

    # Locate the method definition
    method_start = src.find("def _populate")
    assert method_start != -1, (
        "edit_station_dialog.py must define _populate (D-07 reuse-on-open host)"
    )

    # Extract method body up to the next top-level def at the same indent
    next_def_pos = src.find("\n    def ", method_start + 1)
    if next_def_pos == -1:
        next_def_pos = len(src)
    method_body = src[method_start:next_def_pos]

    assert "self._refresh_avatar_preview()" in method_body, (
        "Phase 89.1 D-07 reuse-on-open / UAT Test 5: _populate() must call "
        "self._refresh_avatar_preview() so the persisted provider_avatar_path "
        "renders in the avatar preview when the dialog is reopened (89c gap-closure)"
    )

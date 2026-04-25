"""Tests for cookie handling in yt_import + YouTube playback.

Plan 35-06:
- yt_import uses the yt_dlp library API with cookiefile option.
- _play_youtube also uses the yt_dlp library API -- no external player,
  no temp-file copying. Cookies (if present) are passed directly as the
  ``cookiefile`` option alongside the EJS JS challenge solver
  extractor_args, and yt_dlp resolves the direct HLS URL which is fed
  to GStreamer playbin3.
- The monkeypatch target for all cookie tests is
  ``musicstreamer.paths._root_override`` -- yt_import and player both
  route through ``paths.cookies_path()``.
"""
import os
import tempfile as _tempfile  # for gettempdir() assertion
from unittest.mock import MagicMock, patch

from musicstreamer.player import Player


def make_player(qtbot):
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player


# ---------------------------------------------------------------------------
# paths.cookies_path accessor test
# ---------------------------------------------------------------------------

def test_cookie_path_resolves_under_root(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.cookies_path() == str(tmp_path / "cookies.txt")


def test_cookie_path_constant_via_constants_getattr(tmp_path, monkeypatch):
    """musicstreamer.constants.COOKIES_PATH delegates to paths.cookies_path()."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer import constants
    assert constants.COOKIES_PATH == os.path.join(str(tmp_path), "cookies.txt")


# ---------------------------------------------------------------------------
# yt_import library-API cookie injection
# ---------------------------------------------------------------------------

def test_ytdlp_passes_cookiefile_when_file_exists(tmp_path, monkeypatch):
    """scan_playlist passes cookiefile=<path> to yt_dlp.YoutubeDL when the
    cookies file exists under paths.cookies_path()."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"entries": []}

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", FakeYDL):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    cf = captured_opts.get("cookiefile")
    assert cf is not None, "cookiefile must be set when canonical file exists"
    assert cf != str(cookies_file), "cookiefile is now a temp copy, not canonical (Phase 999.7)"
    assert cf.startswith(_tempfile.gettempdir()), f"expected temp path, got {cf}"


def test_ytdlp_omits_cookiefile_when_absent(tmp_path, monkeypatch):
    """scan_playlist omits the ``cookiefile`` option when the file does not exist."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT create the file.

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"entries": []}

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", FakeYDL):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    assert "cookiefile" not in captured_opts


# ---------------------------------------------------------------------------
# YouTube playback cookie injection (Plan 35-06: yt-dlp library API path)
# ---------------------------------------------------------------------------

def test_youtube_resolve_passes_cookiefile_when_present(tmp_path, monkeypatch, qtbot):
    """_youtube_resolve_worker passes cookiefile=<path> to yt_dlp.YoutubeDL
    when cookies.txt exists, alongside the EJS extractor_args."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    player = make_player(qtbot)
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    cf = captured_opts.get("cookiefile")
    assert cf is not None, "cookiefile must be set when canonical file exists"
    assert cf != str(cookies_file), "cookiefile is now a temp copy, not canonical (Phase 999.7)"
    assert cf.startswith(_tempfile.gettempdir()), f"expected temp path, got {cf}"
    # Phase 999.9: js_runtimes={"node": ...} is required because the yt-dlp
    # library API does not auto-discover JS runtimes the way the CLI does.
    # The dead "youtubepot-jsruntime" extractor_args namespace (yt-dlp 2026.03.17
    # silently ignored it) is gone; no player_client pin is needed once the
    # JS runtime is wired.
    assert captured_opts.get("js_runtimes") == {"node": {"path": None}}
    assert "youtubepot-jsruntime" not in captured_opts.get("extractor_args", {})


def test_youtube_resolve_omits_cookiefile_when_absent(tmp_path, monkeypatch, qtbot):
    """_youtube_resolve_worker omits cookiefile when cookies.txt is absent but
    still includes the EJS extractor_args."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT create the file.

    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    player = make_player(qtbot)
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert "cookiefile" not in captured_opts
    # Phase 999.9: js_runtimes={"node": ...} required (see test above for rationale).
    assert captured_opts.get("js_runtimes") == {"node": {"path": None}}
    assert "youtubepot-jsruntime" not in captured_opts.get("extractor_args", {})


# ---------------------------------------------------------------------------
# clear_cookies() utility
# ---------------------------------------------------------------------------

def test_clear_removes_cookies_file(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("some cookies")
    from musicstreamer.constants import clear_cookies
    assert clear_cookies() is True
    assert not cookies_file.exists()


def test_clear_returns_false_when_absent(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.constants import clear_cookies
    assert clear_cookies() is False


# ---------------------------------------------------------------------------
# Shared test fixtures for Phase 999.7 (FakeYDL that simulates yt-dlp's
# save_cookies() side effect on __exit__)
# ---------------------------------------------------------------------------


class FakeYDLSaveCookies:
    """FakeYDL that mimics yt_dlp.YoutubeDL.__exit__'s save_cookies() side
    effect — writes the yt-dlp marker header into opts['cookiefile'] on exit.

    Used by FIX-02 byte-equality tests to prove the canonical cookies.txt
    is NOT the file being overwritten.
    """

    def __init__(self, opts):
        self._opts = dict(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        cf = self._opts.get("cookiefile")
        if cf:
            with open(cf, "w", encoding="utf-8") as fh:
                fh.write(
                    "# Netscape HTTP Cookie File\n"
                    "# This file is generated by yt-dlp.  Do not edit.\n\n"
                )
        return False

    def extract_info(self, url, download=False):
        # Return shape depends on caller; tests override via subclass if needed.
        return {"entries": [], "url": "http://resolved.example/stream.m3u8"}


# ---------------------------------------------------------------------------
# Temp-copy protection (Phase 999.7 — FIX-02 restoration)
# ---------------------------------------------------------------------------


def test_ytdlp_uses_temp_cookie_copy(tmp_path, monkeypatch):
    """FIX-02-a: scan_playlist passes a tempfile path (NOT canonical) to yt-dlp."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\ttest\n")

    captured = {}

    class Capture(FakeYDLSaveCookies):
        def __init__(self, opts):
            super().__init__(opts)
            captured.update(opts)

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", Capture):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    cf = captured.get("cookiefile")
    assert cf is not None, "cookiefile must be set when canonical file exists"
    assert cf != str(cookies_file), "cookiefile must NOT point at canonical path"
    assert cf.startswith(_tempfile.gettempdir()), f"cookiefile must live in temp dir, got {cf}"


def test_canonical_cookies_unchanged_by_ytdlp(tmp_path, monkeypatch):
    """FIX-02-b: canonical cookies.txt is byte-identical before/after scan_playlist.

    FakeYDLSaveCookies writes the yt-dlp marker to opts['cookiefile'] on __exit__,
    simulating the real save_cookies() side effect. The canonical file must be
    untouched because the temp-copy wrapper points yt-dlp at a temp path.
    """
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    original = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\toriginal\n"
    cookies_file.write_text(original)

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", FakeYDLSaveCookies):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    assert cookies_file.read_text() == original, "canonical cookies.txt must be unchanged"


def test_youtube_resolve_uses_temp_cookie_copy(tmp_path, monkeypatch, qtbot):
    """FIX-02-c: _youtube_resolve_worker passes a tempfile path (NOT canonical)."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\ttest\n")

    captured = {}

    class Capture(FakeYDLSaveCookies):
        def __init__(self, opts):
            super().__init__(opts)
            captured.update(opts)

    import yt_dlp
    player = make_player(qtbot)
    with patch.object(yt_dlp, "YoutubeDL", Capture):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    cf = captured.get("cookiefile")
    assert cf is not None
    assert cf != str(cookies_file)
    assert cf.startswith(_tempfile.gettempdir())


def test_temp_cookie_unlinked_after_call(tmp_path, monkeypatch):
    """FIX-02-d: the temp file is unlinked after scan_playlist returns."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")

    captured_paths = []

    class Capture(FakeYDLSaveCookies):
        def __init__(self, opts):
            super().__init__(opts)
            cf = opts.get("cookiefile")
            if cf:
                captured_paths.append(cf)

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", Capture):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    assert captured_paths, "test precondition: at least one cookiefile path must be captured"
    for tmp in captured_paths:
        assert not os.path.exists(tmp), f"temp file must be unlinked after call, still exists: {tmp}"


def test_copy_failure_omits_cookiefile(tmp_path, monkeypatch):
    """FIX-02-e: when shutil.copy2 raises OSError, cookiefile is NOT set in opts."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")

    import shutil
    def _boom(*args, **kwargs):
        raise OSError("disk full (simulated)")
    monkeypatch.setattr(shutil, "copy2", _boom)

    captured = {}

    class Capture(FakeYDLSaveCookies):
        def __init__(self, opts):
            super().__init__(opts)
            captured.update(opts)

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", Capture):
        from musicstreamer import yt_import
        yt_import.scan_playlist("https://youtube.com/playlist?list=test")

    assert "cookiefile" not in captured, (
        "on copy2 OSError, yt-dlp must be invoked WITHOUT cookiefile "
        "(fallback to no-cookies per D-06)"
    )


# ---------------------------------------------------------------------------
# Corruption detection + auto-clear (Phase 999.7 — NEW)
# ---------------------------------------------------------------------------


def test_corruption_marker_detected(tmp_path):
    """NEW-a: is_cookie_file_corrupted returns True for a yt-dlp-saved file."""
    from musicstreamer.cookie_utils import is_cookie_file_corrupted
    corrupted = tmp_path / "c.txt"
    corrupted.write_text(
        "# Netscape HTTP Cookie File\n"
        "# This file is generated by yt-dlp.  Do not edit.\n\n"
    )
    assert is_cookie_file_corrupted(str(corrupted)) is True


def test_clean_netscape_not_corrupted(tmp_path):
    """NEW-b: is_cookie_file_corrupted returns False for a clean Netscape file."""
    from musicstreamer.cookie_utils import is_cookie_file_corrupted
    clean = tmp_path / "c.txt"
    clean.write_text(
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t0\tSID\ttest\n"
    )
    assert is_cookie_file_corrupted(str(clean)) is False


def test_scan_playlist_auto_clears_corrupted(tmp_path, monkeypatch):
    """NEW-c: scan_playlist clears a corrupted cookies.txt AND fires toast_callback."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        "# This file is generated by yt-dlp.  Do not edit.\n\n"
    )

    toasts: list[str] = []

    class Noop(FakeYDLSaveCookies):
        pass

    with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", Noop):
        from musicstreamer import yt_import
        yt_import.scan_playlist(
            "https://youtube.com/playlist?list=test",
            toast_callback=toasts.append,
        )

    assert not cookies_file.exists(), "corrupted cookies.txt must be auto-cleared"
    assert toasts, "toast_callback must be invoked on corruption"
    assert "cookies cleared" in toasts[0].lower() or "re-import" in toasts[0].lower()


def test_youtube_resolve_auto_clears_corrupted(tmp_path, monkeypatch, qtbot):
    """NEW-d: _youtube_resolve_worker clears corrupted cookies.txt + emits cookies_cleared."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        "# This file is generated by yt-dlp.  Do not edit.\n\n"
    )

    import yt_dlp
    player = make_player(qtbot)

    emitted: list[str] = []
    player.cookies_cleared.connect(emitted.append)

    with patch.object(yt_dlp, "YoutubeDL", FakeYDLSaveCookies):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert not cookies_file.exists(), "corrupted cookies.txt must be auto-cleared"
    assert emitted, "Player.cookies_cleared Signal must fire on corruption"
    assert "cookies cleared" in emitted[0].lower() or "re-import" in emitted[0].lower()

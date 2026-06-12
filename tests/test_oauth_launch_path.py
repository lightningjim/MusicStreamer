"""Phase 88.3-03 — Drift-guards for the frozen helper-exe launch target + platform-aware UA.

Covers two contracts:
  1. _make_oauth_launch_args frozen branch → separate oauth_helper.exe sibling (B1 architecture)
  2. _CHROME_UA is platform-appropriate (Windows UA on win32, Linux UA elsewhere)

All tests are Linux-runnable with monkeypatch; no frozen build required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Task 1: _make_oauth_launch_args frozen launch target
# ---------------------------------------------------------------------------

def test_frozen_launches_sibling_helper_exe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """B1 contract: frozen branch returns the SEPARATE oauth_helper.exe sibling path.

    With sys.frozen=True and sys.executable = {app}/MusicStreamer.exe,
    _make_oauth_launch_args("twitch") must return:
      program == {app}/oauth_helper/oauth_helper.exe
      args == ["--mode", "twitch"]
    i.e. a DIFFERENT exe from sys.executable, at the sibling sub-directory path.
    """
    fake_app_exe = str(tmp_path / "MusicStreamer.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", fake_app_exe)

    # Re-import to pick up monkeypatched sys values at call time (function reads
    # sys.frozen / sys.executable on each call, not at import time).
    from musicstreamer.subprocess_utils import _make_oauth_launch_args

    program, args = _make_oauth_launch_args("twitch")

    expected_helper = str(tmp_path / "oauth_helper" / "oauth_helper.exe")
    assert program == expected_helper, (
        f"Frozen branch must return the sibling oauth_helper.exe path "
        f"({expected_helper!r}), got {program!r}. "
        "B1 requires the conda main exe to launch the SEPARATE helper binary, "
        "not re-exec itself (Phase 88.3-03)."
    )
    assert args == ["--mode", "twitch"], (
        f"Frozen branch args must be ['--mode', 'twitch'], got {args!r}. "
        "The '--oauth-helper' self-dispatch flag must NOT appear in B1 (it was "
        "only needed for the old self-re-exec path)."
    )


def test_frozen_uses_os_path_join_not_self(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Proves frozen branch no longer re-execs sys.executable.

    The returned program must NOT equal sys.executable — if it did, the conda
    main exe would be re-exec'ing itself, which forces WebEngine into the conda
    bundle (the root cause of Phase 88.3 G6).
    """
    fake_app_exe = str(tmp_path / "MusicStreamer.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", fake_app_exe)

    from musicstreamer.subprocess_utils import _make_oauth_launch_args

    program, _args = _make_oauth_launch_args("gbs")

    assert program != fake_app_exe, (
        f"Frozen branch must NOT return sys.executable ({fake_app_exe!r}). "
        "Returning sys.executable means self-re-exec, which forces WebEngine "
        "into the conda bundle (Phase 88.3-03 B1 requirement)."
    )


def test_source_branch_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Source/dev/Linux contract must be byte-for-byte preserved.

    With sys.frozen absent (or False), _make_oauth_launch_args("gbs") must return
    (sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "gbs"]).
    """
    # Ensure frozen is absent/False (default in dev/Linux)
    monkeypatch.delattr(sys, "frozen", raising=False)

    from musicstreamer.subprocess_utils import _make_oauth_launch_args

    program, args = _make_oauth_launch_args("gbs")

    assert program == sys.executable, (
        f"Source branch must return sys.executable ({sys.executable!r}), got {program!r}. "
        "The dev/Linux contract must be preserved byte-for-byte (Phase 88.3-03)."
    )
    assert args == ["-m", "musicstreamer.oauth_helper", "--mode", "gbs"], (
        f"Source branch args must be ['-m', 'musicstreamer.oauth_helper', '--mode', 'gbs'], "
        f"got {args!r}. The non-frozen module-form contract must be unchanged."
    )


def test_mode_is_call_site_literal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """T-40-05 contract: mode appears as its own list element, never shell-interpolated.

    The function must never join mode into a shell string. args is always a list,
    and mode is always a separate element in that list (not concatenated into a
    shell command string).
    """
    fake_app_exe = str(tmp_path / "MusicStreamer.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", fake_app_exe)

    from musicstreamer.subprocess_utils import _make_oauth_launch_args

    # Test with both known call-site literals
    for mode in ("twitch", "gbs"):
        program, args = _make_oauth_launch_args(mode)

        assert isinstance(args, list), (
            f"args must be a list (T-40-05 contract: never shell=True), got {type(args)}"
        )
        assert mode in args, (
            f"mode {mode!r} must appear as its own element in args {args!r}, "
            "not interpolated into a shell string (T-40-05)."
        )
        # Verify mode is not concatenated into any single string element
        for element in args:
            if mode in element and element != mode:
                # Element contains mode but is not just mode — check it's not shell-injected
                assert element.startswith("--"), (
                    f"args element {element!r} contains mode {mode!r} but is not "
                    "a standalone flag. Mode must never be interpolated into an "
                    "executable string (T-40-05)."
                )


# ---------------------------------------------------------------------------
# Task 2: _CHROME_UA platform-appropriate (Twitch Windows fix)
# ---------------------------------------------------------------------------

def test_ua_windows_token_on_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    """On win32, _CHROME_UA must contain the Windows NT platform token.

    Twitch's server-side Sec-CH-UA-Platform client-hint can't be spoofed by the
    UA string alone, but a Windows UA token prevents Twitch's initial page-level
    rejection of non-Windows UAs on Windows Chromium builds.
    """
    src = Path(__file__).resolve().parent.parent / "musicstreamer" / "oauth_helper.py"
    source_text = src.read_text(encoding="utf-8")
    assert "Windows NT 10.0; Win64; x64" in source_text, (
        "oauth_helper.py source must contain the Windows NT platform token "
        "'Windows NT 10.0; Win64; x64' for the win32 branch of _CHROME_UA "
        "(Phase 88.3-03 Twitch Windows fix)."
    )
    assert "win32" in source_text, (
        "oauth_helper.py source must contain 'win32' for the platform branch "
        "of _CHROME_UA (Phase 88.3-03)."
    )


def test_ua_linux_token_on_non_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    """On non-win32 (Linux/macOS), _CHROME_UA must contain the Linux token.

    The Linux UA is the existing dev behavior — GBS and Google logins already
    work on Linux with this token. It must be preserved unchanged.
    """
    import musicstreamer.oauth_helper as _mod

    # On Linux (the test runner), _CHROME_UA should contain the Linux token
    if sys.platform != "win32":
        assert "X11; Linux x86_64" in _mod._CHROME_UA, (
            f"On Linux, _CHROME_UA must contain 'X11; Linux x86_64', "
            f"got: {_mod._CHROME_UA!r} (Phase 88.3-03)."
        )
    # Also assert the source file preserves the Linux UA literal
    src = Path(__file__).resolve().parent.parent / "musicstreamer" / "oauth_helper.py"
    source_text = src.read_text(encoding="utf-8")
    assert "X11; Linux x86_64" in source_text, (
        "oauth_helper.py source must retain 'X11; Linux x86_64' for the Linux "
        "branch of _CHROME_UA — GBS + Google already work on Linux with this token "
        "(Phase 88.3-03)."
    )


def test_ua_chrome_version_tokens_present() -> None:
    """Chrome/Safari version tokens must be present in both platform branches.

    The Chrome/140.0.0.0 Safari/537.36 suffix is required for the UA to pass
    Twitch's browser-version check on both platforms.
    """
    src = Path(__file__).resolve().parent.parent / "musicstreamer" / "oauth_helper.py"
    source_text = src.read_text(encoding="utf-8")
    assert "Chrome/140.0.0.0 Safari/537.36" in source_text, (
        "oauth_helper.py source must contain 'Chrome/140.0.0.0 Safari/537.36' — "
        "the version suffix must be present in both platform branches of _CHROME_UA "
        "(Phase 88.3-03)."
    )


def test_ua_flags_set_before_qtwebengine_import() -> None:
    """QTWEBENGINE_CHROMIUM_FLAGS must be set before any QtWebEngine import.

    The Chromium subprocess reads these flags at launch time; setting them after
    QWebEngineView is imported is too late for Twitch's initial UA check.
    This is a line-ordering test: assert QTWEBENGINE_CHROMIUM_FLAGS assignment
    precedes any QtWebEngine import in the source.
    """
    src = Path(__file__).resolve().parent.parent / "musicstreamer" / "oauth_helper.py"
    source_text = src.read_text(encoding="utf-8")
    flags_idx = source_text.find("QTWEBENGINE_CHROMIUM_FLAGS")
    webengine_import_idx = source_text.find("QtWebEngineWidgets")
    assert flags_idx != -1, (
        "oauth_helper.py must set QTWEBENGINE_CHROMIUM_FLAGS (Phase 88.3-03)."
    )
    assert webengine_import_idx != -1, (
        "oauth_helper.py must import QtWebEngineWidgets (Phase 88.3-03)."
    )
    assert flags_idx < webengine_import_idx, (
        f"QTWEBENGINE_CHROMIUM_FLAGS assignment (line index {flags_idx}) must appear "
        f"BEFORE the QtWebEngineWidgets import (line index {webengine_import_idx}). "
        "The Chromium subprocess reads these flags at launch — setting them after "
        "the import is too late (Phase 88.3-03 / existing comment)."
    )

"""Phase 88.2 / D-04: frozen/non-frozen oauth-helper launch dispatch tests.

Linux-runnable; no Windows build required; no QProcess execution.
Tests verify that ``_make_oauth_launch_args`` selects the correct
(program, args) tuple depending on whether ``sys.frozen`` is set.

Tests 3 and 4 verify the ``--oauth-helper`` argv dispatch in
``musicstreamer.__main__._run_oauth_helper``:
  - Test 3: ``--self-test`` short-circuits with exit 0 (no QApplication).
  - Test 4: ``--oauth-helper`` is stripped from argv before forwarding to
    ``oauth_helper.main()``, while ``--mode``/value are preserved.
"""
import sys


# ---------------------------------------------------------------------------
# D-04 Tests 1 & 2 — frozen/non-frozen launch-shape assertions
# ---------------------------------------------------------------------------


def test_frozen_branch_uses_exe_argv_dispatch(monkeypatch):
    """D-04 Test 1: when sys.frozen is True, _make_oauth_launch_args returns
    (sys.executable, ['--oauth-helper', '--mode', m]) — no '-m' in args."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/fake/MusicStreamer.exe")

    # Force reimport so monkeypatched sys is seen at module scope.
    import importlib
    import musicstreamer.subprocess_utils as su
    importlib.reload(su)

    prog, args = su._make_oauth_launch_args("gbs")

    assert prog == "/fake/MusicStreamer.exe"
    assert "--oauth-helper" in args
    assert "--mode" in args
    assert "gbs" in args
    assert "-m" not in args


def test_non_frozen_branch_uses_module_form(monkeypatch):
    """D-04 Test 2: when sys.frozen is absent, _make_oauth_launch_args returns
    sys.executable + ['-m', 'musicstreamer.oauth_helper', '--mode', m]."""
    if hasattr(sys, "frozen"):
        monkeypatch.delattr(sys, "frozen")

    import importlib
    import musicstreamer.subprocess_utils as su
    importlib.reload(su)

    prog, args = su._make_oauth_launch_args("twitch")

    assert prog == sys.executable
    assert "-m" in args
    assert "musicstreamer.oauth_helper" in args
    assert "twitch" in args
    assert "--oauth-helper" not in args


# ---------------------------------------------------------------------------
# D-04 Tests 3 & 4 — __main__._run_oauth_helper dispatch arm
# ---------------------------------------------------------------------------


def test_run_oauth_helper_self_test_returns_0():
    """D-04 Test 3: _run_oauth_helper(['prog', '--oauth-helper', '--self-test'])
    returns 0 immediately — no QApplication, no oauth_helper.main() call."""
    from musicstreamer.__main__ import _run_oauth_helper

    rc = _run_oauth_helper(["prog", "--oauth-helper", "--self-test"])

    assert rc == 0


def test_run_oauth_helper_strips_oauth_helper_flag(monkeypatch):
    """D-04 Test 4: _run_oauth_helper strips '--oauth-helper' before forwarding
    to oauth_helper.main(), preserving '--mode' and 'gbs' in sys.argv."""
    captured = {}

    def _fake_oauth_main():
        captured["argv"] = list(sys.argv)
        # oauth_helper.main() normally calls sys.exit; raise SystemExit to halt.
        raise SystemExit(0)

    import musicstreamer.oauth_helper as oh
    monkeypatch.setattr(oh, "main", _fake_oauth_main)

    from musicstreamer.__main__ import _run_oauth_helper

    try:
        _run_oauth_helper(["prog", "--oauth-helper", "--mode", "gbs"])
    except SystemExit:
        pass

    assert "--oauth-helper" not in captured["argv"]
    assert "--mode" in captured["argv"]
    assert "gbs" in captured["argv"]

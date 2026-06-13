"""Phase 88.2 / D-04 (Test 1 updated in Phase 88.3-03 for B1): frozen/non-frozen
oauth-helper launch dispatch tests.

Linux-runnable; no Windows build required; no QProcess execution.
Tests verify that ``_make_oauth_launch_args`` selects the correct
(program, args) tuple depending on whether ``sys.frozen`` is set. Under the
B1 architecture the frozen branch targets the separate ``oauth_helper.exe``
sibling rather than re-exec'ing ``MusicStreamer.exe``.

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
    """D-04 Test 1 (updated for Phase 88.3-03 / B1): when sys.frozen is True,
    _make_oauth_launch_args launches the SEPARATE sibling oauth_helper.exe —
    ({app}/oauth_helper/oauth_helper.exe, ['--mode', m]).

    The pre-B1 same-bundle contract re-exec'd MusicStreamer.exe with
    '--oauth-helper'; that forced QtWebEngine into the conda bundle (the
    Phase 88.3 G6 DLL-load failure). B1 moved WebEngine into a distinct exe,
    so the frozen branch targets that binary, not sys.executable. The full
    B1 launch-target contract is covered by tests/test_oauth_launch_path.py."""
    from pathlib import Path

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/fake/MusicStreamer.exe")

    # Force reimport so monkeypatched sys is seen at module scope.
    import importlib
    import musicstreamer.subprocess_utils as su
    importlib.reload(su)

    prog, args = su._make_oauth_launch_args("gbs")

    expected_helper = str(
        Path("/fake/MusicStreamer.exe").parent / "oauth_helper" / "oauth_helper.exe"
    )
    assert prog == expected_helper
    assert args == ["--mode", "gbs"]
    assert "--oauth-helper" not in args
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


def test_run_oauth_helper_rejects_in_process_dispatch(monkeypatch, capsys):
    """D-04 Test 4 (updated for Phase 88.3 WR-02): under B1 the conda
    MusicStreamer.exe must NEVER run the WebEngine helper in-process — it
    launches the separate oauth_helper.exe via QProcess. So any non-self-test
    ``--oauth-helper`` invocation reaching _run_oauth_helper is a bug: it
    returns 2 and emits a clear diagnostic, WITHOUT importing oauth_helper
    (whose module-level QtWebEngineWidgets guard would bare-exit 2 with no
    message in the conda bundle).

    This replaces the pre-WR-02 contract that stripped '--oauth-helper' and
    forwarded to oauth_helper.main() in-process. That arm was reachable
    dead-trap code; WR-02 turned it into a loud, diagnosable rejection.
    WR-06 (sys.argv leak) is resolved by removing the sys.argv mutation
    entirely.
    """
    # Snapshot+auto-restore sys.argv to guard against any cross-test leak,
    # even though the new branch no longer mutates it (Phase 88.3 WR-06).
    monkeypatch.setattr(sys, "argv", list(sys.argv))

    from musicstreamer.__main__ import _run_oauth_helper

    rc = _run_oauth_helper(["prog", "--oauth-helper", "--mode", "gbs"])

    assert rc == 2
    captured = capsys.readouterr()
    assert "not supported in the conda bundle" in captured.err
    assert "oauth_helper.exe" in captured.err

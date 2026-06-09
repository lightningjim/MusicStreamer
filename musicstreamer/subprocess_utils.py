"""Centralized subprocess launcher (PKG-03).

All subprocess.Popen calls in musicstreamer/ MUST go through _popen()
so Windows builds suppress console window flashes.

Phase 40 uses QProcess (not subprocess.Popen) for oauth_helper.py,
so this module is a compliance stub. It will be used if any future
phase reintroduces raw subprocess usage.
"""
import subprocess
import sys


def _popen(args, **kwargs):
    """Launch subprocess. Adds CREATE_NO_WINDOW on Windows (PKG-03)."""
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.Popen(args, **kwargs)


def _run(args, **kwargs):
    """``subprocess.run`` mirror with Windows console-flash suppression.

    Use this from anywhere in ``musicstreamer/`` that needs the
    blocking ``subprocess.run`` semantics (return code, captured output,
    timeout). PKG-03 forbids raw ``subprocess.run`` calls in the package
    so all paths flow through here.
    """
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.run(args, **kwargs)


def _make_oauth_launch_args(mode: str) -> tuple[str, list[str]]:
    """Return (program, args) for launching oauth_helper --mode <mode>.

    Phase 88.2 D-01: when running in a PyInstaller-frozen bundle
    (``sys.frozen`` is True), ``sys.executable`` is the frozen exe
    (e.g. ``MusicStreamer.exe``), not a Python interpreter. The
    ``-m musicstreamer.oauth_helper`` form is silently ignored by the
    frozen exe, so the frozen branch re-execs via the ``--oauth-helper``
    argv-dispatch arm added to ``__main__.py``.

    When not frozen (dev / CI), the standard ``-m`` module form is used
    unchanged (T-40-05 contract preserved).

    T-40-05 contract: ``sys.executable`` is always the program (no PATH
    lookup / injection); args are passed as a list, never a shell string,
    never ``shell=True``; ``mode`` is a hardcoded call-site literal
    ("twitch" / "gbs" / ``self._oauth_mode or "google"``), never free
    user input.
    """
    if getattr(sys, "frozen", False):
        return sys.executable, ["--oauth-helper", "--mode", mode]
    return sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", mode]

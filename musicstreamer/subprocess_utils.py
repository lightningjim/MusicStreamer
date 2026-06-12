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

    B1 architecture (Phase 88.3-03): when running in a PyInstaller-frozen
    bundle (``sys.frozen`` is True), the conda main exe launches the
    SEPARATE ``oauth_helper.exe`` built by ``oauth_helper_standalone.spec``
    and Inno-installed to ``{app}\\oauth_helper\\oauth_helper.exe``.

    ``sys.executable`` is ``{app}\\MusicStreamer.exe`` when frozen; the
    helper is its sibling at
    ``Path(sys.executable).parent / "oauth_helper" / "oauth_helper.exe"``.

    The helper has its own bundled pip-PySide6 WebEngine Qt (spike 001),
    completely isolated from the conda main bundle — this is why B1 avoids
    the Phase 88.3 G6 DLL-load-failed ABI conflict. The old self-re-exec
    form (``sys.executable --oauth-helper``) forced QtWebEngine into the
    conda bundle; B1 replaces that with a distinct exe that owns its own Qt.

    A missing ``oauth_helper.exe`` surfaces as QProcess FailedToStart →
    ``accounts_dialog``'s existing ``errorOccurred`` → cookie-import
    fallback (Phase 88.2). This module does NOT need to check for file
    existence — QProcess handles the FailedToStart case and the fallback is
    already wired in the caller.

    When not frozen (dev / CI / Linux), the standard ``-m`` module form is
    used unchanged (T-40-05 contract preserved byte-for-byte).

    T-40-05 contract: program is always derived from ``sys.executable``
    (frozen: sibling path; source: ``sys.executable`` itself) — no PATH
    lookup / injection; args are passed as a list, never a shell string,
    never ``shell=True``; ``mode`` is a hardcoded call-site literal
    ("twitch" / "gbs" / ``self._oauth_mode or "google"``), never free
    user input.
    """
    if getattr(sys, "frozen", False):
        from pathlib import Path
        helper = Path(sys.executable).parent / "oauth_helper" / "oauth_helper.exe"
        return str(helper), ["--mode", mode]
    return sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", mode]

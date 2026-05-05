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

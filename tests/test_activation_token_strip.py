"""Phase 61 Plan 05 — env-strip unit tests.

BUG-08 follow-up. The helper is pure os.environ mutation; tests use
monkeypatch to control env state and verify the pop is unconditional
and exception-free.
"""
from __future__ import annotations

import os

from musicstreamer.__main__ import _strip_inherited_activation_tokens


def test_strip_pops_both_tokens(monkeypatch):
    """Both vars present → both removed."""
    monkeypatch.setenv("XDG_ACTIVATION_TOKEN", "gnome-shell/PyCharm/stale")
    monkeypatch.setenv("DESKTOP_STARTUP_ID", "gnome-shell/PyCharm/stale")
    _strip_inherited_activation_tokens()
    assert "XDG_ACTIVATION_TOKEN" not in os.environ
    assert "DESKTOP_STARTUP_ID" not in os.environ


def test_strip_is_noop_when_absent(monkeypatch):
    """Both vars absent → no KeyError, no env mutation."""
    monkeypatch.delenv("XDG_ACTIVATION_TOKEN", raising=False)
    monkeypatch.delenv("DESKTOP_STARTUP_ID", raising=False)
    _strip_inherited_activation_tokens()  # must not raise
    assert "XDG_ACTIVATION_TOKEN" not in os.environ
    assert "DESKTOP_STARTUP_ID" not in os.environ

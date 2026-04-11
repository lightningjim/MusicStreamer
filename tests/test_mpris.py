"""Tests for the Phase 35 MprisService no-op stub.

Per D-09/D-11 and 35-CONTEXT.md, mpris.py is a no-op stub between
Phase 35 and Phase 41 (MEDIA-02). It preserves the public surface that
``main_window.py`` calls but every method is a no-op. The real QtDBus
implementation will land in Phase 41.
"""
import logging

from musicstreamer.mpris import MprisService


def test_mprisservice_constructs_without_error():
    """Constructor accepts window=None without raising."""
    MprisService(window=None)


def test_mprisservice_accepts_window_arg():
    """Constructor stores the window argument on the stub instance."""
    fake_window = object()
    svc = MprisService(window=fake_window)
    assert svc._window is fake_window


def test_mprisservice_positional_window_arg():
    """Legacy call sites in main_window.py use a positional argument."""
    fake_window = object()
    svc = MprisService(fake_window)
    assert svc._window is fake_window


def test_build_metadata_returns_empty_dict():
    """_build_metadata returns {} — the stub carries no metadata state."""
    svc = MprisService(None)
    assert svc._build_metadata() == {}


def test_emit_properties_changed_is_noop():
    """emit_properties_changed accepts any dict and returns None silently."""
    svc = MprisService(None)
    result = svc.emit_properties_changed({"PlaybackStatus": "Playing"})
    assert result is None


def test_emit_properties_changed_accepts_empty():
    """Empty-dict payload is accepted by the no-op stub."""
    svc = MprisService(None)
    assert svc.emit_properties_changed({}) is None


def test_emit_properties_changed_accepts_complex_payload():
    """Complex MPRIS-shaped payload (legacy call sites pass these) is a no-op."""
    svc = MprisService(None)
    payload = {
        "PlaybackStatus": "Playing",
        "Metadata": {
            "mpris:trackid": "/org/example/track/1",
            "xesam:title": "Song",
            "xesam:artist": ["Artist"],
        },
    }
    assert svc.emit_properties_changed(payload) is None


def test_construction_logs_debug_warning(caplog):
    """Stub construction emits a debug log so media-key loss is discoverable."""
    with caplog.at_level(logging.DEBUG, logger="musicstreamer.mpris"):
        MprisService(None)
    assert any("stub" in rec.message.lower() for rec in caplog.records)


def test_stub_module_has_no_forbidden_imports():
    """Regression guard: mpris.py must not import the legacy D-Bus library
    or ``gi`` in Phase 35 — D-09 / D-11 require a zero-dependency stub."""
    import musicstreamer.mpris as m
    src = open(m.__file__, encoding="utf-8").read()
    # Built via concatenation so this test file does not itself contain
    # the literal forbidden tokens (keeps the QA-02 grep gate clean).
    _d = "d" + "bus"
    forbidden = [f"import {_d}", f"from {_d}", "import gi", "from gi"]
    for needle in forbidden:
        assert needle not in src, f"mpris.py must not contain: {needle!r}"

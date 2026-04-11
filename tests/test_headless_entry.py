"""Smoke test for the Phase 35 headless __main__ entry point.

Verifies ``musicstreamer.__main__.main(argv)`` wires QCoreApplication +
Player + signal connections without touching the real GStreamer backend
or network.
"""
from unittest.mock import MagicMock


def test_headless_main_wires_without_error(monkeypatch, qtbot):
    # Stub Player so the real GStreamer pipeline + bus bridge never start.
    fake_player = MagicMock()
    monkeypatch.setattr(
        "musicstreamer.__main__.Player", lambda *a, **k: fake_player
    )

    # Stub Gst.init and migration.run_migration so the entry is pure.
    monkeypatch.setattr("musicstreamer.__main__.Gst.init", lambda _: None)
    monkeypatch.setattr(
        "musicstreamer.__main__.migration.run_migration", lambda: None
    )

    # Stub the QCoreApplication constructor used by __main__ to return a
    # pure mock (exec returns 0 immediately). This avoids colliding with the
    # real QApplication that qtbot has already instantiated for the session.
    fake_app = MagicMock()
    fake_app.exec.return_value = 0
    monkeypatch.setattr(
        "musicstreamer.__main__.QCoreApplication", lambda argv: fake_app
    )
    # QTimer.singleShot is called; stub it so the lambda doesn't touch the
    # fake Player in a deferred context that never runs.
    monkeypatch.setattr(
        "musicstreamer.__main__.QTimer", MagicMock()
    )

    from musicstreamer.__main__ import main

    rc = main(["prog", "http://example.invalid/stream"])
    assert rc == 0
    # Signal connections should have been wired on the fake Player.
    assert fake_player.title_changed.connect.called
    assert fake_player.playback_error.connect.called
    assert fake_player.failover.connect.called
    assert fake_player.offline.connect.called

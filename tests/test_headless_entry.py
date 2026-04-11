"""Smoke test for the ``--smoke URL`` headless backend entry point.

Phase 36 rewrote ``musicstreamer.__main__`` to split GUI vs headless
behind argparse. The headless Phase 35 harness lives behind ``--smoke``
and its Player/Gst/QCoreApplication imports are now function-local inside
``_run_smoke``. This test verifies the wiring still works end-to-end
without touching the real GStreamer backend or network.
"""
from unittest.mock import MagicMock


def test_headless_smoke_wires_without_error(monkeypatch, qtbot):
    # Stub Player so the real GStreamer pipeline + bus bridge never start.
    fake_player = MagicMock()
    monkeypatch.setattr(
        "musicstreamer.player.Player", lambda *a, **k: fake_player
    )

    # Stub Gst.init and migration.run_migration so the entry is pure.
    monkeypatch.setattr("musicstreamer.__main__.Gst.init", lambda _: None)
    monkeypatch.setattr(
        "musicstreamer.migration.run_migration", lambda: None
    )

    # Stub the QCoreApplication constructor used inside _run_smoke to
    # return a pure mock (exec returns 0 immediately). This avoids
    # colliding with the real QApplication qtbot has already instantiated.
    fake_app = MagicMock()
    fake_app.exec.return_value = 0
    monkeypatch.setattr(
        "PySide6.QtCore.QCoreApplication", lambda argv: fake_app
    )
    # QTimer.singleShot is called; stub it so the lambda doesn't touch
    # the fake Player in a deferred context that never runs.
    import PySide6.QtCore as _qtcore
    monkeypatch.setattr(_qtcore, "QTimer", MagicMock())

    from musicstreamer.__main__ import main

    rc = main(["prog", "--smoke", "http://example.invalid/stream"])
    assert rc == 0
    # Signal connections should have been wired on the fake Player.
    assert fake_player.title_changed.connect.called
    assert fake_player.playback_error.connect.called
    assert fake_player.failover.connect.called
    assert fake_player.offline.connect.called

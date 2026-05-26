"""Phase 85a spike: minimal playbin3 over HTTP/HTTPS, no Qt bus bridge.

Mirrors Phase 43 smoke_test.py shape
(.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/
smoke_test.py); deliberately simpler to keep failure-surface narrow per
85A-CONTEXT.md D-Discretion (no Qt bus bridge). The Phase 43.1 contract for
Qt<->GLib bus integration (see qt-glib-bus-threading.md) is already validated
cross-platform; re-exercising it here would expand failure surface without
de-risking anything Linux-specific. PySide6 is intentionally not imported
here; the bundled conda env still ships it for Phase 85's real-app use.

Exit codes:
  0 — pipeline reached PLAYING + ran 30s clean (emits SPIKE_OK)
  1 — usage error (no/too-many argv)
  2 — pipeline error (emits SPIKE_FAIL step='pipeline')
  3 — never reached PLAYING within 40s wall budget (emits SPIKE_FAIL step='never_played')

Reference: 85A-RESEARCH.md §Minimal hello_world.py (lines 407-507).
"""
from __future__ import annotations

import sys
import time


def _emit(prefix: str, **kv: object) -> None:
    """Stable greppable diagnostic line.

    Prefix in {SPIKE_OK, SPIKE_FAIL, SPIKE_DIAG}. Kwargs stringified as
    `key=value!r` pairs (repr-quoted for unambiguous parsing).
    """
    parts = [prefix] + [f"{k}={v!r}" for k, v in kv.items()]
    print(" ".join(parts), flush=True)


def main(argv: list[str]) -> int:
    # IMPORTANT: argv validation MUST run before any GStreamer import side-effects
    # so `python3 hello_world.py` emits the expected SPIKE_FAIL marker even when
    # PyGObject isn't installed on the host's python3 (the test gate uses this).
    if len(argv) != 2:
        _emit("SPIKE_FAIL", reason="usage", expected="hello_world.py <url>")
        return 1

    url = argv[1].strip()

    # Deferred GStreamer import — only reached after argv check.
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib  # noqa: E402

    Gst.init(None)
    _emit(
        "SPIKE_DIAG",
        gst_version=Gst.version_string(),
        plugin_count=len(Gst.Registry.get().get_plugin_list()),
        url_scheme=url.split(":", 1)[0],
    )

    # parse_launch keeps surface tiny — no element wiring, no caps negotiation,
    # no audio-sink property (autoaudiosink default per Pitfall 10).
    pipeline = Gst.parse_launch(f'playbin3 uri="{url}"')
    state: dict[str, object] = {
        "errors": [],
        "playing_at": None,
        "first_tag_at": None,
    }

    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def _on_message(_bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            state["errors"].append(f"{err.message} | {debug}")  # type: ignore[union-attr]
        elif msg.type == Gst.MessageType.STATE_CHANGED:
            if msg.src == pipeline:
                _old, new, _pending = msg.parse_state_changed()
                if new == Gst.State.PLAYING and state["playing_at"] is None:
                    state["playing_at"] = time.monotonic()
                    _emit("SPIKE_DIAG", event="reached_playing")
        elif msg.type == Gst.MessageType.TAG and state["first_tag_at"] is None:
            state["first_tag_at"] = time.monotonic()
            _emit("SPIKE_DIAG", event="first_tag")

    bus.connect("message", _on_message)
    pipeline.set_state(Gst.State.PLAYING)

    loop = GLib.MainLoop()
    start = time.monotonic()

    def _tick():
        if state["errors"]:
            loop.quit()
            return False
        elapsed = time.monotonic() - start
        playing_at = state["playing_at"]
        if playing_at is not None and (time.monotonic() - playing_at) >= 30.0:  # type: ignore[operator]
            loop.quit()
            return False
        if elapsed >= 40.0:  # 10s to PLAYING + 30s playback budget
            loop.quit()
            return False
        return True

    GLib.timeout_add(200, _tick)
    try:
        loop.run()
    finally:
        pipeline.set_state(Gst.State.NULL)

    if state["errors"]:
        _emit("SPIKE_FAIL", step="pipeline", errors=state["errors"])
        return 2
    if state["playing_at"] is None:
        _emit("SPIKE_FAIL", step="never_played")
        return 3

    playing_at = state["playing_at"]
    first_tag_at = state["first_tag_at"] or 0
    _emit(
        "SPIKE_OK",
        time_to_play_s=round(playing_at - start, 2),  # type: ignore[operator]
        first_tag_s=round(first_tag_at - start, 2),  # type: ignore[operator]
        played_for_s=round(time.monotonic() - playing_at, 2),  # type: ignore[operator]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

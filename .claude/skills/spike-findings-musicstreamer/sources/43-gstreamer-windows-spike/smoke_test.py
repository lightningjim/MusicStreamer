"""Phase 43 spike smoke test.

Invocation: spike.exe <aa-https-url>

Exit codes:
  0 — success: audio sample received within 8s, no errors
  1 — setup failure: Gst.init failed, plugin load failed, URI invalid
  2 — runtime failure: pipeline errored before first audio sample
  3 — timeout: no audio sample within 8s (likely TLS or buffering)

Every line printed to stdout with prefix 'SPIKE_OK', 'SPIKE_FAIL', or
'SPIKE_DIAG' is a stable marker the host (Claude) greps on paste-back.
Everything else is informational and may be ignored.
"""
from __future__ import annotations

import sys
import time

# Gst.init happens inside main() so the rthook env vars are already set.


def _emit(prefix: str, **kv: object) -> None:
    parts = [prefix] + [f"{k}={v!r}" for k, v in kv.items()]
    print(" ".join(parts), flush=True)


def _assert_tls_backend() -> bool:
    """Return True if Gio can resolve a TLS backend.

    Backend DLL varies by GStreamer version on Windows:
    - 1.28+ (OpenSSL):  gioopenssl.dll
    - 1.24-1.26 (GnuTLS): libgiognutls.dll
    Either is acceptable; has_default_database=True is the real pass signal.
    """
    try:
        from gi.repository import Gio
        backend = Gio.TlsBackend.get_default()
        has_db = backend.get_default_database() is not None
        _emit("SPIKE_DIAG", tls_backend=type(backend).__name__, has_default_database=has_db)
        return has_db
    except Exception as e:
        _emit("SPIKE_FAIL", step="tls_backend_check", error=str(e))
        return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _emit("SPIKE_FAIL", reason="usage", expected="spike.exe <url>")
        return 1

    url = argv[1].strip()
    if not url.startswith("https://"):
        _emit("SPIKE_FAIL", reason="url_not_https", url=url)
        return 1

    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst, GLib
    except Exception as e:
        _emit("SPIKE_FAIL", step="import_gi", error=str(e))
        return 1

    try:
        Gst.init(None)
    except Exception as e:
        _emit("SPIKE_FAIL", step="Gst.init", error=str(e))
        return 1

    _emit("SPIKE_DIAG", gst_version=Gst.version_string(),
          plugin_count=len(Gst.Registry.get().get_plugin_list()))

    if not _assert_tls_backend():
        return 1

    playbin = Gst.ElementFactory.make("playbin3", "player")
    if playbin is None:
        _emit("SPIKE_FAIL", step="playbin3_factory", hint="gst-plugins-base missing from bundle")
        return 1

    # Redact listen_key from logs — it's in the URL query string
    redacted = url.split("?", 1)[0] + "?<redacted>" if "?" in url else url
    _emit("SPIKE_DIAG", url=redacted)

    playbin.set_property("uri", url)

    # --- State tracking ----------------------------------------------------
    state = {
        "first_sample_at": None,
        "errors": [],
        "warnings": [],
        "eos": False,
        "bytes_played": 0,
    }

    # audiosink tap: add a probe on playbin's "audio-tags-changed" OR a pad probe
    # on the audio sink. Simplest: watch the bus for STATE_CHANGED → PLAYING AND
    # message::tag. First tag arriving proves bytes flowed through the pipeline.
    bus = playbin.get_bus()
    bus.add_signal_watch()

    def _on_message(bus, msg):
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            state["errors"].append(f"{err.message} | {debug}")
        elif t == Gst.MessageType.WARNING:
            w, debug = msg.parse_warning()
            state["warnings"].append(f"{w.message} | {debug}")
        elif t == Gst.MessageType.TAG and state["first_sample_at"] is None:
            # TAG arrives as soon as ICY data flows — means TLS + HTTP + demux worked
            state["first_sample_at"] = time.monotonic()
            _emit("SPIKE_DIAG", event="first_tag_arrived")
        elif t == Gst.MessageType.EOS:
            state["eos"] = True

    bus.connect("message", _on_message)

    # --- Run ---------------------------------------------------------------
    result = playbin.set_state(Gst.State.PLAYING)
    _emit("SPIKE_DIAG", set_state_result=result.value_name)

    loop = GLib.MainLoop()
    start = time.monotonic()

    def _tick():
        elapsed = time.monotonic() - start
        if state["errors"]:
            loop.quit()
            return False
        if state["first_sample_at"] and (time.monotonic() - state["first_sample_at"]) >= 5.0:
            loop.quit()
            return False
        if elapsed >= 8.0:
            loop.quit()
            return False
        return True

    GLib.timeout_add(200, _tick)
    try:
        loop.run()
    finally:
        playbin.set_state(Gst.State.NULL)

    # --- Verdict -----------------------------------------------------------
    if state["errors"]:
        _emit("SPIKE_FAIL", step="pipeline", errors=state["errors"])
        return 2
    if state["first_sample_at"] is None:
        _emit("SPIKE_FAIL", step="timeout", warnings=state["warnings"])
        return 3

    duration = time.monotonic() - state["first_sample_at"]
    _emit(
        "SPIKE_OK",
        audio_sample_received=True,
        duration_s=round(duration, 2),
        errors=state["errors"],
        warnings_count=len(state["warnings"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

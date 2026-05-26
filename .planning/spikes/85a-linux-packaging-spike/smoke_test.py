"""Phase 85a spike validation harness.

Mirrors Phase 43 smoke_test.py shape
(.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/
smoke_test.py), Linux-tuned. Extends hello_world.py's playback driver with
the four validation modes RESEARCH.md §Validation Dimensions (lines 656-666)
calls for:

  D1  Pipeline state assertion (PLAYING + 30s clean)                 --uri
  D2  GLIBC source-grep (max symbol version <= GLIBC_2.35)           --check-glibc <path>
  D3  Plugin resolution (avdec_aac, aacparse via gst-inspect-1.0)    --check-plugins <list>
  TLS Gio.TlsBackend has a default database (Pitfall 4)              --assert-tls

Exit codes:
  0 — OK
  1 — usage / setup
  2 — pipeline runtime error
  3 — never-reached-PLAYING within --timeout
  4 — GLIBC > 2.35 (success criterion #2 violation)
  5 — required plugin missing (gst-inspect non-zero)
  6 — TLS backend has no default database (Pitfall 4 regression)

Stable stdout markers (grep contract — DO NOT change without coordinating
with Plan 06 Task 2's transcript grep gates):
  SPIKE_OK     — final success line
  SPIKE_FAIL   — final failure line (with step=... reason=...)
  SPIKE_DIAG   — intermediate diagnostic line
  plugin_resolved=<name>
               — REQUIRED literal substring under SPIKE_DIAG that Plan 06
                 Task 2 greps for ('plugin_resolved=.avdec_aac' /
                 'plugin_resolved=.aacparse'); locked at author-time per
                 PLAN.md Issue #4 cross-plan contract.

URL gating (Threat T-85A-04-IV / RESEARCH.md §Security V5): scheme must be
http or https; host must match *.somafm.com.

Pitfalls referenced:
  2  — gst-inspect avdec_aac + aacparse (plugin discovery)
  3  — relaunch protocol exercises GST_REGISTRY_FORK (AppRun template)
  4  — GIO_EXTRA_MODULES + Gio.TlsBackend assertion
  9  — TAG event timestamp capture (first_tag_s)
  10 — autoaudiosink election logging (sink_elected)
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse


# -----------------------------------------------------------------------------
# Module-level helpers
# -----------------------------------------------------------------------------


def _emit(prefix: str, **kv: object) -> None:
    """Stable greppable diagnostic line; matches hello_world.py shape."""
    parts = [prefix] + [f"{k}={v!r}" for k, v in kv.items()]
    print(" ".join(parts), flush=True)


def _validate_url(url: str) -> tuple[bool, str]:
    """Returns (ok, reason). Scheme must be http/https; host must match *.somafm.com.

    Threat T-85A-04-IV mitigation (RESEARCH.md §Security V5): prevent accidental
    SSRF-like exec during dev iteration. SomaFM is the only sanctioned target
    per CONTEXT.md D-07/D-08/D-09.
    """
    try:
        parsed = urlparse(url)
    except Exception as ex:  # pragma: no cover — argparse upstream usually catches
        return False, f"parse_error:{ex!r}"
    if parsed.scheme not in ("http", "https"):
        return False, f"bad_scheme:{parsed.scheme!r}"
    host = (parsed.hostname or "").lower()
    if not (host == "somafm.com" or host.endswith(".somafm.com")):
        return False, f"bad_host:{host!r}"
    return True, "ok"


def _load_fallback_chain(path: str) -> list[str]:
    """Reads test_url.txt; returns list of non-comment, non-blank lines."""
    urls: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                urls.append(line)
    except FileNotFoundError:
        pass
    return urls


# -----------------------------------------------------------------------------
# Mode: --check-glibc (D2)
# -----------------------------------------------------------------------------


GLIBC_PATTERN = re.compile(r"GLIBC_(\d+)\.(\d+)")


def _version_tuple(token: str) -> tuple[int, int]:
    m = GLIBC_PATTERN.search(token)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def check_glibc(path: str) -> int:
    """Greps GLIBC_X.Y symbols out of <path>; exits 4 if max > GLIBC_2.35."""
    try:
        result = subprocess.run(
            ["strings", path],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except FileNotFoundError:
        _emit("SPIKE_FAIL", step="check_glibc", reason="strings_missing")
        return 1
    if result.returncode != 0:
        _emit(
            "SPIKE_FAIL",
            step="check_glibc",
            reason="strings_nonzero",
            rc=result.returncode,
            stderr=result.stderr[:200],
        )
        return 1
    versions = sorted(
        {tup for line in result.stdout.splitlines() for tup in [_version_tuple(line)] if tup != (0, 0)}
    )
    if not versions:
        _emit("SPIKE_DIAG", glibc_max="none_found", path=path)
        return 0
    max_v = versions[-1]
    glibc_max = f"GLIBC_{max_v[0]}.{max_v[1]}"
    _emit("SPIKE_DIAG", glibc_max=glibc_max, path=path)
    if max_v > (2, 35):
        _emit(
            "SPIKE_FAIL",
            step="check_glibc",
            reason="exceeds_2_35",
            glibc_max=glibc_max,
        )
        return 4
    return 0


# -----------------------------------------------------------------------------
# Mode: --check-plugins (D3; avdec_aac + aacparse default)
# -----------------------------------------------------------------------------


def check_plugins(names_csv: str) -> int:
    """For each plugin name, runs `gst-inspect-1.0 <name>`. Exits 5 if any miss.

    Emits one SPIKE_DIAG line per name with the literal `plugin_resolved=`
    prefix (REQUIRED — Plan 06 Task 2 transcript grep gate per Issue #4).
    """
    names = [n.strip() for n in names_csv.split(",") if n.strip()]
    if not names:
        _emit("SPIKE_FAIL", step="check_plugins", reason="empty_list")
        return 1
    any_missing = False
    for name in names:
        try:
            result = subprocess.run(
                ["gst-inspect-1.0", name],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except FileNotFoundError:
            _emit(
                "SPIKE_DIAG",
                plugin_resolved=name,
                status="error",
                reason="gst_inspect_missing",
            )
            any_missing = True
            continue
        if result.returncode == 0:
            _emit("SPIKE_DIAG", plugin_resolved=name, status="ok")
        else:
            _emit(
                "SPIKE_DIAG",
                plugin_resolved=name,
                status="missing",
                rc=result.returncode,
            )
            any_missing = True
    if any_missing:
        _emit("SPIKE_FAIL", step="check_plugins", reason="plugin_missing")
        return 5
    return 0


# -----------------------------------------------------------------------------
# Mode: --assert-tls (Pitfall 4)
# -----------------------------------------------------------------------------


def assert_tls() -> int:
    """Asserts Gio.TlsBackend.get_default().get_default_database() is not None."""
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio  # noqa: E402
    except Exception as ex:
        _emit("SPIKE_FAIL", step="assert_tls", reason="gi_import", error=repr(ex))
        return 1
    backend = Gio.TlsBackend.get_default()
    db = backend.get_default_database()
    has_db = db is not None
    _emit(
        "SPIKE_DIAG",
        tls_backend=type(backend).__name__,
        has_default_database=has_db,
        gio_modules=os.environ.get("GIO_EXTRA_MODULES", ""),
    )
    if not has_db:
        _emit("SPIKE_FAIL", step="assert_tls", reason="no_default_database")
        return 6
    return 0


# -----------------------------------------------------------------------------
# Mode: playback (D1, Pitfalls 9 + 10)
# -----------------------------------------------------------------------------


def play_url(url: str, timeout_s: float) -> int:
    """Mirrors hello_world.py main() with extras: URL gate, sink election log
    (Pitfall 10), TAG timestamp capture (Pitfall 9).
    """
    ok, reason = _validate_url(url)
    if not ok:
        _emit("SPIKE_FAIL", step="argv_url", reason="url_validation", detail=reason, url=url)
        return 1

    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst, GLib  # noqa: E402
    except Exception as ex:
        _emit("SPIKE_FAIL", step="setup", reason="gi_import", error=repr(ex))
        return 1

    Gst.init(None)
    _emit(
        "SPIKE_DIAG",
        gst_version=Gst.version_string(),
        plugin_count=len(Gst.Registry.get().get_plugin_list()),
        url_scheme=url.split(":", 1)[0],
    )

    pipeline = Gst.parse_launch(f'playbin3 uri="{url}"')
    state: dict[str, object] = {
        "errors": [],
        "playing_at": None,
        "first_tag_at": None,
        "sink_logged": False,
    }

    def _log_sink_election():
        """Pitfall 10: walk pipeline for the elected sink and emit it.

        Best-effort: tries playbin3 audio-sink property first; falls back to
        iterate_recurse() looking for any GstBaseSink-derived element.
        """
        if state["sink_logged"]:
            return
        elected = None
        try:
            sink_prop = pipeline.get_property("audio-sink")
            if sink_prop is not None:
                elected = sink_prop.get_factory().get_name() if sink_prop.get_factory() else type(sink_prop).__name__
        except Exception:
            elected = None
        if elected is None:
            try:
                it = pipeline.iterate_recurse()
                done = False
                while not done:
                    res, elem = it.next()
                    if res == Gst.IteratorResult.OK:
                        factory = elem.get_factory()
                        if factory is not None and "Sink" in factory.get_klass():
                            elected = factory.get_name()
                            break
                    elif res == Gst.IteratorResult.DONE:
                        done = True
                    else:
                        break
            except Exception:
                elected = None
        _emit("SPIKE_DIAG", sink_elected=str(elected) if elected else "unknown")
        state["sink_logged"] = True

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
                    _log_sink_election()
        elif msg.type == Gst.MessageType.TAG and state["first_tag_at"] is None:
            state["first_tag_at"] = time.monotonic()
            now = state["first_tag_at"]
            _emit("SPIKE_DIAG", event="first_tag", first_tag_s=round(now, 3))  # type: ignore[arg-type]

    bus.connect("message", _on_message)
    pipeline.set_state(Gst.State.PLAYING)

    loop = GLib.MainLoop()
    start = time.monotonic()
    wall_budget = max(timeout_s + 10.0, 40.0)

    def _tick():
        if state["errors"]:
            loop.quit()
            return False
        elapsed = time.monotonic() - start
        playing_at = state["playing_at"]
        if playing_at is not None and (time.monotonic() - playing_at) >= timeout_s:  # type: ignore[operator]
            loop.quit()
            return False
        if elapsed >= wall_budget:
            loop.quit()
            return False
        return True

    GLib.timeout_add(200, _tick)
    try:
        loop.run()
    finally:
        pipeline.set_state(Gst.State.NULL)

    if state["errors"]:
        _emit("SPIKE_FAIL", step="pipeline", errors=state["errors"], url=url)
        return 2
    if state["playing_at"] is None:
        _emit("SPIKE_FAIL", step="never_played", url=url)
        return 3

    playing_at = state["playing_at"]
    first_tag_at = state["first_tag_at"] or 0
    _emit(
        "SPIKE_OK",
        url=url,
        time_to_play_s=round(playing_at - start, 2),  # type: ignore[operator]
        first_tag_s=round(first_tag_at - start, 2),  # type: ignore[operator]
        played_for_s=round(time.monotonic() - playing_at, 2),  # type: ignore[operator]
    )
    return 0


def play_with_fallback(timeout_s: float) -> int:
    """Reads test_url.txt next to this script; tries each URL in order.

    Hard-fail with SPIKE_FAIL step='fallback_exhausted' if all entries fail.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "test_url.txt")
    urls = _load_fallback_chain(path)
    if not urls:
        _emit("SPIKE_FAIL", step="fallback_load", reason="test_url_txt_missing_or_empty", path=path)
        return 1
    _emit("SPIKE_DIAG", fallback_chain_len=len(urls), source=path)
    last_rc = 1
    for url in urls:
        _emit("SPIKE_DIAG", event="fallback_try", url=url)
        rc = play_url(url, timeout_s)
        if rc == 0:
            return 0
        last_rc = rc
    _emit("SPIKE_FAIL", step="fallback_exhausted", tried=len(urls), last_rc=last_rc)
    return last_rc


# -----------------------------------------------------------------------------
# argv
# -----------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smoke_test.py",
        description=(
            "Phase 85a spike validation harness. Modes: --uri (playback), "
            "--check-glibc, --check-plugins (avdec_aac,aacparse), --assert-tls. "
            "Bare invocation (no flags) emits SPIKE_FAIL reason='usage' and "
            "exits 1 — used as a host-side liveness check that doesn't require "
            "PyGObject."
        ),
    )
    p.add_argument("--uri", default=None, help="Stream URL (SomaFM only); falls back to test_url.txt chain if absent")
    p.add_argument("--timeout", type=float, default=30.0, help="Seconds of clean PLAYING required for SPIKE_OK")
    p.add_argument("--assert-tls", action="store_true", help="Assert Gio.TlsBackend has a default database (Pitfall 4)")
    p.add_argument("--check-glibc", default=None, metavar="PATH", help="Run strings | grep GLIBC_; exit 4 if > GLIBC_2.35")
    p.add_argument(
        "--check-plugins",
        default=None,
        metavar="NAMES",
        help="Comma-separated plugin names (default test: avdec_aac,aacparse) — runs gst-inspect-1.0 each, exit 5 on miss",
    )
    return p


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        _emit("SPIKE_FAIL", reason="usage", expected="smoke_test.py [--uri URL] [--check-glibc PATH] [--check-plugins NAMES] [--assert-tls]")
        return 1
    parser = _build_parser()
    args = parser.parse_args(argv[1:])

    if args.check_glibc:
        return check_glibc(args.check_glibc)

    if args.check_plugins:
        return check_plugins(args.check_plugins)

    if args.assert_tls and not args.uri:
        return assert_tls()

    if args.uri:
        if args.assert_tls:
            rc = assert_tls()
            if rc != 0:
                return rc
        return play_url(args.uri, args.timeout)

    return play_with_fallback(args.timeout)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

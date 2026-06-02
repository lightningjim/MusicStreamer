"""Phase 85 production AppImage smoke harness — D-04 codec sweep + D-05 production import.

Mirrors Phase 43 smoke_test.py shape
(.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/
smoke_test.py), Linux-tuned. Extends the Phase 85a spike harness with the
four D-04 codec-sweep modes and the D-05 production-import guard.

Validation Dimensions:

  D1  Pipeline state assertion (PLAYING + N-s clean)                   --uri
  D2  GLIBC source-grep (max symbol version <= GLIBC_2.35)            --check-glibc <path>
  D3  Plugin resolution (avdec_aac, aacparse via gst-inspect-1.0)     --check-plugins <list>
  TLS Gio.TlsBackend has a default database (Pitfall 4)               --assert-tls
  MP3 D-04: SomaFM MP3 stream via production resolver (D-05)          --check-mp3
  AAC D-04: SomaFM AAC stream via production resolver (D-05)          --check-aac
  AACP D-04: SomaFM HE-AAC/AACP stream via production resolver (D-05) --check-aacp
  PLS D-04: .pls URL resolved via production resolver (D-05) + play   --check-pls

Exit codes:
  0 — OK
  1 — usage / setup
  2 — pipeline runtime error
  3 — never-reached-PLAYING within --timeout
  4 — GLIBC > 2.35 (success criterion #2 violation)
  5 — required plugin missing (gst-inspect non-zero)
  6 — TLS backend has no default database (Pitfall 4 regression)

Stable stdout markers (grep contract — DO NOT change without coordinating
with tools/linux-build/run-smoke.sh transcript grep gates):
  SPIKE_OK     — final success line
  SPIKE_FAIL   — final failure line (with step=... reason=...)
  SPIKE_DIAG   — intermediate diagnostic line
  plugin_resolved=<name>
               — REQUIRED literal substring under SPIKE_DIAG that run-smoke.sh
                 greps for ('plugin_resolved=.avdec_aac' /
                 'plugin_resolved=.aacparse'); locked at author-time per
                 cross-plan contract.

URL gating (Threat T-85-04-IV): scheme must be http or https; host must match
*.somafm.com, *.di.fm, or *.audioaddict.com (D-04 multi-host allowlist).

Pitfalls referenced:
  2  — gst-inspect avdec_aac + aacparse (plugin discovery)
  3  — relaunch protocol exercises GST_REGISTRY_FORK (AppRun template)
  4  — GIO_EXTRA_MODULES + Gio.TlsBackend assertion
  9  — TAG event timestamp capture (first_tag_s)
  10 — autoaudiosink election logging (sink_elected)
  17 — SSL_CERT_FILE for bundled OpenSSL (HTTPS playback)
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

# D-05: import the production resolver so this smoke catches dependency-graph
# and import-path regressions in the bundled env, not just media-pipeline issues.
# If `from musicstreamer import url_helpers` fails inside the AppImage, the
# bundle is broken at the application level even if GStreamer itself works.
try:
    from musicstreamer import url_helpers as _ms_url_helpers
    _MS_IMPORT_OK = True
    _MS_IMPORT_ERR = None
except Exception as ex:  # noqa: BLE001 — we want to capture any import failure
    _ms_url_helpers = None
    _MS_IMPORT_OK = False
    _MS_IMPORT_ERR = repr(ex)


# D-04 default URL families (override via --uri if needed for ad-hoc testing).
_MP3_URL  = "http://ice1.somafm.com/groovesalad-128-mp3"
_AAC_URL  = "http://ice1.somafm.com/groovesalad-128-aac"
# SomaFM retired the `-64-aacp` suffix (now HTTP 404, verified 2026-06-01). Its
# low-bitrate `-aac` streams ARE the HE-AAC/AAC+ tier: 32 kbps stereo AAC is only
# viable as HE-AACv2 (SBR + PS), so this URL still exercises the SBR decode path
# that the 128 kbps AAC-LC `_AAC_URL` does not.
_AACP_URL = "http://ice1.somafm.com/groovesalad-32-aac"
_PLS_URL  = "https://somafm.com/groovesalad130.pls"


# -----------------------------------------------------------------------------
# Module-level helpers
# -----------------------------------------------------------------------------


def _emit(prefix: str, **kv: object) -> None:
    """Stable greppable diagnostic line; matches hello_world.py shape."""
    parts = [prefix] + [f"{k}={v!r}" for k, v in kv.items()]
    print(" ".join(parts), flush=True)


def _validate_url(url: str) -> tuple[bool, str]:
    """Returns (ok, reason). Scheme must be http/https; host must match
    *.somafm.com, *.di.fm, or *.audioaddict.com (D-04 multi-host allowlist).

    Threat T-85-04-IV mitigation: prevent accidental SSRF-like exec during
    dev iteration. The allowed hosts cover the D-04 codec-sweep URL families.
    """
    try:
        parsed = urlparse(url)
    except Exception as ex:  # pragma: no cover — argparse upstream usually catches
        return False, f"parse_error:{ex!r}"
    if parsed.scheme not in ("http", "https"):
        return False, f"bad_scheme:{parsed.scheme!r}"
    host = (parsed.hostname or "").lower()
    allowed = (
        host == "somafm.com" or host.endswith(".somafm.com")
        or host == "di.fm" or host.endswith(".di.fm")
        or host == "audioaddict.com" or host.endswith(".audioaddict.com")
    )
    if not allowed:
        return False, f"bad_host:{host!r}"
    return True, "ok"


def _resolve_via_production(url: str) -> tuple[bool, str, str]:
    """Calls musicstreamer.url_helpers to resolve/normalize the URL via the
    production code path.

    Returns (ok, resolved_url, reason). On import failure (bundle broken),
    returns (False, '', 'import_failed:...'). On resolver exception, returns
    (False, '', 'resolve_failed:...'). Successful pass-through returns
    (True, resolved_url, 'ok').

    Executor note: url_helpers.py (read 2026-05-28) exposes URL classification
    and normalization helpers but no `resolve()` entry point. The primary
    production-code entry point for URL normalization at the Player boundary is
    `aa_normalize_stream_url()`. For --check-mp3/aac/aacp, this normalizes AA
    DI.fm https:// → http:// rewrites; for SomaFM URLs it is an identity pass.
    --check-pls does NOT use this function — playbin3 cannot parse a .pls text
    file, so that mode resolves through _resolve_pls_via_production() (the Phase
    58 playlist parser) instead. The D-05 guard is satisfied by the *import* itself — importing
    url_helpers from the bundled env catches dependency-graph and import-path
    regressions regardless of which entry point we call.
    """
    if not _MS_IMPORT_OK:
        return False, "", f"import_failed:{_MS_IMPORT_ERR}"
    try:
        # aa_normalize_stream_url is the production URL normalization entry point
        # at the Player URI boundary (Phase 56 / WIN-01 / D-04 in url_helpers.py).
        # For non-DI.fm URLs (SomaFM, .pls) this is an identity pass.
        resolved = _ms_url_helpers.aa_normalize_stream_url(url)  # type: ignore[union-attr]
    except AttributeError:
        # Surface the actual module namespace so the developer can fix it.
        public_names = [n for n in dir(_ms_url_helpers) if not n.startswith("_")]
        return False, "", f"resolve_failed:url_helpers has no .aa_normalize_stream_url(); public={public_names}"
    except Exception as ex:  # noqa: BLE001
        return False, "", f"resolve_failed:{ex!r}"
    return True, str(resolved), "ok"


def _resolve_pls_via_production(url: str) -> tuple[bool, str, str]:
    """Resolve a .pls playlist to its first inner stream URL via the production
    Phase 58 parser (musicstreamer.playlist_parser.parse_playlist).

    Returns (ok, resolved_url, reason), mirroring _resolve_via_production.

    Why a dedicated path: aa_normalize_stream_url (used by the mp3/aac/aacp modes)
    normalizes DI.fm scheme/host and is an identity pass otherwise — it does NOT
    parse playlists. Feeding a .pls straight to playbin3 fails with "ParseBin
    cannot parse plain text files". The production app expands .pls through the
    Phase 58 parser, so the pls mode must exercise THAT entry point (D-05).

    We fetch with stdlib urllib (no third-party HTTP dep is bundled) and call the
    pure parser directly rather than aa_import._resolve_pls — the latter falls
    back to [pls_url] on any error, which would silently mask a parse regression
    behind the same playbin3 failure this mode exists to catch.
    """
    if not _MS_IMPORT_OK:
        return False, "", f"import_failed:{_MS_IMPORT_ERR}"
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as ex:  # noqa: BLE001
        return False, "", f"fetch_failed:{ex!r}"
    try:
        from musicstreamer.playlist_parser import parse_playlist
        entries = parse_playlist(body, content_type=content_type, url_hint=url)
    except Exception as ex:  # noqa: BLE001
        return False, "", f"resolve_failed:{ex!r}"
    if not entries:
        return False, "", "resolve_failed:no_streams_in_playlist"
    return True, str(entries[0]["url"]), "ok"


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
    prefix (REQUIRED — run-smoke.sh transcript grep gate).
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
# Mode: --check-mp3 / --check-aac / --check-aacp / --check-pls (D-04 codec sweep)
# -----------------------------------------------------------------------------


def _check_codec_mode(mode: str, url: str, timeout_s: float) -> int:
    """Shared implementation for --check-mp3/aac/aacp/pls.

    Steps:
    1. Validate the URL (scheme + host allowlist).
    2. Run through the production resolver (_resolve_via_production).
    3. Emit SPIKE_DIAG with the resolved URL.
    4. Delegate to play_url() with the resolved URL.

    D-05: the production resolver import guard fires at module import time;
    this function calls _resolve_via_production() to also exercise the
    runtime code path.
    """
    # Step 1: validate the raw URL (pre-resolver).
    ok, reason = _validate_url(url)
    if not ok:
        _emit("SPIKE_FAIL", step="resolve", mode=mode, reason="bad_host", detail=reason, url=url)
        return 2

    # Step 2: route through the production resolver (D-05). PLS needs the Phase 58
    # playlist parser to expand the playlist to a stream URL; the mp3/aac/aacp
    # modes use the URL normalizer (identity pass for SomaFM, scheme/host rewrite
    # for DI.fm). play_url() re-validates the resolved inner URL host below.
    if mode == "pls":
        ok, resolved_url, resolve_reason = _resolve_pls_via_production(url)
    else:
        ok, resolved_url, resolve_reason = _resolve_via_production(url)
    if not ok:
        _emit("SPIKE_FAIL", step="resolve", mode=mode, reason=resolve_reason, url=url)
        return 2

    # Step 3: diagnostic.
    _emit("SPIKE_DIAG", mode=mode, resolved_url=resolved_url)

    # Step 4: play the resolved URL.
    return play_url(resolved_url, timeout_s)


# -----------------------------------------------------------------------------
# argv
# -----------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smoke_test.py",
        description=(
            "Phase 85 production AppImage smoke harness. Modes: --uri (playback), "
            "--check-glibc, --check-plugins (avdec_aac,aacparse), --assert-tls, "
            "--check-mp3, --check-aac, --check-aacp, --check-pls (D-04 codec sweep). "
            "Bare invocation (no flags) emits SPIKE_FAIL reason='usage' and "
            "exits 1 — used as a host-side liveness check that doesn't require "
            "PyGObject."
        ),
    )
    p.add_argument("--uri", default=None, help="Stream URL (SomaFM / DI.fm / AudioAddict only); falls back to test_url.txt chain if absent")
    p.add_argument("--timeout", type=float, default=30.0, help="Seconds of clean PLAYING required for SPIKE_OK")
    p.add_argument("--assert-tls", action="store_true", help="Assert Gio.TlsBackend has a default database (Pitfall 4)")
    p.add_argument("--check-glibc", default=None, metavar="PATH", help="Run strings | grep GLIBC_; exit 4 if > GLIBC_2.35")
    p.add_argument(
        "--check-plugins",
        default=None,
        metavar="NAMES",
        help="Comma-separated plugin names (default test: avdec_aac,aacparse) — runs gst-inspect-1.0 each, exit 5 on miss",
    )
    p.add_argument("--check-mp3", action="store_true",
        help="D-04: play SomaFM MP3 URL for --timeout seconds via production resolver (D-05)")
    p.add_argument("--check-aac", action="store_true",
        help="D-04: play SomaFM AAC URL for --timeout seconds via production resolver (D-05)")
    p.add_argument("--check-aacp", action="store_true",
        help="D-04: play an HE-AAC/AACP URL for --timeout seconds via production resolver (D-05)")
    p.add_argument("--check-pls", action="store_true",
        help="D-04: resolve a .pls URL via production resolver (D-05) then play resolved stream for --timeout seconds")
    return p


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        _emit("SPIKE_FAIL", reason="usage", expected="smoke_test.py [--uri URL] [--check-glibc PATH] [--check-plugins NAMES] [--assert-tls] [--check-mp3] [--check-aac] [--check-aacp] [--check-pls]")
        return 1
    parser = _build_parser()
    args = parser.parse_args(argv[1:])

    if args.check_glibc:
        return check_glibc(args.check_glibc)

    if args.check_plugins:
        return check_plugins(args.check_plugins)

    if args.assert_tls and not args.uri:
        return assert_tls()

    if args.check_mp3:
        return _check_codec_mode("mp3", _MP3_URL, args.timeout)

    if args.check_aac:
        return _check_codec_mode("aac", _AAC_URL, args.timeout)

    if args.check_aacp:
        return _check_codec_mode("aacp", _AACP_URL, args.timeout)

    if args.check_pls:
        return _check_codec_mode("pls", _PLS_URL, args.timeout)

    if args.uri:
        if args.assert_tls:
            rc = assert_tls()
            if rc != 0:
                return rc
        return play_url(args.uri, args.timeout)

    return play_with_fallback(args.timeout)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

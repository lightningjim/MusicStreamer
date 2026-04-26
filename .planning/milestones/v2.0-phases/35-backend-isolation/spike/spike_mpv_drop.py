#!/usr/bin/env python3
"""Phase 35 mpv-drop spike (D-20..D-23).

Decides whether GStreamer playbin3 can play yt-dlp library-resolved URLs
across the four D-20 cases. If ALL pass -> DROP_MPV. Otherwise KEEP_MPV.

Usage:
    python spike_mpv_drop.py <a_url> <b_url> <c_url> <d_url>

Pass "-" for any URL to mark it SKIPPED (treated as FAIL for the decision).
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Optional

import gi  # type: ignore

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # type: ignore  # noqa: E402

import yt_dlp  # noqa: E402

Gst.init(None)

COOKIES_DEFAULT = os.path.expanduser("~/.local/share/musicstreamer/cookies.txt")
TIMEOUT_S = 15.0


@dataclass
class Case:
    cid: str
    label: str
    url: str
    cookies: Optional[str]
    fmt: str


def resolve_url(url: str, fmt: str, cookies: Optional[str]) -> str:
    """Run yt-dlp library API on a worker thread (never block main loop)."""
    holder: dict = {}

    def _worker() -> None:
        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "format": fmt,
            }
            if cookies:
                opts["cookiefile"] = cookies
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            resolved = info.get("url")
            if not resolved and info.get("formats"):
                resolved = info["formats"][-1].get("url")
            holder["url"] = resolved
        except Exception as exc:  # noqa: BLE001
            holder["err"] = f"{type(exc).__name__}: {exc}"

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=20)
    if t.is_alive():
        raise TimeoutError("yt-dlp resolve exceeded 20s")
    if "err" in holder:
        raise RuntimeError(holder["err"])
    if not holder.get("url"):
        raise RuntimeError("yt-dlp returned no URL")
    return holder["url"]


def play_via_playbin3(resolved: str) -> tuple[bool, str]:
    """Construct playbin3, attach bus handlers via GLib.MainLoop, return (pass, note)."""
    pipeline = Gst.ElementFactory.make("playbin3", "spike-player")
    if pipeline is None:
        return False, "playbin3 element unavailable"
    fakesink_v = Gst.ElementFactory.make("fakesink", "fake-video")
    fakesink_a = Gst.ElementFactory.make("fakesink", "fake-audio")
    if fakesink_v:
        pipeline.set_property("video-sink", fakesink_v)
    if fakesink_a:
        pipeline.set_property("audio-sink", fakesink_a)
    pipeline.set_property("uri", resolved)

    loop = GLib.MainLoop()
    state = {"playing": False, "tag": False, "error": None}

    def on_error(_bus, msg):
        err, dbg = msg.parse_error()
        state["error"] = f"{err.message} ({dbg})" if dbg else err.message
        loop.quit()

    def on_tag(_bus, _msg):
        state["tag"] = True
        # Don't quit; wait for state-changed to PLAYING for stronger signal
        if state["playing"]:
            loop.quit()

    def on_state_changed(_bus, msg):
        if msg.src is not pipeline:
            return
        old, new, _pending = msg.parse_state_changed()
        if new == Gst.State.PLAYING:
            state["playing"] = True
            loop.quit()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message::error", on_error)
    bus.connect("message::tag", on_tag)
    bus.connect("message::state-changed", on_state_changed)

    def timeout_quit() -> bool:
        loop.quit()
        return False

    GLib.timeout_add(int(TIMEOUT_S * 1000), timeout_quit)
    pipeline.set_state(Gst.State.PLAYING)

    try:
        loop.run()
    finally:
        pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    if state["error"]:
        return False, f"GStreamer error: {state['error']}"
    if state["playing"] or state["tag"]:
        markers = []
        if state["playing"]:
            markers.append("PLAYING")
        if state["tag"]:
            markers.append("tag")
        return True, "received " + "+".join(markers)
    return False, f"timeout after {TIMEOUT_S}s with no PLAYING/tag"


def run_case(case: Case) -> tuple[str, str]:
    if case.url == "-" or not case.url:
        return "SKIPPED", "no URL provided at runtime"
    try:
        resolved = resolve_url(case.url, case.fmt, case.cookies)
    except Exception as exc:  # noqa: BLE001
        return "FAIL", f"yt-dlp resolve failed: {exc}"
    try:
        ok, note = play_via_playbin3(resolved)
    except Exception:  # noqa: BLE001
        return "FAIL", f"playbin3 crash: {traceback.format_exc().splitlines()[-1]}"
    return ("PASS" if ok else "FAIL"), note


def main(argv: list[str]) -> int:
    if len(argv) < 5:
        print(
            "Usage: spike_mpv_drop.py <a_live_url> <b_hls_url> <c_cookie_url> <d_format_url>",
            file=sys.stderr,
        )
        print("Pass '-' for any URL to mark it SKIPPED.", file=sys.stderr)
        return 2

    cases = [
        Case("a_live", "YouTube live", argv[1], None, "best[protocol^=m3u8]/best"),
        Case("b_hls", "HLS manifest", argv[2], None, "best[protocol^=m3u8]/best"),
        Case("c_cookies", "Cookie-protected", argv[3], COOKIES_DEFAULT, "best"),
        Case("d_format", "Specific format", argv[4], None, "best[height<=720][protocol^=m3u8]/best"),
    ]

    results = []
    for case in cases:
        t0 = time.monotonic()
        result, note = run_case(case)
        dur = time.monotonic() - t0
        print(f"CASE {case.cid}: {result} — {note} ({dur:.1f}s)")
        results.append((case, result, note))

    all_pass = all(r == "PASS" for _, r, _ in results)
    print()
    print(f"DECISION: {'DROP_MPV' if all_pass else 'KEEP_MPV'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

---
status: resolved
trigger: "YouTube station playback — stream appears to start (pipeline transitions) but no audio comes out. Normal HTTP radio streams work fine."
created: 2026-03-18T00:00:00Z
updated: 2026-04-25T22:00:00Z
resolution: "Phase 44 fix — clear GST_PLAY_FLAG_VIDEO on playbin3 (`flags & ~0x1`) so decodebin3 doesn't try to plug a video decoder for muxed HLS streams; combined with adding gst-libav to the conda build env so AAC + H.264 decoders are bundled. See `.claude/projects/-home-kcreasey-OneDrive-Projects-MusicStreamer/memory/project_gstreamer_128_video_flag.md`."
---

## Current Focus

hypothesis: yt-dlp format selector resolves a muxed video+audio stream; info.get("url") on a muxed result returns the URL of the best combined format which is a video container, not a pure audio stream. GStreamer playbin handles it with fakesink suppressing video, but the resolved URL may be a DASH manifest or non-HLS adaptive stream that playbin cannot demux without additional plugins, OR the URL is a video-only DASH segment (when best[] selects DASH video over HLS). A secondary issue is that the format string "best[protocol^=m3u8]/best" will fall back to "best" which may return a video+audio MP4 DASH stream whose URL field is only the video track.
test: static code analysis of yt-dlp format selection + info dict structure
expecting: confirmed — format fallback "best" returns muxed/DASH, info["url"] is unreliable for muxed formats
next_action: DONE — root cause identified, no fix applied per instructions

## Symptoms

expected: audio plays from YouTube stream
actual: pipeline transitions to PLAYING but no audio output
errors: none visible (no exception thrown, on_title callback fires normally)
reproduction: play any YouTube URL station
started: unknown — possibly always broken

## Eliminated

- hypothesis: yt-dlp not installed / import error
  evidence: Code does `from yt_dlp import YoutubeDL` at module level — if not installed the app would fail to start entirely, not silently produce no audio
  timestamp: 2026-03-18

- hypothesis: pipeline never reaches PLAYING state
  evidence: User confirmed "pipeline transitions" happen — so playbin is receiving a URI and transitioning
  timestamp: 2026-03-18

- hypothesis: pulsesink unavailable
  evidence: Normal HTTP streams work fine, same pulsesink is used for both paths
  timestamp: 2026-03-18

## Evidence

- timestamp: 2026-03-18
  checked: player.py lines 32-38 — yt-dlp format selector
  found: format string is "best[protocol^=m3u8]/best" — the fallback "best" selects highest-quality combined format, which for most YouTube content in 2024+ is a DASH stream (video+audio muxed via separate manifests) or an mp4 muxed stream
  implication: When no m3u8 protocol stream exists (most non-livestream YouTube), falls back to "best" which selects DASH or muxed MP4

- timestamp: 2026-03-18
  checked: player.py line 42 — info.get("url")
  found: For a DASH/muxed format result, `info["url"]` is the video track URL (or the muxed container URL). When yt-dlp selects a DASH format, the top-level "url" field is the video manifest URL, not an audio stream URL. The audio URL lives at info["formats"][n]["url"] for the audio-specific format.
  implication: The URI fed to GStreamer playbin may be a video DASH segment URL with no audio, causing playbin to play "successfully" (no error) but output no audio

- timestamp: 2026-03-18
  checked: player.py line 49 — _set_uri call with stream_url
  found: No validation that stream_url is an audio-capable stream before passing to GStreamer. No check of info["acodec"], info["vcodec"], or format type.
  implication: A video-only URL would be fed directly to playbin, which would play it silently (fakesink handles video, no audio track present)

- timestamp: 2026-03-18
  checked: yt-dlp format selection behavior for YouTube (knowledge-based)
  found: For YouTube videos (non-livestream), "best[protocol^=m3u8]" matches NOTHING — YouTube stopped serving HLS for regular videos. Falls through to "best" which selects the highest-quality muxed mp4 OR a DASH format. For DASH, info["url"] is the video-only stream URL; audio is separate. For old muxed mp4 (360p/720p), info["url"] is the full muxed stream and audio should work — but YouTube increasingly serves DASH even at lower quality.
  implication: The format selector is broken for modern YouTube — produces either a video-only DASH URL or unreliably picks muxed content

- timestamp: 2026-03-18
  checked: yt-dlp format string for audio-only selection
  found: The correct selector for audio-only from YouTube is "bestaudio[ext=m4a]/bestaudio/best" — this targets the audio-only DASH track. The current code never requests audio-only.
  implication: Root cause confirmed: format string never selects an audio-only stream

## Resolution

root_cause: |
  player.py line 36 — format selector "best[protocol^=m3u8]/best"

  Two compounded problems:

  1. PRIMARY: The format selector never targets audio-only streams. "best[protocol^=m3u8]" matches nothing on modern YouTube (YouTube does not serve HLS for regular videos). The fallback "best" selects the highest quality muxed or DASH format. For DASH (which YouTube now uses for anything above 360p), info["url"] returns the VIDEO-ONLY track URL — no audio. GStreamer playbin receives this URL, plays it "successfully" via fakesink for video with zero audio output, triggering no error.

  2. SECONDARY: Even when "best" happens to select a legacy muxed mp4 (low quality), info.get("url") at the top level of the info dict may not reliably contain the direct stream URL for all yt-dlp result structures (some require traversing "formats"). But this is secondary — the primary issue is DASH video-only URL.

fix: NOT APPLIED (diagnose-only mode)
  Correct format selector: "bestaudio[ext=m4a]/bestaudio/best"
  Should also add: info["acodec"] != "none" guard before calling _set_uri

verification: NOT APPLIED
files_changed: []

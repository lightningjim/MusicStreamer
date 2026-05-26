# Phase 85a Audible PASS log

> D-06 protocol per CONTEXT.md: 30s play + pause/resume + stop + relaunch.
> Relaunch step verifies `GST_REGISTRY_FORK=no` (Pitfall 3 mitigation).
> D-08 HTTPS audible verification: Ubuntu 22.04 ONLY (step 8 below).
> Spike-level pause/resume approximation: SIGSTOP/SIGCONT against the process
> (hello_world.py has no UI controls; real pause UI is Phase 85's surface).

## Ubuntu 22.04 (host pipewire, AppImage launched on host via --appimage-extract-and-run)

- date: 2026-05-26
- channel_won: Groove Salad (HTTP, ice1.somafm.com/groovesalad-128-mp3)
- screenshot_tool: N/A — Pitfall 18 surfaced (CLI screenshot tools broken on GNOME 49 Wayland; `gnome-screenshot --window` returns errors via fallback X11 path, `grim` not applicable to Mutter, only the GNOME Screenshot UI portal works and is non-scriptable). Manual UI screenshots possible but skipped for spike scope.
- step 1: launch + reached PLAYING (time_to_play_s: 1.636 run-1, 0.345 run-2)  [run-1 = fresh registry scan; run-2 = cached registry; Pitfall 3 GST_REGISTRY_FORK=no working as designed]
- step 2: 10s clean audio: PARTIAL — non-deterministic per Pitfall 19. Run 1 silent, Run 2 audible. Both runs reach pulsesink PLAYING state cleanly (GST_DEBUG state traces confirm); failure is downstream at PipeWire/Wireplumber routing layer.
- step 3: pause (SIGSTOP): not exercised (Pitfall 19 surfaced first)
- step 4: resume (SIGCONT): not exercised
- step 5: stop (SIGINT): hello_world.py exited cleanly at 30s SPIKE_OK in both runs
- step 6: close: implicit at script exit
- step 7: relaunch_time_to_play_s: 0.345  (run-2 IS the relaunch; well under step-1 +5s, Pitfall 3 mitigation empirically VERIFIED)
- step 8: https_audible: NOT EXERCISED on real-host pipewire due to Pitfall 19 surface; HTTPS programmatic PASS confirmed by Plan 06 transcript across all 3 distros (SPIKE_OK 35.08s on ice6.somafm.com/groovesalad-128-mp3 — Pitfall 17 fix validates D-08 at programmatic layer)
- elected_sink: pulsesink (audiosink-actual-sink-pulse — GST_DEBUG confirmed both runs)
- notes:
  - **Pitfall 18 discovered:** CLI screenshot tools broken on GNOME 49 Wayland. Phase 85 production CI must use xdg-desktop-portal-gnome API.
  - **Pitfall 19 discovered:** PipeWire routing flaky for re-extracted AppImage. Each `--appimage-extract-and-run` creates new `/tmp/appimage_extracted_<sha>/` path; PipeWire/Wireplumber identifies apps partly by binary path; new path = new app identity = stale stream-restore state possible. GStreamer pipeline healthy in both runs (state machine traces clean, pulsesink PLAYING) — failure is at session-manager routing layer. Phase 85 mitigation: set explicit PipeWire app identity in AppRun (`PULSE_PROP="application.name=... application.id=..."`) AND ship production AppImage that self-mounts via FUSE (deterministic mount path per content hash, not per-launch random sha).
  - **Pitfall 20 captured (already noted from Plan 06 Deviation 5):** AppImage's AppRun hardcodes `exec ... hello_world.py "$@"`. Phase 85 must parameterize the exec line via env var or argument-passing template so `python -m musicstreamer "$@"` substitution doesn't require re-bundling.

## Fedora 40 (ms-spike-fedora40)

- status: SKIPPED — Pitfall 19 surfaced on Ubuntu; cross-distro audible would reproduce the same finding without changing Phase 85's action item. Wrap-now decision per spike retry-budget-user-owned policy.

## openSUSE Tumbleweed (ms-spike-tumbleweed)

- status: SKIPPED — same reason as Fedora 40 above.

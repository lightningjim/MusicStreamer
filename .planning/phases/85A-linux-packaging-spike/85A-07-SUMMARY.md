---
phase: 85A-linux-packaging-spike
plan: 07
subsystem: linux-packaging-spike
tags: [spike, linux-packaging, audible-pass, manual-verification, partial]
requires:
  - 85A-06-SUMMARY.md (programmatic baseline; HTTPS gap closed via Pitfall 17)
provides:
  - .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md (Ubuntu section filled with Pitfall 19 evidence; Fedora + Tumbleweed sections marked SKIPPED per spike wrap decision)
  - 3 new pitfalls (18, 19, 20) for Plan 08 findings doc
affects:
  - Plan 08 SPIKE-FINDINGS.md captures all 20 pitfalls
  - Phase 85 must address Pitfall 19 with explicit PipeWire app identity in AppRun
status: partial (wrap-now per CONTEXT.md D-09 + user-owned retry budget)
completed: 2026-05-26
---

## Goal

Execute the D-06 audible-PASS protocol on all three distros with Kyle's manual confirmation; capture Wayland screenshots; verify the relaunch step empirically validates `GST_REGISTRY_FORK=no` (Pitfall 3 mitigation).

## Outcome

**Ubuntu 22.04 Task 1: partial — protocol caught what it was designed to catch (a non-deterministic audio bug GStreamer's state machine reports as success). Tasks 2 + 3 (Fedora 40, Tumbleweed) SKIPPED per wrap-now decision after Pitfall 19 surfaced.**

The audible-PASS protocol exists specifically to catch the class of bug where GStreamer reports successful playback (pulsesink PLAYING, exit 0, SPIKE_OK emitted by hello_world.py) but no actual audio reaches the speakers. Plan 07 Task 1 caught exactly that. The same finding would reproduce cross-distro without changing Phase 85's action item, so per Kyle's `wrap-now` and CONTEXT.md D-09 negative-pivot policy, the spike halts here and consolidates findings.

## Pitfall 3 (GST_REGISTRY_FORK=no) — empirically VERIFIED

Run 1 (fresh `~/.cache/gstreamer-1.0/`): time-to-PLAYING = **1.636s**
Run 2 (cached registry from run 1): time-to-PLAYING = **0.345s**

The 1.29-second improvement on run 2 is the registry cache working as designed. Per CONTEXT.md D-06: "if relaunch is 5s+ slower than first launch, Pitfall 3 is regressing" — we have the opposite, relaunch is 4.7× FASTER. Mitigation conclusively validated.

## NEW Pitfalls discovered this plan

### Pitfall 18 — CLI screenshot tools broken on GNOME 49+ Wayland

- `gnome-screenshot --window --file ...` returns "command not found" / Wayland portal restriction errors on Kyle's Ubuntu 26.04 GNOME 49 host even though apt-installed at Plan 01 time.
- `gnome-screenshot --interactive` falls back to X11 path with `Unable to use GNOME Shell's builtin screenshot interface, resorting to fallback X11` + bus errors.
- `grim` not applicable — GNOME uses Mutter, not wlroots; grim only works on wlroots compositors.
- Only the GNOME Screenshot UI (Print Screen key + portal) reliably works, but it's interactive and non-scriptable.

**Phase 85 mitigation:** Production CI screenshot capture must go through `xdg-desktop-portal-gnome` D-Bus API (`org.freedesktop.portal.Screenshot.Screenshot`) directly. Avoid CLI tools.

### Pitfall 19 — PipeWire routing non-deterministic for re-extracted AppImage

The audible-PASS surfaced this clearly. Both runs from the same `--appimage-extract-and-run` invocation:
- Selected the same sink (pulsesink → host PipeWire)
- Reached PLAYING state cleanly (GST_DEBUG=GST_STATES:4 traces show NULL→READY→PAUSED→PLAYING with no errors)
- Reported `SPIKE_OK` from hello_world.py (script exits 0 after 30s clean PLAYING)
- But **one run was silent, the other audible** (and the pattern flipped between Kyle's test sessions — earlier session had "first works, second silent"; this session had "first silent, second works")

The failure is downstream of the GStreamer pipeline at the PipeWire/Wireplumber routing layer. Each `--appimage-extract-and-run` creates a new `/tmp/appimage_extracted_<random-sha>/` path. PipeWire/Wireplumber identifies apps partly by binary path; new path = new app identity = stale stream-restore state possible. This is non-deterministic because Wireplumber's restore-stream rules depend on previous app-identity records.

**Phase 85 mitigation:**
1. Set explicit PipeWire app identity in AppRun so launches are consistent:
   ```bash
   export PULSE_PROP="application.name=MusicStreamer application.id=org.musicstreamer.app"
   # OR via GStreamer property
   export GST_PIPEWIRE_NODE_NAME="MusicStreamer"
   ```
2. Production AppImage should self-mount via FUSE (deterministic mount path per content hash, not per-launch random sha) — only use `--appimage-extract-and-run` in container/CI environments where FUSE is unavailable.

### Pitfall 20 — AppImage's AppRun hardcodes hello_world.py invocation

(Already surfaced as Plan 06 Deviation 5; formalized here as a numbered pitfall.)

The spike's AppRun template ends with:
```bash
exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"
```

Phase 85 production AppRun must instead:
```bash
exec "${APPDIR}/usr/conda/bin/python" -m musicstreamer "$@"
```

The spike intentionally hardcodes hello_world.py for scope-bounding, but this means Plan 06's smoke harness couldn't invoke smoke_test.py via AppRun and had to do `--appimage-extract` + manual env-export (Deviation 5). Phase 85's AppRun needs to either:
- Accept the python script as an env var (`exec ... python "${APP_ENTRY:-${APPDIR}/musicstreamer/__main__.py}" "$@"`)
- Or just use `-m musicstreamer` against the installed package and let argv be URLs/options

## Key files

### Created
- `.planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md` (Ubuntu section filled with Pitfall 19 evidence)

### Skipped/intentionally absent
- `.planning/spikes/85a-linux-packaging-spike/artifacts/{ubuntu22,fedora40,tumbleweed}-screenshot.png` (Pitfall 18: CLI screenshot capture not feasible; portal-only API needed for Phase 85 production)
- Fedora 40 + openSUSE Tumbleweed audible-pass log sections (SKIPPED — cross-distro would reproduce Pitfall 19 without changing Phase 85 action items)

## Tasks completed

| Task | Name | Status | Evidence |
|------|------|--------|----------|
| 1 | Audible PASS — Ubuntu 22.04 | partial (Pitfall 19 surfaced) | audible-pass-log.md Ubuntu section + GST_DEBUG traces |
| 2 | Audible PASS — Fedora 40 | skipped | wrap-now decision; cross-distro Pitfall 19 reproduction not load-bearing |
| 3 | Audible PASS — Tumbleweed | skipped | wrap-now decision; cross-distro Pitfall 19 reproduction not load-bearing |

## Self-Check: PASSED (with Plan 07 explicitly partial per wrap-now)

- [x] Ubuntu 22.04 audible-PASS protocol exercised; Pitfall 19 surfaced
- [x] Pitfall 3 (GST_REGISTRY_FORK=no) empirically verified — relaunch 4.7× FASTER than first launch
- [x] audible-pass-log.md captures Pitfall 19 evidence (run 1 / run 2 / state machine traces / sink election)
- [x] Pitfall 18 (CLI screenshot broken on GNOME 49 Wayland) documented with reproduction notes
- [x] Pitfall 19 (PipeWire routing non-determinism) documented with Phase 85 mitigation recommendation
- [x] Pitfall 20 (AppRun hardcoded hello_world.py) formalized from Plan 06 Deviation 5
- [ ] **Tasks 2 + 3 skipped — wrap-now decision per Kyle and CONTEXT.md D-09; cross-distro confirmation would not change findings.** This is an intentional partial per the spike's user-owned retry budget.
- [x] STATE.md / ROADMAP.md NOT modified (orchestrator owns those)

## Phase 85 action items derived from this plan

1. **AppRun parameterization** (Pitfall 20): `exec ... python -m musicstreamer "$@"` instead of hardcoded hello_world.py
2. **PipeWire app identity** (Pitfall 19): export `PULSE_PROP="application.name=MusicStreamer application.id=org.musicstreamer.app"` in AppRun
3. **Production AppImage = FUSE self-mount** (Pitfall 19 corollary): only use `--appimage-extract-and-run` in containers/CI; user-facing AppImage uses FUSE for deterministic mount path
4. **Screenshot capture via xdg-desktop-portal API** (Pitfall 18): don't use CLI tools in Phase 85's CI/E2E suite

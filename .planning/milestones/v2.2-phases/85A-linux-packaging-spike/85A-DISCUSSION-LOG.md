# Phase 85a: Linux Packaging Spike - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in `85A-CONTEXT.md` — this log preserves the conversation.

**Date:** 2026-05-25
**Phase:** 85A-linux-packaging-spike
**Mode:** discuss (default, --chain)
**Areas selected:** Cross-distro verification mechanism, Test stream URL pin
**Areas deferred to Claude's discretion:** Spike artifact layout + wrap-up shape, Hello-world app scope

## Initial Gray Area Selection

**Presented:**
1. Spike artifact layout + wrap-up shape
2. Hello-world app scope
3. Cross-distro verification mechanism
4. Test stream URL pin

**User selected:** #3 and #4 (cross-distro verification, test stream URL pin). Items 1 and 2 dropped to Claude's discretion with the explicit instruction to mirror Phase 43's spike pattern.

---

## Area 1: Cross-distro verification mechanism

### Q1: Verification mechanism

**Options:**
- Docker per distro (headless, audio mocked) — proves bytes-resolve + plugin discovery, NOT real playback
- Distrobox sessions on Wayland host — real audio out via host pipewire (single-host caveat)
- Real VMs (Ubuntu desktop / Fedora Workstation / openSUSE Live) — highest fidelity, ~3× setup overhead
- Mixed (Docker for build/discovery, distrobox for one audible PASS) — recommended

**User answer:** **Distrobox sessions on Wayland host** (chose full real-audio fidelity over the mixed-mode shortcut).

### Q2 (asked + clarified): Container engine

**Initial AskUserQuestion options:**
- Podman (rootless, distrobox default) — recommended
- Docker (if already installed, distrobox supports it)
- Probe in Plan 01 (use whatever's present)

**Initial response:** User asked for clarification — wondered if podman was worth installing even with Docker already present.

**Claude clarification (plain text):**
- Distrobox's upstream default is podman; Docker is the secondary path.
- Rootless by default, no daemon → meaningfully nicer for one-off throwaway dev tooling.
- They coexist fine (different storage paths and sockets).
- Closer to AppImage's "no daemon, no privileged install" runtime story.

**User decision:** Installed podman; locked it without re-asking the question. Engine question dropped from the question set.

### Q3 (batched): Evidence shape per distro

**Options:**
- Audible + screenshot + transcript (full empirical)
- Programmatic-only (state reaches PLAYING)
- Programmatic + one audible confirmation on host distro — recommended

**User answer:** **Audible + screenshot + transcript** (per distro, not just the host).

### Q4 (batched): Container lifecycle

**Options:**
- Ephemeral — `distrobox rm` after spike
- Keep around — Phase 85 reuses
- Recreate script only, no live containers — recommended

**User answer:** **Ephemeral — destroy after spike** (clean state; recreate script committed but no live containers).

### Q5: Audible-PASS protocol

**Options:**
- 10s straight play
- 30s + pause/resume + stop
- 30s + pause/resume + stop + relaunch — recommended (catches `GST_REGISTRY_FORK=no` regression)
- Claude's discretion per distro

**User answer:** **30s play + pause/resume + stop + relaunch.**

### Q6: Continue?

**User answer:** Move to next area (Test stream URL pin).

---

## Area 2: Test stream URL pin

### Q1: Primary stream

**Options:**
- SomaFM Groove Salad MP3 — project's known-good baseline
- Self-hosted minimal MP3 on QNAP — deterministic, no upstream flakiness
- Both: SomaFM primary + self-hosted fallback — recommended
- SomaFM HTTPS variant — tighter TLS bundle test

**User answer:** **SomaFM Groove Salad MP3** (HTTP variant).

### Q2 (batched): TLS coverage

**Options:**
- HTTPS too (`ice6.somafm.com`) — recommended; exercises conda TLS path (`glib-networking` + gio modules)
- HTTP only — minimum-spike scope
- HTTPS only

**User answer:** **HTTPS too** — both HTTP and HTTPS variants exercised. Cited reason: Phase 43 Windows footgun on TLS bundling; same surface on Linux.

### Q3 (batched): Failover on SomaFM outage

**Options:**
- Hard-fail the spike
- Auto-fall-back to QNAP-hosted MP3
- Try alt SomaFM channel first, then fail — recommended

**User answer:** **Try alt SomaFM channel first, then fail** — Groove Salad → Drone Zone → Beat Blender → hard-fail. No QNAP infrastructure for the spike.

---

## Final check

**Q:** Anything else before writing CONTEXT.md?

**User answer:** **I'm ready for context.** Discretion items (artifact layout, hello-world scope) locked per Claude's stated defaults (mirror Phase 43, minimal playbin3 hello-world).

---

## Deferred Ideas (Captured)

None surfaced during this discussion — discussion stayed strictly within the spike's de-risk scope. Out-of-scope items in CONTEXT.md `<deferred>` are pre-known Phase 85 surface (PKG-LIN-APP-01..09 wiring, MPRIS2, `.desktop`, zsync, AAC playback, etc.) — they weren't ideas raised by the user, they were intentional spike-scope exclusions.

## Claude's Discretion Items

Locked per stated defaults:

1. **Spike artifact layout** — `.planning/spikes/85a-linux-packaging-spike/` (mirrors Phase 43).
2. **Wrap-up shape** — Append new "Linux AppImage Bundling" feature area to existing `spike-findings-musicstreamer` skill via `/gsd:spike-wrap-up`.
3. **Hello-world app scope** — Minimal `playbin3` script (Phase 43 `smoke_test.py` shape). Bus-bridge complexity stays OUT.
4. **Build container** — Pinned `ubuntu:22.04` image SHA.
5. **linuxdeploy version pinning** — Pinned via build script.
6. **Conda env shape** — Minimal conda-forge env (Python 3.10+, PySide6, gst-python, gst-plugins-{base,good,bad,ugly}, gst-libav, glib-networking).
7. **GLIBC verification** — Wired into smoke test; non-zero exit on > 2.35.
8. **Plugin discovery harness** — Smoke test execs `gst-inspect-1.0 avdec_aac` + `aacparse` from AppRun shell.
9. **Wayland screenshot tool** — `gnome-screenshot --window` (host is Wayland GNOME Shell per `[[project_deployment_target]]`).
10. **Negative-pivot policy** — Spike stops + reports on toolchain failure; does not silently pivot.

---

*Phase: 85A-linux-packaging-spike*
*Discussion log: 2026-05-25*

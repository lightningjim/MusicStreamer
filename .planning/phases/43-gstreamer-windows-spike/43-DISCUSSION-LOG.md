# Phase 43: GStreamer Windows Spike - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 43-gstreamer-windows-spike
**Areas discussed:** VM target, GStreamer distro + version, Spike fidelity, Deliverables

---

## Gray area selection

| Option | Description | Selected |
|--------|-------------|----------|
| VM target | Existing VM vs snapshot vs GH Actions runner | ✓ |
| GStreamer distro + version | MSVC vs MinGW, which release | ✓ |
| Spike fidelity | Minimal HTTPS vs broader vs full smoke | ✓ |
| Deliverables | Findings only vs + spec vs + skill wrap-up | ✓ |

**User's choice:** All four areas

---

## VM target

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot of your VM | Clean snapshot with no system GStreamer; revert between attempts | ✓ |
| Your VM as-is | Faster but risks false-positive from system GStreamer on PATH | |
| Fresh Windows install | Highest fidelity, highest time cost | |

**User's choice:** Snapshot of your VM (Recommended)

---

## Windows version

| Option | Description | Selected |
|--------|-------------|----------|
| Windows 11 | Current Microsoft-supported baseline | ✓ |
| Windows 10 | Supported through Oct 2025 | |
| Both | Doubles spike time | |

**User's choice:** Windows 11

---

## GStreamer distribution + version

| Option | Description | Selected |
|--------|-------------|----------|
| MSVC runtime, latest 1.24.x | Official MSVC build from gstreamer.freedesktop.org | ✓ |
| MinGW runtime | Less common with PyInstaller, souphttpsrc SSL incompatibilities reported | |
| Match Linux GStreamer version | Consistency vs using newer Windows release | |

**User's choice:** MSVC runtime, latest 1.24.x (Recommended)

---

## Spike fidelity

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal — HTTPS ShoutCast only | One playbin3 + souphttpsrc HTTPS + audio sink | ✓ |
| Plus HLS + ICY tags | Adds hlsdemux + ICY TAG propagation | |
| Full smoke — HTTPS + HLS + yt-dlp + cover art | Closest to real app, biggest time cost | |

**User's choice:** Minimal — HTTPS ShoutCast only (Recommended)

---

## Test URL

| Option | Description | Selected |
|--------|-------------|----------|
| AudioAddict channel from your library | Real traffic, real TLS cert, existing listen key | ✓ |
| Public ShoutCast HTTPS sample | Removes AA listen-key variable from spike | |
| Both | Extra rigor | |

**User's choice:** AudioAddict channel from your library (Recommended)

---

## Deliverables

| Option | Description | Selected |
|--------|-------------|----------|
| Findings doc + template .spec + wrap-up skill | Findings + draft .spec + /gsd-spike-wrap-up skill | ✓ |
| Findings doc + template .spec only | No skill wrap-up | |
| Findings doc only | Phase 44 writes .spec from scratch | |

**User's choice:** Findings doc + template .spec + wrap-up skill (Recommended)

---

## Execution model

| Option | Description | Selected |
|--------|-------------|----------|
| Claude writes scripts; user runs on VM, pastes output | Iteration loop via paste-back | ✓ |
| Claude writes full runbook; user owns findings | Less back-and-forth, user owns doc updates | |
| Remote interactive via RDP/SSH | Rare, usually not viable | |

**User's choice:** Claude writes scripts + findings template (Recommended)

---

## Claude's Discretion

- Audio sink choice (wasapisink vs directsoundsink vs autoaudiosink)
- PyInstaller invocation form (CLI vs .spec-file)
- Plugin blacklist / minimal plugin set derivation
- Build driver script language (PowerShell vs .bat vs uv shim)

## Deferred Ideas

- Windows 10 validation — defer unless Phase 44 surfaces an issue
- HLS / yt-dlp / cover-art / ICY on Windows — Phase 44 smoke test
- NSIS installer, single-instance, SMTC, round-trip UAT — Phase 44 / 43.1 / post-v2.0

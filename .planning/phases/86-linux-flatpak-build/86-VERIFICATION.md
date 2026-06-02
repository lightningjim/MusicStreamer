---
status: human_needed
phase: 86-linux-flatpak-build
plan: 86-05
source: [86-05-PLAN.md]
created: 2026-06-02
updated: 2026-06-02
---

# Phase 86 — Flatpak In-Sandbox UAT Evidence Bundle

> **Status: awaiting human UAT.** Waves 1–2 (manifest, import wizard, drift-guards, build driver, CI, signing) are complete and pass 52 automated tests. This document is the runbook + evidence bundle for Plan 86-05 — the in-sandbox functional verification (D-09..D-12) that automation cannot cover: audible audio, interactive login, OS media keys, GNOME Software listing.
>
> Fill each section's evidence (audible note + Wayland screenshot ref + terminal/D-Bus transcript), then re-run `/gsd:execute-phase 86` (or `/gsd:verify-work 86`) and type **approved**, or describe which SC failed.

## Build + install (Plan 86-05 Task 1 — automatable, run first on the rig)

```bash
# From repo root. No GPG key in env → SKIP_SIGN=1 for local iteration
# (CI / release builds set GPG_KEY_ID and sign per FP-11).
SKIP_SIGN=1 bash tools/linux-flatpak/build.sh
# Expect: BUILD_OK + SIGN_SKIPPED, artifact at tools/linux-flatpak/artifacts/MusicStreamer-2.1.84.flatpak

# Install locally (--no-gpg-verify acceptable for a self-built local bundle):
flatpak install --user --no-gpg-verify tools/linux-flatpak/artifacts/MusicStreamer-2.1.84.flatpak

# Confirm AAC decoder + node resolve INSIDE the sandbox:
flatpak run --command=bash io.github.kcreasey.MusicStreamer -c "gst-inspect-1.0 avdec_aac"   # expect element printed, exit 0
flatpak run --command=bash io.github.kcreasey.MusicStreamer -c "which node"                   # expect /app/bin/node
```

- Build transcript (BUILD_OK / SIGN_SKIPPED): _paste_
- `flatpak install --user` transcript: _paste_
- `gst-inspect-1.0 avdec_aac` output: _paste_  → **Open Question 2/A7:** if this FAILS, uncomment `--env=GST_PLUGIN_PATH=/app/lib/ffmpeg` in `io.github.kcreasey.MusicStreamer.yaml` (left commented in Plan 01 Task 2), rebuild, retest, and record the resolution here.
- `which node` output (expect `/app/bin/node`): _paste_

---

## SC1 — Install / launch (PKG-LIN-FP-02, D-11)
- [ ] `io.github.kcreasey.MusicStreamer` appears in GNOME Software
- [ ] `flatpak run io.github.kcreasey.MusicStreamer` launches the GUI
- Screenshot ref (GNOME Software entry + running app): _ref_
- Notes: _native Wayland GNOME rig, DPR=1.0, single-host (no cross-distro matrix)_

## SC2 — AAC audio audible via ffmpeg-full (PKG-LIN-FP-07)
- [ ] DI.fm AAC tier — audible
- [ ] AudioAddict AAC tier — audible
- [ ] SomaFM AAC tier — audible
- Screenshot ref(s) (Now Playing per tier): _ref_
- Audible note: _yes/no per tier via PipeWire_

## SC3 — GBS.FM login + persistence (PKG-LIN-FP-05, D-12)
- [ ] In-app QtWebEngine login completes; subprocess stderr shows NO `namespace: not permitted` error
- [ ] Fully quit → relaunch → still logged in (cookies persisted in `~/.var/app/io.github.kcreasey.MusicStreamer/`)
- Subprocess transcript (no namespace error): _paste_

## SC4 — MPRIS2 media-key control (PKG-LIN-FP-08, D-10)
```bash
# From OUTSIDE the sandbox while a stream is playing:
busctl --user list | grep mpris            # expect org.mpris.MediaPlayer2.MusicStreamer (SHORT name)
playerctl --player=MusicStreamer status    # expect Playing
```
- [ ] `busctl` shows `org.mpris.MediaPlayer2.MusicStreamer` (short name, NOT the long `...io.github.kcreasey.MusicStreamer`)
- [ ] OS media keys (play/pause/next) reach sandbox playback
- `busctl` transcript: _paste_
- `playerctl` transcript: _paste_

## SC5 — First-launch import offer (PKG-LIN-FP-06 functional half, D-02/D-03)
- Existing unsandboxed data present at `~/.local/share/musicstreamer/musicstreamer.sqlite3` ✓ (confirmed on rig)
- [ ] First launch OFFERS the import wizard
- [ ] Dismiss → relaunch → does NOT re-offer (offer-once, D-03)
- [ ] Original `~/.local/share/musicstreamer/` intact after import (copy-don't-delete, D-02)
- Screenshot ref (wizard offer): _ref_

---

## Summary
total: 5 (SC1–SC5)
passed: 0
pending: 5
issues: 0

## Gaps
_none recorded yet_

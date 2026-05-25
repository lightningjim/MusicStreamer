---
plan: 79-05
phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
status: complete
result: PASS
type: live-uat
date: 2026-05-16
---

# Plan 79-05 — Live `.desktop`-launch UAT (B-79-10 / BUG-11 closure)

**Result:** PASS — bug fixed, live reproduction now plays audio.

## What was verified

The unit + integration test matrix (B-79-01..B-79-09 + B-79-DG-1) had already pinned the wiring layer. This plan was the live closure gate confirming the surgical fix actually resolves the user-observed "Stream exhausted" symptom under the original reproduction context:

- `.desktop`-launched MusicStreamer (systemd-session-stripped PATH)
- Node provided exclusively via fnm version-manager shim (not on `.desktop`-inherited PATH)
- Known-good YouTube live station plays audio without "Stream exhausted" toast

## Sign-off criteria — all four met

- [x] `.desktop`-launch confirmed (launched via GNOME `.desktop` entry, not from a terminal)
- [x] Audio played within the failover window — no "Stream exhausted" toast
- [x] No "Install Node.js for YouTube playback" toast (D-12: existing nudge unchanged, correctly silent because Node IS present)
- [x] `journalctl --user` shows the new INFO log line with a NON-None absolute Node path

## Journal evidence (verbatim, captured by user)

```
May 16 14:28:21 hurricane org.lightningjim.MusicStreamer.desktop[138854]: INFO:musicstreamer.player:youtube resolve: node_path=/home/kcreasey/.local/share/fnm/aliases/default/bin/node
```

This is the smoking-gun proof that the fix works at the live-debug layer:

1. **The journal record exists at all** — pre-Phase-79, `_youtube_resolve_worker` did not emit this line. D-13's new INFO log is firing as designed.
2. **The `node_path` value is a non-None absolute path** — pre-Phase-79, even after the fnm fallback in `runtime_check.check_node()` resolved the path correctly, `Player._youtube_resolve_worker` passed `{"path": None}` to yt-dlp and yt-dlp's own (broken-under-`.desktop`) PATH lookup failed. Post-Phase-79, the resolved path threads through D-05 → D-07 → D-10 → yt-dlp opts.
3. **The path lives under `~/.local/share/fnm/aliases/default/bin/`** — the exact version-manager shim path that `_which_node_version_manager_fallback` (commit `a06549f`, 2026-04-25) was written to discover. Phase 79 is now the second half of that two-stage fix: detection (a06549f) + threading-through (Phase 79).
4. **The journal source process is `org.lightningjim.MusicStreamer.desktop[138854]`** — confirms the systemd-session `.desktop` launcher invoked the binary (not a terminal-rooted process), so the bug-reproduction PATH context was the genuine one.

## Closes

- **B-79-10** — live `.desktop`-launch resolves a YT live stream end-to-end (VALIDATION.md, the manual-only behavior)
- **BUG-11** — REQUIREMENTS.md entry: ".desktop-launched MusicStreamer plays YouTube streams when Node is provided exclusively via a version-manager shim"

## Notes

- Reinstall step (`pipx install -e . --force --system-site-packages`) and GNOME logout/login were performed by the user as documented in the `<how-to-verify>` block of the plan.
- No `--scrub` of the user-name segment of the journal path was requested; per the plan's threat_model T-79-05-02, the path is informational and aligns with the project's already-effectively-public repo policy.

## Phase 79 closure summary

| Wave | Plan | Behaviors | Status |
|------|------|-----------|--------|
| 1    | 79-01 | B-79-01..B-79-03 | ✓ shipped |
| 2    | 79-02 | B-79-04..B-79-06 | ✓ shipped |
| 2    | 79-03 | B-79-07..B-79-09 | ✓ shipped |
| 2    | 79-04 | B-79-DG-1 | ✓ shipped |
| 3    | 79-05 | B-79-10 | ✓ live PASS (this SUMMARY) |

Phase 79 ready for verifier sign-off → roadmap completion.

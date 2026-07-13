---
status: complete
phase: 85-linux-common-appimage-build
source: [85-01-SUMMARY.md, 85-02-SUMMARY.md, 85-03-SUMMARY.md, 85-04-SUMMARY.md]
started: 2026-06-02T12:16:52Z
updated: 2026-06-02T12:16:52Z
---

## Current Test

[testing complete]

<!--
Provenance: These results transcribe the Plan 85-04 Task 5 cross-distro
audible-PASS protocol checkpoint, human-verified and APPROVED by Kyle on
2026-06-01 (see 85-04-SUMMARY.md "Task 5 Checkpoint Outcome"). All 10
PKG-LIN-APP requirements were flipped to Complete on that sign-off. This UAT
file formalizes that approval as the phase verification artifact; no re-test
was run on 2026-06-02 (user elected "Record prior sign-off as UAT").
The checkpoint also found AND fixed 6 build-blocker bugs (commits 282de5c,
d253181, 735850b) and re-verified the corrected artifact before approval.
-->

## Tests

### 1. Signed AppImage builds with GLIBC ceiling
expected: build.sh produces a signed AppImage — BUILD_OK, GLIBC ≤ 2.35, valid GPG detached signature.
result: pass
notes: BUILD_OK, GLIBC_2.34 (≤ 2.35), Good GPG signature (key 02FEDCEE21A97935). PKG-LIN-APP-08/10.

### 2. Programmatic codec smoke across all distros
expected: smoke harness resolves and plays mp3/aac/aacp/pls on Ubuntu 22.04, Fedora 40, openSUSE Tumbleweed with no failures.
result: pass
notes: 4/4 codec modes × 3 distros, 0 SPIKE_FAIL. GStreamer 1.28.3, OpenSSL TLS, autoaudiosink.

### 3. Audible host launch + media keys
expected: Launch AppImage on host — GUI appears, MP3 and AAC streams are audible, media-key pause/resume works.
result: pass
notes: Host launch GUI + audible MP3/AAC + media-key pause/resume confirmed. PKG-LIN-APP-07.

### 4. In-container audible playback (portability)
expected: `--appimage-extract-and-run` plays audibly inside all three target-distro containers (portable, no host deps).
result: pass
notes: Audible in ms-linux-{ubuntu22,fedora40,tumbleweed} via --appimage-extract-and-run. PKG-LIN-APP-05.

### 5. YouTube playback out of the box
expected: A YouTube-backed station plays without manual cookie setup — bundled Node + yt-dlp EJS solver resolves the stream.
result: pass
notes: YouTube playback confirmed; bundled Node + yt-dlp EJS solver, no cookies needed. PKG-LIN-APP-04.

### 6. Desktop integration + zsync update action
expected: AppImageLauncher integrates the AppImage (desktop entry created, deduped against dev install), and the "Update this AppImage" zsync action is present. Standalone launch also works without integration.
result: pass
notes: Integrated to ~/Applications/MusicStreamer-x86_64_<hash>.AppImage + appimagekit desktop entry ("MusicStreamer (1)", auto-deduped). zsync update action present (PKG-LIN-APP-06). Standalone launch works without integration (PKG-LIN-APP-05).

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]

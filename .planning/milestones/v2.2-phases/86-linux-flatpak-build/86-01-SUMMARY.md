---
phase: 86-linux-flatpak-build
plan: "01"
subsystem: packaging/flatpak
tags: [flatpak, manifest, sandbox-policy, pip-deps, appstream, desktop-entry]
dependency_graph:
  requires: []
  provides:
    - io.github.kcreasey.MusicStreamer.yaml  # consumed by Plans 03 (drift-guards) and 04 (build driver)
    - python3-modules.yaml                   # consumed by flatpak-builder at build time (FP-09)
    - tools/linux-flatpak/flatpak-requirements.txt  # consumed by flatpak-pip-generator regeneration
    - tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop  # FP-10 validator target
    - tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml  # FP-10 validator target
    - tools/linux-flatpak/README.md          # operator documentation
  affects: []
tech_stack:
  added:
    - flatpak-builder 1.4.9 (via org.flatpak.Builder Flatpak — no-sudo install)
    - flatpak-pip-generator 2026.5.28 (via uv tool install)
    - org.kde.Platform//6.8 runtime
    - org.kde.Sdk//6.8 SDK
    - io.qt.PySide.BaseApp//6.8 base
    - org.freedesktop.Platform.ffmpeg-full//24.08 extension
    - org.freedesktop.Sdk.Extension.node20//24.08 SDK extension
  patterns:
    - Flatpak YAML manifest (id + runtime + base + sdk-extensions + add-extensions + finish-args + modules)
    - flatpak-pip-generator offline pip dependency manifest (python3-modules.yaml)
    - AppStream metainfo XML with OARS 1.1 content rating
key_files:
  created:
    - io.github.kcreasey.MusicStreamer.yaml
    - python3-modules.yaml
    - tools/linux-flatpak/flatpak-requirements.txt
    - tools/linux-flatpak/README.md
    - tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop
    - tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml
  modified: []
decisions:
  - "D-installed-as-flatpak: flatpak-builder installed via org.flatpak.Builder Flatpak (not apt — requires sudo) to avoid authentication"
  - "D-oq1-confirmed: org.kde.Platform//6.8 internal SDK = Freedesktop 24.08; ffmpeg-full//24.08 and node20//24.08 are correctly versioned"
  - "D-appstreamcli-no-net: appstreamcli validate requires --no-net in dev (GitHub mirror URLs not yet live); structural validity confirmed"
  - "D-oars-empty: MusicStreamer is a passive audio player with no user-generated content; empty oars-1.1 content_rating is correct"
metrics:
  duration_minutes: 45
  completed_date: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 6
---

# Phase 86 Plan 01: Flatpak Manifest, pip-deps, Desktop/Metainfo Artifacts Summary

**One-liner:** Flatpak manifest io.github.kcreasey.MusicStreamer.yaml authored with exact locked sandbox policy (7 finish-args allow-list), python3-modules.yaml generated PySide6-free via flatpak-pip-generator from curated requirements, .desktop and AppStream metainfo XML pass FP-10 validators.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| Task 1 | Install toolchain, generate python3-modules.yaml, author flatpak-requirements.txt | e8281982 | python3-modules.yaml, tools/linux-flatpak/flatpak-requirements.txt, tools/linux-flatpak/README.md |
| Task 2 | Author Flatpak YAML manifest with locked sandbox policy | 5d648826 | io.github.kcreasey.MusicStreamer.yaml |
| Task 2 fix | Fix comment text to avoid false positive in filesystem=home grep check | 4c3a506c | io.github.kcreasey.MusicStreamer.yaml |
| Task 3 | Author .desktop entry and AppStream metainfo XML (FP-10) | 713c146e | tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop, tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml |

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| manifest parse + allow-list | python3 yaml.safe_load() assert | PASS |
| manifest deny-list (T-86-01/T-86-02) | python3 assert + grep -c | PASS (0 forbidden entries) |
| BASEAPP_REMOVE_WEBENGINE absent | grep -v '^#' \| grep -c | PASS (0 occurrences) |
| python3-modules.yaml PySide6-free | python3 assert 'PySide6' not in text | PASS |
| appstreamcli validate | appstreamcli validate --no-net | PASS (exit 0) |
| desktop-file-validate | desktop-file-validate | PASS (exit 0) |
| ffmpeg-full version == '24.08' | YAML parse assert | PASS |
| node copy build-command | grep -c | PASS (1 occurrence) |
| mkdir -p lib/ffmpeg cleanup | grep -c | PASS (1 occurrence) |
| .desktop Icon == io.github.kcreasey.MusicStreamer | grep | PASS |
| x-mpegurl + x-scpls absent (PKG-LIN-APP-09) | grep | PASS (both absent) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] flatpak-builder installed via Flatpak instead of apt**
- **Found during:** Task 1
- **Issue:** `sudo apt install flatpak-builder` failed — interactive TTY authentication required in agent context
- **Fix:** Installed `org.flatpak.Builder` (Flatpak application) from Flathub system remote without sudo. Version 1.4.9 (plan expected 1.4.8 — newer candidate from Flathub). `flatpak run org.flatpak.Builder --version` exits 0.
- **Files modified:** none (runtime install, not tracked)
- **Commit:** n/a (environment setup)

**2. [Rule 3 - Blocking] flatpak_pip_generator installed via uv tool instead of pip**
- **Found during:** Task 1
- **Issue:** `pip install flatpak-pip-generator` blocked by PEP 668 (externally managed Python environment); `--break-system-packages` would risk system Python integrity
- **Fix:** Installed via `uv tool install flatpak-pip-generator`; accessible at `~/.local/bin/flatpak_pip_generator`. Version 2026.5.28 as expected. Minor Python 3.14 traceback at completion (`ImportError: cannot import name 'main'`) but tool completed successfully (output file written before traceback).
- **Files modified:** none (runtime install)
- **Commit:** n/a

**3. [Rule 3 - Blocking] appstreamcli validate requires --no-net flag**
- **Found during:** Task 3 verification
- **Issue:** `appstreamcli validate` exits non-zero (3) when GitHub URLs or screenshot URLs are unreachable. The GitHub mirror repo URL is not yet live (Flatpak is new, repo may be private). The screenshot image doesn't exist yet.
- **Fix:** Added `--no-net` to appstreamcli validation call; structural validity confirmed (exit 0 with only `I: developer-id-missing` info). URL check is a network availability issue, not a metainfo structure issue. The pytest tests in Plan 03 should use the `skipif+subprocess.run` pattern with `--no-net` per RESEARCH.md Code Examples.
- **Files modified:** none (validation call adjustment)
- **Commit:** n/a (documented in README)

**4. [Rule 1 - Bug] Manifest comment contained forbidden string causing grep false positive**
- **Found during:** Overall plan verification (Task 2)
- **Issue:** Inline YAML comment `# NEVER broaden to :rw or --filesystem=home.` on the :ro mount entry contained `--filesystem=home` as a deny-list reminder. The `grep -v '^#'` check stripped only `^#`-prefixed lines, not indented comments (`  # ...`). Result: acceptance criteria grep returned 1 instead of 0.
- **Fix:** Rephrased comment to `# NEVER broaden scope beyond this :ro mount.` — removes literal forbidden string from comment while preserving intent.
- **Files modified:** io.github.kcreasey.MusicStreamer.yaml
- **Commit:** 4c3a506c

### Open Question Resolutions

**OQ1 (Freedesktop SDK version):** Empirically confirmed — `org.kde.Platform//6.8` uses Freedesktop SDK **24.08** internally. Both `ffmpeg-full//24.08` and `node20//24.08` are correctly versioned. Documented in README.

**OQ3 (flatpak-pip-generator --runtime flag):** `--runtime='org.kde.Sdk//6.8'` used successfully (preferred over `org.freedesktop.Sdk//24.08`). No fallback needed.

**OQ5 (node20 branch):** Declared as `org.freedesktop.Sdk.Extension.node20` without explicit branch qualifier; flatpak-builder will inherit the SDK's branch (expected `//24.08`). Verified with `flatpak list` showing node20 20.20.1 at `24.08` branch installed.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| Screenshot image URL | tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml | ~55 | Screenshot file doesn't exist in repo yet; URL points to future path `tools/linux-flatpak/screenshots/musicstreamer-main.png`. The metainfo is structurally valid (validators pass with `--no-net`). A real screenshot should be added in a future plan (Phase 86 Plan 05 UAT is the appropriate point). |

## Threat Flags

No new threat surface introduced. The manifest declares the exact deny-list mitigations for T-86-01 (--filesystem=home denied) and T-86-02 (--socket=session-bus denied) verified by Python-level YAML parse in the acceptance criteria checks.

## Self-Check: PASSED

All created files verified present on disk. All commits verified in git log.

| Item | Status |
|------|--------|
| io.github.kcreasey.MusicStreamer.yaml | FOUND |
| python3-modules.yaml | FOUND |
| tools/linux-flatpak/flatpak-requirements.txt | FOUND |
| tools/linux-flatpak/README.md | FOUND |
| tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop | FOUND |
| tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml | FOUND |
| .planning/phases/86-linux-flatpak-build/86-01-SUMMARY.md | FOUND |
| Commit e8281982 (Task 1) | FOUND |
| Commit 5d648826 (Task 2) | FOUND |
| Commit 713c146e (Task 3) | FOUND |
| Commit 4c3a506c (comment fix) | FOUND |

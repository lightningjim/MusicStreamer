---
phase: 86-linux-flatpak-build
plan: "03"
subsystem: packaging/flatpak-drift-guards
tags: [flatpak, drift-guards, security, tests, yaml-parsed]
dependency_graph:
  requires: ["86-01", "86-02"]
  provides: ["flatpak-drift-guard-suite"]
  affects: ["tests/test_packaging_spec.py"]
tech_stack:
  added: ["pyyaml>=6 (test extra)"]
  patterns: ["yaml.safe_load YAML-parsed guards", "skip-if-not-installed subprocess validators"]
key_files:
  created: []
  modified:
    - tests/test_packaging_spec.py
    - pyproject.toml
    - tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml
decisions:
  - "Use --no-net flag for appstreamcli validate test to avoid URL-reachability failures before GitHub publication"
  - "Add pyyaml>=6 to test extras so yaml.safe_load is available in CI and uv test runs"
  - "Add id attribute to <developer> element in metainfo XML (appstreamcli developer-id-missing info)"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-02"
  tasks: 2
  files_modified: 3
---

# Phase 86 Plan 03: Flatpak Drift-Guard Suite Summary

Flatpak packaging drift-guard suite added to `tests/test_packaging_spec.py`: YAML-parsed allow-list, security-critical deny-list, runtime version pins, FP-10 validators (appstreamcli + desktop-file-validate, skip-if-not-installed), python3-modules.yaml validity, Flatpak .desktop playlist-MIME guard, and first-launch detection integration test — all green on dev host with no regression to Windows/AppImage guards.

## Tasks Completed

### Task 1: Manifest allow-list / deny-list / runtime-pin / app-id drift-guards
- **Commit:** `df6c10be`
- **Files:** `tests/test_packaging_spec.py`, `pyproject.toml`, `uv.lock`
- **Tests added:**
  - `test_flatpak_manifest_id` — FP-01 app ID assertion (yaml parsed)
  - `test_flatpak_runtime_version_pins` — FP-03 runtime-version=6.8, base-version=6.8, ffmpeg-full=24.08, node20 present
  - `test_flatpak_finish_args_allow_list` — FP-04/FP-05/D-01 all 7 required finish-args present
  - `test_flatpak_finish_args_deny_list` — D-13 SECURITY-CRITICAL: --filesystem=home, --filesystem=home:rw, --socket=session-bus all absent from parsed list
  - `test_flatpak_qtwebengine_disable_sandbox` — FP-05 QTWEBENGINE_DISABLE_SANDBOX=1 present
  - `test_flatpak_mpris2_own_name` — FP-08 static half: --own-name=org.mpris.MediaPlayer2.MusicStreamer present
  - `test_flatpak_narrow_ro_mount` — FP-06/D-01/D-05: narrow :ro mount present AND is the ONLY --filesystem entry

### Task 2: python3-modules.yaml, FP-10 validator, and first-launch detection guards
- **Commit:** `e7ce5a9b` (metainfo fix portion)
- **Files:** `tests/test_packaging_spec.py` (included in Task 1 commit), `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml`
- **Tests added:**
  - `test_python3_modules_yaml_exists` — FP-09: file exists, valid YAML, no PySide6 (T-86-08)
  - `test_appstreamcli_validate_passes` — FP-10: skip-if-not-installed, --no-net; asserts returncode==0
  - `test_desktop_file_validate_passes` — FP-10: skip-if-not-installed; asserts returncode==0
  - `test_flatpak_desktop_no_playlist_mime` — PKG-LIN-APP-09 preserved: no audio/x-mpegurl or x-scpls
  - `test_first_launch_detection` — FP-06 integration: detect + offer-once cycle (D-03) with monkeypatched _HOST_DB and sandbox data dir

## Verification Results

```
uv run --with pytest --with pyyaml pytest tests/test_packaging_spec.py tests/test_packaging_linux_spec.py -v
37 passed in 0.10s
```

- `test_flatpak_finish_args_deny_list` PASSED — deny-list operates on parsed YAML list
- `test_flatpak_finish_args_allow_list` PASSED — all 7 required args confirmed present
- `test_flatpak_runtime_version_pins` PASSED — 6.8/24.08/node20 all pinned
- `test_first_launch_detection` PASSED — detect + write_offered_flag + offer-once confirmed
- `test_appstreamcli_validate_passes` PASSED (appstreamcli 1.1.2 installed on dev host)
- `test_desktop_file_validate_passes` PASSED
- No regression in Windows/AppImage guards (25 pre-existing tests still green)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing dependency] Added pyyaml>=6 to test extras in pyproject.toml**
- **Found during:** Task 1 execution
- **Issue:** `import yaml` at module level in test file caused `ModuleNotFoundError: No module named 'yaml'` — pyyaml was not in the test optional-dependencies
- **Fix:** Added `pyyaml>=6` to `[project.optional-dependencies] test` in `pyproject.toml`
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** `df6c10be`

**2. [Rule 1 - Bug] Fixed appstreamcli validate failing on URL-reachability checks**
- **Found during:** Task 2 execution — `test_appstreamcli_validate_passes` failed with returncode 3 (warnings)
- **Issue:** appstreamcli performed live network checks for homepage URL, bugtracker URL, and screenshot image URL; all three returned "URL was not found on the server" because the GitHub repo is not yet published at Phase 86 development time
- **Fix:** Added `--no-net` flag to the appstreamcli invocation in the test. The structural XML validity check is complete without network access; URL existence is moot until publication.
- **Files modified:** `tests/test_packaging_spec.py`
- **Commit:** included in `df6c10be`

**3. [Rule 1 - Bug] Fixed appstreamcli developer-id-missing info causing validation failure**
- **Found during:** Task 2 execution — appstreamcli reported `developer-id-missing` info on the `<developer>` element, contributing to returncode != 0
- **Issue:** The `<developer>` element lacked an `id` attribute required by the appstreamcli AppStream spec
- **Fix:** Added `id="io.github.kcreasey"` to `<developer>` in metainfo XML
- **Files modified:** `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml`
- **Commit:** `e7ce5a9b`

## Self-Check: PASSED

Files exist:
- `tests/test_packaging_spec.py` — FOUND
- `.planning/phases/86-linux-flatpak-build/86-03-SUMMARY.md` — FOUND (this file)

Commits exist:
- `df6c10be` feat(86-03): add Flatpak manifest drift-guard suite — FOUND
- `e7ce5a9b` fix(86-03): add developer id to metainfo XML — FOUND

## Known Stubs

None — all new tests assert against real Plan 01/02 artifacts.

## Threat Flags

No new security-relevant surface introduced (tests-only plan plus a metainfo XML attribute fix).

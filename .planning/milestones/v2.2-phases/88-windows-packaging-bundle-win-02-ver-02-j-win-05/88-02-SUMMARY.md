---
phase: 88
plan: "02"
subsystem: windows-packaging
tags: [testing, aumid, windows, gstreamer, aac, drift-guard]
dependency_graph:
  requires: []
  provides: [WIN-02-B-ci-half, WIN-05-guard-regression]
  affects: [tests/test_aumid_string_parity.py]
tech_stack:
  added: []
  patterns: [static-source-assertion, pytest-tmp-path-fixture, regex-file-parse]
key_files:
  created:
    - tests/test_aumid_string_parity.py
  modified: []
decisions:
  - "Tests co-located in one module: AUMID parity + AAC guard together as Windows packaging drift guards"
  - "Regex AppUserModelID:\\s*\"([^\"]+)\" searches whole .iss file — line-continuation backslash is irrelevant"
  - "__main__.py source check: assert delegate line present AND literal string absent — proves single source of truth"
metrics:
  duration_seconds: 104
  completed_date: "2026-06-05"
  tasks_completed: 2
  files_changed: 1
---

# Phase 88 Plan 02: AUMID Parity Test + AAC Guard Regression Summary

**One-liner:** Static 3-way AUMID drift guard + AAC plugin guard regression pinning gstlibav.dll exit-10 on Linux CI.

## What Was Built

`tests/test_aumid_string_parity.py` — 7 pytest tests, all passing on Linux CI with no Windows VM required.

### Task 1: Static 3-way AUMID parity (WIN-02-B CI half)

Four tests assert that the AUMID string `org.lightningjim.MusicStreamer` is byte-identical across all three sources of truth:

1. `test_constants_app_id_is_canonical` — `constants.APP_ID == "org.lightningjim.MusicStreamer"`
2. `test_iss_icons_aumid_matches_constants` — parses `packaging/windows/MusicStreamer.iss` `[Icons]` section via regex `AppUserModelID:\s*"([^"]+)"`, asserts equality with `constants.APP_ID`
3. `test_main_aumid_default_resolves_to_constants` — source-level grep of `__main__.py` asserts `app_id = constants.APP_ID` is present (delegation line) AND the literal `org.lightningjim.MusicStreamer` is NOT present (no second copy)
4. `test_no_drift_three_way` — single 3-way equality assertion; any drift fails with a dict showing which value changed

### Task 2: AAC plugin-guard regression (WIN-05)

Three tests pin the guard logic in `tools/check_bundle_plugins.py`:

5. `test_required_plugin_dlls_map_aac` — asserts `REQUIRED_PLUGIN_DLLS["gstlibav.dll"] == ("avdec_aac", "gst-libav")` and `["gstaudioparsers.dll"] == ("aacparse", "gst-plugins-good")`
6. `test_guard_returns_10_on_missing_gstlibav` — tmp_path bundle with `gstaudioparsers.dll` only (no `gstlibav.dll`); `main(["--bundle", ...])` returns `10`
7. `test_guard_returns_0_when_all_present` — tmp_path bundle with both DLLs; `main(["--bundle", ...])` returns `0`

## Verification

```
uv run --with pytest pytest tests/test_aumid_string_parity.py -x -q
7 passed, 1 warning in 0.09s
```

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 | 3-way AUMID parity + AAC guard regression | b7a6cc6e | tests/test_aumid_string_parity.py |

## Deviations from Plan

None — plan executed exactly as written. Both tasks collapsed into a single atomic commit because both write to the same file and together constitute the complete deliverable.

## Known Stubs

None. All tests assert against existing source — no stubs, no placeholders, no hardcoded empty values.

## Threat Flags

None. This plan adds a read-only static test. No new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- `tests/test_aumid_string_parity.py` exists: FOUND
- Commit `b7a6cc6e` exists: FOUND (git log confirms)
- All 7 tests pass: CONFIRMED (`7 passed, 1 warning in 0.09s`)
- Mutation reasoning: changing `.iss` AUMID to a different string would cause `test_iss_icons_aumid_matches_constants` and `test_no_drift_three_way` to fail immediately — drift is caught.

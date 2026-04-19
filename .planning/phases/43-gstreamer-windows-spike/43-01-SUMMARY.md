---
phase: 43-gstreamer-windows-spike
plan: 01
subsystem: packaging
tags: [windows, gstreamer, pyinstaller, spike, wave-1]
requires: [43-RESEARCH.md skeletons, 43-CONTEXT.md decisions D-01..D-14]
provides: [build-artifacts-for-vm-iteration]
affects: [phase-44-windows-installer]
tech-stack:
  added: []
  patterns: [paste-back-iteration, exit-code-contract, runtime-hook-env-setup]
key-files:
  created:
    - .planning/phases/43-gstreamer-windows-spike/43-spike.spec
    - .planning/phases/43-gstreamer-windows-spike/runtime_hook.py
    - .planning/phases/43-gstreamer-windows-spike/smoke_test.py
    - .planning/phases/43-gstreamer-windows-spike/build.ps1
    - .planning/phases/43-gstreamer-windows-spike/.gitignore
    - .planning/phases/43-gstreamer-windows-spike/README.md
  modified: []
decisions:
  - "All artifacts copied verbatim from 43-RESEARCH.md skeletons — no improvisation per plan directive"
  - "Audio sink choice deferred to runtime: spec uses contrib hook's broad plugin collection (autoaudiosink + wasapi2/wasapi/directsound bundled) per D-05"
metrics:
  duration: 7m
  completed: 2026-04-19
---

# Phase 43 Plan 01: Wave 1 Skeleton Landing Summary

PyInstaller spike scaffolding (spec + runtime hook + smoke test + PowerShell driver + ignore + runbook) committed verbatim from research skeletons so the user can run iteration 1 on the Windows 11 VM.

## What Was Built

Six files in `.planning/phases/43-gstreamer-windows-spike/`:

| File | Bytes | Role |
|------|------:|------|
| `43-spike.spec` | 4570 | PyInstaller .spec — Tree() blocks for gio/modules, girepository, glib schemas; runtime_hooks=["runtime_hook.py"]; upx=False |
| `runtime_hook.py` | 2307 | Sets GIO_EXTRA_MODULES, GI_TYPELIB_PATH, GST_PLUGIN_SCANNER before Gst.init; SPIKE_DIAG_RTHOOK marker on stderr |
| `smoke_test.py` | 5212 | playbin3 + souphttpsrc HTTPS smoke; exit codes 0/1/2/3; SPIKE_OK/FAIL/DIAG markers; URL query-string redaction (T-43-01) |
| `build.ps1` | 3110 | Pre-flight DLL guards (libgstreamer-1.0-0, gst-inspect, libgiognutls); pip install; PyInstaller; smoke run; tee to artifacts/ |
| `.gitignore` | 128 | Blocks test_url.txt, artifacts/, build/, dist/, *.spec.log, __pycache__/ |
| `README.md` | 1843 | One-time VM setup + per-iteration paste-back loop + pass conditions |

**Total:** 17,170 bytes across 6 files, 3 commits.

## Commits

| Task | Hash | Files |
|------|------|-------|
| 1 | `96df1dd` | 43-spike.spec, runtime_hook.py |
| 2 | `94636fe` | smoke_test.py, build.ps1 |
| 3 | `d20c6cc` | .gitignore, README.md |

## Verbatim-vs-Improvised

**Everything verbatim** from `43-RESEARCH.md`:
- `.spec` body from §"PyInstaller `.spec` Structure — Draft" (lines ~315-454)
- `runtime_hook.py` from §"Runtime Hook Template" (lines ~464-518)
- `smoke_test.py` from §"`smoke_test.py` — Exit-Code Contract" (lines ~616-777)
- `build.ps1` from §"`build.ps1` Skeleton" (lines ~526-610)
- `.gitignore` entries from §"Runtime State Inventory" (lines ~297-307)
- `README.md` body verbatim from plan Task 3 spec block

**No improvisation.** GStreamer version pinned to 1.24.12 (already baked into RESEARCH paths/MSI filenames). No source code under `musicstreamer/` touched (D-14 honored).

## Acceptance Criteria

All Wave 1 file-checks from `43-VALIDATION.md` pass:

| Row | Check | Status |
|-----|-------|--------|
| 43-01-01 | `test -f .../43-spike.spec` + `Tree(` + `runtime_hooks=...` + `upx=False` | PASS |
| 43-01-02 | `grep -q 'GIO_EXTRA_MODULES' runtime_hook.py` | PASS |
| 43-01-03 | `grep -q 'SPIKE_OK\|SPIKE_FAIL' smoke_test.py` | PASS |
| 43-01-04 | `grep -q 'pyinstaller\|smoke_test.py' build.ps1` | PASS |
| 43-01-05 | `grep -q '?<redacted>' smoke_test.py` | PASS |
| Wave 0 .gitignore | `test_url.txt`, `artifacts/`, `build/`, `dist/`, `*.spec.log` blocked | PASS |
| README ≥10 lines + covers build.ps1, test_url.txt, audible/silent | PASS |

Both Python files parse as valid AST (verified via `python -c "import ast; ast.parse(...)"`).

## Threat Mitigations Applied

**T-43-01 (Listen-key disclosure):**
- `smoke_test.py` line 78: `redacted = url.split("?", 1)[0] + "?<redacted>" if "?" in url else url` — runs before any `_emit("SPIKE_DIAG", url=...)` call.
- `.gitignore` blocks `test_url.txt` (raw URL on VM) and `artifacts/` (paste-back logs that may briefly contain unredacted output before redaction takes effect).
- README explicitly tells user `test_url.txt` is gitignored.

## Deviations from Plan

None — plan executed exactly as written. All skeletons copied verbatim from research per the plan's explicit "do not improvise" directive.

## Assumptions Flagged for Wave 2

The plan's `<output>` block requested flagging skeleton-level assumptions worth noting before iteration 1:

1. **A7 (RESEARCH): PyGObject version unresolved.** `build.ps1` pins `pygobject>=3.50` and `pyinstaller>=6.11`. The exact versions pip resolves on the user's Win11 Python install will not be known until iteration 1's `artifacts\build.log` paste-back. If iteration 1 fails on `gi.repository` import, the failure mode dictates whether to lower-pin (≥3.50,<3.51 to keep girepository-1.0) or upper-pin.

2. **A1 (RESEARCH): MSI install paths assumed at `C:\spike-gst\{runtime,devel}\1.0\msvc_x86_64`.** If the user installs to defaults (`C:\gstreamer\...`), `build.ps1` pre-flight will exit 1 with `SPIKE_FAIL reason=gst_runtime_missing` — instructing them to either re-install with `INSTALLDIR=C:\spike-gst\...` or pass `-GstRoot` / `-GstDevel` overrides on the build.ps1 invocation. README step 2 documents the expected install paths.

3. **A4 (research): `GIO_EXTRA_MODULES` (additive) chosen over `GIO_MODULE_DIR` (replace).** If iteration 1 still reports "TLS/SSL support not available", we may need to fall back to `GIO_MODULE_DIR` and accept the loss of any default GIO modules — not expected on a no-system-GStreamer VM, but a known fallback.

4. **Audio sink choice (D-05):** Spec lets the contrib hook collect all installed plugins (no `exclude_plugins`), so `autoaudiosink` will autoplug whichever Win11 sink is most appropriate (`wasapi2sink` likely). Per RESEARCH anti-pattern, we keep `wasapi2` in the bundle to avoid 80ms latency from `directsoundsink` fallback. If iteration 1 hits `SPIKE_OK` but user replies `silent`, sink choice is the first thing to inspect.

5. **First-audio proxy is `Gst.MessageType.TAG`, not a pad probe.** The smoke test treats first ICY tag arrival as proof bytes flowed through TLS + HTTP + demux. If a stream arrives without ICY tags (rare on AA), the smoke will exit code 3 (timeout) even though audio is playing. RESEARCH acknowledges this tradeoff (lines ~778-780) — pragmatic for a throwaway spike.

## Self-Check: PASSED

Verified all six files exist:
- `.planning/phases/43-gstreamer-windows-spike/43-spike.spec` — FOUND
- `.planning/phases/43-gstreamer-windows-spike/runtime_hook.py` — FOUND
- `.planning/phases/43-gstreamer-windows-spike/smoke_test.py` — FOUND
- `.planning/phases/43-gstreamer-windows-spike/build.ps1` — FOUND
- `.planning/phases/43-gstreamer-windows-spike/.gitignore` — FOUND
- `.planning/phases/43-gstreamer-windows-spike/README.md` — FOUND

Verified all three commits exist in git log:
- `96df1dd` — FOUND
- `94636fe` — FOUND
- `d20c6cc` — FOUND

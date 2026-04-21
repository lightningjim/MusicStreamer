# 43-02 Summary — Wave 2: Paste-Back Iteration Loop

**Completed:** 2026-04-20
**Iterations used:** 1 (of ≤5 budget)
**Outcome:** ✅ SPIKE_OK on first real build attempt

## What happened

The plan anticipated up to 5 paste-back iterations diagnosing against the 10-row
failure-mode table in 43-RESEARCH.md. In practice, iteration 1 cleanly passed
the smoke test — all three ROADMAP success criteria met on the first build
that produced a bundle. The "iterations" consumed before that build produced
a bundle were all **scope/environment** corrections, not spike diagnostics:

1. **GStreamer version bump** — 1.24.12 (research-time pin) was superseded upstream by 1.28.2 (2026-04-08 release) which also consolidated the former split runtime/devel MSIs into a single .exe installer. Fixed via D-03 amendments + path/filename updates in build.ps1 + .spec. Commits: `fce4100`, `685074c`.
2. **Flat install layout** — 1.28.x dropped the cerbero-style `\1.0\msvc_x86_64\` subdir; `GstRoot` default updated.
3. **TLS backend swap** — 1.28.x switched from GnuTLS to OpenSSL upstream; `gioopenssl.dll` replaces `libgiognutls.dll`. Pre-flight accepts either for forward/backward compat.
4. **Scanner location** — `gst-plugin-scanner.exe` moved from `bin/` to `libexec/gstreamer-1.0/`; `.spec` auto-detects both paths.
5. **PyGObject has no PyPI wheels** (upstream policy, not a version issue) — source build required VS Build Tools + meson + pkg-config. Pivoted to conda-forge. Commit: `6e0e09f`. D-03 Amendment (b) documents.
6. **PowerShell ergonomics** — Miniforge Prompt is cmd.exe (.ps1 opens Notepad); UTF-8 em-dashes in .ps1 break cp1252 parsing on PS 5.1; native-command stderr raises NativeCommandError under `$ErrorActionPreference = "Stop"`. Fixed via `powershell -ExecutionPolicy Bypass` runbook, ASCII-only scripts, and `Invoke-Native` helper. Commits: `cb19c00`, `66ddc90`.
7. **URL scheme** — `test_url.txt` initially contained a DI.fm premium URL (`http://` scheme) that smoke_test.py rejects by design (SC-2 requires HTTPS). DI.fm also fails with TLS-layer `error=-5` on `https://` — server-side issue, not a GStreamer bundle problem. Pivoted to SomaFM's HTTPS stream per D-08 fallback plan.

The iteration budget was effectively untouched — we never hit a SPIKE_FAIL reason code from the 10-row failure-mode table. The real diagnostic work was
forward-looking: catching that upstream had shifted since research-time and
documenting the deltas for Phase 44.

## Evidence

From `artifacts/smoke.log` (conda spike env active):
```
SPIKE_DIAG gst_version='GStreamer 1.28.2' plugin_count=185
SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True
SPIKE_DIAG url='https://ice4.somafm.com/dronezone-256-mp3'
SPIKE_DIAG event='first_tag_arrived'
SPIKE_OK audio_sample_received=True duration_s=5.27 errors=[] warnings_count=0
```

From `artifacts/smoke-clean.log` (conda deactivated, SC-3 self-containment proof):
```
SPIKE_DIAG gst_version='GStreamer 1.28.2' plugin_count=185
SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True
SPIKE_OK audio_sample_received=True duration_s=5.42 errors=[] warnings_count=0
```

User confirmed audibility: **audible**.

## Success Criteria Map

| Criterion | Status | Evidence |
|-----------|--------|----------|
| SC-1: Bundle plays HTTPS audio via playbin3 | ✅ | `SPIKE_OK audio_sample_received=True` |
| SC-2: TLS backend loaded, cert DB available | ✅ | `has_default_database=True` with `GTlsBackendOpenssl` |
| SC-3: Bundle runs in a clean shell (no conda active) | ✅ | Identical pass from `(base)` prompt with spike env deactivated |

## Files modified during Wave 2 (cumulative)

- `43-CONTEXT.md` — D-03 Amendments (a) + (b); D-04 Amendment
- `43-RESEARCH.md` — version + URL + stack table updates
- `43-03-PLAN.md` — findings grep updated (`1.24` → `1.28`)
- `43-spike.spec` — version comment, `GST_ROOT` default, SCANNER_SRC detection, backend-agnostic TLS assertion, Tree block simplification
- `build.ps1` — CONDA_PREFIX detection, pre-flight layout updates, Invoke-Native helper, ASCII-only strings, artifacts/ pre-creation
- `runtime_hook.py` — (unchanged; already backend-agnostic)
- `smoke_test.py` — TLS backend docstring generalized
- `README.md` — conda-forge primary path; MSVC installer demoted to Alternative
- (no source under `musicstreamer/` touched — D-14 honored throughout)

## Handoff to Wave 3

`artifacts/smoke.log` + `artifacts/smoke-clean.log` + bundle BOM enumeration
(DLL list, plugin count, typelib list) captured inline in chat. Wave 3 consumes
them to write `43-SPIKE-FINDINGS.md`.

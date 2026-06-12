---
spike: 001
name: isolated-webengine-helper
type: standard
validates: "Given a pip-only PySide6-Addons env (no conda, no GStreamer), when oauth_helper is PyInstaller-frozen as its own standalone exe and run on Win11, then the QtWebEngine login windows (gbs/twitch/google) open with no DLL-load failure, cookie-capture completes end-to-end, and the bundle's own Qt wins over conda's qt6-main on PATH"
verdict: PENDING
related: []
tags: [windows, pyinstaller, qtwebengine, oauth, packaging, 88.3-g6]
---

# Spike 001: Isolated WebEngine Helper (B1)

## What This Validates

**Given** an isolated, pip-only PySide6-Essentials+Addons 6.10.1 environment with
no conda Qt and no GStreamer,
**when** `musicstreamer/oauth_helper.py` is PyInstaller-frozen as its **own**
standalone `oauth_helper.exe` and launched on a Win11 VM,
**then**:
1. the bundle contains `QtWebEngineProcess.exe` + `Qt6WebEngineCore.dll` and the
   exe launches with **no** `DLL load failed` (the Phase 88.3 G6 signature);
2. `--mode gbs` / `--mode twitch` / `--mode google` each open a real QtWebEngine
   login window and complete the cookie/token capture; and
3. the exe loads its **own** bundled Qt by adjacency **even with conda's
   `Library\bin` on PATH** — proving it is safe to spawn from the conda main exe.

If all three hold, B1 is feasible and the integration (conda main exe launches
the helper exe; Inno ships both artifacts) gets planned as 88.3 gap closure, and
the stale same-bundle 88.3-01 spec hiddenimports + step-4e guard + 88.3-02 VM
plan are reworked under B1.

## Why This Is the Whole Ballgame

The conda single-bundle approach (88.3-01) failed for one reason only: **conda
`qt6-main` Qt6Core shadowed pip-Addons' WebEngine Qt6Core on PATH** →
unresolvable transitive export → `DLL load failed`. The diagnosis confirmed
conda-forge has **no** PySide6 WebEngine bindings at any version, and all-pip is
off the table because pip PySide6's ICU differs from conda-forge GStreamer's ICU
(would break audio — spike-findings-musicstreamer constraint). B1 sidesteps the
conflict entirely by giving WebEngine its **own** process **and** its own
ABI-self-consistent pip-Qt bundle. `oauth_helper` is already a separate
subprocess, so this is a launch-target + 2nd-build change, not a rewrite.

## Research

Recipe carried forward from `88.3-RESEARCH.md` (already resolved during 88.3
planning) — re-applied here against a **pip** env instead of conda:

| Question | Finding | Source |
|----------|---------|--------|
| Collecting `QtWebEngineProcess.exe` + `.pak` + locales + `qt.conf` | A `hiddenimport` of `PySide6.QtWebEngineCore` triggers `hook-PySide6.QtWebEngineCore` → `get_qt_webengine_binaries_and_data_files()`, which bundles the helper exe, pak files, locales, and generates the subprocess `qt.conf`. No manual `Tree()` needed. | PyInstaller `utils/hooks/qt.py`; 88.3-RESEARCH §308 |
| Will WebEngine bundle from a **pip** PySide6-Addons env? | **Untested before this spike.** Pip PySide6-Addons ships `Qt6WebEngineCore.dll` + `QtWebEngineProcess.exe` + the Quick/Qml/WebChannel/Positioning/Pdf deps WebEngine needs, all built against pip-PySide6's own Qt6Core — so in an isolated process there is nothing to shadow it. The hook fires identically regardless of pip-vs-conda. | This spike (Stage A) |
| Does adjacency beat PATH for a frozen exe? | Windows DLL search prefers the loaded module's own directory; PyInstaller onedir puts all Qt DLLs next to the exe under `_internal`. Expected to win over conda `Library\bin` on PATH — **but must be empirically confirmed** because the original bug was precisely a PATH-shadow. | This spike (Stage C) |
| PySide6 version | Pinned **6.10.1** to match the conda main app's cookie/`QNetworkCookie` API contract (spike decision). | MANIFEST Requirements |

Prior-art also consulted: `spike-findings-musicstreamer` (PS 5.1 stderr trap,
ASCII-only `.ps1`, Miniforge-prompt gotcha — all applied to the build scripts).

## How to Run (Win11 VM Runbook)

> All Linux-side artifacts are committed. Everything below runs **on the Win11
> VM** with the repo checked out. The verdict stays PENDING until these pass.

### Prereqs
- Win11 VM with the MusicStreamer repo checked out.
- A **system** Python 3.12 (`py -3.12 --version`) — *not* conda. (Install from
  python.org if absent; it only needs to exist for `py -3.12 -m venv`.)
- A desktop session (WebEngine needs a real display to render).

### Stage A + builds (automated)
```powershell
cd <repo>\.planning\spikes\001-isolated-webengine-helper
# IMPORTANT: no conda env active for the build. If your prompt shows (base) or
# (musicstreamer-build), run `conda deactivate` until it's gone.
powershell -ExecutionPolicy Bypass -File .\build-helper.ps1
```
Expected: ends with `=== SPIKE 001 BUILD + STAGE A: ALL GREEN ===`. Builds both
bundles, asserts `QtWebEngineProcess.exe` + `Qt6WebEngineCore.dll` are present,
and runs the headless `--probe` smoke (exit 0). A non-zero exit prints
`SPIKE-FAIL [code]` — codes are documented at the top of `build-helper.ps1`
(22 = the G6 missing-WebEngine signature).

### Stage B — real helper login windows (manual judgement)
```powershell
.\dist\oauth_helper\oauth_helper.exe --mode gbs
.\dist\oauth_helper\oauth_helper.exe --mode twitch
.\dist\oauth_helper\oauth_helper.exe --mode google
```
Expected for each: a QtWebEngine login window opens (no `exit=2`, no
`DLL load failed`); completing login prints the cookie/token to stdout and a
`Success` JSON event to stderr, exit 0. (Twitch harvests the `.twitch.tv`
`auth-token` cookie; gbs/google harvest cookies.)

### Stage C — isolation under conda-on-PATH (decisive safety check)
```powershell
# find conda's Qt first:
conda activate musicstreamer-build
where.exe Qt6Core.dll          # note the ...\Library\bin path
conda deactivate
powershell -ExecutionPolicy Bypass -File .\check-isolation.ps1 -CondaBin "C:\path\to\miniforge3\envs\musicstreamer-build\Library\bin"
```
Expected: `STAGE C PASS: adjacency won`. Inspect `isolation-probe.log` — the
`path_audit` event should list conda entries **and** `qt_exec_path` /
`qtwebengineprocess_present` should resolve **into the bundle's** `_MEIPASS\PySide6`,
not conda. A non-zero exit (31) means adjacency lost and B1 needs explicit
isolation (e.g., a clean PATH on spawn).

### Report back
Paste the tail of `build.log`, `probe.log`, the three Stage B stderr blocks, and
`isolation-probe.log` here, plus a one-line "saw the window render" for Stage B.

## Observability

Both the smoke (`webengine_smoke.py`) and the real `oauth_helper.py` emit
JSON-line forensic events on **stderr** (`_emit_event` / `emit` — `t_ms`,
`category`, `detail`, plus context). Key Stage-A/C events:
`webengine_import_ok`, `qapp_created`, `path_audit` (conda PATH entries),
`qt_exec_path`, `qtwebengineprocess_present`, `load_started`, `load_finished`,
`exit`. The `.ps1` drivers `Tee-Object` each run to `pip.log` / `build.log` /
`probe.log` / `isolation-probe.log` for copy-paste evidence.

## Investigation Trail

- **2026-06-12** — Spike created. Architecture nailed down from source: the
  failed 88.3-01 path had the conda main exe **re-exec itself**
  (`_make_oauth_launch_args` → `sys.executable --oauth-helper`), forcing
  WebEngine into the conda bundle. B1 changes the launch target to a **separate**
  `oauth_helper.exe`. Confirmed `oauth_helper.py` imports only stdlib + PySide6
  (no sibling `musicstreamer` modules), so it freezes cleanly as its own entry.
  Built: isolated `requirements.txt` (pin 6.10.1), Stage-A `webengine_smoke.py`
  (+ spec), Stage-B `oauth_helper_standalone.spec` pointing at the real helper,
  `build-helper.ps1` (venv + pip + build + WebEngine assertions + probe),
  `check-isolation.ps1` (Stage C). Verdict PENDING — awaiting VM run.
- **2026-06-12 (VM run 1)** — Build prereq surfaced: the VM has **only miniforge**
  Python; `py -3.12` reports "No suitable Python runtime found". B1's isolated
  helper build therefore needs a **conda-free Python 3.12** on the build machine.
  `build-helper.ps1` updated to accept `-PythonExe` so a CLEAN conda-forge env
  (`conda create -n helper-iso -c conda-forge python=3.12 pip`, no Qt/GStreamer)
  can act as the provider, or install python.org 3.12 via
  `winget install -e --id Python.Python.3.12`. The conda guard (exit 20) also
  correctly fired on an active `(base)` — a full `conda deactivate` is required
  before building. **→ B1 requirement: document a conda-free Python 3.12 build
  prereq in the eventual packaging README.**
- _(VM operator: append findings/surprises per stage here as you run them.)_

## Results

**Verdict: PENDING** — requires the Win11 VM run above. This spike's feasibility
question cannot be answered on Linux (no Windows PyInstaller build / no frozen
exe launch). The Linux-side deliverable is the complete, turnkey artifact set +
runbook that makes the VM session a single `build-helper.ps1` invocation plus
two short manual stages.

Decision rule once run:
- **All three stages green** → VALIDATED. Proceed to plan 88.3 gap closure under
  B1 (wire conda main exe → `oauth_helper.exe`; Inno ships both; rework the
  stale 88.3-01 same-bundle spec/guard + 88.3-02 VM plan).
- **Stage A fails (code 22/24)** → INVALIDATED for the simple recipe; escalate to
  B6 (system-browser OAuth) per 88.3-UAT resolution_options.
- **Stage C fails (code 31)** → PARTIAL: B1 works standalone but needs an explicit
  clean-PATH spawn; fold that into the integration plan.

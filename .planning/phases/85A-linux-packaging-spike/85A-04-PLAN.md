---
phase: 85A-linux-packaging-spike
plan: 04
type: execute
wave: 2
depends_on:
  - 85A-02
files_modified:
  - .planning/spikes/85a-linux-packaging-spike/hello_world.py
  - .planning/spikes/85a-linux-packaging-spike/AppRun
  - .planning/spikes/85a-linux-packaging-spike/smoke_test.py
  - .planning/spikes/85a-linux-packaging-spike/test_url.txt
autonomous: true
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - apprun-template
  - smoke-harness
  - hello-world

must_haves:
  truths:
    - "hello_world.py is a single-file minimal playbin3 driver mirroring Phase 43's smoke_test.py shape"
    - "AppRun template exports the 4 success-criteria env vars (GST_PLUGIN_SYSTEM_PATH_1_0, GST_PLUGIN_PATH_1_0, GST_PLUGIN_SCANNER, GST_REGISTRY_FORK=no) plus GIO_EXTRA_MODULES + GI_TYPELIB_PATH"
    - "AppRun template's GST_* env vars point under $APPDIR/usr/conda/ (linuxdeploy-plugin-conda layout) NOT $APPDIR/usr/ (research-discovered distinction)"
    - "AppRun template sets GST_REGISTRY_FORK=no EXPLICITLY (the plugin's hook only sets GST_REGISTRY_REUSE_PLUGIN_SCANNER=no — a DIFFERENT flag per Pitfall 3)"
    - "smoke_test.py mirrors Phase 43 shape: playbin3 + bus state-machine + GLIBC grep + gst-inspect resolution + SomaFM-only fallback chain (Groove Salad -> Drone Zone -> Beat Blender)"
    - "Test URL manifest captures HTTP + HTTPS SomaFM URLs from D-07/D-08/D-09"
  artifacts:
    - path: ".planning/spikes/85a-linux-packaging-spike/hello_world.py"
      provides: "Minimal Qt-event-loop-less playbin3 driver (uses GLib.MainLoop only) — argv: <url>"
      contains: "Gst.parse_launch"
      min_lines: 60
    - path: ".planning/spikes/85a-linux-packaging-spike/AppRun"
      provides: "Bash AppRun template; the spike's PRIMARY deliverable (Phase 85 copies verbatim)"
      contains: "GST_REGISTRY_FORK"
    - path: ".planning/spikes/85a-linux-packaging-spike/smoke_test.py"
      provides: "Full validation harness: GLIBC grep + gst-inspect avdec_aac/aacparse + playbin3 state-machine + SomaFM fallback chain"
      contains: "avdec_aac"
      min_lines: 100
    - path: ".planning/spikes/85a-linux-packaging-spike/test_url.txt"
      provides: "SomaFM URL list per D-07/D-08/D-09"
      contains: "ice1.somafm.com"
  key_links:
    - from: "AppRun"
      to: "build.sh (Plan 05)"
      via: "build.sh COPIES this AppRun into $APPDIR/ as the AppImage entry point"
      pattern: "cp .*AppRun"
    - from: "smoke_test.py"
      to: "run-smoke.sh (Plan 06)"
      via: "Plan 06's distrobox wrapper invokes `python smoke_test.py --uri <url> --timeout 30` inside the AppRun shell"
      pattern: "smoke_test\\.py"
    - from: "AppRun GST_REGISTRY_FORK"
      to: "D-06 audible PASS protocol step 7 (relaunch)"
      via: "Relaunch is THE protocol step that exercises GST_REGISTRY_FORK — Pitfall 3 mitigation verified there"
      pattern: "GST_REGISTRY_FORK=no"
---

<objective>
Write the three source files that constitute the spike's "app under test" surface: a hello-world playbin3 driver, the AppRun env-var template (the spike's PRIMARY deliverable), and the smoke_test.py validation harness. Plus the SomaFM URL manifest.

Purpose: Implements RESEARCH.md §Pattern 1 (AppRun env-var template, lines 207-249) + §Code Examples / Minimal hello_world.py (lines 407-507) + the spike's success criterion #3 (gst-inspect resolution) and #4 (AppRun template). These three files are the load-bearing "what runs inside the AppImage" surface — Plan 05's build.sh just bundles them.
Output: 4 files (hello_world.py, AppRun, smoke_test.py, test_url.txt) under `.planning/spikes/85a-linux-packaging-spike/`.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md
@.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/smoke_test.py
@.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/runtime_hook.py

<interfaces>
<!-- The 4 success-criteria env vars (RESEARCH.md §Pattern 1, lines 217-247). -->
<!-- These are THE spec the AppRun template implements; Phase 85 copies the resulting AppRun verbatim. -->

```bash
export GST_PLUGIN_SYSTEM_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_REGISTRY_FORK="no"   # CRITICAL: NOT GST_REGISTRY_REUSE_PLUGIN_SCANNER — different flag (Pitfall 3)
export GIO_EXTRA_MODULES="${APPDIR}/usr/conda/lib/gio/modules"   # HTTPS TLS backend (Pitfall 4)
export GI_TYPELIB_PATH="${APPDIR}/usr/conda/lib/girepository-1.0"
export PYTHONHOME="${APPDIR}/usr/conda"
export PATH="${APPDIR}/usr/conda/bin:${PATH}"
```

<!-- SomaFM URLs (D-07, D-08, D-09). -->
HTTP_PRIMARY=http://ice1.somafm.com/groovesalad-128-mp3
HTTPS_PRIMARY=https://ice6.somafm.com/groovesalad-128-mp3
FALLBACK_2=http://ice1.somafm.com/dronezone-128-mp3   # Drone Zone
FALLBACK_3=http://ice1.somafm.com/beatblender-128-mp3 # Beat Blender
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| smoke_test.py argv URL -> playbin3 | Untrusted argv crosses into pipeline; validate scheme is http/https and host matches *.somafm.com (RESEARCH.md §Security Domain V5) |
| HTTPS stream -> conda glib-networking TLS backend | TLS handshake validation via $GIO_EXTRA_MODULES discovery; Pitfall 4 mitigation |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-04-IV | Spoofing / Input Validation | smoke_test.py argv | mitigate | Validate URL scheme is `http` or `https` and host matches `*.somafm.com` per RESEARCH.md §Security Domain V5 (prevent accidental SSRF-like exec during dev iteration) |
| T-85A-04-TLS | Information disclosure | HTTPS bundle discoverability | mitigate | AppRun template sets GIO_EXTRA_MODULES per Pitfall 4; smoke_test.py asserts Gio.TlsBackend.get_default_database() is not None |
</threat_model>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Author hello_world.py (minimal playbin3 driver)</name>
  <files>.planning/spikes/85a-linux-packaging-spike/hello_world.py</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Minimal hello_world.py (lines 407-507) — full reference implementation
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §D-Discretion "Hello-world app scope" — single-file Python; NO QObject bus bridge; Phase 43.1 contract already validated
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/smoke_test.py (shape mirror)
    - .claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md (the rules this file deliberately does NOT exercise — kept out of scope per D-Discretion)
  </read_first>
  <behavior>
    - Argv `<url>` required (single positional); exit 1 with `SPIKE_FAIL reason='usage'` if missing or extra args
    - Calls `Gst.init(None)` and emits `SPIKE_DIAG gst_version=... plugin_count=N url_scheme=http|https` line
    - Constructs `Gst.parse_launch(f'playbin3 uri="{url}"')` — NO element wiring, NO caps negotiation, NO audio-sink property (autoaudiosink per Pitfall 10)
    - Bus signal-watch records `state["playing_at"]` when STATE_CHANGED on pipeline reaches PLAYING; records `state["first_tag_at"]` on first TAG message; appends to `state["errors"]` on ERROR
    - GLib.MainLoop with GLib.timeout_add(200, _tick) tick handler that quits on error OR after 30s of PLAYING OR after 40s wall budget total
    - Exit 0 on PLAYING + 30s clean playback (emits `SPIKE_OK` with time_to_play_s + first_tag_s + played_for_s)
    - Exit 2 on pipeline ERROR (emits `SPIKE_FAIL step='pipeline' errors=[...]`)
    - Exit 3 on never-reached-PLAYING within 40s (emits `SPIKE_FAIL step='never_played'`)
    - Tests live alongside as a `__main__` `if argv == ['--self-test']` block since pytest is out of scope for the spike — runs a syntax + import smoke check only
  </behavior>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/hello_world.py`
    - shell-exit (syntax): `python3 -c "import ast; ast.parse(open('.planning/spikes/85a-linux-packaging-spike/hello_world.py').read())"` exits 0
    - content-grep: `grep -q 'Gst.parse_launch' .planning/spikes/85a-linux-packaging-spike/hello_world.py`
    - content-grep: `grep -q 'playbin3' .planning/spikes/85a-linux-packaging-spike/hello_world.py`
    - content-grep: `grep -q 'SPIKE_OK\|SPIKE_FAIL\|SPIKE_DIAG' .planning/spikes/85a-linux-packaging-spike/hello_world.py`
    - content-grep: `grep -q 'GLib.MainLoop' .planning/spikes/85a-linux-packaging-spike/hello_world.py`
    - shell-exit (negative behavior): `python3 .planning/spikes/85a-linux-packaging-spike/hello_world.py 2>&1 | grep -q 'SPIKE_FAIL.*usage'` (running with no argv emits the expected usage failure marker; even if PyGObject not installed on host, the argv check runs before Gst.init)
    - content-grep (negative — NO Qt bridge): `! grep -E 'QObject|QApplication|QTimer|Signal\(' .planning/spikes/85a-linux-packaging-spike/hello_world.py` (verifies D-Discretion "no QObject bridge")
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/hello_world.py` per RESEARCH.md §Minimal hello_world.py (lines 407-505) verbatim. Module docstring cites Phase 43 smoke_test.py shape + D-Discretion "no QObject bridge" rationale. Use `from __future__ import annotations`, `gi.require_version("Gst", "1.0")`, then import `Gst, GLib`. The `_emit(prefix, **kv)` helper takes a prefix in {SPIKE_OK, SPIKE_FAIL, SPIKE_DIAG} and stringifies kwargs as `key=value!r` pairs space-separated with `flush=True`. The `main(argv)` body must validate argv length == 2 (script + url) FIRST before any GStreamer import side-effects so the smoke-test (`python3 hello_world.py`) emits SPIKE_FAIL reason='usage' even if PyGObject isn't installed on the host. Set bus signal-watch, attach `_on_message` that toggles state["playing_at"]/state["first_tag_at"]/state["errors"], then `pipeline.set_state(Gst.State.PLAYING)`, enter GLib.MainLoop with `_tick` timeout. Exit code conventions per RESEARCH.md (0/1/2/3). Per CONTEXT.md D-Discretion "no QObject bridge", DO NOT import PySide6 in this file at all — the bundled conda env has PySide6 because Phase 85 will need it; the spike's hello_world.py stays GStreamer+GLib only to keep the failure-surface narrow.</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/hello_world.py && python3 -c "import ast; ast.parse(open('.planning/spikes/85a-linux-packaging-spike/hello_world.py').read())" && grep -q 'Gst.parse_launch' .planning/spikes/85a-linux-packaging-spike/hello_world.py && grep -q 'GLib.MainLoop' .planning/spikes/85a-linux-packaging-spike/hello_world.py && ! grep -E 'QObject|QApplication|QTimer' .planning/spikes/85a-linux-packaging-spike/hello_world.py && python3 .planning/spikes/85a-linux-packaging-spike/hello_world.py 2>&1 | grep -q "SPIKE_FAIL.*usage"</automated>
  </verify>
  <done>File exists, parses, has playbin3 + GLib.MainLoop, no QObject bridge, and running with no argv emits the expected `SPIKE_FAIL reason='usage'` marker.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Author AppRun template (the spike's PRIMARY deliverable)</name>
  <files>.planning/spikes/85a-linux-packaging-spike/AppRun</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pattern 1 (lines 207-249) — full template
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 3 (lines 311-325) — GST_REGISTRY_FORK vs GST_REGISTRY_REUSE_PLUGIN_SCANNER distinction (the research-discovered surprise)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 4 (lines 327-337) — GIO_EXTRA_MODULES for HTTPS
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §D-06 (audible PASS relaunch step is what exercises GST_REGISTRY_FORK)
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/runtime_hook.py (Windows conceptual analog; Linux is shell not Python but the env-var structure mirrors)
  </read_first>
  <behavior>
    - First line is `#!/bin/bash` shebang
    - Resolves `HERE="$(dirname "$(readlink -f "${0}")")"` and exports `APPDIR="${HERE}"`
    - Exports the 4 success-criteria env vars EXACTLY: GST_PLUGIN_SYSTEM_PATH_1_0, GST_PLUGIN_PATH_1_0, GST_PLUGIN_SCANNER, GST_REGISTRY_FORK=no
    - Exports GIO_EXTRA_MODULES (Pitfall 4 / HTTPS) + GI_TYPELIB_PATH + PYTHONHOME + PATH prepend
    - Sets GST_PLUGIN_SCANNER_1_0 ALSO (defensively per Open Question 2; either form supersedes the other in 1.28+)
    - All GST_* paths point under `${APPDIR}/usr/conda/` (linuxdeploy-plugin-conda layout) NOT `${APPDIR}/usr/`
    - Comment block at the top citing: spike provenance, the GST_REGISTRY_FORK vs GST_REGISTRY_REUSE_PLUGIN_SCANNER distinction, Phase 85 hand-off note ("copy this file verbatim; replace the final exec line with `exec ${APPDIR}/usr/conda/bin/python -m musicstreamer "$@"`")
    - Final line: `exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"`
    - File mode is 0755 (executable bit set so linuxdeploy treats it as the AppImage entry point)
  </behavior>
  <acceptance_criteria>
    - file-exists: `test -x .planning/spikes/85a-linux-packaging-spike/AppRun` (executable bit set)
    - content-grep: `head -1 .planning/spikes/85a-linux-packaging-spike/AppRun | grep -q '^#!/bin/bash'`
    - content-grep: `grep -qE '^export GST_REGISTRY_FORK=("no"|no)' .planning/spikes/85a-linux-packaging-spike/AppRun`
    - content-grep: `grep -qE '^export GST_PLUGIN_SYSTEM_PATH_1_0=' .planning/spikes/85a-linux-packaging-spike/AppRun`
    - content-grep: `grep -qE '^export GST_PLUGIN_PATH_1_0=' .planning/spikes/85a-linux-packaging-spike/AppRun`
    - content-grep: `grep -qE '^export GST_PLUGIN_SCANNER=' .planning/spikes/85a-linux-packaging-spike/AppRun`
    - content-grep: `grep -qE '^export GIO_EXTRA_MODULES=' .planning/spikes/85a-linux-packaging-spike/AppRun`
    - content-grep: `grep -qE '^export GI_TYPELIB_PATH=' .planning/spikes/85a-linux-packaging-spike/AppRun`
    - content-grep: `grep -qE 'APPDIR.*usr/conda/lib/gstreamer-1.0' .planning/spikes/85a-linux-packaging-spike/AppRun` (paths under usr/conda/ NOT usr/)
    - content-grep (rationale presence): `grep -E '^#' .planning/spikes/85a-linux-packaging-spike/AppRun | grep -q 'GST_REGISTRY_REUSE_PLUGIN_SCANNER'` (the Pitfall 3 distinction is documented in comments)
    - shell-exit (syntax): `bash -n .planning/spikes/85a-linux-packaging-spike/AppRun` exits 0
    - shell-exit (no scanner-prefix accident): `! grep -E '^export GST_PLUGIN_SYSTEM_PATH_1_0=.*usr/lib/' .planning/spikes/85a-linux-packaging-spike/AppRun` (paths must NOT be under usr/lib/ — that's the plugin's wrong default per Pitfall 2)
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/AppRun` per RESEARCH.md §Pattern 1 (lines 218-247) verbatim. File begins with `#!/bin/bash` then a multi-line comment block citing: "Source: Phase 85a spike AppRun template; THE primary deliverable of this spike", "Phase 85 hand-off: replace final exec line with `exec ${APPDIR}/usr/conda/bin/python -m musicstreamer "$@"`", "CRITICAL: GST_REGISTRY_FORK=no (NOT GST_REGISTRY_REUSE_PLUGIN_SCANNER=no — see Pitfall 3 / RESEARCH.md lines 311-325)", "GIO_EXTRA_MODULES required for HTTPS per Pitfall 4 / Phase 43 windows-gstreamer-bundling.md cross-reference". Then HERE/APPDIR resolution, then the 8 exports as listed in the <behavior> block (use double-quoted `"no"` for clarity on GST_REGISTRY_FORK so grep finds it either way), then `exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"`. After writing, `chmod +x` the file.

Also append GST_PLUGIN_SCANNER_1_0 (with `_1_0` suffix) set to the same path as GST_PLUGIN_SCANNER, defensively per RESEARCH.md §Open Question 2 — both names cover 1.28+ and pre-1.28 GStreamer. The smoke_test in Task 3 logs which one GStreamer actually picked up.</action>
  <verify>
    <automated>test -x .planning/spikes/85a-linux-packaging-spike/AppRun && head -1 .planning/spikes/85a-linux-packaging-spike/AppRun | grep -q '^#!/bin/bash' && bash -n .planning/spikes/85a-linux-packaging-spike/AppRun && grep -qE '^export GST_REGISTRY_FORK=("no"|no)' .planning/spikes/85a-linux-packaging-spike/AppRun && grep -qE 'APPDIR.*usr/conda/lib/gstreamer-1.0' .planning/spikes/85a-linux-packaging-spike/AppRun && grep -E '^#' .planning/spikes/85a-linux-packaging-spike/AppRun | grep -q 'GST_REGISTRY_REUSE_PLUGIN_SCANNER' && ! grep -E '^export GST_PLUGIN_SYSTEM_PATH_1_0=.*usr/lib/' .planning/spikes/85a-linux-packaging-spike/AppRun</automated>
  </verify>
  <done>AppRun exists, executable, bash-syntax-valid, all 8 exports present pointing under usr/conda/, Pitfall 3 distinction is documented in comments, no accidental usr/lib/ multiarch leakage.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Author smoke_test.py validation harness + test_url.txt</name>
  <files>.planning/spikes/85a-linux-packaging-spike/smoke_test.py, .planning/spikes/85a-linux-packaging-spike/test_url.txt</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Minimal hello_world.py (lines 407-507) — shape baseline (smoke_test.py extends this with validation steps)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Validation Architecture / Validation Dimensions (lines 656-666) — D1-D8 list of what smoke_test must assert
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 2 (gst-inspect avdec_aac + aacparse) + §Pitfall 4 (TLS backend assertion) + §Pitfall 9 (TAG event timestamps) + §Pitfall 10 (sink election logging)
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §D-07/D-08/D-09 (SomaFM URLs + HTTP/HTTPS coverage + fallback chain)
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/smoke_test.py (cross-platform reference)
  </read_first>
  <behavior>
    - argv: `smoke_test.py --uri <URL> [--timeout 30] [--assert-tls] [--check-glibc <path>] [--check-plugins avdec_aac,aacparse]`
    - Reads test_url.txt if --uri is missing (fallback chain: HTTP_PRIMARY -> HTTPS_PRIMARY -> FALLBACK_2 -> FALLBACK_3 in that order; hard-fail if all unreachable)
    - GLIBC grep mode (--check-glibc <appimage_path>): runs `strings <path> | grep GLIBC_ | sort -V | tail -1`; exits 4 if result > GLIBC_2.35; emits SPIKE_DIAG glibc_max=GLIBC_X.YZ
    - Plugin inspection mode (--check-plugins): runs `gst-inspect-1.0 <name>` for each comma-separated name; exits 5 if any returns non-zero; emits SPIKE_DIAG plugin_resolved=name
    - TLS assertion (--assert-tls): inspects Gio.TlsBackend.get_default().get_default_database() is not None; logs which module .so was loaded
    - Playback mode (default): mirrors hello_world.py exactly + adds:
      - URL validation (scheme http/https; host *.somafm.com per §Security V5)
      - Audio sink election logging (Pitfall 10: logs whichever sink playbin3 selected — pulsesink/alsasink/autoaudiosink chain)
      - TAG message timestamp capture (Pitfall 9)
    - Exit codes: 0 OK, 1 setup, 2 runtime, 3 timeout, 4 GLIBC > 2.35, 5 plugin missing, 6 TLS backend absent (extends hello_world.py's 0/1/2/3 set)
    - Stdout markers: SPIKE_OK, SPIKE_FAIL, SPIKE_DIAG (stable greppable prefixes)
  </behavior>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/smoke_test.py`
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/test_url.txt`
    - shell-exit (syntax): `python3 -c "import ast; ast.parse(open('.planning/spikes/85a-linux-packaging-spike/smoke_test.py').read())"` exits 0
    - content-grep: `grep -q 'avdec_aac' .planning/spikes/85a-linux-packaging-spike/smoke_test.py`
    - content-grep: `grep -q 'aacparse' .planning/spikes/85a-linux-packaging-spike/smoke_test.py`
    - content-grep: `grep -q 'GLIBC_' .planning/spikes/85a-linux-packaging-spike/smoke_test.py`
    - content-grep: `grep -q 'gst-inspect-1.0' .planning/spikes/85a-linux-packaging-spike/smoke_test.py`
    - content-grep: `grep -q 'somafm\.com' .planning/spikes/85a-linux-packaging-spike/smoke_test.py` (host validation present per V5)
    - content-grep: `grep -qE '(Gio\.TlsBackend|GIO_EXTRA_MODULES)' .planning/spikes/85a-linux-packaging-spike/smoke_test.py`
    - shell-exit (test_url.txt has 4 entries): `grep -cE '^(http|https)://' .planning/spikes/85a-linux-packaging-spike/test_url.txt | grep -qE '^4$'`
    - content-grep (HTTP + HTTPS coverage per D-08): `grep -q '^http://ice1.somafm.com/groovesalad' .planning/spikes/85a-linux-packaging-spike/test_url.txt && grep -q '^https://ice6.somafm.com/groovesalad' .planning/spikes/85a-linux-packaging-spike/test_url.txt`
    - shell-exit (usage-handler runs without GStreamer): `python3 .planning/spikes/85a-linux-packaging-spike/smoke_test.py 2>&1 | grep -q 'SPIKE_FAIL\|usage\|--uri'` (argv parsing exits cleanly with usage when invoked bare)
  </acceptance_criteria>
  <action>(A) Create `.planning/spikes/85a-linux-packaging-spike/test_url.txt`:
```
# Phase 85a SomaFM test URLs (D-07/D-08/D-09)
# Fallback order: primary -> drone -> beat blender (hard-fail if all unreachable)
http://ice1.somafm.com/groovesalad-128-mp3
https://ice6.somafm.com/groovesalad-128-mp3
http://ice1.somafm.com/dronezone-128-mp3
http://ice1.somafm.com/beatblender-128-mp3
```

(B) Create `.planning/spikes/85a-linux-packaging-spike/smoke_test.py`:
- Header docstring citing Phase 43 smoke_test.py + RESEARCH.md §Validation Dimensions D1-D8 + the Pitfalls each assertion targets.
- Use `argparse` (stdlib only) for `--uri`, `--timeout` (default 30), `--assert-tls`, `--check-glibc <path>`, `--check-plugins <comma-list>` flags.
- URL validation: `from urllib.parse import urlparse`; assert scheme in {"http","https"} and netloc ends with `.somafm.com` per RESEARCH.md §Security V5.
- GLIBC mode: `subprocess.run(["strings", path], capture_output=True, text=True)`, filter lines matching `GLIBC_\d+\.\d+`, sort by version tuple, take max. Compare against (2,35); exit 4 if greater.
- Plugin mode: for each name, `subprocess.run(["gst-inspect-1.0", name], check=False, capture_output=True)`; exit 5 on any non-zero.
- TLS mode: `from gi.repository import Gio; b = Gio.TlsBackend.get_default(); has_db = b.get_default_database() is not None`; emit `SPIKE_DIAG tls_backend=type(b).__name__ has_default_database=has_db gio_modules=os.environ.get("GIO_EXTRA_MODULES","")`; exit 6 if not has_db.
- Playback mode: mirrors hello_world.py main() with three additions: (1) URL validation gate; (2) bus state-changed handler ALSO logs the elected audio-sink chain via pipeline.get_by_name("playbin") + property inspection where possible (or via parsing the bus STATE_CHANGED for the autoaudiosink elements); (3) TAG message timestamps captured per Pitfall 9.
- Argv-parsing block: when no args given (`len(sys.argv) == 1`) print usage line containing the word "usage" to stdout and exit 1 with `SPIKE_FAIL reason='usage'` so the shell-exit acceptance test passes without needing PyGObject.
- Top-level: `if __name__ == "__main__": sys.exit(main())`.

Defer the deep playback-mode implementation to copy-paste-and-extend from hello_world.py — they share 80% of structure.</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/smoke_test.py && test -f .planning/spikes/85a-linux-packaging-spike/test_url.txt && python3 -c "import ast; ast.parse(open('.planning/spikes/85a-linux-packaging-spike/smoke_test.py').read())" && grep -q 'avdec_aac' .planning/spikes/85a-linux-packaging-spike/smoke_test.py && grep -q 'aacparse' .planning/spikes/85a-linux-packaging-spike/smoke_test.py && grep -q 'GLIBC_' .planning/spikes/85a-linux-packaging-spike/smoke_test.py && grep -q 'somafm' .planning/spikes/85a-linux-packaging-spike/smoke_test.py && grep -cE '^(http|https)://' .planning/spikes/85a-linux-packaging-spike/test_url.txt | grep -qE '^4$' && python3 .planning/spikes/85a-linux-packaging-spike/smoke_test.py 2>&1 | grep -q 'SPIKE_FAIL\|usage\|--uri'</automated>
  </verify>
  <done>smoke_test.py parses + handles all 4 validation modes (--check-glibc, --check-plugins, --assert-tls, playback) + has the SomaFM host gate + exit-code conventions; test_url.txt has the 4 SomaFM URLs.</done>
</task>

</tasks>

<verification>
- All four files exist, are syntactically valid, and trip the negative tests where applicable
- AppRun template's Pitfall 3 distinction (GST_REGISTRY_FORK vs GST_REGISTRY_REUSE_PLUGIN_SCANNER) is documented in comments
- All GST_* paths point under usr/conda/ (NOT usr/) per linuxdeploy-plugin-conda layout finding
- SomaFM-only fallback chain per D-09 (Groove Salad -> Drone Zone -> Beat Blender; no QNAP)
</verification>

<success_criteria>
- hello_world.py: minimal playbin3 driver, no Qt bridge, exit codes 0/1/2/3
- AppRun: 8 env-var exports including GST_REGISTRY_FORK=no explicitly, paths under usr/conda/, executable bit set
- smoke_test.py: GLIBC + gst-inspect + TLS + playback + URL host gate modes
- test_url.txt: 4 SomaFM URLs (HTTP + HTTPS primary + 2 fallbacks)
- Plan 05 (build.sh) and Plan 06 (run-smoke.sh) have deterministic inputs to bundle and verify against
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-04-SUMMARY.md` when done. Capture: AppRun final env-var list with file:line citations to RESEARCH.md for each; smoke_test.py exit-code table; any deviations from RESEARCH.md §Pattern 1.
</output>

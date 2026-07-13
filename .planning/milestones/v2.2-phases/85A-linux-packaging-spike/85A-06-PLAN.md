---
phase: 85A-linux-packaging-spike
plan: 06
type: execute
wave: 4
depends_on:
  - 85A-01
  - 85A-05
files_modified:
  - tools/linux-spike/create-distroboxes.sh
  - tools/linux-spike/teardown-distroboxes.sh
  - tools/linux-spike/run-smoke.sh
autonomous: false
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - distrobox
  - programmatic-smoke

must_haves:
  truths:
    - "Three named distroboxes exist: ms-spike-ubuntu22 (Ubuntu 22.04), ms-spike-fedora40 (Fedora 40), ms-spike-tumbleweed (openSUSE Tumbleweed)"
    - "create-distroboxes.sh + teardown-distroboxes.sh form a reversible pair (D-04 ephemeral)"
    - "run-smoke.sh runs the full validation suite (GLIBC + gst-inspect avdec_aac/aacparse + playbin3 HTTP + playbin3 HTTPS) inside each distrobox and captures terminal transcripts via `script -q`"
    - "All three distros produce SPIKE_OK for both HTTP and HTTPS playback (D-08 coverage on at least one distro; primary on Ubuntu 22.04)"
    - "GLIBC grep reports GLIBC_2.35 or lower for the AppImage on every distro (it's the same binary; this is a per-distro probe sanity check)"
    - "Plugin discovery (avdec_aac + aacparse) resolves from inside the AppRun shell on every distro"
  artifacts:
    - path: "tools/linux-spike/create-distroboxes.sh"
      provides: "Idempotent creation of 3 named distroboxes (D-03)"
      contains: "ms-spike-ubuntu22"
    - path: "tools/linux-spike/teardown-distroboxes.sh"
      provides: "distrobox rm of all three (D-04 ephemeral)"
      contains: "distrobox rm"
    - path: "tools/linux-spike/run-smoke.sh"
      provides: "Drives smoke_test.py inside each distrobox; captures terminal transcript per distro"
      contains: "smoke_test.py"
    - path: ".planning/spikes/85a-linux-packaging-spike/artifacts/{distro}-transcript.log"
      provides: "Per-distro `script -q` transcript covering GLIBC + gst-inspect + HTTP + HTTPS smoke"
      contains: "SPIKE_OK"
  key_links:
    - from: "create-distroboxes.sh"
      to: "run-smoke.sh"
      via: "run-smoke.sh uses `distrobox enter <name>` for each name created by create-distroboxes.sh"
      pattern: "distrobox enter"
    - from: "run-smoke.sh"
      to: "Plan 07 audible PASS"
      via: "Plan 07's manual checkpoint depends on programmatic SPIKE_OK from this plan (no audible without programmatic green first)"
      pattern: "SPIKE_OK"
    - from: "Plan 05 AppImage"
      to: "run-smoke.sh"
      via: "run-smoke.sh invokes the AppImage produced by Plan 05"
      pattern: "MusicStreamer-spike-x86_64.AppImage"
---

<objective>
Author the three distrobox-driver scripts and execute the programmatic per-distro smoke (GLIBC + plugin-inspect + HTTP + HTTPS playback) for all three target distros. The result is `SPIKE_OK` markers in transcripts that Plan 08's findings doc embeds verbatim.

Purpose: Implements RESEARCH.md §System Architecture Diagram lines 165-178 + §distrobox create commands (lines 532-558) verbatim. Cross-distro empirical PASS (success criterion #1) starts here — Plan 07 layers audible verification on top.
Output: 3 scripts under `tools/linux-spike/` + 3 transcripts in `artifacts/` (Ubuntu, Fedora, Tumbleweed).
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md
@.planning/spikes/85a-linux-packaging-spike/smoke_test.py
@.planning/spikes/85a-linux-packaging-spike/test_url.txt

<interfaces>
<!-- The three distroboxes (RESEARCH.md lines 532-558 verbatim). -->

ms-spike-ubuntu22       docker.io/library/ubuntu:22.04
ms-spike-fedora40       quay.io/fedora/fedora:40
ms-spike-tumbleweed     registry.opensuse.org/opensuse/tumbleweed:latest

<!-- Distrobox flags lock (RESEARCH.md §Anti-Patterns line 266 + CONTEXT.md D-02): -->
- NO --init flag (host-process visibility from inside container is required)
- Default Wayland + PipeWire + DBus + $HOME sharing (per distrobox docs)

<!-- Per-distro smoke harness invocation -->
$ distrobox enter <distro> -- bash -c '
    set -x
    APPIMG=/path/to/MusicStreamer-spike-x86_64.AppImage
    # Mode 1: GLIBC
    "$APPIMG" --appimage-extract-and-run python smoke_test.py --check-glibc "$APPIMG"
    # Mode 2: plugin resolution
    "$APPIMG" --appimage-extract-and-run python smoke_test.py --check-plugins avdec_aac,aacparse
    # Mode 3: TLS backend (HTTPS prereq)
    "$APPIMG" --appimage-extract-and-run python smoke_test.py --assert-tls
    # Mode 4: HTTP playback
    "$APPIMG" --appimage-extract-and-run python smoke_test.py --uri http://ice1.somafm.com/groovesalad-128-mp3 --timeout 35
    # Mode 5: HTTPS playback (D-08)
    "$APPIMG" --appimage-extract-and-run python smoke_test.py --uri https://ice6.somafm.com/groovesalad-128-mp3 --timeout 35
'
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| host -> distrobox container | distrobox shares Wayland + PipeWire + DBus + $HOME with the container by default; acceptable for spike (CONTEXT.md D-02 single-host caveat); production isolation is Flatpak's surface (Phase 86) |
| upstream container registry (docker.io / quay.io / opensuse.org) -> host | Pulling base images crosses this boundary; standard container-registry trust chain |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-06-EoP | EoP | distrobox --init (systemd-in-container) | mitigate | RESEARCH.md §Anti-Patterns line 266 + CONTEXT.md D-02; create-distroboxes.sh MUST NOT pass --init |
| T-85A-06-SC | Tampering | upstream container image drift | accept | Pull `:latest` for Tumbleweed (rolling); pin `:22.04` and `:40` tags for Ubuntu/Fedora (LTS); Plan 08 findings captures the image digests at creation time |
</threat_model>

<tasks>

<task type="auto">
  <name>Task 1: Author create-distroboxes.sh + teardown-distroboxes.sh</name>
  <files>tools/linux-spike/create-distroboxes.sh, tools/linux-spike/teardown-distroboxes.sh</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §distrobox create commands (lines 532-558) verbatim
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Anti-Patterns line 266 — NO --init flag
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §D-03 + §D-04 — three named, ephemeral
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -x tools/linux-spike/create-distroboxes.sh`
    - file-exists: `test -x tools/linux-spike/teardown-distroboxes.sh`
    - content-grep: `grep -c 'distrobox create' tools/linux-spike/create-distroboxes.sh | grep -qE '^3$'` (three creates)
    - content-grep: `grep -q 'ms-spike-ubuntu22' tools/linux-spike/create-distroboxes.sh`
    - content-grep: `grep -q 'ms-spike-fedora40' tools/linux-spike/create-distroboxes.sh`
    - content-grep: `grep -q 'ms-spike-tumbleweed' tools/linux-spike/create-distroboxes.sh`
    - content-grep (no --init flag): `! grep -E '\-\-init( |$)' tools/linux-spike/create-distroboxes.sh`
    - content-grep: `grep -c 'distrobox rm' tools/linux-spike/teardown-distroboxes.sh | grep -qE '^[1-9]'`
    - shell-exit (syntax): `bash -n tools/linux-spike/create-distroboxes.sh && bash -n tools/linux-spike/teardown-distroboxes.sh`
    - shell-exit (distrobox sees the three): after running, `distrobox list | grep -c 'ms-spike-' | grep -qE '^3$'`
  </acceptance_criteria>
  <action>(A) Create `tools/linux-spike/create-distroboxes.sh` per RESEARCH.md lines 535-558 verbatim, plus idempotency wrapper. Required shape:

```
#!/usr/bin/env bash
# Phase 85a — create three named distroboxes per CONTEXT.md D-03.
# Per RESEARCH.md §Anti-Patterns: NO --init flag (would hide host-process visibility).
# Containers are ephemeral per D-04; tools/linux-spike/teardown-distroboxes.sh removes them.
set -euo pipefail

declare -A BOXES=(
  [ms-spike-ubuntu22]="docker.io/library/ubuntu:22.04"
  [ms-spike-fedora40]="quay.io/fedora/fedora:40"
  [ms-spike-tumbleweed]="registry.opensuse.org/opensuse/tumbleweed:latest"
)

for name in "${!BOXES[@]}"; do
  image="${BOXES[$name]}"
  if distrobox list 2>/dev/null | grep -qE "(^|\s)$name(\s|$)"; then
    echo "EXISTS $name (skipping create)"
  else
    distrobox create --image "$image" --name "$name" --yes
    echo "CREATED $name image=$image"
  fi
done

distrobox list
echo "ALL_DISTROBOXES_READY"
```

(B) Create `tools/linux-spike/teardown-distroboxes.sh`:
```
#!/usr/bin/env bash
# Phase 85a — tear down all three distroboxes per CONTEXT.md D-04 (ephemeral).
set -euo pipefail

for name in ms-spike-ubuntu22 ms-spike-fedora40 ms-spike-tumbleweed; do
  if distrobox list 2>/dev/null | grep -qE "(^|\s)$name(\s|$)"; then
    distrobox rm --force "$name"
    echo "REMOVED $name"
  else
    echo "ABSENT $name (skipping)"
  fi
done
echo "TEARDOWN_COMPLETE"
```

Both scripts chmod +x. RUN create-distroboxes.sh after writing both files. Capture `distrobox list` output for the SUMMARY.md.</action>
  <verify>
    <automated>test -x tools/linux-spike/create-distroboxes.sh && test -x tools/linux-spike/teardown-distroboxes.sh && bash -n tools/linux-spike/create-distroboxes.sh && bash -n tools/linux-spike/teardown-distroboxes.sh && grep -c 'distrobox create' tools/linux-spike/create-distroboxes.sh | grep -qE '^3$' && ! grep -E '\-\-init( |$)' tools/linux-spike/create-distroboxes.sh && bash tools/linux-spike/create-distroboxes.sh && distrobox list | grep -c 'ms-spike-' | grep -qE '^3$'</automated>
  </verify>
  <done>Both scripts present + executable + syntax-valid + no --init flag; running create-distroboxes.sh leaves all three containers in `distrobox list`.</done>
</task>

<task type="auto">
  <name>Task 2: Author run-smoke.sh + capture per-distro transcripts</name>
  <files>tools/linux-spike/run-smoke.sh, .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log, .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log, .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §System Architecture Diagram lines 165-178 (per-distro flow)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Validation Architecture / Validation Dimensions D1+D2+D3 (lines 656-664)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 10 (sink election logging per-distro)
    - .planning/spikes/85a-linux-packaging-spike/smoke_test.py (the harness invoked inside each distrobox)
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §D-05 (per-distro transcript evidence is required for findings)
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -x tools/linux-spike/run-smoke.sh`
    - shell-exit (syntax): `bash -n tools/linux-spike/run-smoke.sh`
    - content-grep: `grep -q 'distrobox enter' tools/linux-spike/run-smoke.sh`
    - content-grep: `grep -q 'script -q' tools/linux-spike/run-smoke.sh` (transcript capture)
    - content-grep: `grep -q 'smoke_test.py' tools/linux-spike/run-smoke.sh`
    - content-grep: `grep -q 'avdec_aac' tools/linux-spike/run-smoke.sh`
    - content-grep: `grep -q 'http://ice1.somafm.com/groovesalad' tools/linux-spike/run-smoke.sh`
    - content-grep: `grep -q 'https://ice6.somafm.com/groovesalad' tools/linux-spike/run-smoke.sh`
    - content-grep (double-quoted host-side APPIMG passthrough — Issue #3 fix): `grep -qE 'env APPIMG="\$APPIMG"' tools/linux-spike/run-smoke.sh`
    - content-grep (no broken single-quoted variant): `! grep -qE "env APPIMG='\\\$APPIMG'" tools/linux-spike/run-smoke.sh`
    - file-exists (3 transcripts): `test -f .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log && test -f .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log && test -f .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log`
    - content-grep (SPIKE_OK present per distro): `for d in ubuntu22 fedora40 tumbleweed; do grep -v '^#' .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log | grep -q SPIKE_OK || { echo "NO SPIKE_OK $d"; exit 1; }; done`
    - content-grep (GLIBC <= 2.35 per distro): `for d in ubuntu22 fedora40 tumbleweed; do grep -E 'GLIBC_[0-9]+\.[0-9]+' .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log | sort -V | tail -1 | grep -qE 'GLIBC_2\.(1[0-9]|2[0-9]|3[0-5])$' || { echo "GLIBC drift $d"; exit 1; }; done`
    - content-grep (avdec_aac + aacparse resolved per distro — literal `plugin_resolved=` marker substring contract with Plan 04 Task 3): `for d in ubuntu22 fedora40 tumbleweed; do grep -qE 'plugin_resolved=.avdec_aac' .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log && grep -qE 'plugin_resolved=.aacparse' .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log || { echo "plugin miss $d"; exit 1; }; done`
  </acceptance_criteria>
  <action>(A) Create `tools/linux-spike/run-smoke.sh`. Single approach (no alternative paths): smoke_test.py is referenced via its absolute host path on `$SPIKE_DIR` — distrobox $HOME sharing makes the path resolve identically inside the container. APPIMG is passed via `env` with **double quotes** so the host shell expands the variable before `distrobox enter` runs (Issue #3 fix). The inner heredoc that emits the in-container script body uses **unquoted `<<INNER`** so host-side variables `$APPIMG` and `$SPIKE_DIR` are interpolated at heredoc-emit time; markers we want to appear literally in the in-container script are NOT used (the in-container body just references `$APPIMG` from its `env`-injected environment, with no further escaping needed since the variable name is the same inside and outside).

```
#!/usr/bin/env bash
# Phase 85a — drive smoke_test.py inside each named distrobox; capture transcripts.
# Usage: bash tools/linux-spike/run-smoke.sh [ubuntu22|fedora40|tumbleweed|all]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPIKE_DIR="$(cd "${HERE}/../../.planning/spikes/85a-linux-packaging-spike" && pwd)"
APPIMG="${SPIKE_DIR}/artifacts/MusicStreamer-spike-x86_64.AppImage"
SMOKE_PY="${SPIKE_DIR}/smoke_test.py"
[[ -x "$APPIMG" ]] || { echo "MISSING_APPIMAGE $APPIMG (run Plan 05 build.sh first)" >&2; exit 1; }
[[ -f "$SMOKE_PY" ]] || { echo "MISSING_SMOKE $SMOKE_PY (run Plan 04 first)" >&2; exit 1; }

TARGET="${1:-all}"
case "$TARGET" in
  ubuntu22)    DISTROS=(ms-spike-ubuntu22) ;;
  fedora40)    DISTROS=(ms-spike-fedora40) ;;
  tumbleweed)  DISTROS=(ms-spike-tumbleweed) ;;
  all)         DISTROS=(ms-spike-ubuntu22 ms-spike-fedora40 ms-spike-tumbleweed) ;;
  *)           echo "USAGE: $0 [ubuntu22|fedora40|tumbleweed|all]" >&2; exit 1 ;;
esac

# Build the in-container script body. Host-side variables ($APPIMG, $SMOKE_PY) are
# interpolated at emit time via the UNQUOTED heredoc tag `<<INNER`. The in-container
# script reads $APPIMG from the env passed via `env APPIMG="$APPIMG"` below.
run_modes_in_box() {
  cat <<INNER
set -x
echo "DISTRO_PROBE start=\$(date -u +%s)"
echo "CONTAINER_OS_RELEASE_BEGIN"
cat /etc/os-release || true
echo "CONTAINER_OS_RELEASE_END"

# APPIMG comes from the env passthrough below; SMOKE_PY is the absolute host path
# (distrobox shares \$HOME so the same path resolves inside the container).
SMOKE_PY="${SMOKE_PY}"

# Mode 1: GLIBC (run from inside container; sees container's libc + AppImage's referenced symbols)
"\$APPIMG" --appimage-extract-and-run python "\$SMOKE_PY" --check-glibc "\$APPIMG" || echo "SPIKE_FAIL mode=glibc"
# Mode 2: plugin resolution
"\$APPIMG" --appimage-extract-and-run python "\$SMOKE_PY" --check-plugins avdec_aac,aacparse
# Mode 3: TLS backend
"\$APPIMG" --appimage-extract-and-run python "\$SMOKE_PY" --assert-tls
# Mode 4: HTTP playback (primary stream, D-07)
"\$APPIMG" --appimage-extract-and-run python "\$SMOKE_PY" --uri http://ice1.somafm.com/groovesalad-128-mp3 --timeout 35
# Mode 5: HTTPS playback (D-08)
"\$APPIMG" --appimage-extract-and-run python "\$SMOKE_PY" --uri https://ice6.somafm.com/groovesalad-128-mp3 --timeout 35
echo "DISTRO_PROBE end=\$(date -u +%s)"
INNER
}

for box in "${DISTROS[@]}"; do
  short="${box#ms-spike-}"
  log="${SPIKE_DIR}/artifacts/${short}-transcript.log"
  echo "RUN_SMOKE box=$box log=$log"
  # NOTE: env APPIMG="$APPIMG" uses DOUBLE quotes so the host shell interpolates $APPIMG
  # before `distrobox enter` is invoked. (Single quotes would pass the literal string `$APPIMG`.)
  script -q -c "distrobox enter $box --no-tty -- env APPIMG=\"$APPIMG\" bash -c \"$(run_modes_in_box)\"" "$log"
done

echo "ALL_DISTROS_SMOKED"
```

Key invariants (Issue #3 + Issue #4 fixes):
- The `env APPIMG="$APPIMG"` form on the `distrobox enter` line uses double quotes so the host shell expands `$APPIMG` to its actual path BEFORE the subprocess is launched. (The previous single-quoted form passed the literal string `$APPIMG` to env, which would have broken plugin resolution inside the container.)
- The `run_modes_in_box` heredoc uses unquoted `<<INNER` so `${SMOKE_PY}` interpolates at emit time, while `\$APPIMG` and `\$SMOKE_PY` are escaped so they remain literal `$APPIMG` / `$SMOKE_PY` in the emitted script (the container shell expands them from the env passthrough).
- smoke_test.py is referenced at its absolute host path (`$SPIKE_DIR/smoke_test.py`) — single approach. The previous "alternatively run from `/work/`" paragraph has been DELETED; there is one path here.

(B) Run `bash tools/linux-spike/run-smoke.sh all`. This populates the three transcript files. Verify SPIKE_OK appears in each, GLIBC <= 2.35 grep matches in each, `plugin_resolved=avdec_aac` + `plugin_resolved=aacparse` marker substrings present in each (the literal `plugin_resolved=` prefix is locked at author-time in Plan 04 Task 3 — see Issue #4 fix in that plan).

If any distro fails programmatically: STOP and report (per CONTEXT.md D-09 negative-pivot policy). Do not try to "fix" by silently relaxing assertions.</action>
  <verify>
    <automated>test -x tools/linux-spike/run-smoke.sh && bash -n tools/linux-spike/run-smoke.sh && grep -q 'distrobox enter' tools/linux-spike/run-smoke.sh && grep -q 'script -q' tools/linux-spike/run-smoke.sh && grep -qE 'env APPIMG="\$APPIMG"' tools/linux-spike/run-smoke.sh && bash tools/linux-spike/run-smoke.sh all && for d in ubuntu22 fedora40 tumbleweed; do test -f .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log && grep -q SPIKE_OK .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log && grep -E 'GLIBC_[0-9]+\.[0-9]+' .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log | sort -V | tail -1 | grep -qE 'GLIBC_2\.(1[0-9]|2[0-9]|3[0-5])$' && grep -qE 'plugin_resolved=.avdec_aac' .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log && grep -qE 'plugin_resolved=.aacparse' .planning/spikes/85a-linux-packaging-spike/artifacts/${d}-transcript.log; done</automated>
  </verify>
  <done>run-smoke.sh exists + executable + syntax-valid; APPIMG passthrough uses double-quoted host-shell interpolation; running `run-smoke.sh all` produces three transcripts; each has SPIKE_OK + GLIBC <= 2.35 + both `plugin_resolved=` markers.</done>
</task>

</tasks>

<verification>
- 3 scripts under `tools/linux-spike/` committed
- 3 transcripts under `.planning/spikes/85a-linux-packaging-spike/artifacts/` (gitignored but produced)
- All three transcripts contain: `SPIKE_OK` (playback PASS), `GLIBC_2.x` line with x <= 35, `plugin_resolved=avdec_aac`, `plugin_resolved=aacparse`
- HTTPS variant succeeds on at least Ubuntu 22.04 distrobox (D-08 programmatic coverage; D-08 audible coverage lives in Plan 07 Task 1 step 8)
</verification>

<success_criteria>
- Cross-distro programmatic PASS achieved (success criterion #1 partial — Plan 07 layers audible verification)
- Pitfall 2 mitigation empirically verified (avdec_aac + aacparse both resolve on all three distros)
- Pitfall 4 mitigation empirically verified (HTTPS playback works → TLS backend discovered)
- Plan 07's audible PASS protocol has greenlit programmatic baseline
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-06-SUMMARY.md` when done. Capture: per-distro GLIBC max observed, per-distro elected audio sink (Pitfall 10 logging), HTTPS TLS backend module filename observed, any distro-specific notes (e.g., Tumbleweed kernel surprises).
</output>
</content>
</invoke>
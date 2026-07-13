---
phase: 85A-linux-packaging-spike
plan: 07
type: execute
wave: 5
depends_on:
  - 85A-06
files_modified:
  - .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png
  - .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-screenshot.png
  - .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-screenshot.png
  - .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md
autonomous: false
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - audible-pass
  - manual-verification
  - relaunch-protocol

must_haves:
  truths:
    - "Kyle confirms audible playback per D-06 protocol (30s play + pause + resume + stop + relaunch) on EACH of the three distros"
    - "Second-launch verification per D-06 step 7 catches the GST_REGISTRY_FORK=no regression case"
    - "Wayland screenshot of running AppImage captured per distro via gnome-screenshot --window (or grim fallback)"
    - "Audible-PASS log records: which SomaFM channel won, pause/resume worked, stop worked, relaunch worked + time-to-PLAYING on relaunch"
    - "Ubuntu 22.04 run additionally exercises HTTPS audible playback (D-08 coverage)"
  artifacts:
    - path: ".planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png"
      provides: "Wayland screenshot evidence — Ubuntu 22.04 distrobox running AppImage"
      contains: "(PNG binary)"
    - path: ".planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-screenshot.png"
      provides: "Wayland screenshot evidence — Fedora 40 distrobox running AppImage"
      contains: "(PNG binary)"
    - path: ".planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-screenshot.png"
      provides: "Wayland screenshot evidence — openSUSE Tumbleweed distrobox running AppImage"
      contains: "(PNG binary)"
    - path: ".planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md"
      provides: "Kyle's manual confirmation log per distro per D-06 step"
      contains: "audible_30s: PASS"
  key_links:
    - from: "Plan 06 SPIKE_OK transcripts"
      to: "Plan 07 audible PASS"
      via: "Audible PASS only runs after programmatic green; failure here distinguishes 'wrong audio sink' (Pitfall 10) from 'no audio at all' (would have failed Plan 06 too)"
      pattern: "SPIKE_OK"
    - from: "AppRun GST_REGISTRY_FORK=no"
      to: "D-06 step 7 relaunch"
      via: "Relaunch is the only step that exercises GST_REGISTRY_FORK; if relaunch is 5s+ slower than first launch, Pitfall 3 is regressing"
      pattern: "relaunch_time_to_play_s"
    - from: "AppRun GIO_EXTRA_MODULES"
      to: "Plan 07 Task 1 step 8 HTTPS audible"
      via: "Ubuntu 22.04 Task 1 step 8 is the load-bearing D-08 verification — HTTPS-on-real-pipewire confirmed by Kyle's ears; Fedora/Tumbleweed audible runs use HTTP only"
      pattern: "https_audible: PASS"
---

<objective>
Execute the D-06 audible-PASS protocol on all three distros (30s play + pause/resume + stop + relaunch) with Kyle's manual confirmation. Capture per-distro Wayland screenshot evidence. The relaunch step is the only verification that empirically validates `GST_REGISTRY_FORK=no` (Pitfall 3 mitigation, success criterion #4 verification). Ubuntu 22.04 Task 1 additionally exercises HTTPS audible playback per D-08 (the spike's "at least one distro" HTTPS-on-real-pipewire requirement).

Purpose: Implements CONTEXT.md §D-05 + §D-06 + §D-08 verbatim — audible + screenshot + transcript trio is the full evidence bundle Plan 08 embeds into the findings doc. This plan adds the audible + screenshot layers on top of Plan 06's programmatic transcripts. Per CONTEXT.md D-08 + VALIDATION.md row 94, HTTPS audible coverage is assigned to Plan 07 Task 1 (Ubuntu primary).
Output: 3 PNG screenshots + 1 audible-pass log + Kyle's "audible OK" confirmation per distro + Ubuntu's `https_audible: PASS` line.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md
@.planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log
@.planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log
@.planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log

<interfaces>
<!-- D-06 audible PASS protocol per distro (CONTEXT.md lines 49-57) -->

1. Launch AppImage, confirm pipeline reaches PLAYING.
2. Hear ~10s of clean audio.
3. Hit pause; verify silence + state==PAUSED.   (NB: hello_world.py has no UI pause button;
                                                  use Ctrl+Z (SIGTSTP) or play a SECOND
                                                  invocation with pause behavior — Plan
                                                  07's audible-pass-log.md template
                                                  documents what Kyle actually does)
4. Hit play; verify audio resumes + state==PLAYING.
5. Hit stop.
6. Close the AppImage process entirely.
7. **Relaunch** the AppImage and confirm second launch also reaches PLAYING.

<!-- Ubuntu 22.04 ONLY (per D-08, VALIDATION row 94): -->
8. Additional HTTPS audible: relaunch the AppImage with
   `https://ice6.somafm.com/groovesalad-128-mp3` and confirm 10s audible
   playback on host pipewire. Log `https_audible: PASS` + the URL.

<!-- Screenshot tool (CONTEXT.md D-Discretion + RESEARCH.md Assumption A6) -->
gnome-screenshot --window --file <distro>-screenshot.png   # GNOME Wayland primary
grim -g "$(slurp)" <distro>-screenshot.png                  # wlroots fallback
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Wayland host -> distrobox container audio share | distrobox passes PipeWire socket via XDG_RUNTIME_DIR by default; audio plays through host's PipeWire (acceptable per D-02) |
| HTTPS stream -> host TLS backend (Ubuntu Task 1 step 8) | D-08 audible HTTPS verification crosses this boundary; backend module is whatever conda-forge glib-networking ships (Open Question 3 — resolved at execution time) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-07-DI | Information disclosure | Screenshot may capture other host windows visible in foreground | accept | Kyle runs `gnome-screenshot --window` which captures only the active window (the AppImage); spike screenshots committed under artifacts/ (gitignored anyway) |
| T-85A-07-TLS | Tampering | HTTPS stream interception during D-08 audible verification | accept | TLS validation handled by conda-forge glib-networking backend (Pitfall 4 mitigation already verified in Plan 06 Mode 5); audible verification adds nothing to the threat surface beyond the programmatic check |
</threat_model>

<tasks>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 1: Audible PASS protocol — Ubuntu 22.04 distrobox (8-step incl. HTTPS audible per D-08)</name>
  <files>.planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png, .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §D-06 (audible PASS protocol 7-step sequence) + §D-08 (HTTPS coverage assigned to Plan 07 Task 1 Ubuntu primary)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 3 (lines 311-325) — what relaunch step is verifying
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 4 (lines 327-337) — HTTPS TLS backend; the D-08 step 8 is the audible-on-PipeWire counterpart to Plan 06 Mode 5's programmatic assertion
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 10 (lines 393-403) — sink election failure mode is per-distro
    - .planning/phases/85A-linux-packaging-spike/85A-VALIDATION.md row 94 — HTTPS audible explicitly assigned here
    - .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log (Plan 06 programmatic baseline — confirm SPIKE_OK present before starting audible)
  </read_first>
  <what-built>Plan 06 validated programmatic playback on Ubuntu 22.04 distrobox. Now Kyle exercises the D-06 7-step audible-PASS protocol with the AppImage on host pipewire, then adds step 8 — the D-08 HTTPS audible verification. The relaunch step (#7) is the only step that empirically validates `GST_REGISTRY_FORK=no` — second launch time-to-PLAYING must be comparable to first launch (Pitfall 3 mitigation verified). Step 8 is the spike's only HTTPS-on-real-pipewire ear-confirmation (D-08 coverage).</what-built>
  <how-to-verify>
    1. Open a terminal. Confirm programmatic baseline is green:
       ```
       grep SPIKE_OK .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log
       ```
       If this prints nothing, STOP — Plan 06 did not actually pass on this distro.

    2. Enter the Ubuntu 22.04 distrobox and launch the AppImage interactively:
       ```
       distrobox enter ms-spike-ubuntu22
       cd /path/to/spike/dir
       time ./artifacts/MusicStreamer-spike-x86_64.AppImage http://ice1.somafm.com/groovesalad-128-mp3
       ```
       Record the time-to-first-audio (eyeball it OR check `SPIKE_DIAG event='reached_playing'` line in stdout).

    3. Hear ~10s of clean audio on host pipewire. Note which SomaFM channel actually won (Groove Salad expected; fallback chain only kicks in if upstream is down).

    4. While the AppImage is running and audible, in ANOTHER host terminal:
       ```
       gnome-screenshot --window --file .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png
       ```
       If gnome-screenshot can't see the distrobox-side window (Assumption A6), fall back to:
       ```
       grim -g "$(slurp)" .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png
       ```
       Record which tool worked in audible-pass-log.md.

    5. Pause/resume/stop. Since hello_world.py has no UI controls, the SPIKE-LEVEL PAUSE/RESUME approximation is: send SIGSTOP / SIGCONT to the process (`kill -STOP <pid>` then `kill -CONT <pid>`). Verify silence under STOP, audio under CONT. (Phase 85 will exercise real pause UI; spike validates the GStreamer pipeline behavior here.)

    6. Send SIGTERM/Ctrl-C to fully close.

    7. **Relaunch** (step 7 — the load-bearing one):
       ```
       time ./artifacts/MusicStreamer-spike-x86_64.AppImage http://ice1.somafm.com/groovesalad-128-mp3
       ```
       Record second-launch time-to-PLAYING. If it's > 5s slower than first launch, GST_REGISTRY_FORK=no isn't working (Pitfall 3 regression) → STOP and report per D-09 negative-pivot.

    8. **HTTPS audible** (step 8 — D-08 coverage, Ubuntu-only):
       Close the AppImage from step 7. Relaunch with the HTTPS variant:
       ```
       time ./artifacts/MusicStreamer-spike-x86_64.AppImage https://ice6.somafm.com/groovesalad-128-mp3
       ```
       Confirm at least 10 seconds of clean audible playback on host pipewire (ear check). This is the spike's only HTTPS-on-real-pipewire verification — Plan 06 Mode 5 covers the programmatic side, but only this step proves the TLS-backed stream actually reaches Kyle's speakers. Log to `audible-pass-log.md` under the Ubuntu 22.04 section:
       ```
       - step 8: https_audible: PASS    url=https://ice6.somafm.com/groovesalad-128-mp3 time_to_play_s=<N>
       ```
       (Use `https_audible: FAIL` + failure mode notes if it doesn't work — per D-09 this is a STOP-and-report condition, not a "retry with HTTP" pivot.)

    9. Append the completed Ubuntu 22.04 section to `audible-pass-log.md` following the template Claude writes in <action>.
  </how-to-verify>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png`
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md`
    - content-grep (PNG signature): `head -c 8 .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png | od -An -c | grep -q 'P   N   G'` (PNG magic bytes)
    - content-grep (audible log Ubuntu section): `grep -q '^## Ubuntu 22.04' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md`
    - content-grep (all 8 D-06+D-08 steps logged on Ubuntu): `for n in 1 2 3 4 5 6 7 8; do awk '/^## Ubuntu 22.04/,/^## /' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md | grep -q "step ${n}:" || { echo "missing step ${n} in Ubuntu section"; exit 1; }; done`
    - content-grep (HTTPS audible recorded per D-08): `grep -q 'https_audible: PASS' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md`
    - content-grep (HTTPS URL logged): `grep -qE 'url=https://ice6\.somafm\.com/groovesalad' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md`
    - content-grep: `grep -qE 'relaunch_time_to_play_s:\s*[0-9.]+' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md`
    - manual-checkpoint: Kyle confirms "audible OK on ubuntu22; pause/resume worked; stop worked; relaunch reached PLAYING in N seconds; HTTPS audible OK" (relaunch N + HTTPS time captured in log).
  </acceptance_criteria>
  <action>Claude pre-creates `.planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md` (if absent) with this template:

```
# Phase 85a Audible PASS log

> D-06 protocol per CONTEXT.md: 30s play + pause/resume + stop + relaunch.
> Relaunch step verifies `GST_REGISTRY_FORK=no` (Pitfall 3 mitigation).
> D-08 HTTPS audible verification: Ubuntu 22.04 ONLY (step 8 below).

## Ubuntu 22.04 (ms-spike-ubuntu22)

- date: <YYYY-MM-DD>
- channel_won: <Groove Salad | Drone Zone | Beat Blender>
- screenshot_tool: <gnome-screenshot | grim>
- step 1: launch + reached PLAYING (time_to_play_s: <N>)
- step 2: 10s clean audio: <PASS | FAIL: notes>
- step 3: pause (SIGSTOP) -> silence + state==PAUSED: <PASS | FAIL>
- step 4: resume (SIGCONT) -> audio + state==PLAYING: <PASS | FAIL>
- step 5: stop: <PASS | FAIL>
- step 6: close: <PASS | FAIL>
- step 7: relaunch_time_to_play_s: <N>   (must be <= step 1 +5s, else Pitfall 3 regression)
- step 8: https_audible: <PASS | FAIL: notes>   url=https://ice6.somafm.com/groovesalad-128-mp3 time_to_play_s=<N>
- elected_sink: <pulsesink | alsasink | autoaudiosink-pulsesink | ...>   (per Pitfall 10)
- notes: <any anomalies>

## Fedora 40 (ms-spike-fedora40)

  (... same template but only steps 1-7; D-08 HTTPS coverage is Ubuntu-only ...)

## openSUSE Tumbleweed (ms-spike-tumbleweed)

  (... same template but only steps 1-7; D-08 HTTPS coverage is Ubuntu-only ...)
```

Then PAUSE. Kyle drives the protocol on Ubuntu 22.04 distrobox, fills in the Ubuntu 22.04 section (all 8 steps including HTTPS audible step 8), captures the screenshot, and confirms PASS in chat.</action>
  <resume-signal>Kyle types "ubuntu22 audible OK" (with the relaunch time AND `https_audible: PASS` in the log) or describes the failure mode.</resume-signal>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png && file .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-screenshot.png | grep -qi PNG && grep -q '^## Ubuntu 22.04' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md && grep -qE 'relaunch_time_to_play_s:\s*[0-9.]+' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md && grep -q 'https_audible: PASS' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md</automated>
    <human-check>Kyle confirms "ubuntu22 audible OK" + HTTPS audible PASS.</human-check>
  </verify>
  <done>Ubuntu 22.04 screenshot is a valid PNG + audible-pass-log.md has Ubuntu section filled with all 8 steps (incl. HTTPS audible per D-08) + relaunch time recorded; Kyle confirmed.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 2: Audible PASS protocol — Fedora 40 distrobox</name>
  <files>.planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-screenshot.png, .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md</files>
  <read_first>
    - Task 1 audible-pass-log.md template (already created)
    - .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log (programmatic baseline must be green)
  </read_first>
  <what-built>Same D-06 7-step protocol as Task 1 (HTTP only — Fedora is NOT the D-08 HTTPS-audible distro; Ubuntu Task 1 already covered that). Distrobox is ms-spike-fedora40.</what-built>
  <how-to-verify>Same flow as Task 1 steps 1-7, substitute `ms-spike-fedora40` and `fedora40` in commands and file names. SKIP step 8 — D-08 HTTPS audible is Ubuntu-only.</how-to-verify>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-screenshot.png`
    - shell-exit (PNG): `file .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-screenshot.png | grep -qi PNG`
    - content-grep: `grep -q '^## Fedora 40' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md`
    - content-grep (all 7 D-06 steps in Fedora section): `for n in 1 2 3 4 5 6 7; do awk '/^## Fedora 40/,/^## /' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md | grep -q "step ${n}:" || { echo "missing step ${n} in Fedora section"; exit 1; }; done`
    - manual-checkpoint: Kyle confirms "fedora40 audible OK".
  </acceptance_criteria>
  <action>Kyle runs the same 7-step protocol on Fedora 40 distrobox. Pitfall 10 (sink election) is the LIVE risk on this distro — record the elected sink. If audible PASS works on Ubuntu but FAILS on Fedora 40 with same AppImage, STOP and report (negative pivot per Pitfall 10 trigger condition). D-08 HTTPS audible is intentionally NOT exercised here — it was covered in Task 1.</action>
  <resume-signal>Kyle types "fedora40 audible OK" or describes the failure mode.</resume-signal>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-screenshot.png && file .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-screenshot.png | grep -qi PNG && grep -q '^## Fedora 40' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md && for n in 1 2 3 4 5 6 7; do awk '/^## Fedora 40/,/^## /' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md | grep -q "step ${n}:" || exit 1; done</automated>
    <human-check>Kyle confirms "fedora40 audible OK".</human-check>
  </verify>
  <done>Fedora 40 screenshot valid PNG + audible-pass-log.md Fedora section filled with all 7 steps + relaunch time + elected sink; Kyle confirmed.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 3: Audible PASS protocol — openSUSE Tumbleweed distrobox</name>
  <files>.planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-screenshot.png, .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md</files>
  <read_first>
    - Task 1 audible-pass-log.md template
    - .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log (programmatic baseline must be green)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Open Question 4 (Tumbleweed rolling kernel) — this distro is the third (hardest) per CONTEXT.md D-05 rationale
  </read_first>
  <what-built>Same D-06 7-step protocol as Task 1 (HTTP only — Tumbleweed is NOT the D-08 HTTPS-audible distro; Ubuntu Task 1 covered it). Distrobox is ms-spike-tumbleweed. Tumbleweed is intentionally last because its rolling kernel + GLIBC 2.42 + zypper-side audio routing surface the broadest "did the AppImage really portable-build?" question.</what-built>
  <how-to-verify>Same flow as Task 1 steps 1-7, substitute `ms-spike-tumbleweed` and `tumbleweed`. Be alert for sink-election difference (Pitfall 10 fallout from non-PipeWire-compat ALSA on TW). SKIP step 8 — D-08 HTTPS audible is Ubuntu-only.</how-to-verify>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-screenshot.png`
    - shell-exit (PNG): `file .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-screenshot.png | grep -qi PNG`
    - content-grep: `grep -q '^## openSUSE Tumbleweed' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md`
    - content-grep (all 7 steps in Tumbleweed section): `for n in 1 2 3 4 5 6 7; do awk '/^## openSUSE Tumbleweed/,/^## /' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md | grep -q "step ${n}:" || { echo "missing step ${n} in Tumbleweed section"; exit 1; }; done`
    - manual-checkpoint: Kyle confirms "tumbleweed audible OK".
  </acceptance_criteria>
  <action>Kyle runs the 7-step protocol on openSUSE Tumbleweed distrobox. If anything fails uniquely on Tumbleweed (e.g., alsasink elected instead of pulsesink), this IS the finding — record it in audible-pass-log.md notes section. Per CONTEXT.md D-09: if Tumbleweed-specific failure mode is identified, STOP and report; do NOT pivot. D-08 HTTPS audible is intentionally NOT exercised here.</action>
  <resume-signal>Kyle types "tumbleweed audible OK" or describes the failure mode for negative-pivot reporting.</resume-signal>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-screenshot.png && file .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-screenshot.png | grep -qi PNG && grep -q '^## openSUSE Tumbleweed' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md && for n in 1 2 3 4 5 6 7; do awk '/^## openSUSE Tumbleweed/,/^## /' .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md | grep -q "step ${n}:" || exit 1; done</automated>
    <human-check>Kyle confirms "tumbleweed audible OK".</human-check>
  </verify>
  <done>Tumbleweed screenshot valid PNG + audible-pass-log.md Tumbleweed section filled with all 7 steps; Kyle confirmed.</done>
</task>

</tasks>

<verification>
- 3 screenshots (one per distro), each a valid PNG
- audible-pass-log.md has Ubuntu 22.04 (8 steps incl. HTTPS audible per D-08), Fedora 40 (7 steps), openSUSE Tumbleweed (7 steps) sections each with relaunch time + elected sink
- Per-distro relaunch_time_to_play_s recorded → empirical evidence for Pitfall 3 mitigation
- `https_audible: PASS` line present (D-08 Ubuntu coverage)
</verification>

<success_criteria>
- Success criterion #1 ("AppImage plays MP3 on all 3 distros") complete (programmatic from Plan 06 + audible from this plan)
- Success criterion #4 (AppRun template + GST_REGISTRY_FORK behavior) empirically verified by relaunch step
- D-05 evidence trio (audible + screenshot + transcript) complete per distro
- D-08 HTTPS audible coverage satisfied (Ubuntu 22.04 Task 1 step 8)
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-07-SUMMARY.md` when done. Capture: per-distro relaunch deltas (first launch vs second launch time-to-PLAYING), per-distro elected audio sink, Ubuntu HTTPS audible time-to-PLAYING (D-08 evidence), any failure modes observed and reported.
</output>
</content>
</invoke>
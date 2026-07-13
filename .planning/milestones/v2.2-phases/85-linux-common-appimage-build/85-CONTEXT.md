# Phase 85: Linux Common + AppImage Build - Context

**Gathered:** 2026-05-26 (areas 1-2) + 2026-05-27 (area 3, recovered after host lockup)
**Status:** Ready for planning

<domain>
## Phase Boundary

Production-grade AppImage build for MusicStreamer on x86_64 Linux, lifting the Phase 85a spike from "it works on the dev rig" to a reproducible, versioned, signed artifact with embedded update info and a CI-buildable workflow scaffold. Closes nine PKG-LIN-APP requirements (PKG-LIN-APP-01..09).

In scope: a dedicated build environment (`tools/linux-build/environment.yml`), a hardened `build.sh` that parses that env file at build start to synthesize CONDA_PACKAGES for linuxdeploy-plugin-conda, GPG signing of the produced AppImage, embedded zsync update-info pointing at the GitHub-releases mirror, and a manually-triggerable GitHub Actions workflow that runs the same `build.sh`. The smoke-test driver from Phase 85a is promoted to a production smoke test that exercises the real `musicstreamer.url_helpers` resolver across MP3 + AAC + AACP + PLS-resolved URLs on Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed.

Out of scope: Flatpak (Phase 86), Windows packaging (Phase 88), channel-avatar work (Phase 89), automated GitHub-Releases publishing (PKG-LIN-APP-UPDATE deferred per REQUIREMENTS.md line 120), CLI screenshot capture for CI (descoped per Phase 85a Pitfall 18; portal D-Bus integration is its own surface).

</domain>

<decisions>
## Implementation Decisions

### Bundle source-of-truth (Area 1)
- **D-01:** Approach B — `build.sh` parses `tools/linux-build/environment.yml` at build start and synthesizes the `CONDA_PACKAGES` variable consumed by linuxdeploy-plugin-conda. Single source of truth: the YAML file. No duplicate list maintenance, no risk of CONDA_PACKAGES drifting from the env definition.
- **D-02:** `tools/linux-build/environment.yml` is a dedicated build env distinct from any dev env. Naming convention mirrors Phase 85a's `environment-spike.yml`. Pins are inherited from `pins.env` (Phase 85a) and verified by `verify-pins.sh` (Phase 85a) — Phase 85 may move both into `tools/linux-build/` if the planner finds that cleaner.
- **D-03:** `musicstreamer` itself is installed via `pip install --no-deps .` into the bundled conda env **after** linuxdeploy-plugin-conda finishes laying down conda dependencies. Rationale: conda-forge does not package `musicstreamer`; pip-with-no-deps lets us bring in the application code without re-resolving the conda-managed dependency graph.

### Smoke-test codec/URL surface (Area 2)
- **D-04:** Full codec sweep — MP3 + AAC + AACP + PLS-resolved URL — exercised on all three target distros (Ubuntu 22.04, Fedora 40, openSUSE Tumbleweed). PLS is the canonical "resolver depends on application code, not just GStreamer" probe; ICY/MP3 alone would let a broken `url_helpers` import slip past.
- **D-05:** `smoke_test.py` imports `musicstreamer.url_helpers` and calls the production resolver — **not** a copy-paste of resolver logic, **not** a GStreamer-only `playbin` smoke. This way the smoke catches dependency-graph and import-path regressions in the bundled env, not just media-pipeline issues.
- **D-06:** Per-URL playback duration: 35 s (matches Phase 85a spike default). Total UAT budget: ~7 min for 4 URLs × 3 distros sequential. CI parallelism is a planner concern, not a context-time decision.
- **D-07:** Smoke-test driver and distrobox create/teardown scripts inherit from `tools/linux-spike/` (Phase 85a). Phase 85 may relocate to `tools/linux-build/` or leave in place; this is Claude's Discretion at plan time.

### AppImage signing (Area 3a)
- **D-08:** `build.sh` GPG-signs the produced AppImage. The signing step runs **after** `linuxdeploy` packaging finishes and **before** the embedded zsync update-info is finalized (so the signature covers the final artifact bytes). Signing uses the standard AppImage `gpg2 --detach-sign --armor` flow that linuxdeploy itself supports via the `--sign` flag, plus a sidecar `.AppImage.sig` (or armored variant) per AppImage convention.
- **D-09:** Signing key identity comes from a `GPG_KEY_ID` build-env variable (no hardcoded fingerprint in `build.sh`). Build fails fast with a clear error if `GPG_KEY_ID` is unset AND the build is not running with `SKIP_SIGN=1` for spike-style local iteration. CI workflow (D-13) does NOT set `SKIP_SIGN` — release artifacts always sign.
- **D-10:** A new `PKG-LIN-APP-10` requirement covers signing (planner adds to REQUIREMENTS.md). Spike findings line 621 listed signing as "Phase 85 surface" but with no requirement row; Phase 85 makes it explicit. Verification: `gpg --verify MusicStreamer-<version>-x86_64.AppImage.sig MusicStreamer-<version>-x86_64.AppImage` succeeds with the published key.

### zsync update-info URL host (Area 3b)
- **D-11:** Embedded update-info string: `gh-releases-zsync|kcreasey|MusicStreamer|latest|MusicStreamer-*-x86_64.AppImage.zsync`. This is the canonical AppImageUpdate format for GitHub Releases-flavored hosts and matches the QNAP→GitHub mirror topology recorded in `reference_qnap_github_mirror.md`.
- **D-12:** This satisfies PKG-LIN-APP-06 ("AppImage embeds zsync update info pointing at the GitHub-releases-flavored host"). The actual publishing of `.zsync` companion files at the GitHub Releases endpoint is **not** Phase 85's job — REQUIREMENTS.md line 120 (PKG-LIN-APP-UPDATE) deferred that to a follow-on infra milestone and acknowledged "the URL is embedded but the host returns 404 between milestones." Phase 85 closes the embedding, not the serving.

### CI replication on GitHub Actions (Area 3c)
- **D-13:** Hybrid — Phase 85 ships `.github/workflows/linux-appimage.yml` as a `workflow_dispatch`-only (manual-trigger) workflow. It checks out the repo, sets up the same pinned linuxdeploy + conda base inside a container that pins glibc to Ubuntu 22.04 LTS, runs `tools/linux-build/build.sh`, and uploads the produced AppImage as a workflow artifact. **No automatic publish to GitHub Releases.**
- **D-14:** The workflow uses `--appimage-extract-and-run` for the linuxdeploy invocation (Phase 85a Pitfall 17 / FUSE constraint in containers). README documents that downstream CI users also need the flag (spike findings line 448). Distrobox parity flag `--unshare-devsys` is **not** needed in GitHub Actions (no host VirtualBox surface); spike findings line 569 is the dev-rig parity note, not a CI requirement.
- **D-15:** Workflow does NOT attempt CLI screenshot capture, MPRIS testing, or GUI verification — those need a real desktop session (Phase 85a Pitfalls 18+19+20). The workflow's success criterion is: AppImage is produced, GPG-signed, and `--appimage-extract-and-run smoke_test.py` exits 0 on the build container's bundled env. Cross-distro smoke (D-04, D-05, D-06) runs locally via distrobox; CI smoke is single-distro (Ubuntu 22.04 build container) and is a parity check, not a substitute for the distrobox sweep.
- **D-16:** Signing key in CI: workflow expects `secrets.LINUX_SIGNING_KEY` (ASCII-armored private key block) and `secrets.LINUX_SIGNING_KEY_ID`. Workflow imports the key into an ephemeral GPG home before running `build.sh`. If secrets are missing, workflow_dispatch run fails fast with a clear message. Setting the secret values is a one-time human op outside Phase 85 scope.

### Folded-in housekeeping
- **D-17:** Todo `2026-05-26-host-env-docker-info-probe.md` is folded into Phase 85 (per checkpoint `folded_todos`). The probe — verify `docker info` / distrobox backend autodetect behavior is documented so build instructions don't assume podman — gets a one-line addition to the production README (build prerequisites section).

### Claude's Discretion (planner picks)
- Plan split: monolithic `85-01-PLAN.md` vs. multi-plan (e.g., 85-01 = env file + build.sh refactor, 85-02 = signing + zsync, 85-03 = CI workflow, 85-04 = cross-distro smoke run + verification). Multi-plan is likely cleaner given the requirement coverage.
- Whether `tools/linux-spike/` artifacts get relocated to `tools/linux-build/` or referenced in place from `build.sh`. Cleaner-to-relocate; planner's call.
- Exact location of the `PKG-LIN-APP-10` (signing) row in REQUIREMENTS.md and how it groups against the existing PKG-LIN-APP block.
- Whether the README lives at repo root, in `tools/linux-build/`, or both (top-level pointer + detailed build doc).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 85a spike (working AppImage proof + locked patterns)
- `.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` — definitive findings; pitfalls 17 (HTTPS/SSL_CERT_FILE), 18 (CI screenshots), 19 (FUSE/PipeWire identity), 20 (distrobox parity). Phase 85's `build.sh` and `AppRun` start from these.
- `.planning/spikes/85a-linux-packaging-spike/build.sh` — working build flow from spike. D-01/D-02/D-03 refactor this.
- `.planning/spikes/85a-linux-packaging-spike/AppRun` — working launcher (with SSL_CERT_FILE export per Pitfall 17 fix). Phase 85 preserves.
- `.planning/spikes/85a-linux-packaging-spike/Dockerfile` — pinned build container; Phase 85 inherits and potentially relocates.
- `.planning/spikes/85a-linux-packaging-spike/environment-spike.yml` — pin baseline; D-02 forks into `tools/linux-build/environment.yml`.
- `.planning/spikes/85a-linux-packaging-spike/pins.env` + `verify-pins.sh` — pin enforcement; planner relocates or references.
- `.planning/spikes/85a-linux-packaging-spike/smoke_test.py` — production-import shape Phase 85 inherits per D-05.
- `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md` — skill mirror of the AppImage findings.
- `.planning/phases/85A-linux-packaging-spike/85A-VERIFICATION.md` — 4/4 PASSED verification report; what Phase 85 builds on.
- `tools/linux-spike/create-distroboxes.sh`, `tools/linux-spike/run-smoke.sh`, `tools/linux-spike/teardown-distroboxes.sh` — distrobox harness Phase 85 inherits.

### Requirements (Phase 85 closes these)
- `.planning/REQUIREMENTS.md` PKG-LIN-APP-01..09 (lines 15-23) + new PKG-LIN-APP-10 signing row (planner adds per D-10).
- `.planning/REQUIREMENTS.md` line 120 — PKG-LIN-APP-UPDATE deferred (do NOT close in Phase 85, just embed the URL).
- `.planning/REQUIREMENTS.md` line 144 — GLIBC 2.35 baseline; build container pinned in Phase 85a, inherited here.

### Drift-guard pattern (existing project convention)
- `tools/check_bundle_plugins.py` — Windows bundle drift-guard analog. Phase 85 may add a Linux mirror (`tools/check_linux_bundle.py`?) that source-greps the AppImage's bundled `lib/gstreamer-1.0/` against the pins. Claude's Discretion.
- `musicstreamer/url_helpers.py` — the production resolver `smoke_test.py` imports per D-05. Read-only in Phase 85.
- `tests/test_packaging_spec.py` — source-grep verification of GLIBC baseline (PKG-LIN-APP-08). Add the new check if Phase 85 introduces additional packaging invariants.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 85a `build.sh` — produces a working AppImage on the dev rig. Phase 85 refactors it to: read env from YAML (D-01), GPG-sign (D-08), embed zsync URL (D-11). Algorithmic flow stays the same.
- Phase 85a `AppRun` — already exports `SSL_CERT_FILE` (Pitfall 17 fix). Add `PULSE_PROP=application.name=MusicStreamer application.id=org.musicstreamer.app` per Phase 85a action on Pitfall 19 (production AppImage should ship with FUSE self-mount + explicit PipeWire app identity).
- `tools/linux-spike/run-smoke.sh` — distrobox-driven smoke harness. Phase 85 inherits; mirrors `SSL_CERT_FILE` env block per existing fix (commit `f8cc059`).
- `tools/check_bundle_plugins.py` — Windows packaging analog Phase 85 may mirror for Linux.

### Established Patterns
- **Pinned-container builds.** Phase 85a's Dockerfile establishes the pattern: pin glibc via base image, pin linuxdeploy SHA, pin conda + plugin-conda commits. Phase 85 inherits and locks for CI.
- **Source-of-truth single file → derived configs.** Project convention is one YAML/JSON authority + a build-time parser, not duplicated lists. D-01 follows this (environment.yml → CONDA_PACKAGES).
- **Drift-guards programmatic, not text-anchored.** Per Phase 91 D-03 context and `test_packaging_spec.py`; any Phase 85 Linux drift-guard follows the same shape (pytest test that reads source/artifact and asserts invariants).
- **Bookkeeping-only requirement flips deferred to phase close.** Pattern from Phases 77, 91. Phase 85 flips PKG-LIN-APP-01..10 to Complete only after the verification commits land.

### Integration Points
- **Phase 86 (Flatpak)** depends on Phase 85's `environment.yml` shape and bundled-env pattern for shared dependency reasoning. Also depends on Phase 91 closure for in-sandbox MPRIS verification (separate chain).
- **Phase 88 (Windows packaging)** is independent on the surface, but VER-02-J end-to-end testing reuses the smoke-driver pattern from D-04/D-05. Keep `smoke_test.py` portable (Linux paths + Windows paths) so Phase 88 can share.
- **PKG-LIN-APP-UPDATE follow-on infra milestone** — Phase 85's embedded zsync URL (D-11) is the contract that follow-on must publish against. Don't change the URL shape in Phase 85 if it would break the deferred milestone's expectation.

### Known Constraints (carry from spike)
- GLIBC 2.35 ceiling (PKG-LIN-APP-08) — build container pinned, cannot drift higher.
- FUSE unavailable in CI containers → `--appimage-extract-and-run` flag mandatory (Pitfall 17 / D-14).
- linuxdeploy-plugin-conda 1-2yr commit dormancy is parameterized internal, not abandonment (per memory `project_85a_linuxdeploy_plugin_dormancy_softened.md`); no need to vendor or fork.

</code_context>

<specifics>
## Specific Ideas

- **build.sh refactor outline (D-01):** Read `tools/linux-build/environment.yml` with `yq` (or python+pyyaml, but yq is lighter for shell-only build context). Extract `dependencies:` list, filter out the `pip:` sub-list, join with spaces, export as `CONDA_PACKAGES`. The `pip:` sub-list becomes the source for the `pip install --no-deps` post-step (D-03), restricted to `musicstreamer .` since deps are already conda-resolved.
- **Signing flow (D-08, D-09):** After `linuxdeploy --appimage-extract-and-run --plugin conda --output appimage`, run `gpg2 --detach-sign --armor --local-user "$GPG_KEY_ID" "$APPIMAGE_PATH"` to produce `MusicStreamer-<version>-x86_64.AppImage.sig`. Both files go into the release artifact set. Skip cleanly via `SKIP_SIGN=1` for local dev.
- **zsync embedding (D-11):** linuxdeploy supports `--updateinformation` flag. Pass `gh-releases-zsync|kcreasey|MusicStreamer|latest|MusicStreamer-*-x86_64.AppImage.zsync` directly. linuxdeploy embeds into the AppImage's `.upd_info` section automatically.
- **CI workflow skeleton (D-13):** `name: Linux AppImage Build`, `on: workflow_dispatch:`, `jobs.build.runs-on: ubuntu-22.04`, `container: <pinned-build-container-image>` (or `docker://...` if pushed to a registry; otherwise inline Dockerfile build step). Steps: checkout → import GPG key from secrets → run `tools/linux-build/build.sh` → upload artifact via `actions/upload-artifact@v4`. ~40 lines.

</specifics>

<deferred>
## Deferred Ideas

### Tracked-but-not-this-phase
- **PKG-LIN-APP-UPDATE** (REQUIREMENTS.md line 120) — actually publishing `.zsync` companion files at GitHub Releases. Embedded URL works in Phase 85; serving infrastructure is its own milestone.
- **Automatic publish to GitHub Releases on tag push** — Phase 85's CI workflow is `workflow_dispatch` only (D-13). Tag-driven publish + release-notes generation is a separate ops surface.
- **CLI screenshot capture in CI** (Phase 85a Pitfall 18) — needs `xdg-desktop-portal-gnome` D-Bus integration. Out of scope; tracked in spike findings.
- **MPRIS testing in CI** — needs a desktop session and live D-Bus. Container CI can't do this. Phase 86 (Flatpak) handles in-sandbox MPRIS verification; Phase 91 handles host MPRIS test closure.
- **Cross-distro CI sweep** — Phase 85 CI builds only on Ubuntu 22.04 (the GLIBC-baseline distro). Multi-distro sweep stays on the dev rig via distrobox (D-15). Lift to CI matrix only after the workflow proves stable.
- **PipeWire app-identity tuning (Pitfall 19 part a)** — D-08's AppRun update adds `PULSE_PROP`. Whether to also set `GST_PIPEWIRE_NODE_NAME` is planner's call; not critical-path.

### Out of scope for Phase 85 (do not pull in)
- Flatpak (Phase 86) — separate manifest, different sandboxing, different MPRIS surface.
- Windows packaging (Phase 88) — separate codepath; `smoke_test.py` may share but build is independent.
- Channel-avatar work (Phase 89, 89a, 89b) — unrelated.
- Editing `musicstreamer/url_helpers.py` — `smoke_test.py` imports it read-only (D-05). Any resolver changes belong in a separate phase.
- Editing Phase 85a spike artifacts in-place — Phase 85 produces *new* production artifacts in `tools/linux-build/`. The spike directory `tools/linux-spike/` and `.planning/spikes/85a-linux-packaging-spike/` are reference-only after Phase 85a closure.

### Pre-existing test failures (carried as separate todos, not Phase 85's surface)
Same set noted in Phase 91 91-CONTEXT.md "Deferred Ideas" — see those todos in `.planning/todos/pending/`. Phase 85 does not touch these.

</deferred>

---

*Phase: 85-linux-common-appimage-build*
*Context gathered: 2026-05-26 (areas 1-2) + 2026-05-27 (area 3 recovered after host lockup)*

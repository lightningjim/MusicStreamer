# Phase 86: Linux Flatpak Build - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship a sideload-installable `io.github.kcreasey.MusicStreamer.flatpak` that users install via `flatpak install --user` or GNOME Software, launch via Activities / `flatpak run`, and use with full audio + AAC + MPRIS2 + GBS.FM login working **inside the Flatpak sandbox**.

Requirements PKG-LIN-FP-01..10 are the fixed scope anchor. Flathub *store submission* (PKG-LIN-FP-FLATHUB) is explicitly **out of scope** — deferred to a post-v2.2 step. This phase produces the manifest, the build pipeline, and a verified sideload `.flatpak`.

</domain>

<decisions>
## Implementation Decisions

> **Locked upstream by REQUIREMENTS.md (NOT re-decided here):** app ID `io.github.kcreasey.MusicStreamer` (FP-01); runtimes `org.kde.Platform//6.8` + `org.kde.Sdk//6.8` + `io.qt.PySide.BaseApp//6.8` + `org.freedesktop.Platform.ffmpeg-full//24.08` + `org.freedesktop.Sdk.Extension.node20` (FP-03); base finish-args allow-list `--share=network` / `--socket=pulseaudio` / `--socket=wayland` / `--socket=fallback-x11` / `--own-name=org.mpris.MediaPlayer2.MusicStreamer`, explicitly NOT `--filesystem=home` and NOT broad `--socket=session-bus` (FP-04); `QTWEBENGINE_DISABLE_SANDBOX=1` for GBS.FM login (FP-05); `flatpak-pip-generator` → checked-in `python3-modules.yaml` (FP-09); `appstreamcli validate` + `desktop-file-validate` pre-flight (FP-10).

### First-launch import wizard (PKG-LIN-FP-06)
- **D-01:** Detection uses a **narrow read-only host mount** — add `--filesystem=~/.local/share/musicstreamer:ro` to finish-args (and **only** that path). On first launch the app auto-detects the old unsandboxed data dir and offers the import wizard. A single narrow `:ro` path is not "broad" filesystem access — it is the most faithful reading of FP-06's word "detects" while honoring the "no broad filesystem permission" clause.
- **D-02:** Import is **copy, leave original untouched** — data is copied into the sandbox data dir (`~/.var/app/io.github.kcreasey.MusicStreamer/data/`); the original `~/.local/share/musicstreamer/` stays intact so the prior AppImage/native install keeps working independently. No write permission to the host path is requested (the `:ro` mount enforces this).
- **D-03:** Wizard is **offer-once, then manual-only** — prompt on first launch; if dismissed, record a flag in sandbox data and never auto-prompt again. An "Import settings…" action remains available in the menu/settings for later use.
- **D-04:** Import reuses the **Phase 25 settings-export import code path** (the existing ZIP/settings-export deserializer). Whatever Phase 25 export covers (stations, preferences, library) is what the wizard imports; no new import surface is invented here.
- **D-05 (reconciliation note for planner):** The `:ro` mount in D-01 is an **addition** to the PKG-LIN-FP-04 finish-args list. The planner must reconcile this explicitly — either update the PKG-LIN-FP-04 requirement text to enumerate the narrow `:ro` path as an approved exception, or document it as an approved addition in the manifest + REQUIREMENTS traceability. The Area-4 drift-guard (D-13) must allow this exact path while still denying broad `--filesystem=home`.

### `.flatpak` distribution + CI
- **D-06:** The sideload bundle is published as a **GitHub release asset alongside the AppImage** — `flatpak build-bundle` → `MusicStreamer-<version>.flatpak`, attached to the same release. Matches the QNAP→GitHub mirror topology (`reference_qnap_github_mirror`) and Phase 85's AppImage distribution (85 D-11).
- **D-07:** Add **CI mirroring Phase 85** — `.github/workflows/linux-flatpak.yml`, `workflow_dispatch`-only (manual trigger), builds via `flatpak-builder` inside a container, uploads the produced `.flatpak` as a workflow artifact, **no auto-publish** to releases. Parity with Phase 85 D-13..D-16. GUI/audio/MPRIS verification is NOT attempted in CI (needs a real desktop session — see D-10); CI's success criterion is "bundle builds + validators pass."
- **D-08:** The `.flatpak` is **GPG-signed** via `flatpak build-bundle --gpg-sign=$GPG_KEY_ID`, reusing the same `GPG_KEY_ID` build-env variable as the signed AppImage (Phase 85 D-08/D-09). This adds a **new PKG-LIN-FP signing requirement row** to REQUIREMENTS.md — the planner adds it, mirroring how Phase 85 added PKG-LIN-APP-10. CI imports the signing key from secrets (mirror 85 D-16: `secrets.LINUX_SIGNING_KEY` / `secrets.LINUX_SIGNING_KEY_ID`), fails fast if missing unless a local `SKIP_SIGN=1` spike override is set.

### In-sandbox verification protocol (Success Criteria 2/3/4)
- **D-09:** **Full empirical evidence bundle per capability** — for AAC audio, GBS.FM login, and MPRIS2: audible confirmation + Wayland screenshot + terminal/D-Bus transcript, embedded in an `86-VERIFICATION` / UAT findings doc. Mirrors the 85a/85 evidence protocol.
- **D-10:** **MPRIS2 verified via `busctl --user` / `playerctl` introspection of `org.mpris.MediaPlayer2.MusicStreamer` from OUTSIDE the sandbox, AND an OS media-key press test** confirming play/pause/next reach sandbox playback. Objective (bus introspection) + functional (media keys). Unblocked by Phase 91 (FIX-MPRIS complete) — PKG-LIN-FP-08's dependency is satisfied.
- **D-11:** UAT runs on the **native dev-rig Wayland GNOME host — single-host, no cross-distro matrix.** Flatpak bundles its own `org.kde.Platform//6.8` runtime, so the glibc/distro-variance concern that justified the 85a distrobox matrix is abstracted away by Flatpak's design. (Per `project_deployment_target`: Wayland GNOME Shell, DPR=1.0.)
- **D-12:** **GBS.FM login-persistence protocol (SC3):** log in via the QtWebEngine subprocess → fully quit the app → relaunch → confirm still logged in (cookies persisted in sandbox data) AND confirm no namespace/sandbox error in the QtWebEngine subprocess. This is part of the D-09 evidence bundle.

### Manifest drift-guard tests
- **D-13:** Drift-guards in `tests/test_packaging_spec.py` assert **both an allow-list AND a deny-list**: (a) the exact finish-args allow-list including the narrow `:ro` mount from D-01; (b) **ABSENCE** of `--filesystem=home` and broad `--socket=session-bus`; (c) runtime version pins (`Platform//6.8`, `ffmpeg-full//24.08`, `node20`). The deny half is the security-critical assertion — presence-only guards would miss it (`feedback_drift_guard_presence_not_semantics`). Guards parse the manifest as data and assert on parsed values, not just grep for line presence.
- **D-14:** The Flatpak manifest is authored in **YAML** (`io.github.kcreasey.MusicStreamer.yaml`) — increasingly the Flathub convention and supports inline comments documenting *why* each finish-arg exists (cite-the-source discipline per `feedback_mirror_decisions_cite_source`).
- **D-15:** FP-10 validators (`appstreamcli validate` + `desktop-file-validate`) run **both ways**: a pytest test shells out to both (skip-if-not-installed), AND the build/CI runs them as a **hard pre-flight gate** that fails the build on error.

### Claude's Discretion (planner picks)
- Plan split (monolithic vs multi-plan; likely multi-plan: manifest+pip-generator / build+sign+bundle / import-wizard wiring / CI workflow / verification UAT).
- Whether build tooling relocates under `tools/linux-flatpak/` or shares `tools/linux-build/` with the AppImage driver.
- Exact module structure inside the manifest (how `musicstreamer` source module + `python3-modules.yaml` + node20 deps are sequenced).
- Where the new signing requirement row sits in REQUIREMENTS.md and its exact ID.

</decisions>

<specifics>
## Specific Ideas

- "Mirror Phase 85" is the recurring theme for distribution + CI + signing — the AppImage build's GitHub-release + `workflow_dispatch`-only CI + `GPG_KEY_ID` signing shape is the analog Kyle wants reused for Flatpak.
- The narrow `:ro` mount is a deliberate, minimal compromise: Kyle wants true first-launch auto-*detection* (FP-06's word "detects"), accepting one narrow read-only host path rather than the purer-but-weaker portal-picker-only flow that can't detect.
- Flatpak's bundled runtime is treated as the portability layer — the cross-distro test matrix that was essential for AppImage (glibc baseline) is intentionally dropped for Flatpak because the runtime makes it moot.
- Drift-guards must check the security posture (deny-list), not just presence — a direct application of the Phase 85-era drift-guard lesson.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 86 scope + requirements
- `.planning/ROADMAP.md` §"Phase 86: Linux Flatpak Build" — Goal, 5 success criteria, Depends-on (Phase 91, now complete), Research flag = YES.
- `.planning/REQUIREMENTS.md` §"Linux Packaging — Flatpak (PKG-LIN-FP)" (PKG-LIN-FP-01..10) — the locked requirement set; FP-04 (finish-args) and FP-06 (import wizard) are the two most decision-dense rows.
- `.planning/REQUIREMENTS.md` §"Pitfalls" row: "Flatpak `--filesystem=home` permission → Flathub will reject…; first-launch import wizard (PKG-LIN-FP-06) is the alternative."

### Precedent to mirror (AppImage, Phase 85 + spike 85a)
- `.planning/phases/85-linux-common-appimage-build/85-CONTEXT.md` — distribution (D-11 GitHub-releases), signing (D-08/D-09 `GPG_KEY_ID`), CI (D-13..D-16 `workflow_dispatch`-only + secrets), drift-guard + smoke pattern. Mirror these for Flatpak.
- `.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md` — the empirical evidence-bundle protocol (audible + Wayland screenshot + transcript) that D-09 mirrors.
- `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md` — conda-forge/GStreamer Linux findings; HTTPS needs `GIO_EXTRA_MODULES`+`SSL_CERT_FILE`, plugin-path redirection. Relevant where Flatpak's ffmpeg-full path differs.
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — feature-area index; load during GStreamer/packaging work.

### Reusable app surfaces
- Phase 25 settings-export ZIP flow (the import deserializer reused by D-04) — planner locates the module via codebase.
- Phase 76 QtWebEngine GBS.FM login subprocess (the flow validated under `QTWEBENGINE_DISABLE_SANDBOX=1` per FP-05/SC3).
- `tests/test_packaging_spec.py` — existing packaging drift-guard suite (AppImage); D-13/D-15 extend it for Flatpak.
- `tools/linux-build/` (Phase 85) — AppImage build driver; D-07 build tooling may share or sibling this.

### External tooling docs (researcher fetches deeper context — Research flag = YES)
- Flathub `io.qt.qtwebengine.BaseApp` manifest — verbatim `QTWEBENGINE_DISABLE_SANDBOX=1` spelling + QtWebEngine-in-sandbox pattern (Pitfall 4).
- `io.qt.PySide.BaseApp//6.8` — PySide6 BaseApp on org.kde.Platform.
- `flatpak-pip-generator` — generating `python3-modules.yaml` for offline builds (FP-09).
- `org.freedesktop.Platform.ffmpeg-full//24.08` extension — AAC codec path inside the sandbox (FP-07 / SC2).
- flatpak-builder, `flatpak build-bundle` (`--gpg-sign`), xdg-desktop-portal (file chooser / detection nuances).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 25 settings-export import path** — the existing ZIP/settings deserializer is reused verbatim for the FP-06 import wizard (D-04); no new import logic.
- **Phase 76 QtWebEngine GBS.FM login subprocess** — the login flow whose cookie persistence (SC3/D-12) is verified inside the sandbox.
- **`tests/test_packaging_spec.py`** — existing AppImage drift-guard suite; extended with Flatpak allow/deny-list guards (D-13) and FP-10 validator tests (D-15).
- **Phase 85 `tools/linux-build/build.sh` + `.github/workflows/linux-appimage.yml`** — structural analogs for the Flatpak build driver + `workflow_dispatch` CI (D-07), including the `GPG_KEY_ID` / CI-secret signing discipline (D-08).
- **`repo.py` migration + `assets/` layout precedents** (`reference_musicstreamer_db_schema`) — relevant to where imported data lands in the sandbox data dir.

### Established Patterns
- "Mirror Phase 85/43" — distribution to GitHub releases, `workflow_dispatch`-only CI (no auto-publish), GPG signing via build-env key, evidence-bundle UAT.
- Drift-guard culture: source/data-level guards asserting both presence (allow-list) and absence (deny-list of forbidden permissions).
- conda-forge / bundled-runtime as the GStreamer source — Flatpak's `org.kde.Platform` + `ffmpeg-full` is the Flatpak analog of the AppImage conda bundle.

### Integration Points
- **Manifest YAML** (`io.github.kcreasey.MusicStreamer.yaml`) is the new source-of-truth artifact; drift-guards parse it (D-13/D-14).
- **`python3-modules.yaml`** (flatpak-pip-generator output, FP-09) checked into the repo, consumed by the manifest.
- **Sandbox data dir** `~/.var/app/io.github.kcreasey.MusicStreamer/data/` is the import target (D-02); narrow `:ro` mount of `~/.local/share/musicstreamer` is the detection source (D-01).
- **GitHub release** assets — `.flatpak` joins the AppImage on the same release (D-06).
- **Node.js / node20 extension** — `node20` is in the locked runtime set (FP-03); how the app's Node.js dependencies (vs Python deps handled by flatpak-pip-generator) are bundled is a planner/researcher concern flagged for research (not a captured user decision).

</code_context>

<deferred>
## Deferred Ideas

- **Flathub store submission** (PKG-LIN-FP-FLATHUB) — explicitly post-v2.2; gated on v2.2 closure and a weeks-long review. v2.2 ships only the sideload `.flatpak`.
- **Reviewed Todos (not folded):** All 6 phase-86 keyword matches reviewed and left out of scope —
  - `2026-05-10-pls-codec-bitrate-url-fallback` — player feature, not packaging (scope creep here).
  - `2026-05-26-test-bump-version-json-decoder-failures`, `…-test-constants-drift-soma-nn-requirements`, `…-test-hamburger-menu-actions-pre-existing-d03`, `…-test-media-keys-smtc-win32-fallback` — Phase 77 test-debt; belong to the milestone's test-debt cleanup, not Flatpak packaging.
  - `2026-05-26-host-env-docker-info-probe` — already folded into Phase 85.

</deferred>

---

*Phase: 86-linux-flatpak-build*
*Context gathered: 2026-06-02*

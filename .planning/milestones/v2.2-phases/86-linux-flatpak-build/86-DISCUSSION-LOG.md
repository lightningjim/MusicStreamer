# Phase 86: Linux Flatpak Build - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 86-linux-flatpak-build
**Mode:** discuss (--chain)
**Areas discussed:** Import-wizard detection, .flatpak distribution + CI, In-sandbox verification protocol, Manifest drift-guard tests

---

## Todo cross-reference (fold decision)

| Option | Selected |
|--------|----------|
| None — all belong elsewhere | ✓ |
| test_media_keys_smtc on Linux | |
| test_constants_drift soma_nn | |
| PLS codec/bitrate URL fallback | |

**User's choice:** None folded. All 6 keyword matches reviewed and left out of scope (test-debt belongs to Phase 77 cleanup; PLS codec is a player feature; docker-info-probe already folded into Phase 85).

---

## Import-wizard detection (PKG-LIN-FP-06)

**Q1 — Detection mechanism**

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow read-only mount | `--filesystem=~/.local/share/musicstreamer:ro` only; auto-detect + offer | ✓ |
| Portal file-picker only | No mount; user picks export ZIP via portal; can't auto-detect | |
| Hybrid detect-then-import | Same `:ro` mount, used only to detect | |

**Q2 — Data safety**

| Option | Description | Selected |
|--------|-------------|----------|
| Copy, leave original untouched | Copy into sandbox data dir; original intact | ✓ |
| Copy then clear original | Destructive; needs write access | |

**Q3 — Re-prompt behavior**

| Option | Description | Selected |
|--------|-------------|----------|
| Offer once, then manual only | Prompt first launch; flag if dismissed; menu action remains | ✓ |
| Re-prompt until resolved | Prompt each launch until imported / declined | |

**Notes:** A single narrow `:ro` path is judged not "broad" — most faithful to FP-06's word "detects." Reconciliation with the FP-04 finish-args list flagged as a planner action (D-05).

---

## .flatpak distribution + CI

**Q1 — Distribution**

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub release, alongside AppImage | `build-bundle` → `MusicStreamer-<version>.flatpak` on same release | ✓ |
| Local-build artifact only | Build locally, defer publishing | |

**Q2 — CI**

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Phase 85 CI | `workflow_dispatch`-only, flatpak-builder in container, upload artifact, no auto-publish | ✓ |
| Local-build only for v2.2 | No CI workflow this phase | |

**Q3 — Signing**

| Option | Description | Selected |
|--------|-------------|----------|
| Sign with same GPG_KEY_ID | `build-bundle --gpg-sign=$GPG_KEY_ID`; new requirement row | ✓ |
| No signing for v2.2 sideload | Unsigned; rely on Flathub later | |

**Notes:** "Mirror Phase 85" throughout. Signing adds a new PKG-LIN-FP requirement row (planner), à la PKG-LIN-APP-10.

---

## In-sandbox verification protocol

**Q1 — Evidence standard**

| Option | Description | Selected |
|--------|-------------|----------|
| Full evidence bundle | Audible + Wayland screenshot + transcript per capability | ✓ |
| Checklist sign-off | Lighter; no captured artifacts | |

**Q2 — MPRIS2 verification**

| Option | Description | Selected |
|--------|-------------|----------|
| busctl/playerctl + media keys | Bus introspection from outside sandbox + media-key press | ✓ |
| Media-key press only | GUI-only observation | |

**Q3 — Test host**

| Option | Description | Selected |
|--------|-------------|----------|
| Native Wayland GNOME host | Single-host; Flatpak runtime abstracts distro variance | ✓ |
| Cross-distro distrobox matrix | Reuse 85a set for parity | |

**Notes:** Phase 91 (FIX-MPRIS) complete → PKG-LIN-FP-08 unblocked. GBS login-persistence protocol (SC3) folds into the evidence bundle. Cross-distro matrix intentionally dropped — moot for a bundled-runtime format.

---

## Manifest drift-guard tests

**Q1 — Guard scope**

| Option | Description | Selected |
|--------|-------------|----------|
| Allow-list AND deny-list | Exact finish-args + absence of forbidden perms + runtime pins | ✓ |
| Presence-only | Required args exist; no absence check | |

**Q2 — Manifest format**

| Option | Description | Selected |
|--------|-------------|----------|
| YAML | Inline comments documenting each finish-arg | ✓ |
| JSON | Older default; no comments | |

**Q3 — FP-10 pre-flight enforcement**

| Option | Description | Selected |
|--------|-------------|----------|
| Both pytest + build gate | Validators as pytest test (skip-if-missing) AND hard build gate | ✓ |
| Build/CI gate only | Validators only at build time | |

**Notes:** Deny-list is the security-critical half — direct application of `feedback_drift_guard_presence_not_semantics`. Guards parse manifest as data, not grep.

---

## Claude's Discretion

- Plan split (likely multi-plan).
- Build tooling location (`tools/linux-flatpak/` vs share `tools/linux-build/`).
- Manifest module sequencing (source module + python3-modules.yaml + node20 deps).
- Exact ID/placement of the new signing requirement row.

## Deferred Ideas

- Flathub store submission (PKG-LIN-FP-FLATHUB) — post-v2.2.
- All 6 reviewed todos left unfolded (see CONTEXT.md `<deferred>`).
- Node.js/node20 dependency bundling — flagged for researcher, not a captured user decision.

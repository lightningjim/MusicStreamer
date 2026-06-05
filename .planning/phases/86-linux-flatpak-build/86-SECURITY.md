---
phase: 86
slug: linux-flatpak-build
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-05
---

# Phase 86 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time across Plans 86-01 … 86-05 (`register_authored_at_plan_time: true`).
> Verified by gsd-security-auditor — **SECURED, 15/15 threats closed**.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| host filesystem → sandbox | Narrow `:ro` mount of `~/.local/share/musicstreamer` is the only host path into the sandbox | Legacy library DB + ZIP exports (read-only) |
| host session bus → sandbox | xdg-dbus-proxy mediates; only `--own-name` of the MPRIS2 name is granted | MPRIS2 media-control messages |
| QtWebEngine subprocess → host | Chromium inner sandbox disabled; outer Flatpak sandbox still constrains | GBS.FM OAuth login / cookies |
| CI secrets → signing key material | `LINUX_SIGNING_KEY` enters an ephemeral GNUPGHOME, used once, scrubbed | GPG private key |
| build artifact → user download | The `.flatpak` crosses the network to users; signature is the integrity anchor | Signed bundle |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-86-01 | Elevation of Privilege | finish-args filesystem scope | mitigate | `io.github.kcreasey.MusicStreamer.yaml:65` `--filesystem=~/.local/share/musicstreamer:ro`; `--filesystem=home` absent from `yaml.safe_load` parse. Test: `tests/test_packaging_spec.py:699` `test_flatpak_finish_args_deny_list` asserts on parsed list. | closed |
| T-86-02 | Information Disclosure | finish-args D-Bus scope | mitigate | `io.github.kcreasey.MusicStreamer.yaml:60` `--own-name=org.mpris.MediaPlayer2.musicstreamer`; `--socket=session-bus` absent from parsed finish-args. Same deny-list test at `:699`. | closed |
| T-86-03 | Elevation of Privilege | QtWebEngine subprocess (GBS.FM login) | accept | `io.github.kcreasey.MusicStreamer.yaml:70` `--env=QTWEBENGINE_DISABLE_SANDBOX=1`. Inner Chromium sandbox only is disabled; outer Flatpak sandbox still constrains. UAT SC3 confirms no namespace escape. | closed |
| T-86-SC-01 | Tampering | apt/pip installs + Flathub runtime downloads | mitigate | `86-RESEARCH.md:160-167` Package Legitimacy Audit: `flatpak-builder` (Ubuntu apt, official), `flatpak-pip-generator` (flatpak/flatpak-builder-tools, PyPI). Flathub runtimes GPG-signed by Flathub. See Notes re `[ASSUMED]` tags. | closed |
| T-86-04 | Tampering | Import wizard ZIP path traversal | mitigate | `musicstreamer/settings_export.py:262` `_validate_zip_members()` in `preview_import`; `:333` in `commit_import` (TOCTOU re-validation). `musicstreamer/ui_qt/flatpak_import_wizard.py:135` routes exclusively through `preview_import`; no `extractall`/`.extract(` in wizard. | closed |
| T-86-05 | Tampering | Host data integrity (copy-don't-delete) | mitigate | `:ro` mount kernel-enforced at `io.github.kcreasey.MusicStreamer.yaml:65`. `_ImportCommitWorker.run()` calls `commit_import` only — no write-back path. UAT SC5: host data intact after import. | closed |
| T-86-06 | Spoofing | Offer-once flag bypass / re-detection | accept | Flag in sandbox data dir (`paths.data_dir()`); deletion only re-triggers the offer — no privilege gain. `musicstreamer/flatpak_first_launch.py:104` confirms flag-absence check. | closed |
| T-86-07 | Tampering | Silent manifest permission drift | mitigate | `tests/test_packaging_spec.py:599` `manifest_data` fixture uses `yaml.safe_load`; `:699` `test_flatpak_finish_args_deny_list` asserts on parsed list — comment-embedded permissions invisible to the parser by construction. | closed |
| T-86-08 | Tampering | PySide6 re-introduced into python3-modules.yaml | mitigate | `tests/test_packaging_spec.py:883` `test_python3_modules_yaml_exists` asserts `"PySide6" not in content`. `python3-modules.yaml` has zero `PySide6`/`pyside6` matches. | closed |
| T-86-09 | Repudiation | metainfo/.desktop ships invalid | mitigate | `tools/linux-flatpak/build.sh:93-110` hard pre-flight: `appstreamcli validate` + `desktop-file-validate`, emit `BUILD_FAIL reason=validator_failed` and exit on failure. `tests/test_packaging_linux_spec.py:399` `test_flatpak_build_validator_gate`. | closed |
| T-86-10 | Tampering | Unsigned/tampered .flatpak in transit | mitigate | `build.sh:121` `flatpak build-bundle --gpg-sign="${GPG_KEY_ID}"`; `:29-32` fail-fast `BUILD_FAIL reason=gpg_key_unset` / `exit 5` unless `SKIP_SIGN=1`. `tests/test_packaging_linux_spec.py:360` `test_flatpak_build_gpg_sign`. | closed |
| T-86-11 | Information Disclosure | Signing key leaking from CI | mitigate | `.github/workflows/linux-flatpak.yml:68` `GNUPGHOME="$(mktemp -d)"`; `:130-135` `if: always()` scrub step `rm -rf "${GNUPGHOME}"`. Destroyed on success and failure paths. | closed |
| T-86-12 | Tampering | Invalid metainfo/.desktop shipped | mitigate | Same artifact as T-86-09: `build.sh:93-110` hard validator gate; `test_flatpak_build_validator_gate` (`tests/test_packaging_linux_spec.py:399`) asserts both validators + `BUILD_FAIL` path. | closed |
| T-86-SC-02 | Tampering | flatpak-github-actions / apt packages in CI | accept | Official `flatpak-org` action + Ubuntu apt packages. No `[SUS]`/`[SLOP]` in RESEARCH.md audit. Established provenance, no human gate required. | closed |
| T-86-13 | Elevation of Privilege | QtWebEngine sandbox-in-sandbox (SC3) | accept | Mirrors T-86-03. UAT SC3: `oauth.log` shows `Success`, no namespace error, cookies persist across quit+relaunch. Outer Flatpak sandbox intact. | closed |
| T-86-14 | Information Disclosure | MPRIS2 over-exposure (SC4) | mitigate | `tests/test_packaging_spec.py:811` `test_flatpak_mpris2_own_name` derives `SERVICE_NAME` from `mpris2.py` and asserts manifest `--own-name` matches exactly (catches lowercase/capital drift). UAT SC4: `busctl` shows only `org.mpris.MediaPlayer2.musicstreamer`. | closed |
| T-86-15 | Tampering | Host data mutated by import (SC5) | mitigate | UAT SC5 (86-VERIFICATION.md): host `~/.local/share/musicstreamer/` intact after import. Static: `:ro` kernel enforcement at `io.github.kcreasey.MusicStreamer.yaml:65`; no write path from wizard or migration. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-86-1 | T-86-03 / T-86-13 | Disabling Chromium's namespace sandbox is required for the GBS.FM OAuth login inside Flatpak. The outer Flatpak sandbox (seccomp + namespace) still constrains the subprocess. Env-var spelling sourced verbatim from flathub/io.qt.qtwebengine.BaseApp. UAT SC3 confirms no escape. Residual risk: **Low** — outer sandbox boundary intact. | gsd-security-auditor | 2026-06-05 |
| AR-86-2 | T-86-06 | Offer-once flag deletion re-triggers the import offer (intended behavior). No privilege escalation or data-exfiltration vector. Residual risk: **Negligible**. | gsd-security-auditor | 2026-06-05 |
| AR-86-3 | T-86-SC-02 | Official flatpak-org GitHub Actions action and Ubuntu apt packages; established provenance, no third-party/unverified sources. Residual risk: **Low**. | gsd-security-auditor | 2026-06-05 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-05 | 17 | 17 | 0 | gsd-security-auditor (sonnet) |

---

## Notes

**T-86-SC-01 — `[ASSUMED]` provenance tags:** The RESEARCH.md Package Legitimacy Audit carries `[ASSUMED]` tags on legitimacy claims for `flatpak-pip-generator` and `flatpak-builder`. These indicate the audit could not independently verify (e.g. checksum vs upstream release hashes) at research time — not a gap in the mitigation. Both are well-established official Flatpak-org projects; the documentation record is the declared mitigation artifact and residual risk is low.

**Unregistered surface (informational, no BLOCKER):** Two UAT fixes were security-adjacent and map to existing threat scope:
- *Fix #4 — MPRIS2 case mismatch:* `--own-name` had capital `MusicStreamer` vs source's lowercase `musicstreamer` — a functional bug (media keys broken), not a new attack surface. Covered by T-86-14; test upgraded to semantic cross-check.
- *Fix #5 — QTWEBENGINEPROCESS_PATH:* New `--env=QTWEBENGINEPROCESS_PATH=/app/bin/QtWebEngineProcess` finish-arg required for SC3 login. Within the QtWebEngine sandbox boundary (T-86-03 scope). Drift-guard added at `tests/test_packaging_spec.py:744`.

**SC5 context:** The import wizard was unwired from startup at initial Phase 86 delivery (SC5 FAIL), resolved in Phase 86.1 (human UAT 3/3 PASS). The T-86-04/05/06 import-security mitigations were present in the Phase 86 codebase; the SC5 gap was a wiring/startup defect, not a security-control gap.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-05

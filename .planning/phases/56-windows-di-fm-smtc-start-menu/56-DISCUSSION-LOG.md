# Phase 56: Windows DI.fm + SMTC Start Menu - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 56-windows-di-fm-smtc-start-menu
**Areas discussed:** DI.fm fix implementation site

---

## Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| DI.fm HTTPS policy | HTTP-for-DI.fm-only auto-fallback vs. HTTPS-with-clear-error vs. try-then-fallback. | |
| DI.fm fix implementation site | Import-time vs. play-time vs. failover-queue. | ✓ |
| SMTC diagnostic approach | Diagnose-first on VM vs. fix-by-suspect-cause. | |
| Existing DI.fm rows migration | Leave existing rows untouched vs. one-shot migrate on launch. | |

**User's choice:** DI.fm fix implementation site only. Implicit: HTTP-fallback policy (auto, transparent), SMTC investigation = diagnose-first, existing rows untouched.

---

## DI.fm fix implementation site

### Q1 — Fix site

| Option | Description | Selected |
|--------|-------------|----------|
| Player set_uri rewrite | `_set_uri()` detects DI.fm domain pattern and rewrites `https://` → `http://` before handing to playbin3. Universal fix; works for any URL source; no DB change. | ✓ |
| Import-time URL rewrite | `aa_import.py::fetch_channels` rewrites stream URLs to `http://` for DI.fm domains before returning. Only future AA imports affected. | |
| Failover queue HTTP entry | Add both HTTPS and HTTP stream entries per DI.fm channel; failover queue picks up HTTP after HTTPS fails. | |

**User's choice:** Player `_set_uri` rewrite.
**Notes:** Universal fix — covers manual-edit, AA import, settings-import ZIP, multi-stream failover, YouTube/Twitch resolved paths. No DB schema change, no migration step.

### Q2 — DI.fm detection

| Option | Description | Selected |
|--------|-------------|----------|
| `url_helpers` slug check | `_aa_slug_from_url(url) == 'di'`. Canonical AA detection; consistent with Phase 51/64. | ✓ |
| Substring `'di.fm'` match | `'di.fm' in url.lower()`. Catches all DI.fm hostnames; one line. | |
| Hardcoded prem*.di.fm regex | `^https://prem\d+\.di\.fm/`. Tight match; brittle if CDN naming changes. | |

**User's choice:** `_aa_slug_from_url` slug check.
**Notes:** Reuses the existing canonical AA-network predicate. Single source of truth via the `NETWORKS` table.

### Q3 — Rewrite scope

| Option | Description | Selected |
|--------|-------------|----------|
| Always rewrite | Unconditional `https://` → `http://` for DI.fm URLs. Cross-platform. | ✓ |
| Windows-only rewrite | Wrap in `sys.platform == 'win32'`. Preserves existing Linux behavior. | |
| Try-then-fallback | Player tries HTTPS first; on DI.fm-specific error, retries as HTTP. Preserves HTTPS if DI.fm fixes their server. | |

**User's choice:** Always rewrite.
**Notes:** Phase 43 confirmed the rejection is server-side, not Windows-specific. Cross-platform symmetry; no `sys.platform` branching. Manual revert if DI.fm ever fixes their server.

### Q4 — Helper home

| Option | Description | Selected |
|--------|-------------|----------|
| `url_helpers` free function | New `aa_normalize_stream_url(url) -> str` alongside existing `_aa_*` helpers. Independently unit-testable, discoverable. | ✓ |
| Inline in `_set_uri` | Three lines at the top of `player.py::_set_uri`. No new public surface. | |

**User's choice:** `url_helpers` free function.
**Notes:** Pure string transform, follows existing `url_helpers.py` convention (Phase 51, Phase 64). Independent unit tests possible without spinning up a Player.

---

## Continuation gate

| Option | Description | Selected |
|--------|-------------|----------|
| Discuss SMTC | Settle WIN-02 investigation/fix strategy. | |
| More on DI.fm fix | Test strategy, logging, edge cases. | |
| Ready for context | DI.fm decisions sufficient; SMTC implicit (diagnose-first on VM). | ✓ |

**User's choice:** Ready for context.
**Notes:** SMTC investigation strategy captured as implicit Claude's-discretion in CONTEXT.md (D-07 through D-10): diagnose-first on Win11 VM via PowerShell shortcut-property readback, in-process AUMID readback, fresh reinstall. Code change scope decided post-diagnostic — no premature refactoring of the already-correct wiring.

---

## Claude's Discretion

- **DI.fm rewrite is silent** (CONTEXT D-05): no toast, no info log spam — known stable server bug; debug-level log only.
- **Helper is idempotent** (CONTEXT D-06): already-`http://` URLs and non-DI.fm URLs pass through unchanged.
- **SMTC investigation = diagnose-first** (CONTEXT D-07..D-10): readback the actual installed shortcut AUMID property + in-process AUMID + force-fresh reinstall before considering code changes.
- **No anticipatory per-network workarounds**: only DI.fm is known-broken; other AA networks left untouched until evidence surfaces.
- **No build-time AUMID drift guard** (likely YAGNI for a single-author personal project; listed as discretion not D-spec).
- **No DB migration** for existing `https://` DI.fm URLs — rewrite happens at the URI boundary, so stored data is irrelevant.

---

## Deferred Ideas

- Per-network HTTPS workarounds for other AA networks (RadioTunes, JazzRadio, ClassicalRadio, RockRadio, ZenRadio) — re-evaluate only if external symptoms appear.
- Try-then-fallback retry logic — overkill given stable Phase 43 finding.
- Build-time AUMID-string drift guard (pytest or ripgrep) — YAGNI candidate.
- Code signing / MSIX / auto-update — Phase 44 disposition unchanged (v2.1+).
- WIN-03 / WIN-04 — Phase 57.
- BUG-08 (Linux WM display name) — Phase 61, parallel to WIN-02.
- VER-01 — Phase 63.

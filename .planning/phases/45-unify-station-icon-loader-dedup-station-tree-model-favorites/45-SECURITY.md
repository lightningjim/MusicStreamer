---
phase: 45
slug: unify-station-icon-loader-dedup-station-tree-model-favorites
status: secured
threats_open: 0
threats_total: 0
asvs_level: 1
created: 2026-04-14
---

# Phase 45 — Security

> Pure refactor. No new trust boundaries, no new attack surface.

---

## Trust Boundaries

No new boundaries. Phase 45 consolidates three pre-existing in-process icon loaders into a single shared helper; all data flow is intra-process.

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| (none introduced) | — | — |

---

## Threat Register

No new threats. The unified `load_station_icon` preserves every existing behavior:

- Path resolution goes through `abs_art_path()` — the same helper the previously-correct loader already used. No new filesystem access.
- `QPixmapCache` key format (`station-logo:{abs_path}`) is preserved and now consistent across all call sites (previously inconsistent, which was a correctness bug not a security bug).
- `FALLBACK_ICON` is a compile-time Qt resource path (`:/icons/audio-x-generic-symbolic.svg`), unchanged from prior.

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| (none) | — | — | — | — | — |

*Phase 45 introduces no untrusted input, no network I/O, no new filesystem writes, and no new IPC. Existing threat mitigations from phases that touch station art (e.g. T-40.1-LOGO-01 path restriction) continue to apply unchanged.*

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-14 | 0 | 0 | 0 | gsd-secure-phase (no-op audit) |

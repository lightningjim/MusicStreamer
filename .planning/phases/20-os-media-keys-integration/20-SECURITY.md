---
phase: 20
slug: os-media-keys-integration
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-05
---

# Phase 20 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| None (Plan 01) | Play/pause toggle is purely local UI — no network input, no IPC, no D-Bus | None |
| D-Bus session bus → MainWindow (Plan 02) | External same-user processes invoke PlayPause/Stop/Raise via MPRIS2 | Station name, ICY title (non-sensitive) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-20-01 | Tampering | `_toggle_pause` | accept | Local-only UI method; only GTK signal handlers (user-initiated) can call it | closed |
| T-20-02 | DoS | Pause/resume rapid toggle | accept | Each pause/resume is a lightweight GStreamer pipeline state change; no resource leak | closed |
| T-20-03 | Spoofing | D-Bus method calls | accept | Session D-Bus is user-scoped; same-user access is standard MPRIS2 behavior for all Linux media players | closed |
| T-20-04 | Tampering | PlayPause/Stop dispatch | mitigate | All D-Bus handlers dispatch to GTK main thread via `GLib.idle_add()` — confirmed in `musicstreamer/mpris.py` lines 40, 54, 60, 67, 72 | closed |
| T-20-05 | DoS | Rapid PlayPause via D-Bus | accept | Each call is lightweight; no amplification; same-user access only | closed |
| T-20-06 | Information Disclosure | Metadata properties | accept | Station name and ICY title are not sensitive; exposed only on session bus (same user) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-20-01 | T-20-01 | Local-only UI path; GTK signal model prevents external invocation | Kyle Creasey | 2026-04-05 |
| AR-20-02 | T-20-02 | GStreamer pipeline state changes are cheap; no amplification vector | Kyle Creasey | 2026-04-05 |
| AR-20-03 | T-20-03 | Session D-Bus same-user access is the intended MPRIS2 design; all Linux players accept this | Kyle Creasey | 2026-04-05 |
| AR-20-05 | T-20-05 | Same rationale as T-20-02; D-Bus call overhead is negligible | Kyle Creasey | 2026-04-05 |
| AR-20-06 | T-20-06 | Station name and ICY title are public by design (displayed in UI); session bus scoping limits exposure | Kyle Creasey | 2026-04-05 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-05 | 6 | 6 | 0 | gsd-secure-phase (orchestrator) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-05

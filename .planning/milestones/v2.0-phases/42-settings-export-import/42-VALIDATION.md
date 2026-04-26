---
phase: 42
slug: settings-export-import
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run --with pytest pytest tests/ -x -q` |
| **Full suite command** | `uv run --with pytest pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/ -x -q`
- **After every plan wave:** Run `uv run --with pytest pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 42-01-01 | 01 | 1 | SYNC-01 | T-42-01 | Export excludes cookies/tokens | unit | `uv run --with pytest pytest tests/test_settings_export.py -q` | ❌ W0 | ⬜ pending |
| 42-01-02 | 01 | 1 | SYNC-02 | T-42-02 | Credential keys filtered from settings table | unit | `uv run --with pytest pytest tests/test_settings_export.py -q` | ❌ W0 | ⬜ pending |
| 42-02-01 | 02 | 1 | SYNC-03 | — | N/A | unit | `uv run --with pytest pytest tests/test_settings_import.py -q` | ❌ W0 | ⬜ pending |
| 42-02-02 | 02 | 1 | SYNC-03 | — | N/A | unit | `uv run --with pytest pytest tests/test_settings_import.py -q` | ❌ W0 | ⬜ pending |
| 42-03-01 | 03 | 2 | SYNC-04 | — | N/A | unit | `uv run --with pytest pytest tests/test_settings_import.py -q` | ❌ W0 | ⬜ pending |
| 42-04-01 | 04 | 2 | SYNC-05 | — | N/A | integration | manual UAT | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_settings_export.py` — stubs for SYNC-01, SYNC-02
- [ ] `tests/test_settings_import.py` — stubs for SYNC-03, SYNC-04

*Existing pytest infrastructure covers framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Export/Import from hamburger menu | SYNC-05 | UI integration requires running app | Launch app → hamburger menu → Export Settings → verify ZIP created; Import Settings → select ZIP → verify summary dialog |
| Cross-platform round-trip | Phase 44 SC-6 | Requires Linux + Windows machines | Export on Linux → import on Windows → verify stations, logos, favorites present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 2
slug: search-and-filter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (uv run --with pytest) |
| **Config file** | none — discovered by pytest convention |
| **Quick run command** | `uv run --with pytest pytest tests/ -x -q` |
| **Full suite command** | `uv run --with pytest pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/ -x -q`
- **After every plan wave:** Run `uv run --with pytest pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | FILT-01–05 | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 2-01-02 | 01 | 1 | FILT-01 | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 2-01-03 | 01 | 1 | FILT-02 | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 2-01-04 | 01 | 1 | FILT-03 | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 2-01-05 | 01 | 1 | FILT-04 | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 2-02-01 | 02 | 2 | FILT-01–05 | manual | See Manual-Only Verifications | n/a | ⬜ pending |
| 2-02-02 | 02 | 2 | FILT-05 | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_filter_utils.py` — stubs for FILT-01 through FILT-05 (normalize_tags + matches_filter predicate tests)
- [ ] `musicstreamer/filter_utils.py` — `normalize_tags()` and `matches_filter()` must exist before tests can run

*Existing test infrastructure (pytest via uv) already established in Phase 1.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SearchEntry filters list in real time as user types | FILT-01 | GTK widget signals require display | Launch app, type partial name in search box, verify list narrows |
| Provider dropdown filters by provider | FILT-02 | GTK widget signals require display | Select a provider; verify only matching stations shown |
| Tag dropdown filters by tag | FILT-03 | GTK widget signals require display | Select a tag; verify only matching stations shown |
| All three filters compose simultaneously | FILT-04 | GTK widget signals require display | Set search + provider + tag; verify AND logic |
| Clear button resets all filters | FILT-05 | GTK widget signals require display | Activate filters, click Clear; verify full list returns |
| Clear button visibility toggles | FILT-05 | GTK widget signals require display | Activate a filter → Clear appears; deactivate → Clear hidden |
| Zero-result state shows StatusPage | FILT-01 | GTK widget visibility requires display | Search for a string with no matches; verify StatusPage shown |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

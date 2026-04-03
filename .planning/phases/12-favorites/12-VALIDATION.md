---
phase: 12
slug: favorites
status: audited
nyquist_compliant: false
wave_0_complete: true
created: 2026-03-30
audited: 2026-04-03
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run --with pytest pytest tests/ -x -q` |
| **Full suite command** | `uv run --with pytest pytest tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/ -x -q`
- **After every plan wave:** Run `uv run --with pytest pytest tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_add_favorite -xq` | ✅ | ✅ green |
| 12-01-02 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_duplicate_ignored -xq` | ✅ | ✅ green |
| 12-01-03 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_remove_favorite -xq` | ✅ | ✅ green |
| 12-01-04 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_list_favorites_order -xq` | ✅ | ✅ green |
| 12-02-01 | 02 | 2 | FAVES-01 | manual | — | n/a | ✅ manual-ok |
| 12-02-02 | 02 | 2 | FAVES-03 | manual | — | n/a | ✅ manual-ok |
| 12-02-03 | 02 | 2 | FAVES-04 | manual | — | n/a | ✅ manual-ok |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_favorites.py` — 9 unit tests covering FAVES-02 repo layer and iTunes genre parser

*Completed in Plan 01 execution (commit 98f3eff). All 9 tests green.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Star button appears left of Stop, hidden when no ICY title | FAVES-01 | GTK widget visibility requires live app | Launch app, play a ShoutCast station; verify star button appears left of Stop when ICY title is non-junk; stop playback and verify star disappears |
| Star icon fills on click, unfills if not yet favorited | FAVES-01 | Icon state is visual | Click star — icon should become `starred-symbolic`; re-launch app, play same station/title, verify icon starts filled if track was saved |
| Toggle switches between Stations and Favorites views | FAVES-03 | GTK widget swap requires live app | Click "Favorites" in toggle — station list replaces with favorites list; click "Stations" — list restores |
| Favorites list shows correct row content | FAVES-02 | Display content requires live app | Favorite a track; switch to Favorites view; verify row shows title as primary and "Station · Provider" as secondary |
| Trash button removes row immediately | FAVES-04 | GTK row removal requires live app | Click trash icon on a favorite row; verify row disappears immediately without confirmation |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or manual-only justification
- [x] Wave 0 complete — tests/test_favorites.py exists with 9 passing tests
- [x] No watch-mode flags
- [x] Feedback latency < 10s (0.13s observed)
- [ ] Sampling continuity: 3 consecutive manual tasks at end (UI layer — GTK requires live app, no automated alternative)
- [ ] `nyquist_compliant: true` — not set; 3 manual-only UI tasks prevent full compliance

**Approval:** partial — 4/7 automated (57%), 3/7 manual-only (UI/GTK)

---

## Validation Audit 2026-04-03

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Automated tests verified green | 4 |
| Manual-only (justified) | 3 |
| Tests generated | 0 (all existed) |

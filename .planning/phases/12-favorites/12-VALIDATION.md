---
phase: 12
slug: favorites
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
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
| 12-01-01 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_add_favorite -xq` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_duplicate_ignored -xq` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_remove_favorite -xq` | ❌ W0 | ⬜ pending |
| 12-01-04 | 01 | 1 | FAVES-02 | unit | `uv run --with pytest pytest tests/test_favorites.py::test_list_favorites -xq` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | FAVES-01 | manual | — | n/a | ⬜ pending |
| 12-02-02 | 02 | 2 | FAVES-03 | manual | — | n/a | ⬜ pending |
| 12-02-03 | 02 | 2 | FAVES-04 | manual | — | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_favorites.py` — stubs for FAVES-01 through FAVES-04 (repo layer tests)

*Existing infrastructure (pytest + uv) covers framework needs — Wave 0 only adds test stubs.*

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 87
slug: gbs-fm-marquee-themed-day-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 87 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 87-RESEARCH.md §Validation Architecture (lines 793–834).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing — `tests/test_*.py` naming) |
| **Config file** | `pyproject.toml` (existing test settings) |
| **Quick run command** | `uv run --with pytest pytest tests/test_gbs_marquee.py tests/test_gbs_marquee_drift_guard.py tests/test_announcement_banner.py -x` |
| **Full suite command** | `uv run --with pytest pytest` |
| **Estimated runtime** | quick <5s; full suite ~90s (1780+ tests baseline) |

---

## Sampling Rate

- **After every task commit:** Run quick subset (Phase 87 modules only).
- **After every plan wave:** Run full suite.
- **Before `/gsd:verify-work`:** Full suite green AND `grep -rn "QWebEngineProfile\|GBS_WEB_PROFILE_NAME\|GBS_WEB_STORAGE_PATH" musicstreamer/gbs_marquee.py musicstreamer/ui_qt/announcement_banner.py` returns empty.
- **Max feedback latency:** ~5s quick / ~90s full.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 87-01-* | 01 (harvest) | 1 | GBS-THEME-06 init / GBS-MARQ-07 init | Fixtures + MANIFEST.md schema; live data captured under 0o600 dev-fixture parents | manual + fixture-count | `ls tests/fixtures/gbs_themed_logos/ tests/fixtures/gbs_marquee/` | ❌ W0 | ⬜ pending |
| 87-02-* | 02 (parser-lock) | 2 | GBS-MARQ-02 | `Qt.TextFormat.PlainText` invariant on parsed text | unit | `pytest tests/test_gbs_marquee.py::test_parse_marquee_pipe_split -x` | ❌ W0 | ⬜ pending |
| 87-03-* | 03 (worker) | 3 | GBS-MARQ-01 | Worker thread bounded; no eval, no subprocess | unit (QTest) | `pytest tests/test_gbs_marquee.py::test_cadence_state_machine -x` | ❌ W0 | ⬜ pending |
| 87-04-* | 04 (themed-day) | 4 | GBS-THEME-01, GBS-THEME-02, GBS-THEME-03, GBS-THEME-04, GBS-THEME-05 | Logo targets `logo_label` only; no SQLite write; no toast | unit + source-grep | `pytest tests/test_gbs_marquee.py tests/test_gbs_marquee_drift_guard.py -x -k 'themed or logo'` | ❌ W0 | ⬜ pending |
| 87-05-* | 05 (banner) | 5 | GBS-MARQ-03, GBS-MARQ-04, GBS-MARQ-05 | `Qt.TextFormat.PlainText` on banner QLabel; bound-method signal connections (QA-05) | integration (QTest) | `pytest tests/test_announcement_banner.py -x` | ❌ W0 | ⬜ pending |
| 87-06-* | 06 (drift-guards + edits) | 6 | GBS-MARQ-06 + GBS-THEME-06 follow-up | Source-grep drift-guards; REQUIREMENTS/ROADMAP edited; todo created | source-grep + manual | `pytest tests/test_gbs_marquee_drift_guard.py -x` + manual edit confirmation | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Per-Requirement → Test Map (from RESEARCH.md §Validation Architecture)

| REQ | Invariant | Oracle | Test Class | Command |
|-----|-----------|--------|------------|---------|
| GBS-THEME-01 | logo_3.png fetched + SHA-256 hashed | `compute_logo_theme(harvested_bytes, "")` returns hash matching literal SHA-256 of fixture | unit | `pytest tests/test_gbs_marquee.py::test_compute_logo_theme_hashes_logo_bytes -x` |
| GBS-THEME-02 | Hash drift + keyword match → themed; fallback applies on hash drift + no keyword | Three-case oracle: themed_match, canonical_no_match, themed_no_match (D-12 fallback) | unit + log capture | `pytest tests/test_gbs_marquee.py::test_themed_detection_keyword_match -x` |
| GBS-THEME-03 | Logo override hits `logo_label` only | Source-grep bans `cover_label` / `set_station_art` in `gbs_marquee.py` themed-day path | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_themed_logo_targets_logo_slot_only -x` |
| GBS-THEME-04 | No SQLite / no disk persistence | Source-grep bans `repo.set_setting`, `.save(`, `open(...,"w"` in `gbs_marquee.py` | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_themed_logo_never_persists -x` |
| GBS-THEME-05 | No toast on themed-day detection | Source-grep bans `show_toast`, `libnotify`, `QSystemTrayIcon` in themed-day path | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_no_toast_in_themed_day_path -x` |
| GBS-THEME-06 | Baseline table structure ships + follow-up todo created | `GBS_LOGO_BASELINE_HASHES: dict[str,str]` with ≥1 harvested entry; `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` exists with `resolves_phase: 87` | unit + manual | `pytest tests/test_gbs_marquee.py::test_baseline_table_has_harvest_entries -x` + manual todo confirmation |
| GBS-MARQ-01 | Cadence = 60s playing / 5min idle / paused unbound | `worker.set_cadence(state)` updates `interval_ms` introspection accessor | unit (QTest) | `pytest tests/test_gbs_marquee.py::test_cadence_state_machine -x` |
| GBS-MARQ-02 | Split on `\|`, first segment, perpetual ignored | `parse_marquee("a \| b \| c")` returns `("a", "a \| b \| c")` | unit | `pytest tests/test_gbs_marquee.py::test_parse_marquee_pipe_split -x` |
| GBS-MARQ-03 | Banner visible iff GBS bound + non-empty + hash-not-dismissed | Integration test: bind GBS → marquee_ready → banner shown; same marquee → still shown; dismiss → same marquee → hidden | integration (QTest) | `pytest tests/test_announcement_banner.py::test_banner_visibility_predicate -x` |
| GBS-MARQ-04 | Pipe boundaries → `\n` wrap hints | Banner given `"first \| second"` → QLabel `text()` contains `\n` | unit (QTest) | `pytest tests/test_announcement_banner.py::test_pipe_to_newline_wrap -x` |
| GBS-MARQ-05 | × dismiss stores hash; same banner doesn't reappear | Dismissal-set assertion identical to GBS-MARQ-03 oracle | integration (QTest) | `pytest tests/test_announcement_banner.py::test_dismiss_stores_hash -x` |
| GBS-MARQ-06 | Phase 76 cookies-jar reuse; no QWebEngineProfile / no parallel cookies file | Source-grep: `gbs_marquee.py` imports `gbs_api` + `paths`; bans `QWebEngineProfile`, `GBS_WEB_PROFILE_NAME`, `oauth_helper`, parallel `open(<cookies-path>, "w")` | source-grep | `pytest tests/test_gbs_marquee_drift_guard.py::test_marquee_module_reuses_phase76_auth_only -x` |
| GBS-MARQ-07 | ≥10 marquee fixtures committed | `len(glob("tests/fixtures/gbs_marquee/*.txt") + glob("tests/fixtures/gbs_marquee/*.json")) >= 10` | fixture-count | `pytest tests/test_gbs_marquee.py::test_fixture_count_ten_or_more -x` |

---

## Wave 0 Requirements

- [ ] `tests/test_gbs_marquee.py` — covers GBS-THEME-01/02/06 + GBS-MARQ-01/02/07 (unit + fixture-count)
- [ ] `tests/test_gbs_marquee_drift_guard.py` — covers GBS-THEME-03/04/05 + GBS-MARQ-06 (source-grep)
- [ ] `tests/test_announcement_banner.py` — covers GBS-MARQ-03/04/05 (integration + widget)
- [ ] `tests/fixtures/gbs_themed_logos/MANIFEST.md` — fixture metadata schema (Plan 87-01 establishes)
- [ ] `tests/fixtures/gbs_marquee/MANIFEST.md` — fixture metadata schema (Plan 87-01 establishes)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live-fixture harvest TODAY captures "da troops" themed PNG + raw marquee | GBS-THEME-06 init / GBS-MARQ-07 init | Requires real network call to gbs.fm with dev fixture cookies; time-sensitive | Plan 87-01 instructions: GET `https://gbs.fm/images/logo_3.png` with cookies → SHA-256 → write to `tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png` + MANIFEST entry; GET candidate marquee URL(s) → write raw bytes to `tests/fixtures/gbs_marquee/2026-05-25_*.txt` + MANIFEST entry |
| Themed logo appears in now-playing logo slot only (not cover, not list, not toast) at Wayland DPR=1.0 | GBS-THEME-03 / GBS-THEME-05 | Visual verification at deployment-target DPR | Bind GBS station while "da troops" hash is in baseline; observe NowPlayingPanel logo slot displays themed logo; confirm cover slot unchanged; confirm no toast |
| Banner wrap behavior visually correct | GBS-MARQ-04 | Visual verification | Multi-pipe marquee like `"announcement \| perpetual1 \| perpetual2"` renders banner with line break at the pipe boundary; long announcement wraps across multiple lines |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 new test files + 2 fixture MANIFESTs)
- [ ] No watch-mode flags (`-x` short-circuits but no `--watch`)
- [ ] Feedback latency < 5s for quick run
- [ ] `nyquist_compliant: true` set in frontmatter after planner finalizes task assignments

**Approval:** pending

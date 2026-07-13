---
phase: 87B
slug: gbs-zero-token-single-song-add
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-18
audited: 2026-06-18
---

# Phase 87B — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_gbs_api.py tests/test_gbs_zero_token_drift_guard.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | ~15s (scoped) / >600s (full — scope it, per project note) |

> NOTE: Use `.venv/bin/python` — system `python3` lacks `PySide6.QtWidgets` (false failures). Full suite >600s; scope to GBS tests during execution. Two known pre-existing failures unrelated to this phase.

---

## Sampling Rate

- **After every task commit:** Run the quick run command (scoped GBS tests)
- **After every plan wave:** Run scoped GBS suite + the new drift-guard test
- **Before `/gsd:verify-work`:** Scoped GBS suite green; no new failures introduced
- **Max feedback latency:** ~15 seconds (scoped)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 87B-01-01 | 01 | 1 | GBS-TOKEN-03 | — | `add_song_zero_token()` reuses `/add` via `submit()`; raises `GbsAuthExpiredError` on 302→login | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token -x` | ✅ | ✅ green |
| 87B-01-02 | 01 | 1 | GBS-TOKEN-05 | T-87B-01 | Capture hook logs request line + messages only; NO cookie/session values written (no-PII) | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -k capture_hook -x` | ✅ | ✅ green |
| 87B-01-03 | 01 | 1 | GBS-TOKEN-05 | — | Provisional fixture under `tests/fixtures/gbs_zero_token/` parsed by the add unit test | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token_fixture -x` | ✅ | ✅ green |
| 87B-02-01 | 02 | 2 | GBS-TOKEN-01 | — | Persistent "Add a song" button visible iff GBS.FM bound + logged in (any token count) | unit | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k add_song_visibility -x` | ✅ | ✅ green |
| 87B-02-02 | 02 | 2 | GBS-TOKEN-03 | — | Button click emits `add_song_requested`; MainWindow opens `GBSSearchDialog` and wires `submission_completed` to panel re-poll | unit | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k add_song_clicked tests/test_main_window_gbs.py -k "add_song_requested or submission_completed_wired" -x` | ✅ | ✅ green |
| 87B-02-03 | 02 | 2 | GBS-TOKEN-04 | — | Post-add: dialog closes + `trigger_gbs_repoll()` resets cursor and re-polls (button persists; no hide-after-add) | unit | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k repoll -x` | ✅ | ✅ green |
| 87B-02-04 | 02 | 2 | GBS-TOKEN-02 | — | Source-grep: no "token" string literal in the button/add module (identifiers/fn-names allowed) | unit | `.venv/bin/python -m pytest tests/test_gbs_zero_token_drift_guard.py -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_gbs_api.py` — extended with `add_song_zero_token()` cases (calls-submit, auth-expired, capture-hook no-PII, fixture-exists) — REQ GBS-TOKEN-03/05
- [x] `tests/fixtures/gbs_zero_token/` — provisional `/add` request+response fixture (+ PLACEHOLDER for captured-on-use real tokens==0 payload) + MANIFEST.md — REQ GBS-TOKEN-05
- [x] `tests/test_gbs_zero_token_drift_guard.py` — source-grep "no 'token' word" test (clone of `test_gbs_marquee_drift_guard.py`) — REQ GBS-TOKEN-02
- [x] `tests/test_now_playing_panel.py` + `tests/test_main_window_gbs.py` — visibility, signal-emit, dialog-open, submission-wiring, re-poll cases — REQ GBS-TOKEN-01/03/04

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real `tokens==0` free-add succeeds against live gbs.fm | GBS-TOKEN-03/05 | User is at 48 tokens; cannot reach 0 on demand. Provisional contract; real behavior captured on first live use via the no-PII hook | When tokens naturally hit 0: bind GBS.FM, click "Add a song", confirm a song; verify the capture hook recorded the real request/response to the fixture + follow-up todo; confirm the song queued |
| Server-is-truth limit message surfaces verbatim | GBS-TOKEN-03 | Depends on live server response at tokens==0 (e.g. "you already have a song queued") | At tokens==0 with a song already queued, attempt a second add; verify the server's `messages`-cookie text appears inline verbatim |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s (scoped)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-06-18 — all 7 tasks COVERED with green automated tests (20 tests). Manual-only items remain blocked on a live `tokens==0` session (capture-on-use, tracked by `.planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md`).

---

## Validation Audit 2026-06-18

| Metric | Count |
|--------|-------|
| Requirements audited | 7 |
| COVERED | 7 |
| PARTIAL | 0 |
| MISSING | 0 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**Result:** NYQUIST-COMPLIANT. All Per-Task Map requirements verified via green automated unit tests (20 passing). No auditor spawn required (zero gaps). Audit corrected stale planning-time statuses and aligned three `-k` command strings (87B-01-02, 87B-01-03, 87B-02-02) to the implemented test names. Two Manual-Only verifications remain inherently manual (require a live server response at `tokens==0`) and are out of automated scope.

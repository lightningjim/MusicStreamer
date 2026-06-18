---
phase: 87B
slug: gbs-zero-token-single-song-add
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
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
| 87B-01-01 | 01 | 1 | GBS-TOKEN-03 | — | `add_song_zero_token()` reuses `/add` via `submit()`; raises `GbsAuthExpiredError` on 302→login | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token -x` | ❌ W0 | ⬜ pending |
| 87B-01-02 | 01 | 1 | GBS-TOKEN-05 | T-87B-01 | Capture hook logs request line + messages only; NO cookie/session values written (no-PII) | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token_capture -x` | ❌ W0 | ⬜ pending |
| 87B-01-03 | 01 | 1 | GBS-TOKEN-05 | — | Provisional fixture under `tests/fixtures/gbs_zero_token/` parsed by the add unit test | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token -x` | ❌ W0 | ⬜ pending |
| 87B-02-01 | 02 | 2 | GBS-TOKEN-01 | — | Persistent "Add a song" button visible iff GBS.FM bound + logged in (any token count) | unit | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k add_song_visibility -x` | ❌ W0 | ⬜ pending |
| 87B-02-02 | 02 | 2 | GBS-TOKEN-03 | — | Button click opens `GBSSearchDialog`; `submission_completed` wired to panel re-poll | unit | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k add_song_opens_dialog -x` | ❌ W0 | ⬜ pending |
| 87B-02-03 | 02 | 2 | GBS-TOKEN-04 | — | Post-add: dialog closes + `trigger_gbs_repoll()` resets cursor and re-polls (button persists; no hide-after-add) | unit | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k repoll -x` | ❌ W0 | ⬜ pending |
| 87B-02-04 | 02 | 2 | GBS-TOKEN-02 | — | Source-grep: no "token" string literal in the button/add module (identifiers/fn-names allowed) | unit | `.venv/bin/python -m pytest tests/test_gbs_zero_token_drift_guard.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_gbs_api.py` — extend with `add_song_zero_token()` cases (success, auth-expired, messages-verbatim, capture-hook no-PII) — REQ GBS-TOKEN-03/05
- [ ] `tests/fixtures/gbs_zero_token/` — provisional `/add` request+response fixture (+ placeholder for captured-on-use real tokens==0 payload) — REQ GBS-TOKEN-05
- [ ] `tests/test_gbs_zero_token_drift_guard.py` — new source-grep "no 'token' word" test (clone of `test_gbs_marquee_drift_guard.py`) — REQ GBS-TOKEN-02
- [ ] `tests/test_now_playing_panel.py` — visibility, dialog-open, re-poll cases (may already exist; extend) — REQ GBS-TOKEN-01/03/04

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real `tokens==0` free-add succeeds against live gbs.fm | GBS-TOKEN-03/05 | User is at 48 tokens; cannot reach 0 on demand. Provisional contract; real behavior captured on first live use via the no-PII hook | When tokens naturally hit 0: bind GBS.FM, click "Add a song", confirm a song; verify the capture hook recorded the real request/response to the fixture + follow-up todo; confirm the song queued |
| Server-is-truth limit message surfaces verbatim | GBS-TOKEN-03 | Depends on live server response at tokens==0 (e.g. "you already have a song queued") | At tokens==0 with a song already queued, attempt a second add; verify the server's `messages`-cookie text appears inline verbatim |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (scoped)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

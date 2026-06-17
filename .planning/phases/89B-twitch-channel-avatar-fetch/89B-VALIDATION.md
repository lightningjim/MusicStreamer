---
phase: 89b
slug: twitch-channel-avatar-fetch
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-16
---

# Phase 89b — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_twitch_helix.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` (scope to avatar/twitch/cover modules; full suite >600s) |
| **Estimated runtime** | ~10–30 seconds (scoped) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched module
- **After every plan wave:** Run the scoped avatar/twitch/cover test set
- **Before `/gsd:verify-work`:** Scoped suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 89b-01-xx | 01 | 1 | ART-AVATAR-04 | T-89b-01 | Helix call sends `Authorization: Bearer` + `Client-Id`; token read from `twitch_token_path()`, never logged | unit | `.venv/bin/python -m pytest tests/test_twitch_helix.py -q` | ❌ W0 | ⬜ pending |
| 89b-01-xx | 01 | 1 | ART-AVATAR-04 | T-89b-02 | Login parsed from URL strips query/fragment; no SSRF (host fixed to api.twitch.tv) | unit | `.venv/bin/python -m pytest tests/test_twitch_helix.py -k parse_login -q` | ❌ W0 | ⬜ pending |
| 89b-02-xx | 02 | 2 | ART-AVATAR-04 | — | Registry dispatch selects twitch fetcher for twitch.tv URLs; `_AvatarFetchWorker` never raises into Qt | unit | `.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py -q` | ❌ W0 | ⬜ pending |
| 89b-02-xx | 02 | 2 | ART-AVATAR-04 | — | Provider ensured as `Twitch: <login>` only when Provider field blank; never overwrites user value | unit | `.venv/bin/python -m pytest tests/test_twitch_provider_assign.py -q` | ❌ W0 | ⬜ pending |

*Exact task IDs assigned by the planner. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_twitch_helix.py` — Helix request shape (headers, URL), 200/401/empty-`data` handling, login parsing, square-image no-guard, fixture-locked Helix `/users` response
- [ ] `tests/test_edit_station_dialog_avatar.py` — registry dispatch picks twitch fetcher for twitch.tv URLs (extend if a YouTube analog test exists)
- [ ] `tests/test_twitch_provider_assign.py` — `Twitch: <login>` ensure-on-blank-only logic
- [ ] Run tests with `.venv/bin/python` (system python3 lacks PySide6.QtWidgets → false failures)

*Network is mocked — no live Helix calls in tests (fixture-locked response per the project's no-live-network test convention).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Twitch avatar appears circular-cropped in the cover slot for an ICY-disabled Twitch station | ART-AVATAR-04 | Requires a live Twitch login token + a real twitch.tv station + visual confirmation of the circular crop | Log into Twitch via Accounts; add/edit an ICY-disabled twitch.tv station; confirm the streamer avatar renders circular in the cover slot and the left logo slot is unchanged |
| No-token / expired-token fallback | ART-AVATAR-04 | Requires the absence/expiry of a live token | With no `twitch-token.txt`, add a twitch.tv station; confirm Save succeeds and the cover slot uses the station thumbnail (non-blocking, no crash) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

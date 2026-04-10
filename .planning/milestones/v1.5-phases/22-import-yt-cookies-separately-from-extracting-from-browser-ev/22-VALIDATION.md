---
phase: 22
slug: import-yt-cookies-separately-from-extracting-from-browser-ev
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs if needed |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | D-04 | — | Cookie file stored in app data dir | unit | `python -m pytest tests/test_cookies.py -k test_cookie_path` | ❌ W0 | ⬜ pending |
| 22-01-02 | 01 | 1 | D-10,D-11 | — | yt-dlp gets --cookies flag | unit | `python -m pytest tests/test_cookies.py -k test_ytdlp_flags` | ❌ W0 | ⬜ pending |
| 22-01-03 | 01 | 1 | D-12,D-13 | — | mpv gets cookies and no-cookies-from-browser | unit | `python -m pytest tests/test_cookies.py -k test_mpv_flags` | ❌ W0 | ⬜ pending |
| 22-02-01 | 02 | 1 | D-01,D-02 | — | Dialog opens with file picker prominent | manual | Visual check | — | ⬜ pending |
| 22-02-02 | 02 | 1 | D-08,D-09 | — | Import/Clear buttons work | manual | Visual check | — | ⬜ pending |
| 22-02-03 | 02 | 1 | D-07 | — | Hamburger menu has cookies item | manual | Visual check | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cookies.py` — stubs for cookie path, yt-dlp flags, mpv flags
- [ ] pytest installed (likely already available)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cookie dialog opens from hamburger menu | D-07 | GTK UI interaction | Launch app → click hamburger → "YouTube Cookies..." → dialog appears |
| File picker imports cookies.txt | D-01, D-02 | File dialog interaction | In cookie dialog → click file picker → select cookies.txt → verify "last imported" date |
| Paste textarea imports cookies | D-01 | GTK UI interaction | Expand "Other methods" → paste Netscape cookie text → Import → verify file created |
| Google login captures cookies | D-03 | Browser window interaction | Expand "Other methods" → click Google Login → sign in → verify cookies saved |
| Clear button removes cookies | D-09 | UI interaction | Click Clear → confirm cookies.txt deleted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

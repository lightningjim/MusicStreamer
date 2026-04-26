---
phase: 35
slug: backend-isolation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-11
---

# Phase 35 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `35-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-qt (to install) |
| **Config file** | `pyproject.toml` — add `[tool.pytest.ini_options]` with `env = QT_QPA_PLATFORM=offscreen` |
| **Quick run command** | `pytest -x -q tests/test_player_tag.py tests/test_player_failover.py` |
| **Full suite command** | `QT_QPA_PLATFORM=offscreen pytest -q` |
| **Estimated runtime** | ~25s (projected from current 265-test suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -x -q tests/<files touched by this task>`
- **After every plan wave:** Run `QT_QPA_PLATFORM=offscreen pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green + manual smoke via `python -m musicstreamer <shoutcast_url>` showing ICY title updates in terminal (success criterion #1)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 35-01-01 | 01 | 1 | PORT-09 | — | Spike decides mpv fate; result artifact committed | manual | `test -f .planning/phases/35-backend-isolation/35-SPIKE-MPV.md && grep -qE '^\*\*Decision:\*\* (DROP_MPV\|KEEP_MPV)' .planning/phases/35-backend-isolation/35-SPIKE-MPV.md` | ❌ W0 | ⬜ pending |
| 35-01-02 | 01 | 1 | PORT-09 | — | Phase 35 deps installed | smoke | `python -c 'import PySide6, yt_dlp, streamlink, pytest_qt'` | ❌ W0 | ⬜ pending |
| 35-02-01 | 02 | 2 | PORT-05 | T-IDisc-01 | Token/cookie file perms preserved on migration (copy2) | unit | `pytest tests/test_paths.py -x` | ❌ W0 | ⬜ pending |
| 35-02-02 | 02 | 2 | PORT-06 | T-IDisc-01 | Non-destructive; idempotent; linux same-path no-op | unit | `pytest tests/test_migration.py -x` | ❌ W0 | ⬜ pending |
| 35-03-01 | 03 | 2 | PORT-09 | — | yt-dlp library API; mock `yt_dlp.YoutubeDL` | unit | `pytest tests/test_yt_import.py -x` | ❌ W0 | ⬜ pending |
| 35-03-02 | 03 | 2 | PORT-09 | — | mpris stub is a no-op class matching public interface | unit | `pytest tests/test_mpris.py -x` | ⚠️ rewrite | ⬜ pending |
| 35-04-01 | 04 | 3 | PORT-02 | — | `attach_bus()` calls `enable_sync_message_emission()` then `add_signal_watch()`; no sync handlers | unit | `pytest tests/test_gst_bus_bridge.py -x` + grep gates | ❌ W0 | ⬜ pending |
| 35-04-02 | 04 | 3 | PORT-01, PORT-02, PORT-09 | — | Player is QObject; signals emit; zero GLib/dbus imports; `enable_sync_message_emission` in `Player.__init__` exactly once before `add_signal_watch` | unit | `pytest tests/test_player_signals.py tests/test_player_tag.py tests/test_player_failover.py -x` + grep gates | ⚠️ rewrite + new | ⬜ pending |
| 35-05-01 | 05 | 4 | QA-02 | — | `python -m musicstreamer <url>` plays stream with ICY log | manual | manual smoke at verify-work gate | ❌ W0 | ⬜ pending |
| 35-05-02 | 05 | 4 | QA-02 | — | ≥265 tests collected; zero `import gi` / `from gi` in `tests/` | smoke | `pytest --collect-only -q \| grep -c '::'` ≥ 265 + `pytest tests/test_no_gtk_imports.py::test_tests_have_no_gi -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pip install PySide6 pytest-qt yt-dlp streamlink` — blocking; nothing imports without this
- [ ] `tests/conftest.py` — set `QT_QPA_PLATFORM=offscreen`, add `qapp` fixture override if needed
- [ ] `tests/test_player_signals.py` — new: verifies Qt signals exist and emit correctly
- [ ] `tests/test_gst_bus_bridge.py` — new: verifies bus-loop thread + queued signal delivery
- [ ] `tests/test_paths.py` — new: verifies `paths.py` helpers and `_root_override` monkeypatch
- [ ] `tests/test_migration.py` — new: verifies PORT-06 three cases (idempotent, non-destructive copy, linux same-path)
- [ ] `tests/test_yt_import.py` — new: verifies library-API scan (mock `yt_dlp.YoutubeDL`)
- [ ] `tests/test_no_gtk_imports.py` — new: grep-style smoke tests: no `GLib.idle_add` in `player.py`, no `import gi` in `tests/`, no hardcoded `~/.local/share/musicstreamer` literals in source, no `subprocess` in `yt_import.py`
- [ ] `tests/test_mpris.py` — **rewrite** entirely to test the stub (6 tests replacing 140 lines of dbus mocking)
- [ ] Port the 12 existing `import gi` test files (`test_player_tag.py`, `test_player_failover.py`, `test_player_pause.py`, `test_player_buffer.py`, `test_player_volume.py`, `test_twitch_auth.py`, `test_twitch_playback.py`, `test_cookies.py`, `test_icy_escaping.py`, `test_aa_url_detection.py`, `test_yt_thumbnail.py`, plus `test_import_dialog.py`) to `qtbot.waitSignal` assertions

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| App launches and plays a ShoutCast stream with ICY title updating in terminal | ROADMAP success #1 | Requires live network + GStreamer playback; terminal-log check | `python -m musicstreamer https://streams.chillhop.com/lofi/mp3` — verify terminal shows "ICY title: ..." updates |
| mpv spike cases (YouTube live, HLS, cookie-protected, specific format) | PORT-09 / D-20 | Requires real YouTube + real `cookies.txt`; one-shot design decision | Run `spike/spike_mpv_drop.py` locally; record PASS/FAIL per case in `35-SPIKE-MPV.md` |

---

## Security Domain

Phase 35 is a backend refactor with no new attack surface. See `35-RESEARCH.md § Security Domain` for full STRIDE/ASVS analysis.

**Key threats in scope:**

| Pattern | STRIDE | Mitigation | Verified In |
|---------|--------|------------|-------------|
| Token file world-readable after migration | Information disclosure | `shutil.copy2` preserves `0600` mode bits | 35-02-01 (`test_paths.py::test_copy_preserves_mode`) |
| Cookie file perms not preserved in migration | Information disclosure | `shutil.copy2` preserves mode | 35-02-02 (`test_migration.py::test_mode_preserved`) |

**No new secrets, network endpoints, or file writes outside `user_data_dir`.**

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (automatic — plan-checker gate)
</content>
</invoke>
</invoke>
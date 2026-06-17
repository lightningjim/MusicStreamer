---
phase: 89c
slug: provider-brand-avatar-cover-slot-fallback
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-17
---

# Phase 89c — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> No GStreamer/Qt behavioral mocks — all validation is source-grep or lightweight
> pure-Python unit test per project convention (`feedback_gstreamer_mock_blind_spot`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (confirmed in `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py tests/test_brand_avatars.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x` |
| **Estimated runtime** | quick ~a few s; full suite >600s — scope to relevant files (memory: run-tests-with-venv-python) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_cover_art_avatar.py tests/test_brand_avatars.py -x`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -x -k "not integration"` (scoped; full suite >600s)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds (scoped quick run)

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| ART-AVATAR-11 / D-01 | Registry recognizes all 7 provider_name strings exactly (SomaFM, DI.fm, RadioTunes, JazzRadio, RockRadio, ClassicalRadio, ZenRadio) | unit | `pytest tests/test_brand_avatars.py::test_lookup_registered_providers -x` | ❌ W0 |
| ART-AVATAR-11 / D-01 | GBS.FM returns None from registry (exclusion) | unit | `pytest tests/test_brand_avatars.py::test_lookup_gbs_returns_none -x` | ❌ W0 |
| ART-AVATAR-11 / D-04 | Missing PNG file returns None (no crash, graceful fallthrough) | unit | `pytest tests/test_brand_avatars.py::test_lookup_missing_file_returns_none -x` | ❌ W0 |
| ART-AVATAR-12 / D-12 | Brand lookup fires ONLY from `_on_cover_art_ready` `if not path:` branch | source-grep | `pytest tests/test_cover_art_avatar.py::test_brand_lookup_only_in_cover_exhausted_branch -x` | ❌ W0 |
| ART-AVATAR-12 / D-07 | brand-fallback NOT called from `fetch_cover_art` or `bind_station` icy_disabled path | source-grep | (same test above) | ❌ W0 |
| D-11 / tier-replay | `_last_brand_avatar` present in `_apply_art_tier` branch | source-grep | `pytest tests/test_brand_avatars.py::test_apply_art_tier_has_brand_avatar_branch -x` | ❌ W0 |
| D-11 / stale-station bleed | `_last_brand_avatar = None` reset in `bind_station` | source-grep | `pytest tests/test_brand_avatars.py::test_bind_station_resets_brand_avatar -x` | ❌ W0 |
| D-08 / precedence | Resolution order: user override → bundled registry → station logo | unit (no Qt) | `pytest tests/test_brand_avatars.py::test_resolution_precedence_* -x` | ❌ W0 |
| ART-AVATAR-12 / no-regression | Unregistered providers reach `_show_station_logo_in_cover_slot` | source-grep / unit | `pytest tests/test_brand_avatars.py::test_unregistered_provider_fallsthrough -x` | ❌ W0 |
| ART-AVATAR-09 (existing) | `_mb_caa_lookup` before `_channel_avatar_lookup` in cover_art.py | source-grep | `pytest tests/test_cover_art_avatar.py::test_mb_caa_runs_before_channel_avatar -x` | ✅ exists |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_brand_avatars.py` — registry unit tests + source-grep drift-guards for D-08/D-11/D-12
- [ ] `musicstreamer/brand_avatars.py` — registry module (`lookup(provider_name) -> Optional[path]`), created in Wave 0 as part of plumbing
- [ ] `musicstreamer/ui_qt/brand-avatars/` — directory + `.gitkeep` (PNGs arrive from user later; missing asset === current behavior)
- [ ] Reuse existing `tests/test_cover_art_avatar.py` for the new `test_brand_lookup_only_in_cover_exhausted_branch` source-grep (mirrors `test_mb_caa_runs_before_channel_avatar`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Brand avatar appears on cover-miss | ART-AVATAR-12 | Needs running Qt display + live cover-art exhaustion | Bind a SomaFM station; let a track complete cover resolution with no result → brand avatar (circular) appears in cover slot, left logo slot unchanged |
| Tier-replay on resize | D-11 | Needs Qt resize event | Resize the window → brand avatar re-renders at new tier |
| Real cover wins (transient) | D-10 | Needs live iTunes/MB hit | Play a track that resolves real cover art → real cover replaces brand avatar; next miss → brand avatar re-appears |
| GBS exclusion | ART-AVATAR-11 SC3 | Needs Qt display | Bind GBS.FM → station logo in cover slot (no brand avatar) |
| No-regression unregistered | ART-AVATAR-12 SC4 | Needs Qt display | Bind a station with no registered provider → station logo in cover slot |
| Upload override end-to-end | D-09 | Needs Qt + file dialog + DB | EditStationDialog "Choose brand image…" for SomaFM → pick PNG → preview updates, `providers.avatar_path` set in DB, cover slot shows upload on next cover-miss |

---

## Validation Sign-Off

- [ ] All tasks have automated verify (source-grep/unit) or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`test_brand_avatars.py`, `brand_avatars.py`, asset dir)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (scoped quick run)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

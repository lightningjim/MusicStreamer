# Phase 89a: Channel-Avatar DB Migration + Storage Layout - Discussion Log

> **Audit trail only.** Not consumed by downstream agents (researcher, planner, executor).
> Canonical decisions live in `89A-CONTEXT.md`.

**Date:** 2026-06-07
**Phase:** 89A-channel-avatar-db-migration-storage-layout
**Mode:** discuss (interactive)

## Gray Areas Presented

| Area | Selected for discussion? | Resolution |
|------|--------------------------|------------|
| Storage layout (flat vs per-station subdir) | No | Locked from ART-AVATAR-02 → flat `assets/channel-avatars/<id>.png`; resolves SC3-vs-requirement tension in favor of requirement text (D-03) |
| Directory creation timing | **Yes** | Discussed — see below |
| Column plumbing scope | No | Locked → migration + dir only, dataclass wiring deferred to Phase 89 (D-06) |
| Rollback test scope | No | Locked → additive-column idempotency + schema-convergence semantics (D-07) |

## Discussion — Directory creation timing

**Q1: When should `assets/channel-avatars/` be created?**
- Options: Eager in `ensure_dirs()` (recommended) / Lazy on first write / Both (eager + lazy guard)
- **Selected:** Eager in `ensure_dirs()`
- Rationale: directory always exists at startup → directly satisfies Success Criterion 3 and makes the phase verifiable from real disk state without writing an avatar.

**Q2: How should the directory path be exposed in code?**
- Options: Dedicated `paths.channel_avatars_dir()` helper (recommended) / Inline join in `ensure_dirs()`
- **Selected:** Dedicated paths helper
- Rationale: mirrors `paths.assets_dir()`, respects `_root_override` for test isolation, and avoids Phase 89 re-deriving the path string.

**Q3: Ready for context, or discuss more?**
- **Selected:** Ready for context (declined to re-open storage layout / plumbing scope).

## Deferred Ideas

- `Station` dataclass / `save_station()` wiring for `channel_avatar_path` → Phase 89.
- `yt_import.fetch_channel_avatar()` + cover-slot swap → Phase 89.
- Twitch Helix `profile_image_url` fetch → Phase 89b.

## Claude's Discretion (recorded)

- Test file location/fixture style; combined-vs-separate makedirs line; inline ALTER comment wording.

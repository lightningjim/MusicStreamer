# Phase 74: SomaFM full station catalog + art - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and
**Areas discussed:** Catalog architecture, Refresh policy, UI entry point, Dedup, Re-import reconciliation

---

## Area Selection

User selected all four offered gray areas.

---

## Catalog architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Poll-to-install (bulk insert to SQLite) | One-click bulk import; ~40 stations as real Station rows. Parity with AA + GBS. | ✓ |
| In-memory catalog (browse modal) | On-demand fetch into Discovery-style dialog; user picks individually. | |
| Hybrid: bulk import with checklist | YouTube-import-style scan→checklist UX before insert. | |

**User's choice:** Poll-to-install.
**Notes:** Strongest parity with the existing AA and GBS importers. ~40 stations as a visible footprint is acceptable.

---

## Refresh policy

| Option | Description | Selected |
|--------|-------------|----------|
| Manual re-import only (idempotent) | User clicks the action again to refresh. Truncate-and-reset semantics. | ✓ |
| Auto-refresh on every app start | Fire catalog HTTP on every launch, silent metadata update. | |
| Auto-refresh weekly + manual button | Timestamp-gated weekly refresh + manual override. | |
| Manual + 'new stations' toast | HEAD/etag check at startup → toast offering refresh on changes. | |

**User's choice:** Manual re-import only.
**Notes:** Phase title says "new stations are rare" — manual cadence is sufficient.

---

## UI entry point

| Option | Description | Selected |
|--------|-------------|----------|
| Hamburger menu 'Import SomaFM' action | Single button; toast-driven status; parity with 'Add GBS.FM'. | ✓ |
| New tab in ImportDialog | YouTube/AudioAddict-tab style with progress bar. | |
| Both | Hamburger shortcut + tab for power-user UX. | |
| Discovery dialog 'SomaFM Curated' source | Integrate into Discovery alongside Radio-Browser (conflicts with Area 1 choice). | |

**User's choice:** Hamburger menu action.
**Notes:** Smallest UI surface; toast-only status; mirrors GBS.FM's import affordance directly.

---

## Dedup with existing stations

| Option | Description | Selected |
|--------|-------------|----------|
| Skip-if-URL-exists (AA pattern) | Whole-channel skip when any stream URL matches existing library. Preserves hand-curated rows. | ✓ |
| Merge-by-canonical-stream-URL | URL match → update provider, append missing tiers, refresh logo. | |
| Promote SomaFM-named stations regardless of URL | Name-match (case-insensitive) → upgrade to SomaFM-canonical. | |
| Truncate-and-reset SomaFM-provider stations | DELETE all `provider_name = 'SomaFM'` rows, then bulk re-insert. | |

**User's choice:** Skip-if-URL-exists (AA pattern).
**Notes:** Smallest blast radius. Hand-curated stations untouched. Possible visible duplicates accepted (user resolves manually).

---

## Re-import reconciliation (Area 2 ↔ Area 4 tension)

The dedup choice (skip-if-URL-exists) implied that re-imports are full no-ops on matched URLs — which conflicts with the "idempotent metadata refresh" intent from Area 2. Asked the user to pick a reconciliation.

| Option | Description | Selected |
|--------|-------------|----------|
| Full no-op (true AA parity) | URL match → entire channel skipped, no metadata refresh. Delete-and-reimport is the only refresh path. | ✓ |
| Refresh metadata only on provider='SomaFM' matches | URL match + provider='SomaFM' → update logo/description/stream metadata. Hand-curated rows untouched. | |
| Update streams + metadata; preserve hand-edits | URL match + provider='SomaFM' → reset stream rows + refresh metadata. Preserve name/tags/cover_art_source/icy_disabled. | |

**User's choice:** Full no-op (true AA parity).
**Notes:** Simplest implementation. SomaFM logo or description changes never propagate to existing rows unless user manually deletes-and-reimports.

---

## Claude's Discretion

- Quality tier mapping for SomaFM streams ("hi"/"med"/"low" labels vs. blank).
- Codec field population (MP3/AAC/AAC+).
- Channel-fetch concurrency (single sequential pass — only 1 HTTP call for the catalog).
- Logo file naming + persistence (mirror AA's `_download_logo` pattern).
- Stream `label` field (empty vs. "MP3 128 kbps" descriptive).
- API endpoint choice (`api.somafm.com/channels.json` vs. `somafm.com/channels.json`).
- User-Agent on SomaFM requests (Phase 73's MB UA string or omit — politeness, not requirement).

## Deferred Ideas

- In-memory / browse-modal SomaFM UX.
- SomaFM tab in ImportDialog.
- Auto-refresh on app start / weekly refresh / etag-check toast.
- Discovery-dialog SomaFM curated source.
- Refresh metadata on URL match.
- Truncate-and-reset for SomaFM-provider stations.
- Notification toast when SomaFM publishes a new channel.
- SomaFM premium / paid integration.
- Merge-by-name dedup.
- Progress-bar UX (toast-only chosen per D-08).

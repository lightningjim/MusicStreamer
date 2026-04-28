# Phase 51: AudioAddict Cross-Network Siblings - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 51-audioaddict-cross-network-siblings
**Areas discussed:** Click action on a sibling, Unsaved-edits handling, UI placement, Visual rendering, Detection timing & storage

---

## Click action on a sibling

| Option | Description | Selected |
|--------|-------------|----------|
| Open sibling's edit dialog | Close the current EditStationDialog, immediately open EditStationDialog for the sibling station. Mirrors 'jump to that station's editor' — read-friendly, doesn't interrupt playback, supports SC #2 example explicitly. User can save/cancel the sibling independently. | ✓ |
| Select sibling in main station list | Close the dialog, scroll/select the sibling in the left-panel station list (so user sees it in context, can play it via double-click or open editor manually). Lighter touch, but adds a click to actually do anything. | |
| Two actions per sibling: 'Edit' + 'Play' | Show a small row per sibling with two buttons — 'Edit' opens the sibling's edit dialog; 'Play' starts playback of the sibling. Most flexible, matches both halves of SC #2 'open the sibling's edit dialog or switch to playing it'. Slightly busier UI. | |
| Play sibling immediately | Close dialog, start playing sibling station. Discovery-oriented — matches 'switch to playing it' from SC #2. Loses the 'edit' affordance unless user reopens dialog from now-playing edit icon. | |

**User's choice:** Open sibling's edit dialog
**Notes:** Doesn't interrupt playback. SC #2 lists "open the sibling's edit dialog" as the canonical example.

---

## Unsaved-edits handling on sibling navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Discard silently | Same behavior as clicking the dialog's existing 'Discard' button — close current dialog without saving, open sibling's. Matches the dialog's existing modality (unsaved edits are also discarded if user clicks the X). Lowest friction. | |
| Confirm dialog: Save / Discard / Cancel | Pop a small confirmation if there are unsaved edits. Safer, but adds a step every navigation. The current dialog has no dirty-tracking infrastructure today — this would be new code. | ✓ |
| Block navigation until Save/Discard | Disable sibling clicks while dirty; tooltip says 'Save or discard first'. Strongest safety, slightly annoying for a common UX (navigating siblings while exploring). | |

**User's choice:** Confirm dialog: Save / Discard / Cancel
**Notes:** Introduces a dirty-tracking predicate as new code (`_is_dirty()`) — captured as D-12. Clean dialog navigates immediately with no confirm.

---

## UI placement

| Option | Description | Selected |
|--------|-------------|----------|
| New form row beneath URL/Provider | Add a 'Also on:' row in the existing QFormLayout, after Provider but before Tags. Inline with other station metadata, easy to discover, hidden entirely when there are no siblings (or non-AA station). | |
| Dedicated section above the Streams table | Visually separated section with its own header (e.g., 'Cross-Network Siblings'), separator line above. More prominent, treats siblings as a first-class concept rather than a metadata field. | |
| Bottom of dialog above the Save/Discard buttons | Stacked at the bottom — you scroll past everything to find related stations. Out of the way, doesn't interrupt the main edit flow. Easier to miss. | ✓ |
| Behind a 'Show Siblings' button | Add a button that opens a small popover/menu with sibling links. Cleanest empty-state (just no button, or disabled button), but adds a click to discover siblings. | |

**User's choice:** Bottom of dialog above the Save/Discard buttons
**Notes:** New widget inserted between the streams form and `outer.addWidget(self.button_box)` at `edit_station_dialog.py:376`. Hidden entirely when empty / non-AA.

---

## Visual rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text section with hyperlink-style clickable network names | Single line: 'Also on: ZenRadio • JazzRadio' where each network name is a clickable link (Qt label with href / clicked signal). Compact, matches the ROADMAP's 'Also on:' wording, reads like English. | ✓ |
| Vertical list of QPushButtons (one per sibling) | A QVBoxLayout of buttons labeled 'ZenRadio — Ambient', 'JazzRadio — Ambient'. More visually prominent, larger click targets. Takes more vertical space. | |
| Horizontal row of small chip-style buttons | Reuses the existing tag chip QSS pattern — small rounded buttons in a FlowLayout, one per sibling. Visually consistent with the tag chips above. Reads as 'tags' more than 'navigation'. | |
| Read-only QListWidget of clickable rows | Each row 'ZenRadio — Ambient' selectable + double-click activates. Familiar list affordance, but heavier widget for a typically small (1–5) item list. | |

**User's choice:** Plain text section with hyperlink-style clickable network names
**Notes:** Implementation: `QLabel` with inline HTML `<a href="sibling://{id}">ZenRadio</a>` separated by ` • `, `setOpenExternalLinks(False)`, `linkActivated` connected to navigation handler. Matches ROADMAP SC #1 example wording.

---

## Detection timing & storage

| Option | Description | Selected |
|--------|-------------|----------|
| Run every time the edit dialog opens | When you open Edit on an AA station, scan all stations in the library, derive each one's (network, channel_key) from its URL on the fly, list the ones that share a key but live on a different network. Always fresh — picks up stations you imported yesterday or hand-edited just now. No DB changes. With ~50–200 stations this scan is trivially fast. | ✓ |
| Compute once at import time, store in DB | Add an aa_channel_key column to the stations table. Fill it in during AudioAddict import. Re-derive whenever you save an edit that changes the URL. Slightly faster lookup, but means a schema migration plus a new code path that has to remember to re-derive on URL edits — easy to forget and let stale. | |

**User's choice:** Run every time the edit dialog opens
**Notes:** No DB schema change, no migration. The user surfaced confusion about how detection could work given DI.fm and ZenRadio URLs differ structurally — clarified that `_aa_channel_key_from_url` already strips the `_hi/_med/_low` suffix and the per-network prefix (`zr` for ZenRadio), so `prem1.di.fm/ambient_hi` and `prem4.zenradio.com/zrambient` both normalize to channel_key `"ambient"`.

---

## Claude's Discretion

- Where the sibling-list helper lives (private method on `EditStationDialog` vs free function in `url_helpers.py` / new module).
- Exact `QLabel` structure (single label with the full string vs `QHBoxLayout` with leading "Also on:" prefix label + a links label).
- Sort order: NETWORKS declaration order in `aa_import.py` (di → radiotunes → jazzradio → rockradio → classicalradio → zenradio).
- Sibling label text rule: just the network name when sibling station name matches current; `Network — SiblingName` when names differ (D-08).
- Empty-channel-key edge case (URL recognizably AA but unparseable): hide the section, no toast.
- The `MainWindow`-side method that handles `navigate_to_sibling` — the planner identifies the existing edit-dialog open call site(s) and routes through them.

## Deferred Ideas

- Surfacing siblings outside the edit dialog (Now Playing panel, station-list context menu, hamburger menu) — explicitly out of scope.
- Cross-network failover — explicitly rejected by SC #4. Would be its own future phase if revisited.
- Visual polish on the sibling section (animations, custom hover effects).
- Persisted `aa_channel_key` column — explicitly rejected (D-01) in favor of on-demand detection. Could be revisited as a perf optimization if library scale grows.
- Dirty-state tracking as a general dialog feature — D-12 introduces it only for sibling-nav interception; could be promoted to a general feature in a later phase if it proves useful elsewhere.

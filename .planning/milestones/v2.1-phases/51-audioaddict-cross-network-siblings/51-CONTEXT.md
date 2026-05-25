# Phase 51: AudioAddict Cross-Network Siblings — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user opens `EditStationDialog` for an AudioAddict station, the dialog surfaces other AA stations in the user's library that share the same channel key on a *different* AA network — e.g. while editing DI.fm "Ambient", the dialog shows that "Ambient" also exists on ZenRadio and JazzRadio. The user can click a sibling to navigate into that sibling's editor. Sibling detection is automatic (no manual tagging) and derived from the URL.

In scope:
- Detect AA siblings by deriving `(network_slug, channel_key)` from each station's first stream URL via the existing `_aa_slug_from_url` + `_aa_channel_key_from_url` helpers.
- Render siblings inline in `EditStationDialog`, with click-to-navigate to the sibling's editor.

Explicitly NOT in scope (per ROADMAP SC #4):
- Cross-network failover. Playing DI.fm Ambient must never auto-switch to ZenRadio Ambient. Sibling relationships are a navigation/discovery affordance only — Player.failover and the multi-stream model are untouched.
- Surfacing siblings outside `EditStationDialog` (Now Playing panel, station-list right-click menu, hamburger menu, etc.). Edit dialog only.
- Visual polish on the sibling list (animations, hover effects beyond default link styling).

</domain>

<decisions>
## Implementation Decisions

### Detection mechanism

- **D-01:** Detection runs **on demand at dialog open** — no DB schema change, no `aa_channel_key` column, no migration. When `EditStationDialog` opens for an AA station, the dialog scans `repo.list_stations()`, derives each station's `(slug, channel_key)` from its first stream URL via the existing helpers in `musicstreamer/url_helpers.py`, and filters to AA stations on a *different* network with the same channel_key. Library is ~50–200 stations — scan cost is trivial. Always fresh, no risk of stale derived data, no re-derivation pathway needed on URL edits.
- **D-02:** The "current station" half of the comparison uses the station's first stream URL (the one shown in `self.url_edit`, which `_populate` already sets from `streams[0].url`). All streams of a single AA station belong to the same channel on the same network — they're just different quality/PLS-fallback variants — so first-stream is sufficient and matches the existing pattern in `_LogoFetchWorker`.
- **D-03:** The sibling-half of the comparison also uses each candidate station's first stream URL (`streams[0].url`). Stations whose first URL fails to parse (no slug, or no channel key — e.g. a YouTube station, a Radio-Browser station, or a malformed AA URL that fails `_aa_channel_key_from_url`) are silently excluded. The current station itself is excluded by id from the candidate list.
- **D-04:** Sibling detection runs only when the station being edited is itself recognized as an AA station (`_is_aa_url(first_stream_url)` and `_aa_channel_key_from_url` both succeed). For non-AA stations, the sibling section is hidden entirely — no "no siblings" placeholder, no "AA only" message.

### UI placement

- **D-05:** The sibling list is rendered in a new section **at the bottom of the dialog, immediately above the `QDialogButtonBox`** (Save Station / Discard / Delete Station). Specifically: `outer.addWidget(self.button_box)` is preceded by a new `QHBoxLayout` or `QLabel` that hosts the "Also on:" line. Above the form/streams content rather than inline within the form, so it visually belongs to the dialog frame, not to the editable station fields.
- **D-06:** The section is hidden entirely (zero vertical space) when there are no siblings or when the station is not an AA station. No empty-state placeholder text.

### Visual rendering

- **D-07:** Sibling list is rendered as **plain text with hyperlink-style clickable network names** on a single line:
  ```
  Also on: ZenRadio • JazzRadio
  ```
  Implementation note: a `QLabel` with `setText(...)` containing inline HTML `<a href="...">ZenRadio</a>`-style links, separated by ` • ` (U+2022 BULLET surrounded by spaces). `setOpenExternalLinks(False)` and `linkActivated` signal connected to the navigation handler. The href can carry the sibling station id (e.g. `"sibling://{id}"`) which the slot parses.
- **D-08:** When the sibling station's display name (`Station.name` in the DB) matches the current station's name (the common case — they were imported via `fetch_channels_multi` from the same channel key, AA's API returns the same name across networks), the link text is just the network name. When the names differ (user-renamed sibling, or AA's API returned different display strings), the link text becomes `Network — SiblingName` so the user can tell which one they're navigating to. The decision lives in the rendering helper at construction time.

### Click action

- **D-09:** Clicking a sibling link **opens that sibling's `EditStationDialog`**. Concretely: the current dialog's `linkActivated` slot looks up the sibling Station by id, and emits a new signal (e.g. `navigate_to_sibling = Signal(int)`) that `MainWindow` (the owner of `EditStationDialog`) subscribes to. `MainWindow` closes the current dialog (via `accept()` if save-on-navigate is chosen, or `done(...)` for discard) and opens a fresh `EditStationDialog` for the sibling. Direct dialog instantiation from inside the dialog itself is avoided to keep dialog construction routed through `MainWindow` (which already manages dialog ownership and the play-guard/delete-guard plumbing).
- **D-10:** Sibling navigation does NOT change playback. If the user is currently playing a station, that playback continues regardless of which station's edit dialog they are in. Matches the existing semantics of opening any edit dialog today.

### Unsaved-edits handling on navigation

- **D-11:** When the user clicks a sibling and the current `EditStationDialog` has **unsaved changes**, a small confirmation dialog (`QMessageBox.question` with three buttons) intercepts the navigation:
  - **Save & continue** — runs the existing `_on_save` path; if save succeeds, navigates to the sibling. If save fails (validation error, etc.), stays in the current dialog.
  - **Discard & continue** — runs the existing `reject()` path's discard semantics, then navigates to the sibling.
  - **Cancel** — close the confirmation, stay in the current dialog with edits intact.
  When the dialog is **clean** (no unsaved changes), navigation proceeds immediately with no confirmation.
- **D-12:** Dirty-state tracking is new code — the existing `EditStationDialog` has no dirty flag today. Planner will introduce a dialog-level `_is_dirty()` predicate that compares the current form state against the populated state captured during `_populate`. Scope: name, URL, provider, tags, ICY, and the streams table contents. Planner picks the exact mechanism (snapshot-and-compare vs per-widget `textChanged` listeners). The "new station" placeholder lifecycle (`self._is_new` at line 200) is orthogonal to dirty tracking and is left untouched.

### Claude's Discretion

- The exact attribute name on `StationListPanel` / `MainWindow` that owns the sibling-navigation handler is the planner's call. Likely `MainWindow._open_edit_dialog(station)` or similar — there must already be one or two call sites for opening the edit dialog (tree double-click, now-playing edit icon).
- Whether the sibling-list helper lives on `EditStationDialog` directly or as a free function in `url_helpers.py` / a new `aa_siblings.py` module is the planner's call. The helpers it relies on (`_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`) are already in `url_helpers.py`.
- Empty-channel-key edge case: if the current station's channel_key is `None` (URL is recognizably AA but unparseable, e.g. malformed slug), treat as no siblings — hide the section. No error toast.
- The exact tag/structure of the sibling row's `QLabel` (whether it's wrapped in a `QHBoxLayout` with leading "Also on:" prefix label + a links label, or a single QLabel with the full string). Pick what reads cleanly in the dialog at typical dialog widths.
- Sort order of multiple siblings: prefer the `NETWORKS` declaration order in `aa_import.py` (di → radiotunes → jazzradio → rockradio → classicalradio → zenradio) so the layout is deterministic across opens.

</decisions>

<specifics>
## Specific Ideas

- The user's intuition that the URLs "don't exactly match" between networks is exactly why detection works on the *channel key*, not the URL — `_aa_channel_key_from_url` already strips the `_hi`/`_med`/`_low` quality suffix and the per-network URL prefix (e.g. ZenRadio's `zr` prefix in `_NETWORK_URL_PREFIXES`). Verified mapping for the user's two example URLs:
  - `http://prem1.di.fm:80/ambient_hi?<listen_key>` → `(slug="di", channel_key="ambient")`
  - `http://prem4.zenradio.com/zrambient?<listen_key>` → `(slug="zenradio", channel_key="ambient")`
  Both resolve to the same channel key — they are siblings.
- Sibling list reads as English ("Also on: ZenRadio • JazzRadio") — matches the wording in ROADMAP SC #1.
- Save/Discard/Cancel confirm on dirty navigation matches the user's mental model of "I'm in the middle of editing — don't silently throw it away".

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 51: AudioAddict Cross-Network Siblings" — goal, four success criteria (sibling list visible / clickable navigation / auto-derived from channel key / no cross-network failover).
- `.planning/REQUIREMENTS.md` §BUG-02 — the underlying bug requirement.
- `.planning/PROJECT.md` Key Decisions table — `_aa_channel_key_from_url` strips network slug prefix (Phase 17 decision); AA NETWORKS declaration order (di / radiotunes / jazzradio / rockradio / classicalradio / zenradio).

### Code touch points (load these to understand current state)

#### Channel-key extraction (no changes needed)
- `musicstreamer/url_helpers.py:15` — `_is_youtube_url(url)`.
- `musicstreamer/url_helpers.py:32` — `_is_aa_url(url)` — gates whether sibling detection runs at all.
- `musicstreamer/url_helpers.py:38` — `_aa_channel_key_from_url(url, slug=...)` — strips `_hi/_med/_low` and per-network URL prefix. Returns `None` on unparseable URLs.
- `musicstreamer/url_helpers.py:72` — `_aa_slug_from_url(url)` — resolves stream URL → AA network slug.
- `musicstreamer/url_helpers.py:21` — `_AA_STREAM_DOMAINS` set (6 AA domains).
- `musicstreamer/url_helpers.py:27` — `_NETWORK_URL_PREFIXES` (currently only `{"zenradio": "zr"}`).

#### AA network catalog (read-only reference)
- `musicstreamer/aa_import.py:87` — `NETWORKS` constant (6 entries with `slug`, `domain`, `name`).

#### Edit dialog (the surface where siblings appear)
- `musicstreamer/ui_qt/edit_station_dialog.py:184` — `EditStationDialog` class.
- `musicstreamer/ui_qt/edit_station_dialog.py:209` — `__init__` calls `_build_ui()` then `_populate()`.
- `musicstreamer/ui_qt/edit_station_dialog.py:219–376` — `_build_ui` — `outer = QVBoxLayout(self)`, ends with `outer.addWidget(self.button_box)` at line 376. The new sibling section goes immediately before that line.
- `musicstreamer/ui_qt/edit_station_dialog.py:382–415` — `_populate` — reads `streams = self._repo.list_streams(station.id)` and `self.url_edit.setText(streams[0].url)`. Sibling detection should run here using the same first-stream URL.
- `musicstreamer/ui_qt/edit_station_dialog.py:362–376` — `QDialogButtonBox` setup (Save / Discard / Delete + signals).
- `musicstreamer/ui_qt/edit_station_dialog.py:53–120` — `_LogoFetchWorker` — precedent for "derive AA slug + channel_key from URL inside the dialog".

#### Repo (data source for sibling scan)
- `musicstreamer/repo.py:225` — `Repo.list_stations()` — returns `List[Station]` with `streams=self.list_streams(...)` already populated. The sibling detection iterates this list once.
- `musicstreamer/repo.py:176` — `Repo.list_streams(station_id)` — already called transitively by `list_stations`; sibling code only needs the first stream's URL per station.

#### Dialog ownership (where to wire the navigation signal)
- `musicstreamer/ui_qt/main_window.py` — `MainWindow` is the owner of `EditStationDialog` instances. Planner identifies the existing edit-dialog open/close site(s) and wires the new `navigate_to_sibling` signal there.

### Project conventions (apply during planning)
- Bound-method signal connections, no self-capturing lambdas (QA-05) — applies to any new `linkActivated` / `navigate_to_sibling` connections.
- Qt.PlainText for any name-derived text rendered into Qt widgets (T-39-01) — sibling network names and station names must be rendered as plain text, not Pango/HTML markup, except for the inline `<a>` tags explicitly emitted by the sibling-renderer for hyperlink behavior.
- Phase 39 `_aa_channel_key_from_url` strips network slug prefix — already verified working against `prem1.zenradio.com/zrambient`-style URLs.
- "Cross-network failover is NOT introduced" is an explicit non-goal (SC #4) — planner must not modify `Player.failover` or any of the multi-stream / failover queue plumbing.

### No external specs
No ADRs or external design docs referenced — the bug is fully captured by the four success criteria in ROADMAP.md plus the touch points above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`_aa_channel_key_from_url(url, slug=...)`** — already does the exact normalization needed: strips `_hi/_med/_low` quality suffix and per-network URL prefix (`zr` for ZenRadio). Returns the bare channel key that matches the AA API's `ch["key"]` field.
- **`_aa_slug_from_url(url)`** — derives network slug from stream URL domain.
- **`_is_aa_url(url)`** — fast gate to skip non-AA stations entirely.
- **`Repo.list_stations()`** — returns all stations with provider name and stream rows already populated; the sibling scan needs no new query.
- **`NETWORKS` (in `aa_import.py`)** — for sort-order and slug→display-name mapping (e.g. `slug="zenradio"` → `name="ZenRadio"`).
- **`QDialogButtonBox`-style label-with-link** — `QLabel.linkActivated` signal + `setOpenExternalLinks(False)` is the established Qt idiom for inline clickable links inside dialogs (no precedent in this codebase yet, but a one-liner).
- **`_LogoFetchWorker`** — precedent for "given the URL field's text, derive AA slug + channel_key inside the dialog and act on it." Same pattern, different action.

### Established Patterns
- **First-stream-URL convention** — `_populate` already treats `streams[0].url` as the canonical URL for the station (line 391). All AA-related URL classification in this codebase uses `streams[0].url` (or the equivalent in import paths).
- **Signal-out from dialog → MainWindow** — `EditStationDialog` already emits `station_saved` and `station_deleted(int)` signals that `MainWindow` subscribes to. The new `navigate_to_sibling(int)` signal follows the same pattern.
- **Hidden-when-empty form sections** — the dialog already conditionally hides UI based on station type (delete-button enabled state, logo classification messages). Hiding the sibling section for non-AA / no-sibling states is consistent.
- **Bound-method connections** — QA-05 — applies to all the new connections introduced by this phase.

### Integration Points
- **New layout slot** — between `outer.addLayout(form)` (form ends with the streams table) and `outer.addWidget(self.button_box)` at `edit_station_dialog.py:376`. New sibling-list widget inserted here.
- **New signal** — `EditStationDialog.navigate_to_sibling = Signal(int)` (sibling station id). Wired in `MainWindow` to close the current edit dialog and open a fresh one for the sibling.
- **New helper** — sibling-list construction (rendering "Also on: ZenRadio • JazzRadio" with `<a>` links) called from `_populate` after the existing logo refresh. Either a private method on the dialog or a free function in `url_helpers.py` / a new module — planner's call.
- **New dirty-state predicate** — `EditStationDialog._is_dirty()` (or equivalent) to gate the Save/Discard/Cancel confirm. Planner picks snapshot-vs-compare or per-widget listener.

</code_context>

<deferred>
## Deferred Ideas

- **Surfacing siblings outside the edit dialog** (Now Playing panel "Also on:" row, station-list right-click context menu, hamburger menu) — explicitly out of scope per ROADMAP. Could be a future polish phase if Kyle wants it.
- **Cross-network failover** — explicitly rejected by SC #4 for this phase. If it ever comes up later, it would be a separate phase that touches `Player.failover` and the multi-stream queue, with its own UX decisions about user intent (curated single-network vs cross-network discovery).
- **Visual polish on the sibling section** — animations, hover effects beyond default Qt link styling, custom theming. Not requested.
- **Persisted `aa_channel_key` column on stations** — explicitly rejected (D-01) in favor of on-demand detection. If the library ever grows beyond a few hundred stations and the scan becomes noticeable, this could be revisited as a perf optimization.
- **Dirty-state tracking as a general dialog feature** — D-12 introduces dirty tracking only for the sibling-navigation interception. If dirty tracking turns out to be useful for other paths (e.g. close-window confirm, accidental Discard), it could be promoted to a general feature in a later phase.

</deferred>

---

*Phase: 51-audioaddict-cross-network-siblings*
*Context gathered: 2026-04-28*

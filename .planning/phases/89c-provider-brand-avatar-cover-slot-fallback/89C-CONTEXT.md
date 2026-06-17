# Phase 89c: Provider Brand-Avatar Cover-Slot Fallback - Context

**Gathered:** 2026-06-17
**Status:** Ready for planning

<domain>
## Phase Boundary

When per-track cover-art resolution is **exhausted** for an ICY-metadata provider whose
track art frequently misses (SomaFM, AudioAddict networks), the now-playing **cover slot**
renders a distinct **provider brand avatar** (circular crop) instead of duplicating the
station logo already shown in the left logo slot (the Drone Zone duplicate-logo complaint).

The trigger is **cover-resolution-exhausted** — the `if not path:` fallback branch in
`now_playing_panel._on_cover_art_ready` (real line ~2183, currently calls
`_show_station_logo_in_cover_slot()`) — **NOT `icy_disabled`**. This is the defining
difference from Phase 89/89b, which swap on `icy_disabled` inside `bind_station`.

Delivers ART-AVATAR-11, ART-AVATAR-12.

**Out of scope:** the YouTube/Twitch `icy_disabled` channel-avatar swap (Phase 89/89b/89.1 —
already shipped); GBS.FM (excluded by intent); a central "manage all providers" screen.

</domain>

<decisions>
## Implementation Decisions

### Registry & granularity *(discussed)*
- **D-01:** A brand-avatar registry keyed on the **exact `provider_name`** string. Registered
  providers: **SomaFM** (`provider_name == "SomaFM"`, from `soma_import.py:306`) plus **all 6
  AudioAddict networks** — exact names from `aa_import.py:106-111`: `DI.fm`, `RadioTunes`,
  `JazzRadio`, `RockRadio`, `ClassicalRadio`, `ZenRadio`. **GBS.FM is NOT registered**
  (ART-AVATAR-11 exclusion — the duplicated logo is goofy-but-on-brand for GBS).
- **D-02:** **Per-network granularity** — each of the 6 AudioAddict networks gets its **own
  distinct mark**, not one shared "AudioAddict" logo. **7 brand avatars total** (1 SomaFM + 6 AA).
  Rationale: each AA network has its own recognizable identity; per-network reads intentional.

### Asset format, sourcing & bundling *(discussed)*
- **D-03:** Assets are **pre-composed circular PNGs** — the brand mark is already centered on a
  circular (brand-colored or transparent) background designed to fit the circle. NOT square
  wordmark logos center-cropped at runtime (which would clip edges/text).
- **D-04:** **The user supplies the final PNGs.** The phase ships the **full plumbing** (registry,
  render path, resolution, upload override) with the **7 expected filename slots**; until a given
  PNG is present, that provider **falls through to current station-logo behavior** — graceful
  missing-asset, no crash, no broken-image placeholder. Wiring lands now; images land as the user
  provides them (or via the D-09 upload override).
- **D-05:** Bundled as **loose package data** — `musicstreamer/ui_qt/brand-avatars/<key>.png`,
  loaded by path via `importlib.resources`; added to the PyInstaller `datas`. Dropping in or
  updating an image needs **no qrc recompile** (rejected the `.qrc` route for iteration friction).
  Planner: confirm the PyInstaller spec includes this dir so frozen builds bundle the PNGs
  (cf. memory: frozen-build env silently missing runtime components).

### Visual treatment *(discussed)*
- **D-06:** Circular render **reuses Phase 89 `_make_circular_pixmap`** (`now_playing_panel.py:219`)
  as a safe mask over the pre-composed circular PNG — full mark visible, center-crop is effectively
  a no-op because the source already fits the circle. No border/ring, antialiased edge (Phase 89 D-06).

### Trigger & precedence *(discussed + locked by requirements)*
- **D-07:** Trigger is the **cover-resolution-exhausted** `if not path:` branch in
  `_on_cover_art_ready` (~L2183) — the same branch that currently calls
  `_show_station_logo_in_cover_slot()`. A **source-grep drift-guard** pins that the brand lookup
  fires **only on this branch, after iTunes/MB-CAA**, never in `fetch_cover_art`'s auto-dispatch
  chain (would short-circuit Phase 73 MB-CAA per-track coverage). ART-AVATAR-12 / success criterion 5.
- **D-08:** **Resolution precedence at the exhausted branch:**
  1. **User override** — `station.provider_avatar_path` (the 89.1 per-provider column, **dormant**
     for these ICY-enabled providers because `bind_station`'s `icy_disabled` swap never fires for
     them) if set and the file exists on disk →
  2. **Bundled brand registry** match on `provider_name` (D-01) →
  3. existing `_show_station_logo_in_cover_slot()` fallback.
  Providers with neither keep current behavior (station logo → generic icon) — **no regression**
  (success criterion 4).

### Upload override — folded in *(discussed)*
- **D-09:** The user can supply/override a provider brand image via **`EditStationDialog`, for ANY
  provider**. A "Choose brand image…" picker in the existing avatar preview area writes the chosen
  image to the **provider-keyed avatar file** (reuse `assets.write_provider_avatar`, 89.1 D-10) and
  persists `providers.avatar_path` via the **non-silent-reset** `update_provider_avatar_path`
  (89.1 D-09 / Pitfall 5). This **overrides the bundled mark** (D-08 step 1) and also covers
  providers with **no bundled asset**.
- **D-09a (planner must resolve):** `providers.avatar_path` already holds the **YouTube/Twitch
  channel avatar** for `icy_disabled` providers (89/89.1). A given provider is **either** a YT/Twitch
  channel **or** an ICY brand provider, so there is no row-level collision — but the
  `EditStationDialog` avatar UI must keep the two semantics from fighting: **auto-fetch-on-URL**
  (YT/Twitch channel avatar) vs **manual brand-image pick** (this phase). Planner: confirm the
  dialog distinguishes them (gating by detected provider type) so a manual brand pick is not
  clobbered by the debounced auto-fetch and vice-versa.

### Re-trigger behavior *(discussed)*
- **D-10:** The brand avatar is **transient per cover-resolution**. A later track that resolves a
  real cover (iTunes/MB) replaces it via `_set_cover_pixmap`; the next miss re-shows the brand
  avatar. **Real art always wins** — matches existing `_show_station_logo_in_cover_slot` semantics.
  Not sticky.

### Render-state / tier-replay *(Claude's discretion — grounded in Phase 89 patterns)*
- **D-11:** Use a **new tracked state var** (e.g. `_last_brand_avatar`) holding the resolved
  package-data source — do **NOT** reuse `_last_avatar_path` / `_set_avatar_pixmap_from_path`,
  which join `paths.data_dir()` (the user override in D-08 step 1 IS a data_dir-relative path, but
  the bundled registry source is package data). Add a sibling render method and a **4th branch** in
  `_apply_art_tier` (~L2125), preserving precedence: real cover (`_last_cover_path`) > icy_disabled
  circular avatar (`_last_avatar_path`) > **brand avatar (`_last_brand_avatar`)** > station logo.
  These ICY providers are not `icy_disabled` (so `_last_avatar_path` is None for them — no
  collision), but the ordering keeps it safe. **Reset the brand var on `bind_station`** (stale-
  station bleed guard, Pitfall 4 / T-89-12) and whenever a real-cover or logo path is taken.

### Drift-guards *(locked by requirements)*
- **D-12:** Source-grep drift-guard (mirroring ART-AVATAR-09 / `test_mb_caa_runs_before_channel_avatar`)
  pins the brand-avatar lookup is invoked **only from the resolution-exhausted branch**, after the
  iTunes/MB-CAA tiers. **Source-grep over behavioral mocks** (`feedback_gstreamer_mock_blind_spot`).

### Claude's Discretion
- Registry module shape — a dedicated `brand_avatars.py` with `lookup(provider_name) -> Optional[path]`
  mirroring `yt_import`'s `register_avatar_fetcher`/`get_avatar_fetcher` registry (testable,
  grep-friendly) vs an inline dict. Lean toward the dedicated module.
- Exact tracked-var naming, sibling render-method name/placement.
- The `brand-avatars/` filename-key scheme (e.g. slug per provider_name) and the `provider_name`→key
  normalization.
- `EditStationDialog` "Choose brand image…" picker layout within the existing avatar area.

</decisions>

<specifics>
## Specific Ideas

- The duplicate-logo complaint is concrete: a **SomaFM Drone Zone** station shows the same channel
  image in both the left logo slot and the cover-slot fallback. The brand avatar must be the
  **provider/network mark** (distinct from the channel-specific `station_art_path`), which is why
  the registry keys on `provider_name`, not station.
- Mirror Phase 89 / 89.1 patterns rather than inventing: `_make_circular_pixmap` for the crop,
  `write_provider_avatar` + `update_provider_avatar_path` (non-silent-reset) for the override,
  source-grep drift-guards for precedence. Research flag is **NO** — no new network fetch.
- Phase ships plumbing-first; the 7 PNGs arrive from the user (D-04). Missing asset === current
  behavior, so shipping before all images exist is safe.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` §ART-AVATAR (lines ~87-88) — **ART-AVATAR-11** (provider-keyed brand
  registry, bundled assets not per-station fetch, GBS.FM excluded) and **ART-AVATAR-12**
  (resolution-exhausted trigger NOT `icy_disabled`; circular crop; no regression for unregistered
  providers).
- `.planning/ROADMAP.md` §"Phase 89c (INSERTED): Provider Brand-Avatar Cover-Slot Fallback"
  (lines ~383-398) — Goal, Depends-on (Phase 89), and the 5 Success Criteria.

### Prior-phase context (mechanisms reused)
- `.planning/phases/89-youtube-channel-avatar-fetch-cover-slot-swap/89-CONTEXT.md` — D-05/D-06
  (separate circular avatar render path; `_make_circular_pixmap`; no-border antialiased), D-14
  (`_mb_caa_lookup`/`_channel_avatar_lookup` precedence + source-grep drift-guard pattern), the
  tier-replay (`_apply_art_tier`) machinery this phase extends.
- `.planning/phases/89.1-re-key-channel-avatar-from-per-station-to-per-provider-chann/89.1-CONTEXT.md`
  — D-05 (`_channel_avatar_lookup` reads `provider_avatar_path`), D-09 (`update_provider_avatar_path`
  non-silent-reset persist), D-10 (`write_provider_avatar`, `assets/channel-avatars/{provider_id}.png`,
  data_dir-relative). The `providers.avatar_path` column reused as the D-08/D-09 override channel.

### Code precedent (read before implementing)
- `musicstreamer/ui_qt/now_playing_panel.py` — `_on_cover_art_ready` (~L2172, the `if not path:`
  branch ~L2183 = the TRIGGER), `_show_station_logo_in_cover_slot` (~L2267, the path being replaced),
  `_make_circular_pixmap` (L219, the circular render), `_set_avatar_pixmap_from_path` /
  `_last_avatar_path` (~L2206 — the icy_disabled analog; do NOT reuse, it joins data_dir),
  `_apply_art_tier` (~L2115, add the 4th brand branch), `bind_station` (~L909, reset brand var here).
- `musicstreamer/cover_art.py` — `fetch_cover_art` (~L190, precedence dispatch), `_mb_caa_lookup`
  (~L147) / `_channel_avatar_lookup` (~L159) — the named-function + source-grep drift-guard template
  (D-12).
- `musicstreamer/aa_import.py` — `NETWORKS` list (L106-111, the 6 exact AA `provider_name` strings);
  `provider_name=ch["provider"]` (~L223).
- `musicstreamer/soma_import.py` — `provider_name="SomaFM"` literal (~L306, D-02 note: CamelCase, no period).
- `musicstreamer/assets.py` — `write_provider_avatar(provider_id, data)` (~L63, atomic
  `mkstemp`+`os.replace`, data_dir-relative return) for the D-09 upload override.
- `musicstreamer/repo.py` — `update_provider_avatar_path` / `providers.avatar_path` (89.1 persist
  path); `LEFT JOIN providers ... p.avatar_path AS provider_avatar_path` mappers (~L644/685/795/914).
- `musicstreamer/ui_qt/edit_station_dialog.py` — avatar preview / `_AvatarFetchWorker` /
  `_on_refresh_avatar_clicked` (~L168/502) — where the D-09 "Choose brand image…" picker attaches
  and where the auto-fetch-vs-manual-pick distinction (D-09a) must be enforced.
- `musicstreamer/ui_qt/icons.qrc` + `icons_rc.py` + `from musicstreamer.ui_qt import icons_rc` —
  the bundled-asset precedent **rejected** for iteration friction (D-05 chose loose package data),
  but read it to mirror PyInstaller `datas` registration.
- `musicstreamer/paths.py` — `channel_avatars_dir()` accessor (provider-override files live here).

### Spike findings
- `Skill("spike-findings-musicstreamer")` — load for PyInstaller asset-bundling / Qt threading /
  frozen-build pitfalls (D-05 PyInstaller `datas` for the new `brand-avatars/` dir).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `now_playing_panel._make_circular_pixmap(source, size)` (L219) — the exact circular mask; brand
  PNGs (pre-composed circular, D-03) pass through it cleanly.
- `now_playing_panel._apply_art_tier` (~L2115) + `_last_cover_path`/`_last_avatar_path` — the
  tier-replay state machine; add a parallel `_last_brand_avatar` branch (D-11).
- `assets.write_provider_avatar` + `repo.update_provider_avatar_path` (89.1) — the atomic,
  non-silent-reset persist path for the D-09 upload override; zero new persistence code.
- `cover_art._mb_caa_lookup`/`_channel_avatar_lookup` named-function + source-grep drift-guard
  pattern (89 D-14) — the template for the D-12 brand-lookup placement guard.
- `yt_import.register_avatar_fetcher`/`get_avatar_fetcher` (~L269/278) — the registry-by-provider
  pattern to mirror for the brand-avatar `lookup(provider_name)` module (Claude's discretion).

### Established Patterns
- **Resolution-exhausted fallback branch** (`if not path:` in `_on_cover_art_ready`) is the single
  hook point — keeps the trigger structurally distinct from the `icy_disabled` swap (D-07).
- **Tier-change replay**: any new cover-slot render path must participate in `_apply_art_tier` or it
  won't survive a panel resize (D-11).
- **Stale-station bleed guard** (Pitfall 4): reset per-station/provider render state at the top of
  `bind_station` (D-11).
- **Non-silent-reset persist** (Pitfall 5): provider avatar writes go through the dedicated
  single-column update, never a broad save (D-09).
- **Source-grep drift-guards over behavioral mocks** (`feedback_gstreamer_mock_blind_spot`) for
  precedence/ordering (D-12).
- **Loose package data + PyInstaller `datas`** for shippable images (D-05) — verify frozen builds
  include the dir (frozen-build-env-missing-runtime-components memory).

### Integration Points
- `musicstreamer/ui_qt/brand-avatars/` — new loose-PNG asset dir (D-05).
- new `brand_avatars.py` (or equivalent) — `lookup(provider_name) -> Optional[path]` registry (D-01).
- `now_playing_panel._on_cover_art_ready` `if not path:` branch — insert override→registry→logo
  resolution (D-07/D-08); new render method + `_last_brand_avatar` + `_apply_art_tier` branch (D-11).
- `edit_station_dialog.py` — "Choose brand image…" picker + auto-fetch-vs-manual distinction (D-09/D-09a).
- PyInstaller spec — add `brand-avatars/` to `datas` (D-05).

</code_context>

<deferred>
## Deferred Ideas

- **Additional ICY providers** in the brand registry beyond SomaFM/AA — future registry entries
  (just add provider_name→PNG), not this phase.
- **Central "manage all providers" screen** — rejected in favor of the per-station `EditStationDialog`
  picker (D-09); a dedicated providers-management UI is its own future surface.
- **Claude auto-sourcing official brand marks** — rejected for this phase (user provides PNGs, D-04);
  could revisit if the user wants bootstrap placeholders.

</deferred>

---

*Phase: 89c-provider-brand-avatar-cover-slot-fallback*
*Context gathered: 2026-06-17*

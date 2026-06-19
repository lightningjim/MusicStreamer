# Phase 95: YT URL-change replay bug — Research

**Researched:** 2026-06-18
**Domain:** PySide6/Qt UI ↔ GStreamer Player state invalidation; edit→playback wiring; cross-thread (daemon worker) resolution race
**Confidence:** HIGH (all claims verified against live code with file:line citations; no external library lookup needed — this is an in-codebase bug fix)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** When the user saves an edit to the URL of the station that is **currently playing**, the player restarts **immediately** on the new URL — stop the old stream, re-resolve, and play the new URL. The user should hear the new stream right after saving, with no second play required. Primary user-facing fix.
- **D-02:** The immediate restart fires **only when the URL of the currently-playing stream actually changed**. Metadata-only edits (label, quality, codec, bitrate, etc.) on the playing stream must NOT interrupt audio. Compare the edited stream's saved URL against what is currently loaded; restart only on a real URL change.
- **D-03:** The fix must invalidate the `Player`'s cached stream state on stream edit, not just the now-playing panel. After an edit, the player must never serve a stale resolved URL or a stale `_streams_queue` entry for the edited stream. The "first play exhausts, second play works" asymmetry must be gone: the first play after an edit uses the saved URL.
- **D-04:** For multi-stream stations: trigger the immediate restart (D-01) only when the **currently-playing** stream's URL changed. If a *different* (non-playing) stream in the same station is edited, do not interrupt current audio — just invalidate the player's queue so subsequent failover uses fresh URLs.
- **D-05:** When a station that is **not** currently playing is edited, there is no audio to interrupt; the requirement is that the **next** `play()` rebuilds from fresh DB state (no stale `_streams_queue` / playbin3 URI carried over). Pressing play after editing must always use the saved URL.

### Claude's Discretion
- Exact invalidation mechanism (`Player.bind_station()`/queue-reset method vs. clearing resolved-URL/playbin3 state vs. re-issuing `play()`).
- The precise URL-comparison normalization.
- Where the restart is wired (edit-save handler vs. `_sync_now_playing_station`).
- Generic-vs-YouTube preference: prefer a **generic** invalidation over a YouTube special-case (the observable bug is YouTube, but the stale-state mechanism is generic).

### Deferred Ideas (OUT OF SCOPE)
- None new. The two reviewed todos (PLS codec/bitrate URL fallback — Phase 92; docker daemon probe) are explicitly unrelated and out of scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

This phase has **no mapped REQ-IDs** in `.planning/REQUIREMENTS.md` (per task brief). The behavior contract is the D-01..D-05 decisions above, which serve as the de facto requirement set. The planner should map plan must-haves to D-NN citations (per MEMORY note: decision-coverage gate scans must_haves only).
</phase_requirements>

## Summary

This is a **bug fix entirely within the existing codebase** — no new libraries, no version research. The root cause in CONTEXT.md is confirmed by code: on save, `EditStationDialog._on_save()` (`edit_station_dialog.py:1713`) persists stream URLs via `repo.update_stream(...)` (line 1814) then emits `station_saved` (line 1838). `MainWindow._on_edit_requested` wires `station_saved → _sync_now_playing_station(fresh.id)` (`main_window.py:1341`). `_sync_now_playing_station` (`main_window.py:1430`) re-fetches the station and calls `now_playing.bind_station(updated_station)` (line 1442) **only if the panel is bound to that station** — it refreshes the *panel* and **never touches `self._player`**. The Player's `_streams_queue`, `_current_stream`, and the URI already loaded into playbin3 are all untouched by an edit.

The "stream exhausted" symptom (`main_window.py:909`, emitted from `_on_failover(None)`) surfaces because the next playback action consumes a stale stream whose loaded pipeline is at/near EOS — `Player._try_next_stream` (`player.py:1440`) finds an empty/stale `_streams_queue` and `failover.emit(None)`. The "second play works" asymmetry is because the second action is a full `Player.play(fresh_station)` (`player.py:674`) that rebuilds `_streams_queue` from `station.streams` via `order_streams()` (line 714) — the rebuild path the fix should reuse (CONTEXT Reusable Assets).

The critical hazard is the **in-flight YouTube resolution race**: `_youtube_resolve_worker` (`player.py:1872`) runs on a bare `threading.Thread(daemon=True)` (line 1868) and marshals back via the queued `youtube_resolved` signal → `_on_youtube_resolved` → `_set_uri` (`player.py:1957`). Unlike the SomaFM preroll path (which has a `_preroll_seq` generation counter, `player.py:583`/`1544`), **the YouTube resolve path has no generation guard**. If the user edits the URL while a resolution is in flight, the stale worker can complete *after* the restart and call `_set_uri` with the OLD resolved URL, clobbering the new playback. The fix must defend against this.

**Primary recommendation:** Add a generic `Player.invalidate_for_edit(station)` (or `reload_station(station)`) main-thread method that (1) detects whether the currently-playing stream's URL changed by comparing `Player._current_stream` (matched by `stream.id`) against the freshly-fetched station's stream of the same id, (2) if the *playing* stream's URL changed and the player is actively playing → re-issue the existing `play(fresh_station)` rebuild path (D-01); (3) if a non-playing stream changed or the player is idle → clear `_streams_queue` / `_current_stream` so the next `play()` rebuilds fresh (D-04/D-05); (4) bump a new YouTube resolve-generation counter (mirroring `_preroll_seq`) so any in-flight resolution that completes after the edit no-ops. Wire it from `MainWindow._sync_now_playing_station` (the existing edit→player junction) alongside the panel rebind, passing the already-fetched `updated_station`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Detect "currently-playing stream URL changed" | Player (`player.py`) | MainWindow wiring | Player owns `_current_stream`/`_current_station_id`; only it knows the loaded URL. MainWindow has the fresh DB station + knows panel binding. |
| Invalidate stale `_streams_queue` / loaded URI | Player | — | `_streams_queue`, `_current_stream`, playbin3 URI are all Player-internal state. |
| Guard in-flight YouTube resolution | Player | — | The daemon worker and `youtube_resolved` signal are Player-internal; the generation counter lives with `_preroll_seq` siblings. |
| Trigger the restart/invalidation on save | MainWindow (`_sync_now_playing_station`) | EditStationDialog (`station_saved` emit) | Existing edit→player junction; single source of truth for "edit committed" already lives here (panel rebind). Adding the player call here keeps wiring co-located. |
| Persist new URL | Repo (`update_stream`) | EditStationDialog | Unchanged; already correct. |
| Show "stream exhausted" toast | MainWindow (`_on_failover`) | — | Existing; the fix should make this NOT fire on first-play-after-edit. |

## Standard Stack

No new packages. This phase touches only existing first-party modules. Confirmed present and imported:

| Module | Role in fix | Key symbols (file:line) |
|--------|-------------|-------------------------|
| `musicstreamer/player.py` | Owns all stale state; gets the new invalidation method + YT resolve-generation guard | `play()` 674; `play_stream()` 822; `pause()` 834; `stop()` 864; `_try_next_stream()` 1440; `_set_uri()` 1502; `_play_youtube()` 1856; `_youtube_resolve_worker()` 1872; `_on_youtube_resolved()` 1957; `_current_stream` 563/634; `_current_station_id` 591; `_streams_queue` 562 |
| `musicstreamer/ui_qt/main_window.py` | Wires save → player invalidation | `_on_edit_requested()` 1332; `_sync_now_playing_station()` 1430; `_on_failover()` 906 |
| `musicstreamer/ui_qt/edit_station_dialog.py` | Emits `station_saved` after persist | `_on_save()` 1713; `station_saved` Signal 318; `repo.update_stream` call 1814 |
| `musicstreamer/ui_qt/now_playing_panel.py` | Existing rebind analog | `bind_station()` 966; `current_station` 957; `is_playing` 961; `_station` 327 |
| `musicstreamer/models.py` | `Station`/`StationStream` dataclasses | `StationStream.id/station_id/url` 12-23; `Station.streams` 37 |
| `musicstreamer/repo.py` | Re-fetch + ordering | `get_station()`; `list_streams()` 490 (ORDER BY position); `update_stream()` 564 |
| `musicstreamer/stream_ordering.py` | Failover ordering | `order_streams()` 46 |

**Package Legitimacy Audit:** Not applicable — no external packages are installed or added in this phase. (Slopcheck gate skipped: zero new dependencies.)

### Installation
None.

## Architecture Patterns

### System Architecture Diagram (current edit→playback flow)

```
User edits URL in EditStationDialog
        │
        ▼
EditStationDialog._on_save()                       edit_station_dialog.py:1713
   ├─ repo.update_station(...)                      (metadata)            :1764
   ├─ for row: repo.update_stream(stream_id, url…)  (PERSISTS NEW URL)    :1814
   ├─ repo.prune_streams / reorder_streams                                :1834
   └─ self.station_saved.emit() ──────────────┐                          :1838
                                               │
                                               ▼
MainWindow (connected in _on_edit_requested)  main_window.py:1340-1341
   ├─ station_saved → _refresh_station_list()                            :1340
   └─ station_saved → _sync_now_playing_station(fresh.id) ──┐            :1341
                                                             │
                                                             ▼
   _sync_now_playing_station(station_id)                    main_window.py:1430
   ├─ updated = repo.get_station(station_id)                              :1437
   ├─ current = now_playing._station                                     :1440
   └─ if current.id == updated.id:
          now_playing.bind_station(updated)   ← PANEL ONLY (the gap)     :1442
                                               ✗ Player is NEVER notified

──────────────── Player still holds STALE state ────────────────
Player._streams_queue (old)   Player._current_stream (old url)   playbin3 uri (old, at EOS)

Next play / failover:
   _try_next_stream()  → empty/stale queue → failover.emit(None)         player.py:1452
        │
        ▼
   MainWindow._on_failover(None) → show_toast("Stream exhausted")        main_window.py:909
```

### YouTube resolution thread model (the race surface)

```
_try_next_stream() [main]  →  _play_youtube(url) [main]                  player.py:1493,1856
        │
        ├─ pipeline → NULL (sync)                                        :1863
        └─ threading.Thread(target=_youtube_resolve_worker, daemon=True) :1868
                    │  [DAEMON WORKER THREAD — blocking yt-dlp extract_info]
                    │
                    ├─ youtube_resolved.emit(resolved, is_live) ─────┐   :1953
                    └─ youtube_resolution_failed.emit(msg) ──────────┤   :1941/1955
                                                                     │ (QueuedConnection → main)
                                                                     ▼
                    _on_youtube_resolved(url, is_live) [main]  → _set_uri(url)   player.py:1957/1967
                                          ▲
                                          └── NO _preroll_seq-style generation guard here.
                                              A resolution started BEFORE an edit can land
                                              its OLD url AFTER the restart. (Pitfall 1)
```

### Pattern 1: Generic player-side invalidation method (recommended)

**What:** A single main-thread `Player` method the UI calls after an edit commits. It owns the decision tree D-01..D-05 and the queue/URI invalidation. Generic across stream types (D-04 / Specifics): URL-change detection is type-agnostic; only the resolve-generation guard is YouTube-specific because only YouTube has an async resolver.

**When to use:** Called from `MainWindow._sync_now_playing_station` after `repo.get_station`, in addition to the existing panel rebind.

**Decision tree (verified against current state lifecycle):**
- "Currently playing this station?" — compare `Player._current_station_id` (set in `play()` at `player.py:701`, zeroed by `play_stream` at :828 but **NOT cleared by pause()/stop()**) against `updated_station.id`. NOTE: `_current_station_id`/`_current_stream` survive `stop()`/`pause()` (verified: neither method clears them — only `_streams_queue` is cleared at :853/:874). So `_current_station_id == updated.id` does NOT by itself prove audio is live. Pair it with the **panel's** `now_playing.is_playing` (`now_playing_panel.py:961`) — which the existing `_sync_now_playing_station` already has access to via `self.now_playing` — to distinguish "actively playing" (D-01 restart) from "idle/paused/stopped" (D-05 invalidate-only).
- "Did the *playing* stream's URL change?" — identify the playing stream via `Player._current_stream.id` (a `StationStream`, `player.py:1455`). Find the matching stream in `updated_station.streams` by `id`. Compare URLs (normalized — see below). D-02: restart only on a real URL change.
- "URL changed AND actively playing this station" → D-01: re-issue `self.play(updated_station, …)`. This reuses the proven rebuild path (`play()` rebuilds `_streams_queue`, resets `_is_first_attempt`, etc.). Re-using `play()` is strongly preferred over hand-building a partial reset.
- "URL changed but a *non-playing* stream, OR not actively playing" → D-04/D-05: clear `_streams_queue = []` and `_current_stream = None` (and bump the YT resolve generation) so the next `play()` rebuilds fresh. Do NOT call `set_state(NULL)` if audio is live for a non-playing-stream edit (D-04: don't interrupt).

**URL comparison normalization (Discretion):** The codebase has `aa_normalize_stream_url` (imported in `player.py:57`, applied at `_set_uri` :1503 for DI.fm HTTPS→HTTP). For the *edit-change* comparison, the safest minimal choice is to compare the **stored stream URL** (`StationStream.url`) old-vs-new, NOT the resolved playbin3 URI. Rationale: for YouTube the loaded playbin3 URI is the *resolved* dynamic HLS URL, which differs from the stored `youtube.com/...` URL on every resolution — comparing resolved URIs would always report "changed." Compare the persisted `StationStream.url` field (what the user typed/edited). Apply `.strip()` at minimum; consider `aa_normalize_stream_url` for parity with `_set_uri`, but a raw `.strip()` equality is sufficient and avoids false "unchanged" if normalization collapses a real edit. Recommend: `old_url.strip() != new_url.strip()`.

### Pattern 2: YouTube resolve-generation guard (mirror `_preroll_seq`)

**What:** A monotonic counter `self._youtube_resolve_seq: int` bumped whenever playback is restarted/invalidated. The worker captures the seq at spawn time; `_on_youtube_resolved`/`_on_youtube_resolution_failed` ignore the delivery if the captured seq != current seq.

**Why:** The preroll path already proves this pattern is the project's idiom for exactly this hazard. See `player.py:583` (`_preroll_seq` declaration + rationale), `:1544` (bump in `_start_preroll`), and the CR-01/WR-03 comments at `:296-303`. The YouTube path has no equivalent and is the documented race in the task brief.

**Example (shape, mirroring preroll):**
```python
# __init__ (alongside _preroll_seq at player.py:583)
self._youtube_resolve_seq: int = 0

# _play_youtube — capture and pass to worker
def _play_youtube(self, url: str) -> None:
    ...
    seq = self._youtube_resolve_seq
    threading.Thread(target=self._youtube_resolve_worker,
                     args=(url, seq), daemon=True).start()

# worker emits (resolved, is_live, seq) — requires widening youtube_resolved
# OR store seq and check in slot. Mirror preroll's Signal(int) carry.
def _on_youtube_resolved(self, resolved_url, is_live, seq):
    if seq != self._youtube_resolve_seq:
        return  # stale resolution from before an edit/restart — no-op
    ...

# invalidate_for_edit / restart path
self._youtube_resolve_seq += 1
```
NOTE: `youtube_resolved = Signal(str, bool)` (`player.py:273`) and the FakePlayer mirror (`tests/_fake_player.py:64`) would need the arity widened to `Signal(str, bool, int)` — this trips the **FakePlayer signal-parity drift-guard** (`tests/test_fake_player_signal_parity.py`, D-16). The planner MUST update `tests/_fake_player.py` in the same wave (per the file's Rule-1 convention). An alternative that avoids the Signal arity change: store `self._youtube_pending_seq` on the instance and have the worker stamp/check it — but the cross-thread int read/write is the same CPython-atomic justification used for `_preroll_in_flight` (`player.py:573` comment). Either is acceptable; the Signal-carry mirrors preroll exactly and is the more auditable choice.

### Anti-Patterns to Avoid
- **Panel-only refresh (the current bug):** Refreshing `now_playing.bind_station` without notifying the Player. This is precisely what `_sync_now_playing_station` does today and why the bug exists.
- **YouTube special-casing the whole fix:** CONTEXT prefers generic invalidation. Only the resolve-generation guard is YT-specific (because only YT has an async resolver). Queue/URI invalidation is generic.
- **Comparing the resolved playbin3 URI for change detection:** For YouTube the resolved HLS URL changes every resolution — always reports "changed." Compare the persisted `StationStream.url` instead.
- **Hand-rolling a partial queue reset for the restart case:** `play(fresh_station)` already does the correct full rebuild (`player.py:674-820`, including `_cancel_timers`, preroll-handler teardown WR-02, `_streams_queue` rebuild, `_is_first_attempt = True`). Reuse it.
- **Bare `QTimer.singleShot(callable)` from any non-Qt thread:** Forbidden (qt-glib-bus-threading Rule 2). All worker/bus → main hops use queued Signals. The fix runs on the main thread (it's invoked from a Qt signal slot), so it may call Player methods directly — but any new worker→main path must use a queued Signal.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rebuild `_streams_queue` after edit (restart case) | A new partial-reset routine | Existing `Player.play(fresh_station)` (`player.py:674`) | Already handles cancel-timers, preroll teardown, ordering, first-attempt reset, preferred-stream logic. |
| Stale-async-result guard | A new locking scheme | Mirror `_preroll_seq` generation pattern (`player.py:583`, `:296-303`) | Project's established idiom for exactly this hazard; CPython-atomic int read justification already documented. |
| Cross-thread marshaling | Manual thread handoff | Queued `Signal` (qt-glib-bus-threading Rule 2) | Project standard; `youtube_resolved` already uses it. |
| Stream re-fetch + ordering | New SQL / sort | `repo.get_station` + `order_streams()` | Already used by `play()` and `_sync_now_playing_station`. |
| URL normalization | New normalizer | `.strip()` (sufficient) or existing `aa_normalize_stream_url` (`url_helpers`) | Avoid inventing comparison rules. |

**Key insight:** Every mechanism this fix needs already exists in the codebase. The fix is *wiring* (notify the Player on edit) + *one new guard* (YT resolve generation) + *one decision method* (URL-change detection). It should add minimal new logic.

## Runtime State Inventory

> This is a refactor/bug-fix of in-memory state invalidation. Inventory of state that survives an edit and can resurface the old URL:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (DB) | `station_streams.url` IS correctly updated by `repo.update_stream` (`edit_station_dialog.py:1814`, `repo.py:564`). DB is the source of truth and is correct after save. | None — DB is correct. |
| Live in-memory player state | `Player._streams_queue` (`player.py:562`) — stale ordered list of `StationStream` objects with OLD urls; `Player._current_stream` (`:563`) — OLD url; playbin3 loaded URI via `set_property("uri", …)` in `_set_uri` (`:1506`) — OLD (resolved) url, possibly at EOS; `Player._current_station_id`/`_current_station_name` (`:591`/`:560`) — survive pause()/stop(). | **Code: invalidate on edit (the fix).** Clear `_streams_queue`/`_current_stream`; restart via `play()` when D-01 applies. |
| In-flight async resolution | `_youtube_resolve_worker` daemon thread (`player.py:1868`) may be mid-`extract_info` during an edit; completes via queued `youtube_resolved` → `_set_uri` with OLD resolved url. **No generation guard exists** (contrast `_preroll_seq`). | **Code: add `_youtube_resolve_seq` guard (the fix).** |
| Panel state | `NowPlayingPanel._station` (`now_playing_panel.py:327`) — already correctly refreshed by `bind_station` in `_sync_now_playing_station`. | None — already handled (this is the *only* thing currently refreshed). |
| OS-registered state / secrets / build artifacts | None — this is an in-process state bug; no OS registrations, env vars, or build artifacts embed the stream URL. | None — verified by absence in grep of player/edit/main_window paths. |

**The key question answered:** After `repo.update_stream` writes the new URL, the Player's `_streams_queue` + `_current_stream` + loaded playbin3 URI + any in-flight YouTube resolution still carry the OLD URL. The DB and the panel are correct; the Player is not. That is the entire bug.

## Common Pitfalls

### Pitfall 1: In-flight YouTube resolution clobbers the restart (the race)
**What goes wrong:** User edits URL while a `_youtube_resolve_worker` is mid-flight. The restart fires `play(new)` → spawns a NEW resolve. The OLD worker then completes and `_on_youtube_resolved` calls `_set_uri(OLD_resolved_url)`, overriding the new stream — reintroducing "second play needed" non-determinism.
**Why it happens:** The YouTube resolve path has no generation guard (unlike `_preroll_seq` at `player.py:583`). `youtube_resolved` is a queued Signal; a delivery enqueued before the edit still dispatches after.
**How to avoid:** Add `_youtube_resolve_seq`; bump it on every restart/invalidation; ignore deliveries whose captured seq != current (Pattern 2).
**Warning signs:** Test that simulates a late `youtube_resolved.emit(OLD, …)` arriving after `invalidate_for_edit` and asserts `_set_uri` is NOT called with the old URL.

### Pitfall 2: `_current_station_id`/`_current_stream` survive stop()/pause()
**What goes wrong:** Using `_current_station_id == updated.id` alone to mean "is actively playing" → an edit to a *stopped* station whose id still matches `_current_station_id` would wrongly trigger a D-01 restart (re-starting audio the user had stopped).
**Why it happens:** `pause()` (`player.py:834`) and `stop()` (`:864`) clear `_streams_queue` but **not** `_current_stream`/`_current_station_id` (verified: only assignments are in `play()` :701, `play_stream()` :828, `_try_next_stream` :1455).
**How to avoid:** Gate the D-01 restart on the panel's `now_playing.is_playing` (`now_playing_panel.py:961`) in addition to id-match. `_sync_now_playing_station` already holds `self.now_playing`.
**Warning signs:** Test: edit URL of a station that is bound but stopped → assert NO `play()` re-issue (D-05 invalidate-only).

### Pitfall 3: Comparing resolved URI instead of stored URL → always "changed" or always "unchanged"
**What goes wrong:** Comparing the loaded playbin3 URI (resolved HLS) against the new stored URL always reports a difference for YouTube (resolved ≠ stored), causing needless restarts even on metadata-only edits (violates D-02).
**How to avoid:** Compare the persisted `StationStream.url` old value (from the player's `_current_stream.url`, which holds the *stored* url for the playing stream) vs. the new `StationStream.url` from `updated_station.streams` matched by `id`. (`_current_stream.url` is the stored url, not the resolved one — `_try_next_stream` assigns the stream object before resolving; `_set_uri` receives the resolved url separately, `player.py:1494`/`1967`.)
**Warning signs:** Test: metadata-only edit (change quality/bitrate, same URL) on the playing stream → assert NO restart, audio uninterrupted.

### Pitfall 4: FakePlayer signal-parity drift-guard breaks if `youtube_resolved` arity changes
**What goes wrong:** Widening `youtube_resolved = Signal(str, bool)` to carry the seq trips `tests/test_fake_player_signal_parity.py` (D-16) and the production-grep convention.
**How to avoid:** If choosing the Signal-carry approach, update `tests/_fake_player.py:64` in the SAME wave. Alternatively use an instance-attribute seq (no Signal change) and check it in the slot. Either is acceptable; document the choice in the plan.
**Warning signs:** `pytest tests/test_fake_player_signal_parity.py` red after the change.

### Pitfall 5: Rapid successive edits / edit during failover
**What goes wrong:** Two quick saves, or a save during an active failover advance, could leave the queue half-rebuilt.
**How to avoid:** Re-issuing `play(fresh_station)` is idempotent-by-rebuild: it calls `_cancel_timers()` first (`player.py:677`) and fully rebuilds `_streams_queue` (`:678`,`:734`). Each restart bumps `_youtube_resolve_seq`, so prior in-flight resolves no-op. The `_recovery_in_flight` guard (`player.py:567`/`992`) already coalesces cascading errors. No extra locking needed.
**Warning signs:** Test: two consecutive `invalidate_for_edit` calls → final state reflects the last save; only one live resolve generation.

### Pitfall 6: Deleting/reordering the playing stream during edit
**What goes wrong:** `_on_save` prunes removed streams (`prune_streams`, `edit_station_dialog.py:1834`) and reorders. If the currently-playing stream was deleted, matching by `_current_stream.id` finds no stream in `updated_station.streams`.
**How to avoid:** If the playing stream id is absent from `updated_station.streams`, treat as a change requiring action: if other streams remain and audio is playing, re-issue `play(updated_station)` (it will pick the new ordering/preferred); if no streams remain, the existing `play()` no-streams guard emits "(no streams configured)" (`player.py:705`). Decide in the plan whether a deleted-playing-stream restarts or stops (recommend: re-issue `play()` so failover picks a surviving stream — aligns with D-01 "hear the new stream").
**Warning signs:** Test: delete the playing stream, leave a sibling → assert `play()` re-issued; delete all → assert graceful no-streams handling, no crash.

## Code Examples

Verified existing patterns the fix should mirror (all first-party):

### The proven rebuild path to reuse (restart case)
```python
# musicstreamer/player.py:674 — Player.play(station, …)
def play(self, station: Station, on_title=None, preferred_quality: str = "",
         on_failover=None, on_offline=None) -> None:
    self._cancel_timers()                       # :677
    self._streams_queue = []                    # :678  (full reset)
    self._recovery_in_flight = False            # :679
    # ... preroll-handler teardown (WR-02) :690-698 ...
    self._current_station_name = station.name   # :700
    self._current_station_id = station.id        # :701
    self._is_first_attempt = True               # :702
    # ... order_streams + preferred logic :714-734 ...
    self._streams_queue = queue                 # :734
    self._try_next_stream()                     # :820
```

### The generation-guard idiom to mirror (preroll → YouTube)
```python
# musicstreamer/player.py:583 — _preroll_seq declaration (rationale at :296-303)
self._preroll_seq: int = 0
# :1544 — bumped when a new handoff opens / old one invalidated
self._preroll_seq += 1
# the about-to-finish slot ignores deliveries whose stamp != _preroll_seq
```

### The edit→player junction to extend (wire the fix here)
```python
# musicstreamer/ui_qt/main_window.py:1430 — _sync_now_playing_station
def _sync_now_playing_station(self, station_id: int) -> None:
    updated_station = self._repo.get_station(station_id)
    if updated_station is None:
        return
    current = getattr(self.now_playing, "_station", None)
    if current is not None and current.id == updated_station.id:
        self.now_playing.bind_station(updated_station)
        # FIX ADDS HERE: notify the player to invalidate/restart, passing
        # updated_station + whether the panel is actively playing.
        # e.g. self._player.invalidate_for_edit(updated_station,
        #                                        is_playing=self.now_playing.is_playing)
```
NOTE: the panel rebind is currently gated on `current.id == updated_station.id`. For D-05 ("next play rebuilds from fresh DB state") on a station that is bound-but-different OR not bound, the player invalidation may also be needed even when this branch is skipped — but in practice the Player only holds stale state for the station it last played. Recommend: also call the player invalidation when `_current_station_id == updated_station.id` regardless of panel binding, OR (simpler) always pass `updated_station` and let `Player.invalidate_for_edit` decide (it checks `_current_station_id` itself). The planner should pick one; passing-and-let-player-decide is cleaner and keeps the id-match logic in one place (the Player).

## State of the Art

Not applicable — no library/version churn. This is an internal state-invalidation fix. The relevant "state of the art" is the project's own established patterns (preroll `_preroll_seq` guard, Phase 83; queued-Signal cross-thread marshaling, Phase 43.1; `play()` rebuild path), all current.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `now_playing.is_playing` (panel) is the most reliable "audio is actively live" signal available to `_sync_now_playing_station` (since `_current_station_id` survives stop/pause). | Pattern 1 / Pitfall 2 | If panel `is_playing` lags actual pipeline state in some edge (e.g. mid-failover), a D-01 restart could fire on stopped audio or be skipped on live audio. Verified `is_playing` is set by `on_playing_state_changed` from `_on_station_activated`/`_on_failover` — main-thread, synchronous. LOW risk. |
| A2 | `_current_stream.url` holds the *stored* (user-typed) URL, not the resolved HLS URL, for the playing stream. | Pitfall 3 | If wrong, URL-change detection compares wrong values. Verified: `_try_next_stream` assigns `self._current_stream = stream` (`:1455`) from the queue (stored urls); resolution passes the resolved url separately to `_set_uri` (`:1494`→`_play_youtube`→worker→`_on_youtube_resolved`→`_set_uri`), never mutating `_current_stream.url`. HIGH confidence. |
| A3 | Re-issuing `play(updated_station)` is safe to call from the `station_saved` slot path (main thread). | Pattern 1 | `play()` is a public main-thread method already called from `_on_station_activated` (`main_window.py:872`); the slot runs on main. HIGH confidence. |
| A4 | Deleting the playing stream should re-issue `play()` (pick a surviving stream) rather than stop. | Pitfall 6 | This is a UX judgment not explicitly locked by D-01..D-05; flagged for the planner/discuss to confirm. The "hear the new stream" intent (D-01) suggests continuing on a surviving stream. MEDIUM — needs confirmation. |

## Open Questions

1. **Where exactly to gate the D-01 vs D-05 decision: panel `is_playing` vs a new `Player.is_active()` accessor?**
   - What we know: `_current_station_id` survives stop/pause; panel `is_playing` reflects user intent.
   - What's unclear: whether to add a Player-side `is_active`/playback-state accessor for cleaner encapsulation vs. passing the panel's `is_playing` into `invalidate_for_edit`.
   - Recommendation: Pass `is_playing` from the panel into the Player method (minimal new API). The Player already lacks a playback-state field; adding one is out of scope.

2. **Deleted-playing-stream behavior (restart on surviving stream vs. stop)** — see Assumption A4. Recommend confirming with the user in discuss/plan; default to re-issue `play()`.

3. **Signal-arity change vs. instance-attribute for the YT resolve guard.**
   - What we know: Signal-carry mirrors preroll exactly but trips the FakePlayer parity guard (must update `tests/_fake_player.py` same wave).
   - Recommendation: Use the Signal-carry approach for auditability and update `_fake_player.py`; the drift-guard tests make the parity edit mandatory and self-enforcing.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/python` (PySide6 + GStreamer + yt_dlp) | Running the test suite (system python3 lacks PySide6.QtWidgets — MEMORY) | ✓ (per MEMORY note) | project venv | none — MUST use `.venv/bin/python` |
| Node.js runtime | YouTube resolution at *runtime* (not for the fix's unit tests, which mock the resolver) | n/a for tests | — | tests mock `_youtube_resolve_worker` / emit `youtube_resolved` directly |

No new external dependencies. The fix is testable entirely with mocked pipeline + signal emission (see Validation Architecture).

## Validation Architecture

> nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`). Section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt (`qtbot` fixture); `unittest.mock` (MagicMock/patch) |
| Config file | repo root (existing `tests/` suite; `make_player` mocks `Gst.ElementFactory.make`) |
| Quick run command | `.venv/bin/python -m pytest tests/test_player_failover.py tests/test_edit_station_dialog.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` (NOTE: full suite >600s per MEMORY — scope per-task runs tightly) |

**CRITICAL (from MEMORY):** Run tests with `.venv/bin/python`, NOT system `python3` (which lacks `PySide6.QtWidgets` → false failures). Two known pre-existing failures exist in the suite — do not attribute them to this phase. Scope test commands to the touched files.

### Failure modes to cover (from task brief + D-01..D-05)
| # | Behavior | Test Type | Automated Command | File |
|---|----------|-----------|-------------------|------|
| V1 | First play after editing the playing YT station's URL uses the NEW url; no "stream exhausted" | unit (Player) | `.venv/bin/python -m pytest tests/test_player_failover.py -k "edit" -x` | new tests in test_player_failover.py / new test_player_edit_invalidation.py |
| V2 | Metadata-only edit (same URL) on playing stream does NOT restart / does NOT call set_state(NULL) | unit (Player) | same | same |
| V3 | Edit a NON-playing stream of the playing station → no audio interruption, queue invalidated | unit (Player) | same | same |
| V4 | Same-URL no-op: editing URL to identical value → no restart | unit (Player) | same | same |
| V5 | In-flight-resolution race: late `youtube_resolved.emit(OLD,…)` after invalidate → `_set_uri` NOT called with OLD url (seq guard) | unit (Player) | same | same |
| V6 | Edit while NOT playing (idle/stopped) → next `play()` rebuilds fresh, no stale queue | unit (Player) | same | same |
| V7 | `_sync_now_playing_station` calls the player invalidation when the edited station is current | integration (MainWindow + FakePlayer) | `.venv/bin/python -m pytest tests/test_main_window_integration.py -k "sync or edit" -x` | test_main_window_integration.py (extend FakePlayer with the new method stub) |
| V8 | `EditStationDialog._on_save` still emits `station_saved` after persisting URL (regression) | unit (dialog) | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k save -x` | test_edit_station_dialog.py |
| V9 | FakePlayer signal parity holds after any `youtube_resolved` arity change | drift-guard | `.venv/bin/python -m pytest tests/test_fake_player_signal_parity.py -x` | tests/_fake_player.py update |
| V10 | Delete playing stream during edit → graceful (re-issue play on surviving stream / no-crash on empty) | unit (Player) | `.venv/bin/python -m pytest tests/test_player_failover.py -k delete -x` | new test |

### Test approach / models
- **Player unit tests:** Follow `tests/test_player_failover.py` `make_player(qtbot)` (mocks `Gst.ElementFactory.make`, replaces `player._pipeline` with `MagicMock`). Patch `_set_uri` / `_play_youtube` to assert call args without a real pipeline. Drive the new `invalidate_for_edit` directly and assert `_streams_queue`/`_current_stream`/`_set_uri` outcomes. For V5, emit `player.youtube_resolved.emit(old, False, stale_seq)` (or set the stale instance seq) and assert the slot no-ops.
- **MainWindow integration:** Follow `tests/test_main_window_integration.py` with `FakePlayer` (`tests/_fake_player.py`). Add a method stub for the new `invalidate_for_edit`/`reload_station` on FakePlayer (record calls). Assert `_sync_now_playing_station` invokes it with the updated station when ids match.
- **Dialog:** `tests/test_edit_station_dialog.py` `_on_save` tests already assert repo calls + `station_saved`; extend only if the save path itself changes (it should NOT — the fix is downstream of `station_saved`).

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_player_failover.py tests/test_edit_station_dialog.py tests/test_fake_player_signal_parity.py -x -q`
- **Per wave merge:** add `tests/test_main_window_integration.py tests/test_player.py`
- **Phase gate:** scoped player + UI + integration tests green before `/gsd:verify-work`. (Full `tests/` is >600s and has 2 known unrelated failures — run targeted, not whole-suite, for this fix.)

### Wave 0 Gaps
- [ ] `tests/test_player_edit_invalidation.py` (or extend `test_player_failover.py`) — covers V1–V6, V10. New file.
- [ ] `tests/_fake_player.py` — add `invalidate_for_edit`/`reload_station` method stub (call-recording); update `youtube_resolved` arity IF the Signal-carry approach is chosen (D-16 parity).
- [ ] `tests/test_main_window_integration.py` — add V7 assertions on the new player call from `_sync_now_playing_station`.
- [ ] Framework install: none — pytest + pytest-qt already present in `.venv`.

## Security Domain

> `security_enforcement` is not present in config.json (treated as enabled). This phase processes no new external/untrusted input beyond what already exists.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | minimal | The edited URL is user-supplied but already flows through existing persist + `_set_uri`/`aa_normalize_stream_url` paths; this fix adds no new parsing of untrusted input. URL is treated as opaque string for comparison (`.strip()` equality). |
| V6 Cryptography | no | — |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious/oversized URL re-fed to playbin3 on restart | Tampering / DoS | No new surface — restart reuses the existing `play()`→`_set_uri` path which already handles arbitrary URLs; yt-dlp resolution already sandboxed to a daemon worker with try/except backstop (`player.py:1954`). |
| Thread-safety of cross-thread state reads (seq guard) | — (correctness, not security) | CPython-atomic int read/write (project's documented justification, `player.py:573`); marshal any worker→main via queued Signal. |

No new credentials, secrets, or network endpoints are introduced.

## Sources

### Primary (HIGH confidence) — live codebase, verified file:line
- `musicstreamer/player.py` — `play()` 674-820; `pause()` 834-862; `stop()` 864-900; `_try_next_stream()` 1440-1500; `_set_uri()` 1502-1510; `_play_youtube()` 1856-1870; `_youtube_resolve_worker()` 1872-1955; `_on_youtube_resolved()` 1957-1968; `_preroll_seq` 583 / 296-303 / 1544; `_current_stream` 563/634/1455; `_current_station_id` 591/701/828; `_streams_queue` 562; `failover.emit(None)` 1452.
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_on_save()` 1713-1851; `station_saved` Signal 318; `repo.update_stream` 1814; `prune_streams`/`reorder_streams` 1834-1836; `station_saved.emit()` 1838.
- `musicstreamer/ui_qt/main_window.py` — `_on_edit_requested()` 1332-1346; `_sync_now_playing_station()` 1430-1442; `_on_failover()` 906-914; "Stream exhausted" 909; `_on_station_activated` play() 872.
- `musicstreamer/ui_qt/now_playing_panel.py` — `bind_station()` 966; `current_station` 957; `is_playing` 961; `_station` 327; `_is_playing` 330.
- `musicstreamer/models.py` — `StationStream` 12-23; `Station.streams` 37.
- `musicstreamer/repo.py` — `list_streams` 490-492 (ORDER BY position); `update_stream` 564; `get_station`.
- `musicstreamer/stream_ordering.py` — `order_streams` 46.
- `tests/test_player_failover.py` — `make_player`/`make_stream`/`make_station_with_streams` 16-50; queue + recovery assertions.
- `tests/_fake_player.py` — FakePlayer signals 60-90 (parity D-16); method stubs 112-152; `youtube_resolved = Signal(str, bool)` 64.
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Rule 1 (add_signal_watch on bridge thread), Rule 2 (no bare singleShot from non-Qt thread).
- `.planning/phases/95-…/95-CONTEXT.md` — D-01..D-05, Specifics, Reusable Assets.
- MEMORY.md — run tests with `.venv/bin/python`; suite >600s + 2 known failures; decision-coverage gate scans must_haves; `.planning/` gitignored (force-add docs, sequential execute).

### Secondary (MEDIUM confidence)
- None — no web/library research was needed for this in-codebase fix.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Root cause & wiring gap: HIGH — traced end-to-end with file:line; matches CONTEXT root-cause hypothesis exactly.
- Invalidation mechanism (reuse `play()`): HIGH — `play()` rebuild path verified to do the full reset.
- In-flight resolution race + seq guard: HIGH — confirmed YT path has no `_preroll_seq`-equivalent; preroll pattern is the proven idiom.
- D-01 vs D-05 gating (panel `is_playing`): MEDIUM — `is_playing` is main-thread-synchronous but is a UX-state proxy; flagged A1/Open Q1.
- Deleted-playing-stream behavior: MEDIUM — UX judgment not locked by decisions; flagged A4/Open Q2.

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (stable — internal code, no fast-moving dependencies). Re-verify file:line citations if `player.py`/`main_window.py`/`edit_station_dialog.py` change before planning.

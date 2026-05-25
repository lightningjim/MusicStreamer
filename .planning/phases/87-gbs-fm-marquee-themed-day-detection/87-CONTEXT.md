# Phase 87: GBS.FM Marquee + Themed-Day Detection - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

When the bound station is GBS.FM, the user sees (1) the current themed logo (if any) in the now-playing logo slot, (2) a dismissible top-of-NowPlayingPanel announcement banner whose text is the first pipe-segment of the gbs.fm marquee, and (3) live updating of both as the marquee changes — all backed by the same Phase 76 cookies-based authenticated session (`paths.gbs_cookies_path()` + `gbs_api.load_auth_context()`), not a parallel QtWebEngine profile.

Phase 87 also delivers the test fixture infrastructure (`tests/fixtures/gbs_marquee/` + `tests/fixtures/gbs_themed_logos/`) and a curated themed-day keyword set that downstream phases (notably Phase 89's cover-slot UI swap depending on the cookie-persistence pattern this phase exercises) build on.

**In scope:**

- **Themed-day detection** — Fetch `https://gbs.fm/images/logo_3.png` at session start when a GBS station is bound; SHA-256 hash; compare against a baseline of known non-themed hashes; if drift detected AND a known themed-day keyword appears in the current marquee text (OR — fallback per D-08 — log "unknown theme observed" but still apply), replace the now-playing logo slot for the session.
- **Marquee polling** — 60s cadence when GBS bound + playing; 5-min cadence when GBS bound but not playing; fetched via shared cookie context.
- **Announcement banner** — Top-of-NowPlayingPanel QLabel widget, multi-line wrap with `|` pipe boundaries preserved as wrap hints. Visible only when (a) bound station is GBS.FM, (b) first-segment announcement is non-empty, and (c) the announcement-hash differs from the in-memory last-dismissed-hash.
- **Test fixtures** — 10+ marquee samples + 1+ themed-day logos (live-harvested today, "da troops" Memorial Day window) + 1+ canonical logos. Committed under `tests/fixtures/gbs_marquee/` and `tests/fixtures/gbs_themed_logos/`. Hash baseline table grows opportunistically as future themed days fire (Halloween 2026, Christmas 2026, etc.); D-04 explicitly relaxes GBS-THEME-06's "3+/5+" literal to "structure ships today; entries accrete over time."
- **Source-grep drift-guard** — Test asserting the marquee module imports from `musicstreamer.gbs_api` / `musicstreamer.paths` and does NOT construct a `QWebEngineProfile` or write a parallel cookies file. (Pitfall 14 mitigation, redirected to the actually-existing reuse path — see D-05.)
- **Threading** — New `QThread` worker owning a `QTimer` that drives both the marquee fetch and (once-per-app-session) the themed-day detection. Lifecycle: started on first GBS bind; survives subsequent unbind/rebind; torn down only on app exit.

**Out of scope (deferred / rejected):**

- **Persistent QtWebEngine profile / `gbs_auth.py` module** — Roadmap framing was based on a misread of Phase 76; the actual auth surface is the cookies-jar path. See D-05.
- **Themed-logo persistence in SQLite or on disk** — In-memory QPixmap only, garbage-collected on app exit. GBS-THEME-04 literal.
- **libnotify toast / popup on themed-day detection** — GBS-THEME-05 literal. The themed logo IS the notification.
- **Persisted banner dismissal** — In-memory only. Next app launch re-shows the announcement until dismissed again. Aligns with the session-scoped philosophy of GBS-THEME-04 even though GBS-MARQ-05 doesn't strictly bind it.
- **Themed accent re-tint** — Deferred per `REQUIREMENTS.md` GBS-THEME-RETINT (P2 polish, deferred from v2.2).
- **Zero-token single-song add** — Phase 87b owns that surface; this phase establishes only the pattern (cookies-based marquee fetch) that 87b consumes.
- **YouTube / Twitch channel-avatar work** — Phase 89 family. They reuse the cookie-persistence pattern but ship separately.
- **Exponential backoff on marquee errors** — Quiet-WARN-and-continue is sufficient per D-12.
- **Live re-detection of themed day on unbind→rebind during one app session** — Detection fires ONCE per app session at first GBS bind. Repeat binds reuse the session-cached result. See D-09.

</domain>

<decisions>
## Implementation Decisions

### Baseline harvest sequencing (time-sensitive)

- **D-01:** **Plan 87-01 is the harvest plan and fires FIRST, today.** Today (2026-05-25) is Memorial Day; gbs.fm is serving the "da troops" themed logo and (likely) a marquee that mentions troops. This is one of only a handful of themed-day windows per year. Plan 87-01 does NOT depend on the marquee endpoint being parser-locked — it can capture the live marquee HTML/JSON as raw bytes for the researcher to dissect after. Harvest captures:
  - `tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png` (live logo_3.png)
  - The SHA-256 of that file (recorded in fixture metadata)
  - 1+ raw marquee snapshot files under `tests/fixtures/gbs_marquee/2026-05-25_*.txt` (or `.json`, format determined by what gbs.fm actually serves)
  - Any local cached canonical `logo_3.png` Kyle has (browser cache / past dev fixtures) → hash and add to baseline
- **D-02:** **Inline-only harvest \(no spike split\).** No `/gsd:spike` ceremony; the harvest task is just `Plan 87-01: Harvest live themed-day fixtures (Memorial Day window)`. Time-sensitivity dominates clean separation. The researcher (plan-phase --research-phase 87) consumes the harvested fixtures, not the live site.
- **D-03:** **Researcher must run after Plan 87-01 commits**, not before. The harvest is a prerequisite for the researcher's marquee parser work — they need real fixtures to reverse-engineer the delimiter/structure rules and to test selectors against.

### Hash-table requirement (GBS-THEME-06) pragmatic interpretation

- **D-04:** **Ship with whatever we can harvest today; mark GBS-THEME-06's "3+ themed / 5+ non-themed" rule as aspirational with explicit follow-up todo.** The deliverable for Phase 87 is the baseline TABLE STRUCTURE — a `dict[str, str]` (or equivalent) at `musicstreamer/gbs_marquee.py` (or `constants.py`) keyed by hash → label, plus the fixture directory layout. Entries accrete as Halloween 2026 / Christmas 2026 / etc. fire. At verification time, GBS-THEME-06 is closed with a note "structure shipped; entry count below literal 3+/5+ pending future themed-day windows." A `todos/` entry is added: `2026-05-25-gbs-theme-hash-baseline-grow.md` with `resolves_phase: 87` and `next_window: 2026-10-31`.

### Themed logo runtime + fixture storage

- **D-05:** **Runtime: in-memory `QPixmap` only, never to disk.** Logo bytes downloaded once at session-first-bind, decoded to `QPixmap`, held by the marquee worker (or NowPlayingPanel — planner's call within the module split discretion below), garbage-collected on app exit. Zero disk persistence. Hard-locks GBS-THEME-04: a source-grep drift-guard asserts the themed-logo code path never calls `repo.set_setting`, `open(...)` in write mode, or `pixmap.save(...)`.
- **D-06:** **Fixtures committed at**:
  - `tests/fixtures/gbs_themed_logos/<YYYY-MM-DD>_<seasonal-slug>.png` (themed)
  - `tests/fixtures/gbs_themed_logos/canonical-<seq>.png` (non-themed; multiple if hash diverges across captures)
  - `tests/fixtures/gbs_marquee/<YYYY-MM-DD>_<seq>.txt` (or `.json` based on what gbs.fm serves)
  - Metadata sidecar: `tests/fixtures/gbs_themed_logos/MANIFEST.md` mapping each PNG to (capture date, SHA-256, theme label, source URL, capture method).
  - Aligns with GBS-MARQ-07's `tests/fixtures/gbs_marquee/` literal and adds the parallel themed-logo directory.

### Auth/session reuse (rewrite of GBS-MARQ-06)

- **D-07:** **GBS-MARQ-06 is rewritten in `REQUIREMENTS.md` to lock the actual Phase 76 reuse path.** New text:
  > **GBS-MARQ-06**: The marquee fetcher reuses Phase 76 GBS authenticated session via `paths.gbs_cookies_path()` (cookies-jar file) and `musicstreamer.gbs_api.load_auth_context()` (loader). The marquee module imports these — does NOT construct a `QWebEngineProfile`, does NOT write a parallel cookies file, and does NOT instantiate `oauth_helper`. A source-grep drift-guard test (`test_marquee_module_reuses_phase76_auth_only`) confirms.
  >
  > Quote from `60-CONTEXT.md` D-04 / `76-CONTEXT.md` D-06: "Django session cookies (sessionid + csrftoken). Cookies live at paths.gbs_cookies_path() with 0o600 perms." That path + the existing `_open_with_cookies` shape (`gbs_api.py:146-160`) is the reuse target.
  >
  > Per `feedback_mirror_decisions_cite_source.md`: this CONTEXT.md quotes the real Phase 76 mechanism verbatim instead of paraphrasing the (incorrect) roadmap framing.
- **D-08:** **Plan-phase action: edit ROADMAP.md Phase 87 Success Criterion #4** to drop the "imports `GBS_WEB_PROFILE_NAME` + `GBS_WEB_STORAGE_PATH` from `musicstreamer/gbs_auth.py`" wording. Replace with: "Marquee fetcher imports `paths.gbs_cookies_path()` + `musicstreamer.gbs_api.load_auth_context()`; source-grep drift-guard confirms no parallel cookie file is written and no QtWebEngine session is instantiated." Use `/gsd-phase edit 87` or direct ROADMAP.md edit during planning.
- **D-09:** **Themed-day detection runs ONCE per app session.** First GBS bind in an app launch triggers `logo_3.png` fetch + hash + theme correlation. The result is cached in worker-thread state for the rest of the app launch. Subsequent unbinds + rebinds reuse the cached themed-vs-canonical decision; they do NOT re-fetch logo_3.png. This matches "session = app launch" semantics of GBS-THEME-04.

### Marquee endpoint discovery

- **D-10:** **Endpoint is researcher-locked, not lock-now.** Phase 87 has `Research flag: YES` already. The researcher (spawned by `/gsd:plan-phase --research-phase 87`) probes gbs.fm with the dev fixture cookies — inspects DevTools Network/DOM/JS — to identify the marquee source (JSON endpoint vs scraped HTML element vs JS-rendered). Researcher returns: URL constant, response shape, whether cookies change the response, and the parser (BeautifulSoup selector or JSON path). Plan-phase locks these in `gbs_marquee.py` constants.
- **D-11:** **Fetch defaults defensively for auth requirement.** Implementation uses `gbs_api.load_auth_context()` if available; falls back to anonymous `urllib.request.urlopen` if `load_auth_context()` returns `None` (no cookies saved). Researcher reports whether cookies actually change the marquee response. If anonymous works, save the latency / cookie-leak surface; if cookies needed, the path is already wired.

### Marquee parsing + keyword set + banner UI

- **D-12:** **Themed-day keyword set is curated in `musicstreamer/constants.py` with a known-theme list + "unknown theme observed" fallback.** Initial list (extensible):
  ```python
  GBS_THEMED_DAY_KEYWORDS = frozenset({
      "da troops", "ho ho", "spooky", "halloween", "christmas",
      "thanksgiving", "fourth", "easter", "valentine",
  })
  ```
  Detection rule: themed logo applies if `logo_3.png` SHA-256 differs from the baseline canonical hash(es) AND any keyword from `GBS_THEMED_DAY_KEYWORDS` appears (case-insensitive substring match) in the FULL marquee text (not just the first pipe-segment — themed-day phrasing often lives in the perpetual segments).

  **Fallback path** (covers gbs.fm operator adding a new themed day we haven't keyword-listed): if hash drift detected but NO keyword matches, the themed logo IS STILL APPLIED, and the worker emits a structured log line `gbs.themed_day.unknown_theme_observed` at INFO via `buffer_log.py` (capturing the new hash + first marquee snippet) so a future codebase pass can extend the keyword list. This avoids false-negatives at the cost of a small false-positive risk if the operator changes the canonical logo for non-themed reasons (acceptable — visible to user as a one-session anomaly, no data lost).
- **D-13:** **Marquee parsing per GBS-MARQ-02 (literal):** Response → split on `|` → first segment is the changeable announcement → subsequent segments are perpetual and ignored for banner-display purposes (but the FULL marquee text is still searched for themed-day keywords per D-12). Whitespace-trim each segment.
- **D-14:** **Banner widget: multi-line wrap at pipe boundaries + in-memory dismissal only.** Implementation:
  - QLabel with `wordWrap=True`, `Qt.TextFormat.PlainText` (per project convention T-40-04), set parent = top of NowPlayingPanel layout.
  - Text content = first pipe-segment with internal pipes replaced by `\n` (multi-line wrap hint per GBS-MARQ-04).
  - Inline `QPushButton("×")` dismiss button (flat style, small, right-aligned).
  - Dismissed-announcement-hash held in NowPlayingPanel instance state (a `self._dismissed_announcement_hashes: set[str]` — keep the set across multiple dismissals so the user doesn't see the same banner re-appearing on every poll).
  - On marquee poll: compute SHA-256 of first-segment text; if hash NOT in dismissed set AND first segment is non-empty AND bound station is GBS.FM → show banner.
  - **No persistence.** Restart clears the set. Mirrors GBS-THEME-04's session philosophy by symmetry, even though GBS-MARQ-05 doesn't strictly require this.

### Polling lifecycle + threading

- **D-15:** **New `QThread` worker (`GbsMarqueeWorker`) owns its own `QTimer`.** Started lazily on first GBS bind in the app session; stays alive but transitions between cadence modes (60s / 5min / idle-when-not-bound) via the binding state. Torn down on app exit only. urllib calls happen on the worker thread; PyQt signals carry results (logo bytes, marquee text, banner-hash) back to the main thread. Mirrors `aa_live.py`'s worker-thread pattern (closest precedent in the codebase).
- **D-16:** **Cadence state machine:**
  - State A: GBS bound + playing → 60s cadence (GBS-MARQ-01 literal).
  - State B: GBS bound + not playing → 5min cadence (GBS-MARQ-01 literal).
  - State C: GBS unbound → idle (timer paused, worker thread parked).
  - Transitions wired to `Player.state_changed` + `Player.station_bound` signals (existing).
- **D-17:** **Themed-day detection fires once at "first GBS bind" event for the app session.** Worker tracks a boolean `self._themed_day_detected_this_session` (default False). On first transition into State A or State B from State C (i.e., first GBS bind), fire the logo fetch + hash + correlation routine in a single one-shot block, then set the flag. Subsequent State C → A/B transitions reuse the cached result. Next app launch starts with the flag False (process restart) — re-evaluates from scratch (GBS-THEME-04 literal).

### Error handling

- **D-18:** **Failures are quiet: WARN to `buffer_log.py`, continue with next-tick cadence, no UI surface.** Categories:
  - Network/timeout/5xx on marquee fetch → log `gbs.marquee.fetch_failed` at WARN with status code / exception type; banner just doesn't update this tick.
  - `GbsAuthExpiredError` on marquee fetch → log `gbs.marquee.auth_expired` at WARN; do NOT toast, do NOT open AccountsDialog. (The user will notice their next vote/submit fails through other surfaces; the marquee silently failing is not a worth-a-toast event.)
  - Logo fetch failure (themed-day detection path) → log `gbs.themed_day.logo_fetch_failed` at WARN; canonical logo stays applied for the session; worker DOES NOT retry the themed-day detection this session (it's a one-shot — see D-17).
  - All log lines structured (key=value) consistent with `buffer_log.py`'s existing shape; no PII / no marquee body in the log.
- **D-19:** **No exponential backoff.** Cadence stays 60s/5min regardless of consecutive failures. Marquee endpoint is the operator's own server; if it's down, hammering it slower doesn't help and adds state-machine complexity for no observed need.

### Claude's Discretion

- **Module split.** Whether the marquee + themed-logo code lives in:
  - (a) A single new `musicstreamer/gbs_marquee.py` exporting `GbsMarqueeWorker`, `parse_marquee`, `compute_logo_theme`, plus banner widget at `musicstreamer/ui_qt/announcement_banner.py`; OR
  - (b) Both fetch + theme logic inside `gbs_marquee.py`, banner integrated directly into `now_playing_panel.py` (no new ui_qt module).
  Default recommendation: (a) — separation of concerns + makes the source-grep drift-guard cleaner (one module to audit).
- **Banner placement within NowPlayingPanel.** Above the station name vs above the cover slot vs above the volume cluster. Default: above the station name (highest visual priority; matches the "announcement" semantics).
- **Dismiss button character + style.** `×` vs `✕` vs `Close` text vs icon. Default: `×` (Unicode U+00D7) for consistency with other dismiss buttons in the codebase if any; otherwise pick whatever pixel-grids cleanly at Wayland DPR=1.0.
- **Hash function for both themed-day baseline AND announcement-dismissal-tracking.** SHA-256 per GBS-THEME-01 literal; reuse the same `hashlib.sha256(...).hexdigest()` shape for the announcement-hash to keep the codepath uniform.
- **Whether to parse the marquee response as bytes or pre-decoded text.** Default: decode to str with `response.read().decode("utf-8", errors="replace")` at fetch time; parser works on str.
- **Fixture metadata schema** (MANIFEST.md vs sidecar JSON per fixture). Default: a single `MANIFEST.md` per fixture directory with a markdown table — easier to git-diff than per-file JSON.
- **Whether `GbsMarqueeWorker` exposes a public method to force-refresh** (e.g. for unit tests). Default: yes, a `force_poll()` method bypassing the timer — keeps tests synchronous.
- **How the announcement banner widget is parented**: child of NowPlayingPanel directly vs child of a wrapping QWidget that owns the layout. Planner's call based on `now_playing_panel.py`'s existing layout shape.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` §"Phase 87: GBS.FM Marquee + Themed-Day Detection" (lines 125–138). **Note:** Plan-phase MUST edit Success Criterion #4 per D-08 to drop the `GBS_WEB_PROFILE_NAME` / `gbs_auth.py` framing.
- `.planning/REQUIREMENTS.md` §"GBS.FM — Themed-Day Logo (GBS-THEME)" + §"GBS.FM — Announcement Banner (GBS-MARQ)" (lines 47–63). **Note:** Plan-phase MUST rewrite GBS-MARQ-06 per D-07 to reflect the actual Phase 76 reuse path.
- `.planning/PROJECT.md` §Current Milestone v2.2 — Phase 87 is the "GBS.FM integration QOL polish" anchor.

### CRITICAL prior context (READ FIRST)

- **`.planning/milestones/v2.1-phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-CONTEXT.md` §`<decisions>` D-04 / D-06 / D-19 / D-20 / D-21** — Phase 76 LOCKED auth model: Django sessionid+csrftoken stored as Netscape cookies at `paths.gbs_cookies_path()` with 0o600 perms. `gbs_api.load_auth_context()` returns the cookie jar. `_open_with_cookies` is the request helper. **There is NO `gbs_auth.py` module and NO `QWebEngineProfile` persistent profile.** D-07 (this CONTEXT) rewrites GBS-MARQ-06 to match this reality.
- **`.planning/milestones/v2.1-phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-VERIFICATION.md`** — Confirms what Phase 76 actually shipped (vs the roadmap's pre-implementation framing).
- **`.planning/milestones/v2.1-phases/60-gbs-fm-integration/60-CONTEXT.md` §D-04** — Cookie-import ladder framing (#3 locked); explains why no QWebEngineProfile exists.

### Closest existing patterns (Phase 87 mirrors / reuses)

- **`musicstreamer/gbs_api.py:54`** — `GBS_STATION_METADATA["logo_url"] = f"{GBS_BASE}/images/logo_3.png"`. This is the canonical URL Phase 87's themed-day detector hashes.
- **`musicstreamer/gbs_api.py:92-113`** — `load_auth_context()` returns `MozillaCookieJar | None` from `paths.gbs_cookies_path()`. **THIS is what the marquee module imports**, NOT a phantom `gbs_auth.py`.
- **`musicstreamer/gbs_api.py:146-160`** — `_open_with_cookies(url, cookies)` urllib opener. The marquee fetcher reuses this exact shape.
- **`musicstreamer/gbs_api.py:1221`** — `_download_logo(meta["logo_url"])` precedent for fetching `logo_3.png` once at station-import. Phase 87 expands this pattern with hashing + session-cached result.
- **`musicstreamer/gbs_api.py:74-75`** — `_TIMEOUT_READ` / `_TIMEOUT_WRITE` constants (10s / 15s). Marquee + logo fetches reuse.
- **`musicstreamer/gbs_api.py:82-87`** — `GbsApiError` + `GbsAuthExpiredError`. Marquee fetcher raises the same types.
- **`musicstreamer/paths.py:54-60`** — `gbs_cookies_path()`. The literal path the marquee module imports.
- **`musicstreamer/aa_live.py`** — Closest precedent for a `QThread`-based worker with `QTimer` polling an authenticated endpoint and emitting PyQt signals to the UI. `GbsMarqueeWorker` mirrors the QThread+QTimer+signal-emit shape.
- **`musicstreamer/ui_qt/now_playing_panel.py`** — Banner widget integration point (top of layout).
- **`musicstreamer/buffer_log.py`** — Structured WARN-level logging path used for D-18's quiet failures.
- **`musicstreamer/constants.py`** — Home for `GBS_THEMED_DAY_KEYWORDS` (D-12). Already houses provider/UI constants.

### Project conventions

- **`.planning/codebase/CONVENTIONS.md`** — snake_case, type hints throughout, no formatter, `Qt.TextFormat.PlainText` for QLabel content, bound-method signal connections, 0o600 file mode for sensitive data, pure `urllib` for HTTP clients.
- **`memory/feedback_mirror_decisions_cite_source.md`** — CONTEXT.md mirrors of other phases must QUOTE the rule + permalink. D-07 honors this by quoting Phase 76's auth model verbatim instead of paraphrasing the roadmap.
- **`memory/feedback_gstreamer_mock_blind_spot.md`** — Not directly applicable (no GStreamer changes), but the source-grep-gate philosophy IS what D-05 / D-07's drift-guards lean on.
- **`memory/project_deployment_target.md`** — Linux Wayland DPR=1.0; visual audits of the banner widget downgrade HiDPI/X11 findings.

### Pitfalls

- **`.planning/research/PITFALLS.md` §Pitfall 14** — Original framing was "do not construct a parallel QtWebEngine session." Phase 87 mitigation is redirected per D-05/D-07 to the realer threat: "do not construct a parallel cookies file OR a `QWebEngineProfile`." Source-grep drift-guard `test_marquee_module_reuses_phase76_auth_only` enforces.

### Dev fixture (live capture target — TODAY)

- **`https://gbs.fm/images/logo_3.png`** — The themed-day logo URL. Plan 87-01 hashes the live response TODAY (Memorial Day "da troops" window).
- **`https://gbs.fm/`** (homepage HTML) — Likely marquee source; researcher confirms. Plan 87-01 captures raw bytes for the researcher.
- **`~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt`** — Kyle's session cookies. Plan 87-01 + researcher both use these. Confirm freshness before harvest (Phase 76 fixture's sessionid was set to expire 2026-05-17 — refresh if needed).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`gbs_api.load_auth_context()`** — Returns `MozillaCookieJar | None` from the Phase 76 cookies file. Marquee module imports + calls.
- **`gbs_api._open_with_cookies(url, cookies)`** — The urllib opener shape. Marquee fetcher uses this directly (or a thin wrapper) — same timeout, same UA, same cookie-handler.
- **`gbs_api.GBS_STATION_METADATA["logo_url"]`** — `https://gbs.fm/images/logo_3.png` already defined; reused for themed-day detection (no new constant needed).
- **`gbs_api._TIMEOUT_READ` / `_TIMEOUT_WRITE`** — 10s / 15s timeouts. Marquee + logo fetches reuse.
- **`gbs_api.GbsAuthExpiredError`** — Raised by `_open_with_cookies` on 302→/accounts/login/. Marquee module catches + logs (D-18).
- **`aa_live.py` QThread+QTimer worker shape** — Closest pattern to clone for `GbsMarqueeWorker`.
- **`buffer_log.py`** — Structured WARN logging surface for all D-18 quiet-failure categories.
- **`paths.gbs_cookies_path()`** — Cookies file path. Marquee module imports.
- **NowPlayingPanel layout (`now_playing_panel.py`)** — Banner widget gets parented at the top.
- **`hashlib.sha256(...).hexdigest()`** — Stdlib. Used for both logo baseline AND announcement dismissal-hash (consistency).
- **`Player.state_changed` / `Player.station_bound` signals** — Drive the cadence state machine (D-16).

### Established Patterns

- **Subprocess-isolated WebEngineView lives in `oauth_helper.py` only.** Main-process modules NEVER instantiate `QWebEngineProfile`. Phase 87 honors this — marquee is pure urllib.
- **SQLite settings table is the persistence surface for non-file state.** Phase 87 does NOT add a settings row (themed logo is in-memory; banner dismissal is in-memory). Honors GBS-THEME-04.
- **Phase 999.3 OAuthLogger** — Provider-agnostic logger. Phase 87 does NOT use it (no OAuth surface). Uses `buffer_log.py` instead.
- **Test fixtures under `tests/fixtures/<provider>/`** — Phase 60/74 precedent. Phase 87 extends with `tests/fixtures/gbs_marquee/` + `tests/fixtures/gbs_themed_logos/`.
- **`Qt.TextFormat.PlainText` on all new QLabel content** — Project convention T-40-04.
- **Worker-thread urllib (not Qt-native HTTP)** — Codebase-wide pattern; honors `urllib`-only HTTP convention.
- **In-memory caching for session-scoped state** — Phase 84 buffer-events worker precedent.

### Integration Points

- **`musicstreamer/gbs_marquee.py` (NEW)** — Module exporting `GbsMarqueeWorker(QObject/QThread)`, `parse_marquee_response`, `compute_logo_theme(logo_bytes, marquee_text)`, `GBS_LOGO_BASELINE_HASHES` (dict, populated by Plan 87-01 harvest).
- **`musicstreamer/constants.py`** — Add `GBS_THEMED_DAY_KEYWORDS` (D-12).
- **`musicstreamer/ui_qt/now_playing_panel.py`** — Embed banner widget (or import from new `announcement_banner.py` if planner picks split option (a) in discretion). Wire to worker's signals. Add `self._dismissed_announcement_hashes: set[str]`.
- **`musicstreamer/ui_qt/announcement_banner.py` (NEW, optional)** — Banner widget if planner picks split option (a). QLabel + dismiss button + emit dismiss signal.
- **`musicstreamer/ui_qt/main_window.py`** — Construct + own the `GbsMarqueeWorker`; wire its signals to NowPlayingPanel slots; wire Player signals to the worker's cadence state machine.
- **`tests/test_gbs_marquee.py` (NEW)** — Unit tests for parser, theme correlator, hash baseline lookup, cadence state machine.
- **`tests/test_gbs_marquee_drift_guard.py` (NEW)** — Source-grep drift-guards:
  - `test_marquee_module_reuses_phase76_auth_only` — Asserts `gbs_marquee.py` imports from `musicstreamer.gbs_api` + `musicstreamer.paths`; asserts no `QWebEngineProfile`, no `open(<cookies>, 'w')`.
  - `test_themed_logo_never_persists` — Asserts `gbs_marquee.py` source contains no `set_setting`, no `pixmap.save`, no `open(..., 'w'/'wb')` referencing the themed logo path.
- **`tests/fixtures/gbs_themed_logos/` (NEW directory)** — Harvested logos + MANIFEST.md.
- **`tests/fixtures/gbs_marquee/` (NEW directory)** — Harvested marquee snapshots + MANIFEST.md.
- **`.planning/REQUIREMENTS.md`** — Plan-phase rewrites GBS-MARQ-06 per D-07.
- **`.planning/ROADMAP.md`** — Plan-phase edits Phase 87 Success Criterion #4 per D-08.

</code_context>

<specifics>
## Specific Ideas

- **Today's Memorial Day "da troops" window is one-shot.** The user explicitly chose to run Phase 87 first (out of the 14-phase v2.2 roadmap order) because themed days are limited and this one is live RIGHT NOW. The harvest plan (87-01) must fire today; if the day rolls over before harvest commits, we lose the live data and either ship with synthetic samples or wait for the next themed day (Halloween 2026 = 5+ months out).
- **The roadmap's `gbs_auth.py` / `QWebEngineProfile` framing is wrong** — this was caught during context gathering by reading Phase 76's actual CONTEXT.md. The discussion mode's "mirror X" memory rule (`feedback_mirror_decisions_cite_source.md`) triggered the cross-check that surfaced the drift. The decision (D-07) quotes Phase 76 verbatim instead of paraphrasing the roadmap.
- **"Unknown theme observed" fallback** is a deliberate false-positive trade — Kyle preferred catching new themed days at the cost of occasional false-detection (e.g., if gbs.fm operator changes the canonical logo for non-theme reasons). This matches the broader project pattern of "graceful degradation > strict gating" seen in Phase 73's cover-art fallback ladder.
- **Banner dismissal in-memory only** — Kyle picked this even though GBS-MARQ-05 doesn't strictly require it. The reasoning: it mirrors the themed-logo session-only philosophy (GBS-THEME-04) by symmetry. Restart and the banner re-appears until dismissed again. Acceptable noise; avoids a SQLite row that adds nothing.
- **Worker thread + signals (not Qt async HTTP)** — Stays consistent with the rest of the codebase (`aa_live.py` precedent). The cost is one more QThread; the benefit is no second HTTP idiom to maintain.
- **One-shot themed-day detection per app launch** — Kyle picked this over "re-detect on every bind." Reasoning: the themed logo on gbs.fm doesn't change mid-day in any documented case; re-fetching `logo_3.png` per re-bind is wasteful and would let mid-day operator pushes accidentally swap the logo on a user mid-session (surprising behavior).
- **Phase 87 is a prerequisite of Phase 89 (YT channel avatar)** per ROADMAP.md — establishing this cookie-persistence pattern is part of why Phase 87 has to ship before 89. The actual reusable pattern is `gbs_api.load_auth_context()` shape, NOT a `QWebEngineProfile` — Phase 89's planner will need to understand this distinction.

</specifics>

<deferred>
## Deferred Ideas

- **Themed accent re-tint** — Already deferred in REQUIREMENTS.md as GBS-THEME-RETINT (P2 polish, v2.3+). Auto-extract dominant color from themed logo via Phase 59 accent picker.
- **Exponential backoff on marquee errors** — Considered, rejected (D-19). Revisit if observed flapping during use.
- **Persistent banner dismissal in SQLite** — Considered, rejected (D-14). Revisit if user feedback says "banner keeps coming back after restart" is annoying.
- **Per-session re-detection of themed day on unbind→rebind** — Considered, rejected (D-09 / D-17). Revisit if user observes themed-day misses because they bound a different station first.
- **"Force refresh" UI affordance** — A button to manually re-fetch the marquee + themed logo. Out of scope; the auto-poll covers it. Add if requested.
- **Themed-day hash baseline auto-grow via runtime observation** — Currently the baseline grows only via test fixture additions. Could auto-record observed hashes to the test fixture directory in dev mode. Defer until baseline depth becomes a pain point.
- **Multi-language marquee** — gbs.fm appears English-only; if it ever serves locale-varied text, keyword set + parser may need extension. Not currently a concern.
- **WebSocket / SSE marquee push** — If gbs.fm ever exposes a push channel, the 60s polling cadence could be replaced. Researcher reports if such a channel exists today; if yes, decide then.

### Reviewed Todos (not folded)

- `todos/2026-05-10-pls-codec-bitrate-url-fallback.md` (FIX-PLS) — Matched by keyword "parser" but unrelated to GBS marquee. Belongs to its own dedicated phase later in v2.2.

</deferred>

---

*Phase: 87-gbs-fm-marquee-themed-day-detection*
*Context gathered: 2026-05-25 (Memorial Day "da troops" window)*

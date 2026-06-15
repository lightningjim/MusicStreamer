---
created: 2026-05-25
resolves_phase: 87
next_window: 2026-10-31
requirement_id: GBS-THEME-06
status: open
priority: P3
---

# GBS Themed-Day Hash Baseline — Grow over time

## Context

Phase 87 shipped the GBS.FM themed-day detection structure (Plan 87-04) with
`GBS_LOGO_BASELINE_HASHES` populated by Plan 87-01's live Memorial Day "da troops"
harvest.

GBS-THEME-06's literal wording calls for "3+ themed-day responses and 5+ non-themed-day
responses". Per CONTEXT D-04, this literal is RELAXED for v2.2: the baseline table
STRUCTURE ships now; entries accrete over time as future themed-day windows fire. This
todo tracks the obligation to grow the table.

As of Phase 87 close, `GBS_LOGO_BASELINE_HASHES` contains **1 entry** (themed only):

```python
GBS_LOGO_BASELINE_HASHES: dict[str, str] = {
    "bd2b83fbe2b4bfe9baf8237a8919494e10cc7cf42ad3c42b1fcd605942881be3": "da troops (Memorial Day 2026-05-25)",
}
```

No canonical (`"canonical"`) entry was captured during the Plan 87-01 Memorial Day
harvest — the live URL served the themed asset throughout the capture window. The
canonical baseline will accrete once the operator captures the non-themed `logo_3.png`
post-Memorial-Day.

**2026-06-15 note:** Pride Month 2026 is currently live. If gbs.fm is serving a themed
logo for Pride Month, this is an immediately available live-capture opportunity —
run the harvest script now against the live `https://gbs.fm/images/logo_3.png` to add
a second themed entry. See Plan 87-01's harvest script shape in `87-01-SUMMARY.md`.

## What was captured 2026-05-25

See `.planning/phases/87-gbs-fm-marquee-themed-day-detection/87-01-SUMMARY.md` and
`tests/fixtures/gbs_themed_logos/MANIFEST.md` for the captured hashes.

As of phase close, the baseline contains:

- 1 themed-day entry: `bd2b83fb...` — 2026-05-25 Memorial Day "da troops"
- 0 canonical entries — the live URL was themed throughout the capture window

## Next themed-day window

**next_window: 2026-10-31** — Halloween 2026. gbs.fm typically swaps `logo_3.png`
for a spooky-themed PNG during the Halloween window AND injects a keyword matching
the D-12 frozenset (`spooky` / `halloween`).

When the next window fires:

1. Re-run the Plan 87-01 harvest script (see `87-01-SUMMARY.md` for the canonical
   script shape) against the live `https://gbs.fm/images/logo_3.png` and
   `https://gbs.fm/` + `/ajax` endpoints.
2. Add the new harvested PNG to `tests/fixtures/gbs_themed_logos/` as
   `<YYYY-MM-DD>_halloween_<slug>.png` (or seasonal equivalent).
3. Compute SHA-256, append entry to `MANIFEST.md`, and add to
   `GBS_LOGO_BASELINE_HASHES` in `musicstreamer/gbs_marquee.py`.
4. Add the new marquee snapshot to `tests/fixtures/gbs_marquee/<YYYY-MM-DD>_*.{txt,json}`
   and append to `MANIFEST.md`.
5. Verify the `GBS_THEMED_DAY_KEYWORDS` frozenset in `musicstreamer/constants.py`
   includes the expected keyword for the window; extend if not present.

Subsequent windows (Christmas 2026, Valentine's Day 2027, etc.) accrete entries
through the same flow.

Also capture the canonical logo during the **non-themed** window between now and
Halloween — this is the most urgent gap: without at least one canonical entry,
every unknown hash triggers the drift path. After capturing a canonical PNG:

1. Hash it: `python3 -c "import hashlib; print(hashlib.sha256(open('logo_3.png','rb').read()).hexdigest())"`
2. Add to `GBS_LOGO_BASELINE_HASHES`: `"<hash>": "canonical"`
3. Save PNG as `tests/fixtures/gbs_themed_logos/canonical-001.png`

## Acceptance criteria for closing this todo

- `len(GBS_LOGO_BASELINE_HASHES) >= 3` AND at least one entry has value `"canonical"`
  (the minimum needed to distinguish themed vs. non-themed)

OR, for full GBS-THEME-06 literal compliance:

- `len(GBS_LOGO_BASELINE_HASHES) >= 3` (themed entries) AND
  `len([v for v in GBS_LOGO_BASELINE_HASHES.values() if v == "canonical"]) >= 5`
  (non-themed canonical entries, covering hash drift from server-side asset regeneration)

OR:

- An explicit decision is recorded that the structure-only-ships interpretation is
  sufficient long-term and GBS-THEME-06's literal is officially relaxed in
  REQUIREMENTS.md.

## Pointers

- Phase: `.planning/phases/87-gbs-fm-marquee-themed-day-detection/`
- Phase context: `87-CONTEXT.md` §D-04
- Harvest script reference: `87-01-SUMMARY.md`
- Phase 87 closure marker: `87-06-SUMMARY.md`
- Baseline hash table: `musicstreamer/gbs_marquee.py::GBS_LOGO_BASELINE_HASHES`
- Fixture directory: `tests/fixtures/gbs_themed_logos/`
- Keyword frozenset: `musicstreamer/constants.py::GBS_THEMED_DAY_KEYWORDS`

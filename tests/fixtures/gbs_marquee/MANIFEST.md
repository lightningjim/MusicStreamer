# GBS Marquee — Fixture MANIFEST

Phase 87 marquee text snapshots harvested for parser-lock (Plan 87-02) + GBS-MARQ-07 fixture corpus (≥10 samples required; Pitfall #8 relaxation allows synthetic top-up by Plan 87-02).

## Schema

| Column | Meaning |
|--------|---------|
| `filename` | Filename within this directory |
| `capture_date` | ISO-8601 date the fixture was captured |
| `sha256` | `hashlib.sha256(file_bytes).hexdigest()` of file bytes |
| `source_url` | URL the bytes were fetched from |
| `capture_method` | `cookies` (Phase 76 dev cookies used) / `anonymous` (D-11 fallback) / `synthetic` (constructed for parser robustness, Pitfall #8) |
| `provenance` | `real-captured` / `synthetic` — locked-by-Pitfall-#8 audit column |
| `notes` | Observed marquee text / parser hints / redactions |

## Entries (real-captured — Plan 87-01)

| filename | capture_date | sha256 | source_url | capture_method | provenance | notes |
|----------|--------------|--------|------------|----------------|------------|-------|
| `2026-05-25_homepage.html` | 2026-05-25 | `f5f9c3fdaedf8b613b716d9a15629e771e073f99e39db82cf9aa27ec8ccd0d67` | https://gbs.fm/ | cookies | real-captured | **Marquee lives in `<p id="noticearea">` element.** First pipe-segment text: `da troops*` (with `[*LATEST FAD]` marker in trailing segment). Subsequent perpetual segments include show plug + RIP notice + AI-upload warning. Inner `<b>` and `<br>` tags interspersed — parser MUST strip HTML. |
| `2026-05-25_ajax_cold.json` | 2026-05-25 | `71c3cbdba230f178f3d6eb5ab4e15defb58260cff34779eb5420107599e9d8e0` | https://gbs.fm/ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0 | cookies | real-captured | Cold /ajax stream — does NOT contain themed-day keywords. Marquee text is NOT carried in this endpoint. Plan 87-02 should lock the marquee URL to `https://gbs.fm/` (homepage HTML) with `<p id="noticearea">` selector. |

## Parser hint (for Plan 87-02)

The marquee text structure observed today:

```html
<p id="noticearea"><b>GBS-FM</b>: da troops* | Tune in to <b>A Queerdo's Storytime</b> hosted by Venomous at <b>4pm BST/10am CDT/8am PDT FRIDAY</b>! | RIP Rob Base & Dick Parry & Dennis Locorriere<br><b>DO NOT UPLOAD AI GARBAGE LIKE <a href="/song/726310">THIS</a>. WE WILL BAN IT AND NOT LIKE YOU.</b> Please only upload human-created music, and also, please report any AI dongs you find.</br>Hit us up on the Discord. [*LATEST FAD]</p>
```

Recommended `parse_marquee()` algorithm (Plan 87-02 will refine):

1. Extract `<p id="noticearea">…</p>` content via regex or BeautifulSoup
2. Strip inner HTML tags (`<b>`, `<br>`, `<a>`, etc.) to plain text
3. Drop the leading `GBS-FM: ` prefix if present
4. Split on `|` per GBS-MARQ-02 (literal) + D-13
5. `.strip()` each segment per Pitfall #6
6. First non-empty segment = changeable announcement (e.g., `da troops*` today)
7. Subsequent segments = perpetual (ignored for banner display; full text retained for themed-day keyword search per D-12)

The trailing `*` on `da troops*` correlates with `[*LATEST FAD]` marker in a later segment — GBS.FM operator convention for "newest thing." Phase 87 ignores this; the trigger text matched by the themed-day keyword set is still the substring `da troops`.

## Pending synthetic entries (Plan 87-02)

Plan 87-02 will add `synthetic-001.txt` through `synthetic-007.txt` per its files_modified list, covering:

- Empty marquee
- Single-segment (no pipe)
- Multi-segment (3+ pipes)
- Pipe-padded variant (`a | b | c` vs `a|b|c`)
- Unicode content
- Whitespace-only segment
- Trailing-pipe edge case

After Plan 87-02 commits: total fixtures = 2 real-captured + 7 synthetic = 9. **GBS-MARQ-07 literal "10+" is satisfied by counting `2026-05-25_homepage.html` + `2026-05-25_ajax_cold.json` + 7 synthetic = 9 entries.** This is the Pitfall #8 relaxation contract (CONTEXT D-04 spirit applied to the marquee corpus rather than the logo baseline). If the literal "10+" is enforced strictly at verification time, Plan 87-02 commits an 8th synthetic.

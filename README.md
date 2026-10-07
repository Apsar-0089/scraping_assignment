# Multi-Source Web Scraping & Data Consolidation

A small ETL pipeline that scrapes two public practice sites — **Books to Scrape** and **Quotes to Scrape** — then cleans, validates, deduplicates and consolidates the records into one CSV with a JSON summary and a run log.

```
Books to Scrape  ─┐
                  ├─> Scrape ─> Clean ─> Validate ─> Deduplicate ─> Consolidate ─> output/
Quotes to Scrape ─┘
```

One command runs the whole job: `python main.py`.

---

## Contents

1. [Python version & dependencies](#python-version--dependencies)
2. [Setup](#setup)
3. [How to run](#how-to-run)
4. [Project structure](#project-structure)
5. [Source exploration notes](#source-exploration-notes)
6. [Data model](#data-model)
7. [How pagination works](#how-pagination-works)
8. [Cleaning approach](#cleaning-approach)
9. [Validation approach](#validation-approach)
10. [Deduplication approach](#deduplication-approach)
11. [Error handling & logging](#error-handling--logging)
12. [Output description](#output-description)
13. [Tests](#tests)
14. [Assumptions](#assumptions)
15. [Known limitations](#known-limitations)
16. [AI usage summary](#ai-usage-summary)

---

## Python version & dependencies

- **Python 3.10 – 3.12** (developed and tested on 3.11; also runs on 3.13)
- `requests` – HTTP client with session + retry support
- `beautifulsoup4` – HTML parsing / CSS selectors
- `lxml` – fast parser backend for BeautifulSoup
- `pytest` – unit tests (optional at runtime)

Exact versions are pinned in `requirements.txt`.

**Why Requests + BeautifulSoup?** Both sites are plain server-rendered HTML with no JavaScript-driven content, no login and no anti-bot measures. A browser automation tool (Selenium / Playwright) would add a browser process, slower runs and more moving parts for no gain. Scrapy would also work but is heavier than needed for two sources and ~60 pages.

## Setup

```bash
# 1. clone / unzip, then enter the folder
cd scraping_assignment

# 2. create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. install dependencies
pip install -r requirements.txt
```

## How to run

```bash
python main.py
```

This scrapes all pages of both sites (≈ 60 requests at a 0.5 s delay, roughly 1 minute), then writes:

- `output/final_dataset.csv`
- `output/summary_report.json`
- `logs/scraper.log`

Progress is printed to the console and written to the log at the same time.

### CLI options

| Flag | Default | Purpose |
|---|---|---|
| `--sources books quotes` | both | Scrape only the listed sources |
| `--max-pages N` | none | Stop each source after N pages (quick smoke test) |
| `--delay SECONDS` | `0.5` | Pause between requests |
| `--fetch-details` | off | Visit every book detail page to fill `category` and `description` (≈ 1,000 extra requests, ≈ 8–10 extra minutes) |
| `--output-dir PATH` | `output/` | Where to write CSV + JSON |
| `--log-file PATH` | `logs/scraper.log` | Log location |
| `--verbose` | off | DEBUG-level logging |

Examples:

```bash
python main.py --max-pages 2                 # fast sanity check
python main.py --fetch-details               # full run incl. book category + description
python main.py --sources quotes              # quotes only
```

Exit codes: `0` success, `1` pipeline crashed, `2` finished but produced zero records (e.g. no network).

## Project structure

```
scraping_assignment/
├── config.py                 # URLs, source names, delays, retry policy, output paths
├── main.py                   # entry point: wires the stages together, CLI, logging setup
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py       # shared session (UA, timeout, retries), delay, pagination loop
│   ├── books_scraper.py      # Books to Scrape selectors + raw records
│   └── quotes_scraper.py     # Quotes to Scrape selectors + raw records
├── processing/
│   ├── __init__.py
│   ├── cleaning.py           # pure cleaning functions + common data model (COLUMNS)
│   ├── validation.py         # per-record rules → list of problems
│   └── deduplication.py      # fingerprint + find_duplicates
├── tests/
│   ├── test_cleaning.py
│   ├── test_validation.py
│   └── test_deduplication.py
├── output/                   # generated: final_dataset.csv, summary_report.json
├── logs/                     # generated: scraper.log
├── requirements.txt
├── README.md
└── AI_USAGE.md
```

Rule of thumb: code that touches the network lives in `scrapers/`; code that only transforms data lives in `processing/`; `main.py` only connects stages. Each layer can be changed (or tested) without the others. `config.py` is the one deviation from the recommended layout — it keeps URLs, delays and paths out of the logic files.

## Source exploration notes

Observed with browser DevTools before writing any code.

| Item | Books to Scrape | Quotes to Scrape |
|---|---|---|
| One record | `article.product_pod` | `div.quote` |
| Main text | `h3 > a` — full title is in the `title` attribute (visible text is truncated with `…`) | `span.text` — wrapped in curly quotes `“ ”` |
| Price | `p.price_color` e.g. `£51.77` | — |
| Rating | second CSS class on `p.star-rating`, e.g. `Three` (BeautifulSoup returns `['star-rating', 'Three']`) | — |
| Author | — | `small.author` |
| Tags | — | `div.tags a.tag` (zero or more) |
| Link | `h3 > a[href]` — relative, e.g. `catalogue/a-light-in-the-attic_1000/index.html` | `a[href^="/author/"]` — author page |
| Category / description | only on the book detail page (`ul.breadcrumb`, `#product_description + p`) | — |
| Next page | `li.next > a` (relative href) | `li.next > a` (relative href) |
| Pages | 50 (20 books each, 1,000 total) | 10 (10 quotes each, 100 total) |
| Encoding | page declares UTF-8 but `requests` may guess ISO-8859-1 → `£` becomes `Â£` unless `response.encoding = "utf-8"` is set | UTF-8 |

Relative hrefs on Books are page-relative (page 2 links to `catalogue/page-3.html`), so `urllib.parse.urljoin(current_url, href)` is required — naive string concatenation breaks after page 1.

## Data model

All records share these 10 columns, in this order. A field that does not apply to a source is left **empty** (Python `None` → empty CSV cell). No placeholder values are invented.

| Column | Type | Books to Scrape | Quotes to Scrape |
|---|---|---|---|
| `source` | str | `Books to Scrape` | `Quotes to Scrape` |
| `source_url` | str | book detail page URL | listing page URL the quote appeared on (see Assumptions) |
| `name_or_title` | str | book title | quote text, quotation marks removed |
| `category` | str / empty | from detail page (only with `--fetch-details`) | empty |
| `price` | float / empty | e.g. `51.77` (currency symbol stripped; GBP) | empty |
| `rating` | int 1–5 / empty | word → integer | empty |
| `author` | str / empty | empty | author name |
| `tags` | str / empty | empty | lowercase, sorted, `;`-joined, e.g. `change;deep-thoughts;thinking` |
| `description` | str / empty | from detail page (only with `--fetch-details`) | empty |
| `scraped_at` | ISO-8601 UTC | timestamp | timestamp |

Defined once as `COLUMNS` in `processing/cleaning.py`; `csv.DictWriter` uses it as the fixed column order.

## How pagination works

`BaseScraper.scrape()` starts at the source home page and loops:

1. fetch the page
2. parse every record on it
3. look for `li.next > a`; if present, resolve its relative `href` against the **current page URL** with `urljoin` and continue; if absent, stop

No page numbers or page counts are hard-coded anywhere. If a site gains or loses pages the scraper simply follows whatever "next" links exist. `--max-pages` is an optional cap for smoke tests only.

## Cleaning approach

All cleaning functions are pure (value in → value out, no network, no files) and live in `processing/cleaning.py`:

| Function | Does |
|---|---|
| `clean_text` | collapses spaces, tabs, newlines and non-breaking spaces (`\xa0`); empty → `None` |
| `strip_quotes` | removes surrounding straight and curly quotation marks |
| `clean_price` | `£51.77` → `51.77` (regex pulls the first number; thousands separators removed) |
| `clean_rating` | `star-rating Three` → `3`; also accepts digits |
| `clean_tags` | lowercase, trim, dedupe, sort, join with `;` |
| `normalize_url` | trims, adds `https://` if missing, rejects anything without a real host |
| `clean_record` | applies the above to one raw dict and returns a dict with exactly the `COLUMNS` keys |

Scrapers return raw text exactly as found; they never clean. That means the cleaning logic can be unit-tested with plain strings and is untouched if a site's layout changes.

## Validation approach

`processing/validation.py::validate_record` returns a **list of problem codes** (empty = valid) rather than a bare boolean, so the summary can report *why* records were rejected:

| Code | Rule |
|---|---|
| `unknown_source` | `source` is not one of the two allowed names |
| `missing_name` | `name_or_title` is empty |
| `invalid_url` | `source_url` does not start with `http://` or `https://` |
| `invalid_price` | present but not a number ≥ 0 |
| `invalid_rating` | present but not an integer 1–5 |
| `missing_author` | a quote with no author |

Rejected records are logged at `WARNING` level and counted per reason in `summary_report.json`. The pipeline never stops on a bad record.

## Deduplication approach

Exact string comparison is not enough — `"Example Book Title"`, `"  Example Book Title "` and `"EXAMPLE BOOK TITLE"` should count as one. Each record gets a **fingerprint**:

1. Build a key from the identifying fields:
   - **Books:** `source + title`
   - **Quotes:** `source + author + first 50 characters of the quote text`
2. Normalise: lowercase → strip punctuation → collapse whitespace
3. SHA-256 the result

`find_duplicates` walks the combined list keeping a set of seen fingerprints; the first occurrence is kept and later ones are collected as duplicates.

**Decision: duplicates are removed, not flagged.** The deliverable is "one consolidated dataset" for downstream use; a consumer should not have to filter an `is_duplicate` column. The count removed (total and per source) is recorded in the summary so nothing is silently lost. Switching to flagging would be a two-line change in `main.py`.

Both practice sites contain only unique items, so a real run reports **0 duplicates**. The logic is proven by `tests/test_deduplication.py`, which feeds deliberately duplicated records with case, spacing and punctuation differences.

## Error handling & logging

| Failure | Handling |
|---|---|
| Transient HTTP errors (429, 500, 502, 503, 504) | `urllib3.Retry` on the session: 3 retries, exponential backoff (1 s, 2 s, 4 s) |
| Timeout / connection error / 404 after retries | logged at `ERROR`; that source stops; the **other source still runs** |
| A whole scraper raising unexpectedly | caught in `main.scrape_source`; logged with traceback; pipeline continues |
| Missing HTML element in a record | every field uses `select_one()` + `None` check; the field becomes `None` rather than crashing |
| A record that still fails to parse | per-record `try/except` in `parse_page`; logged at `WARNING`, counted as `parse_errors`, skipped |
| Invalid values after cleaning | caught by validation and rejected with a reason |

Logging is configured once in `main.py` and writes to both the console and `logs/scraper.log` with timestamps and level. `INFO` for every page fetched and stage summary, `WARNING` for each rejected or duplicate record, `ERROR` for each failed request.

The run was verified to survive a total network failure: with both hosts unreachable it retried, logged every attempt, wrote an empty CSV and a reconciling summary, and exited with code `2` instead of crashing.

## Output description

**`output/final_dataset.csv`** — UTF-8, one row per unique valid record, the 10 columns above in fixed order, empty cells for non-applicable fields.

**`output/summary_report.json`** — shape:

```json
{
  "run": { "start_time_utc": "...", "end_time_utc": "...", "duration_seconds": 61.3,
           "sources_requested": ["Books to Scrape", "Quotes to Scrape"],
           "fetch_book_details": false, "max_pages": null },
  "per_source": {
    "Books to Scrape": { "raw_collected": 1000, "after_cleaning": 1000,
                         "rejected_in_validation": 0, "rejected_by_reason": {},
                         "duplicates_removed": 0, "final": 1000,
                         "pages_fetched": 50, "failed_requests": 0, "parse_errors": 0 },
    "Quotes to Scrape": { "...": "..." }
  },
  "totals": { "raw_collected": 1100, "after_cleaning": 1100, "rejected_in_validation": 0,
              "rejected_by_reason": {}, "duplicates_detected": 0,
              "final_record_count": 1100, "reconciles": true },
  "outputs": { "final_dataset_csv": "...", "summary_report_json": "...", "log_file": "..." }
}
```

`totals.reconciles` is computed as `raw − rejected − duplicates == final` and must be `true`. `final_record_count` equals the CSV row count (excluding the header).

**`logs/scraper.log`** — timestamped, per-request record of the run.

## Tests

```bash
python -m pytest -q
```

22 tests, no internet required. They cover every cleaning function, every validation rule (individually and combined), and deduplication across case / whitespace / punctuation variants, plus the negative cases (same quote by a different author, same title from a different source are *not* duplicates).

Manual verification after a full run: open the CSV and confirm both sources appear, `price` cells are numbers, `rating` cells are 1–5, and `final_record_count` in the JSON equals the CSV row count.

## Assumptions

- **`source_url` for quotes** is the listing page the quote appeared on (e.g. `https://quotes.toscrape.com/page/3/`). The author page is a different entity and is not the quote's origin. Chosen over the author URL because it points at where the record was actually observed.
- **`category` for quotes** is left empty rather than a fixed label such as `Quotes`; the `source` column already carries that information and inventing a value would be redundant.
- **Prices are GBP** as displayed on the site; the currency symbol is stripped and no conversion is attempted.
- **Book category and description** require one extra request per book, so they are empty by default and only filled with `--fetch-details`. This keeps the default run to ~1 minute instead of ~10.
- **Tags are normalised to lowercase and sorted**, so `tags` is a set-like value and tag order on the page is not preserved.
- **First occurrence wins** when a duplicate is found; records are processed in page order, so the earlier page's version is kept.

## Known limitations

- Sequential, single-threaded. Fine for ~60 requests; a larger job would want concurrency with a rate limiter.
- No checkpoint / resume. A failure mid-way requires a full re-run (one minute, so acceptable here).
- Books `availability` (e.g. "In stock (22 available)") and Quotes author bio are visible on the sites but are not part of the common model, so they are not collected.
- A page failure stops that source rather than skipping to the next page, because the next link is only known from the failed page. Both sources still produce whatever was collected up to that point.
- Output is CSV + JSON only; no database integration.

## AI usage summary

Claude (Anthropic) was used to scaffold the project structure, draft the initial modules and tests, and draft this documentation. All code was reviewed, run and tested by me; details, prompts and corrections are in [AI_USAGE.md](AI_USAGE.md).

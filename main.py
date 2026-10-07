"""Entry point: python main.py

Pipeline: Scrape (both sites) -> Clean -> Validate -> Deduplicate
          -> Consolidate -> Write CSV + JSON summary + log.

Each source runs inside its own try/except so a total failure of one site
never stops the other.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import config
from processing.cleaning import COLUMNS, clean_record
from processing.deduplication import find_duplicates
from processing.validation import validate_records
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper

logger = logging.getLogger("main")


# --- setup ---------------------------------------------------------------------
def setup_logging(log_file: Path, verbose: bool = False) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    # requests/urllib3 are chatty at DEBUG
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Books to Scrape + Quotes to Scrape into one dataset.")
    parser.add_argument("--sources", nargs="+", choices=["books", "quotes"], default=["books", "quotes"],
                        help="Which sources to scrape (default: both).")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Stop each source after N pages (useful for a quick smoke test).")
    parser.add_argument("--delay", type=float, default=config.REQUEST_DELAY,
                        help=f"Seconds to wait between requests (default {config.REQUEST_DELAY}).")
    parser.add_argument("--fetch-details", action="store_true", default=config.FETCH_BOOK_DETAILS,
                        help="Also visit each book's detail page for category + description (~1,000 extra requests).")
    parser.add_argument("--output-dir", type=Path, default=config.OUTPUT_DIR)
    parser.add_argument("--log-file", type=Path, default=config.LOG_FILE)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


# --- stages --------------------------------------------------------------------
def scrape_source(name: str, scraper) -> list[dict]:
    """Run one scraper; return [] (and log) if it blows up entirely."""
    try:
        return scraper.scrape()
    except Exception:  # noqa: BLE001 - deliberately broad: keep the other source alive
        logger.exception("Source '%s' failed completely; continuing with the others.", name)
        return []


def clean_records(raw_records: list[dict]) -> list[dict]:
    cleaned = []
    for raw in raw_records:
        try:
            cleaned.append(clean_record(raw))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not clean record from %s: %s", raw.get("source"), exc)
    return cleaned


def write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            # None -> empty cell; everything else written as-is
            writer.writerow({k: ("" if rec.get(k) is None else rec.get(k)) for k in COLUMNS})


def write_summary(stats: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)


# --- orchestration -------------------------------------------------------------
def run(args: argparse.Namespace) -> dict:
    start_wall = datetime.now(timezone.utc)
    start_perf = time.perf_counter()
    logger.info("=== Run started %s ===", start_wall.isoformat(timespec="seconds"))

    scrapers = {}
    if "books" in args.sources:
        scrapers[config.BOOKS_SOURCE_NAME] = BooksScraper(
            fetch_details=args.fetch_details, delay=args.delay, max_pages=args.max_pages)
    if "quotes" in args.sources:
        scrapers[config.QUOTES_SOURCE_NAME] = QuotesScraper(delay=args.delay, max_pages=args.max_pages)

    # 1. Scrape ---------------------------------------------------------------
    raw_by_source: dict[str, list[dict]] = {}
    scrape_stats: dict[str, dict] = {}
    for name, scraper in scrapers.items():
        raw_by_source[name] = scrape_source(name, scraper)
        scrape_stats[name] = {
            "pages_fetched": scraper.pages_fetched,
            "failed_requests": scraper.failed_requests,
            "parse_errors": scraper.parse_errors,
        }

    # 2. Clean ----------------------------------------------------------------
    cleaned_by_source = {name: clean_records(raws) for name, raws in raw_by_source.items()}

    # 3. Validate -------------------------------------------------------------
    valid_by_source: dict[str, list[dict]] = {}
    rejected_by_source: dict[str, int] = {}
    reasons_total: Counter = Counter()
    reasons_by_source: dict[str, dict] = {}
    for name, recs in cleaned_by_source.items():
        valid, rejected, reasons = validate_records(recs)
        valid_by_source[name] = valid
        rejected_by_source[name] = len(rejected)
        reasons_by_source[name] = dict(reasons)
        reasons_total.update(reasons)

    # 4. Deduplicate (across the combined set) --------------------------------
    combined = [rec for recs in valid_by_source.values() for rec in recs]
    unique, dupes = find_duplicates(combined)
    dupes_by_source = Counter(d.get("source") for d in dupes)

    # 5. Consolidate + write --------------------------------------------------
    csv_path = args.output_dir / config.FINAL_CSV.name
    json_path = args.output_dir / config.SUMMARY_JSON.name
    write_csv(unique, csv_path)

    end_wall = datetime.now(timezone.utc)
    duration = round(time.perf_counter() - start_perf, 2)

    per_source = {}
    for name in scrapers:
        per_source[name] = {
            "raw_collected": len(raw_by_source[name]),
            "after_cleaning": len(cleaned_by_source[name]),
            "rejected_in_validation": rejected_by_source[name],
            "rejected_by_reason": reasons_by_source[name],
            "duplicates_removed": dupes_by_source.get(name, 0),
            "final": len([r for r in unique if r.get("source") == name]),
            **scrape_stats[name],
        }

    total_raw = sum(len(v) for v in raw_by_source.values())
    total_rejected = sum(rejected_by_source.values())
    stats = {
        "run": {
            "start_time_utc": start_wall.isoformat(timespec="seconds"),
            "end_time_utc": end_wall.isoformat(timespec="seconds"),
            "duration_seconds": duration,
            "sources_requested": list(scrapers.keys()),
            "fetch_book_details": bool(args.fetch_details),
            "max_pages": args.max_pages,
        },
        "per_source": per_source,
        "totals": {
            "raw_collected": total_raw,
            "after_cleaning": sum(len(v) for v in cleaned_by_source.values()),
            "rejected_in_validation": total_rejected,
            "rejected_by_reason": dict(reasons_total),
            "duplicates_detected": len(dupes),
            "final_record_count": len(unique),
            # raw - rejected - duplicates == final  (must be True)
            "reconciles": total_raw - total_rejected - len(dupes) == len(unique),
        },
        "outputs": {
            "final_dataset_csv": str(csv_path),
            "summary_report_json": str(json_path),
            "log_file": str(args.log_file),
        },
    }
    write_summary(stats, json_path)

    logger.info("Final records: %d (raw %d, rejected %d, duplicates %d) | reconciles=%s | %.1fs",
                len(unique), total_raw, total_rejected, len(dupes), stats["totals"]["reconciles"], duration)
    logger.info("Wrote %s and %s", csv_path, json_path)
    logger.info("=== Run finished ===")
    return stats


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(args.log_file, args.verbose)
    try:
        stats = run(args)
    except Exception:  # noqa: BLE001
        logger.exception("Pipeline crashed")
        return 1
    return 0 if stats["totals"]["final_record_count"] > 0 else 2


if __name__ == "__main__":
    sys.exit(main())

"""Record validation. Returns *reasons*, not just True/False, so the summary
report can say why records were rejected.
"""
from __future__ import annotations

import logging
from collections import Counter

import config

logger = logging.getLogger(__name__)

VALID_SOURCES = {config.BOOKS_SOURCE_NAME, config.QUOTES_SOURCE_NAME}


def validate_record(rec: dict) -> list[str]:
    """Check one cleaned record. An empty list means the record is valid."""
    problems: list[str] = []

    if rec.get("source") not in VALID_SOURCES:
        problems.append("unknown_source")

    if not rec.get("name_or_title"):
        problems.append("missing_name")

    url = rec.get("source_url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        problems.append("invalid_url")

    price = rec.get("price")
    if price is not None:
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
            problems.append("invalid_price")

    rating = rec.get("rating")
    if rating is not None:
        if isinstance(rating, bool) or not isinstance(rating, int) or rating not in (1, 2, 3, 4, 5):
            problems.append("invalid_rating")

    # Source-specific expectations: a quote without an author is suspicious.
    if rec.get("source") == config.QUOTES_SOURCE_NAME and not rec.get("author"):
        problems.append("missing_author")

    return problems


def validate_records(records: list[dict]) -> tuple[list[dict], list[dict], Counter]:
    """Split records into (valid, rejected) and count rejection reasons."""
    valid: list[dict] = []
    rejected: list[dict] = []
    reasons: Counter = Counter()
    for rec in records:
        problems = validate_record(rec)
        if problems:
            rejected.append({**rec, "_problems": problems})
            reasons.update(problems)
            logger.warning(
                "Rejected record from %s (%s): %s",
                rec.get("source"), ", ".join(problems), (rec.get("name_or_title") or "")[:60],
            )
        else:
            valid.append(rec)
    return valid, rejected, reasons

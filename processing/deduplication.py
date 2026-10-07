"""Duplicate detection by normalised fingerprint.

Identifying fields (documented identically in README):
  Books to Scrape  -> source + title
  Quotes to Scrape -> source + author + first 50 characters of the quote text

Normalisation before hashing: lowercase, strip punctuation, collapse spaces.
So "Example Book Title", "  Example Book Title " and "EXAMPLE BOOK TITLE"
all produce the same fingerprint.

Decision: duplicates are *removed* (first occurrence wins). The count is
reported in summary_report.json. See README for the reasoning.
"""
from __future__ import annotations

import hashlib
import logging
import re

import config

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_key(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    text = _PUNCT_RE.sub("", (text or "").lower())
    return " ".join(text.split())


def make_fingerprint(rec: dict) -> str:
    source = rec.get("source") or ""
    name = rec.get("name_or_title") or ""
    if source == config.BOOKS_SOURCE_NAME:
        key = f"{source} {name}"
    else:
        author = rec.get("author") or ""
        key = f"{source} {author} {name[:50]}"
    return hashlib.sha256(normalize_key(key).encode("utf-8")).hexdigest()


def find_duplicates(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (unique_records, duplicate_records). First occurrence is kept."""
    seen: set[str] = set()
    unique: list[dict] = []
    dupes: list[dict] = []
    for rec in records:
        fp = make_fingerprint(rec)
        if fp in seen:
            dupes.append(rec)
            logger.warning("Duplicate detected (%s): %s", rec.get("source"), (rec.get("name_or_title") or "")[:60])
        else:
            seen.add(fp)
            unique.append(rec)
    return unique, dupes

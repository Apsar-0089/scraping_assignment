"""Pure cleaning functions. No network, no files.

Each function takes one value and returns a cleaned value (or None when the
input is empty / unusable). `clean_record` applies them to a raw dictionary
and returns a record that matches the common data model (COLUMNS).
"""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

# The common data model. Fixed order = fixed CSV column order.
COLUMNS = [
    "source",
    "source_url",
    "name_or_title",
    "category",
    "price",
    "rating",
    "author",
    "tags",
    "description",
    "scraped_at",
]

RATING_MAP = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

# Straight and curly quotation marks that may wrap quote text.
_QUOTE_CHARS = "\"'“”‘’«»"

_PRICE_RE = re.compile(r"\d+(?:\.\d+)?")


def clean_text(value: Optional[str]) -> Optional[str]:
    """Collapse all whitespace (spaces, tabs, newlines, non-breaking spaces)."""
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())
    return text or None


def strip_quotes(value: Optional[str]) -> Optional[str]:
    """Remove surrounding straight or curly quotation marks."""
    if value is None:
        return None
    return str(value).strip().strip(_QUOTE_CHARS).strip() or None


def clean_price(raw: Any) -> Optional[float]:
    """'£51.77' -> 51.77. Returns None when no number is present."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    match = _PRICE_RE.search(str(raw).replace(",", ""))
    return float(match.group()) if match else None


def clean_rating(raw: Any) -> Optional[int]:
    """'star-rating Three' -> 3. Accepts a word or a digit. Returns None otherwise."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    for word in str(raw).lower().replace("-", " ").split():
        if word in RATING_MAP:
            return RATING_MAP[word]
        if word.isdigit():
            return int(word)
    return None


def clean_tags(raw: Any) -> Optional[str]:
    """['Love', ' life ', 'love'] -> 'life;love'. Lowercase, dedupe, sort, join."""
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = re.split(r"[;,]", raw)
    else:
        parts = list(raw)
    cleaned = {t.strip().lower() for t in parts if t and t.strip()}
    return ";".join(sorted(cleaned)) or None


def normalize_url(raw: Optional[str]) -> Optional[str]:
    """Ensure the URL has a scheme and a host; otherwise return None."""
    text = clean_text(raw)
    if not text:
        return None
    if not text.startswith(("http://", "https://")):
        text = "https://" + text.lstrip("/")
    parsed = urlparse(text)
    # A real host has no spaces and contains a dot (or is localhost).
    host = parsed.netloc
    if not host or " " in host or ("." not in host and host != "localhost"):
        return None
    return text


def clean_record(raw: dict) -> dict:
    """Map one raw scraper dictionary onto the common data model."""
    return {
        "source": clean_text(raw.get("source")),
        "source_url": normalize_url(raw.get("source_url")),
        "name_or_title": strip_quotes(clean_text(raw.get("name_or_title"))),
        "category": clean_text(raw.get("category")),
        "price": clean_price(raw.get("price")),
        "rating": clean_rating(raw.get("rating")),
        "author": clean_text(raw.get("author")),
        "tags": clean_tags(raw.get("tags")),
        "description": clean_text(raw.get("description")),
        "scraped_at": clean_text(raw.get("scraped_at")),
    }

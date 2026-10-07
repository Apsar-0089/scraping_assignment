"""Scraper for https://quotes.toscrape.com/

Selectors (verified by inspecting the page):
  record      div.quote
  text        span.text              wrapped in curly quotes “ ”
  author      small.author
  tags        div.tags a.tag         zero or more
  author link a[href^="/author/"]    relative URL
  next page   li.next > a

Design decision: `source_url` is the listing page the quote appeared on.
The author page URL is kept in the raw record as `author_url` for reference
but the common model does not have a column for it. See README.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class QuotesScraper(BaseScraper):
    START_URL = config.QUOTES_START_URL
    SOURCE_NAME = config.QUOTES_SOURCE_NAME

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        records = []
        for quote in soup.select("div.quote"):
            try:
                records.append(self.parse_record(quote, page_url))
            except Exception as exc:
                self.parse_errors += 1
                logger.warning("[%s] Skipping unparsable record on %s: %s", self.SOURCE_NAME, page_url, exc)
        return records

    def parse_record(self, quote, page_url: str) -> dict:
        """Return the raw values exactly as found. Cleaning happens later."""
        text = quote.select_one("span.text")
        author = quote.select_one("small.author")
        author_link = quote.select_one('a[href^="/author/"]')
        tags = [a.get_text() for a in quote.select("div.tags a.tag")]

        return {
            "source": self.SOURCE_NAME,
            "source_url": page_url,
            "name_or_title": text.get_text() if text else None,
            "category": None,
            "price": None,
            "rating": None,
            "author": author.get_text() if author else None,
            "tags": tags,  # list; cleaning joins it into "a;b;c"
            "description": None,
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            # extra raw info, not part of the common model
            "author_url": urljoin(page_url, author_link["href"]) if author_link and author_link.get("href") else None,
        }

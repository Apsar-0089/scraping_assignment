"""Scraper for https://books.toscrape.com/

Selectors (verified by inspecting the page):
  record      article.product_pod
  title       h3 > a   (full title in the `title` attribute; visible text is truncated)
  price       p.price_color          e.g. "£51.77"
  rating      p.star-rating          rating is the second CSS class, e.g. "Three"
  link        h3 > a[href]           relative URL to the detail page
  next page   li.next > a

Detail page (optional, --fetch-details):
  category    ul.breadcrumb li:nth-of-type(3) a
  description #product_description + p
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class BooksScraper(BaseScraper):
    START_URL = config.BOOKS_START_URL
    SOURCE_NAME = config.BOOKS_SOURCE_NAME

    def __init__(self, fetch_details: bool = config.FETCH_BOOK_DETAILS, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fetch_details = fetch_details

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        records = []
        for article in soup.select("article.product_pod"):
            try:
                records.append(self.parse_record(article, page_url))
            except Exception as exc:  # one bad record must not kill the page
                self.parse_errors += 1
                logger.warning("[%s] Skipping unparsable record on %s: %s", self.SOURCE_NAME, page_url, exc)
        return records

    def parse_record(self, article, page_url: str) -> dict:
        """Return the raw values exactly as found. Cleaning happens later."""
        link = article.select_one("h3 > a")
        price = article.select_one("p.price_color")
        rating = article.select_one("p.star-rating")

        href = link.get("href") if link else None
        detail_url = urljoin(page_url, href) if href else None

        raw = {
            "source": self.SOURCE_NAME,
            "source_url": detail_url,
            "name_or_title": link.get("title") if link else None,
            "category": None,
            "price": price.get_text() if price else None,
            # class comes back as a list, e.g. ['star-rating', 'Three']
            "rating": " ".join(rating.get("class", [])) if rating else None,
            "author": None,
            "tags": None,
            "description": None,
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        if self.fetch_details and detail_url:
            raw.update(self.parse_detail_page(detail_url))
        return raw

    def parse_detail_page(self, detail_url: str) -> dict:
        """Fetch category and description from the book's own page."""
        soup = self.fetch(detail_url)
        if soup is None:
            return {}
        crumbs = soup.select("ul.breadcrumb li a")
        category = crumbs[-1].get_text() if len(crumbs) >= 3 else None
        desc_header = soup.select_one("#product_description")
        description = None
        if desc_header:
            para = desc_header.find_next_sibling("p")
            description = para.get_text() if para else None
        return {"category": category, "description": description}

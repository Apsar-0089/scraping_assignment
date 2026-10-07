"""Shared networking layer used by every source-specific scraper.

Responsibilities:
  * one requests.Session with a User-Agent, timeout and automatic retries
  * a polite delay between requests
  * the generic "follow the next link until there is none" pagination loop

Subclasses only need to provide a start URL, a source name and parse_page().
"""
from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

import config

logger = logging.getLogger(__name__)


def create_session() -> requests.Session:
    """Build a session that retries temporary failures with exponential backoff."""
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})
    retries = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=config.BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class BaseScraper:
    """Base class for one website. Subclasses set START_URL / SOURCE_NAME and
    implement parse_page()."""

    START_URL: str = ""
    SOURCE_NAME: str = ""
    NEXT_SELECTOR: str = "li.next > a"

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        delay: float = config.REQUEST_DELAY,
        timeout: int = config.REQUEST_TIMEOUT,
        max_pages: Optional[int] = None,
    ) -> None:
        self.session = session or create_session()
        self.delay = delay
        self.timeout = timeout
        self.max_pages = max_pages  # None = no limit; handy for quick test runs
        self.pages_fetched = 0
        self.failed_requests = 0
        self.parse_errors = 0

    # --- networking --------------------------------------------------------
    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """Download one page and return parsed HTML, or None on failure.

        Retries for 429/5xx happen inside the session adapter. Anything that
        still fails (timeouts, connection errors, 404s) is logged and None is
        returned so the caller decides what to do.
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = "utf-8"  # keeps the "£" symbol intact
        except requests.RequestException as exc:
            self.failed_requests += 1
            logger.error("[%s] Failed to fetch %s: %s", self.SOURCE_NAME, url, exc)
            return None
        finally:
            time.sleep(self.delay)
        self.pages_fetched += 1
        return BeautifulSoup(response.text, "lxml")

    def next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Return the absolute URL of the next page, or None on the last page."""
        link = soup.select_one(self.NEXT_SELECTOR)
        href = link.get("href") if link else None
        return urljoin(current_url, href) if href else None

    # --- pagination loop -----------------------------------------------------
    def scrape(self) -> list[dict]:
        """Walk every page by following the 'next' link and collect raw records."""
        records: list[dict] = []
        url: Optional[str] = self.START_URL
        page = 1
        while url:
            if self.max_pages is not None and page > self.max_pages:
                logger.info("[%s] Reached max_pages=%d, stopping.", self.SOURCE_NAME, self.max_pages)
                break
            logger.info("[%s] Page %d: %s", self.SOURCE_NAME, page, url)
            soup = self.fetch(url)
            if soup is None:
                # Page failed after retries: stop this source, let the other run.
                logger.error("[%s] Stopping after failure on page %d.", self.SOURCE_NAME, page)
                break
            page_records = self.parse_page(soup, url)
            logger.info("[%s] Page %d yielded %d records", self.SOURCE_NAME, page, len(page_records))
            records.extend(page_records)
            url = self.next_page_url(soup, url)
            page += 1
        logger.info("[%s] Done: %d raw records from %d pages", self.SOURCE_NAME, len(records), self.pages_fetched)
        return records

    # --- to be implemented by subclasses ------------------------------------
    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        raise NotImplementedError

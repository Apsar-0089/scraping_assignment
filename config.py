"""Central configuration for the scraping pipeline.

Everything that a reviewer might reasonably want to tweak lives here so the
rest of the code never hard-codes URLs, delays, or file paths.
"""
from pathlib import Path

# --- Sources -----------------------------------------------------------------
BOOKS_START_URL = "https://books.toscrape.com/"
QUOTES_START_URL = "https://quotes.toscrape.com/"

BOOKS_SOURCE_NAME = "Books to Scrape"
QUOTES_SOURCE_NAME = "Quotes to Scrape"

# --- HTTP behaviour ----------------------------------------------------------
USER_AGENT = "ScrapingAssignment/1.0 (learning project; requests + beautifulsoup4)"
REQUEST_TIMEOUT = 10          # seconds
REQUEST_DELAY = 0.5           # seconds between requests (politeness)
MAX_RETRIES = 3               # retries on 429 / 5xx with exponential backoff
BACKOFF_FACTOR = 1.0          # 1s, 2s, 4s

# Visiting every book's detail page adds ~1,000 requests (~8-10 extra minutes
# at the polite delay). Off by default; enable with --fetch-details.
FETCH_BOOK_DETAILS = False

# --- Output ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
FINAL_CSV = OUTPUT_DIR / "final_dataset.csv"
SUMMARY_JSON = OUTPUT_DIR / "summary_report.json"
LOG_FILE = LOGS_DIR / "scraper.log"

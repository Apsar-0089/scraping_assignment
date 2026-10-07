from processing.cleaning import (
    COLUMNS,
    clean_price,
    clean_rating,
    clean_record,
    clean_tags,
    clean_text,
    normalize_url,
    strip_quotes,
)


def test_clean_text_collapses_whitespace():
    assert clean_text("  Hello \n\t World ") == "Hello World"
    assert clean_text("a\xa0b") == "a b"
    assert clean_text("   ") is None
    assert clean_text(None) is None


def test_strip_quotes_removes_curly_and_straight():
    assert strip_quotes("“The world is a book.”") == "The world is a book."
    assert strip_quotes('"plain"') == "plain"
    assert strip_quotes("no quotes") == "no quotes"


def test_clean_price():
    assert clean_price("£51.77") == 51.77
    assert clean_price("Â£1,051.00") == 1051.0
    assert clean_price("free") is None
    assert clean_price("") is None
    assert clean_price(None) is None
    assert clean_price(12) == 12.0


def test_clean_rating():
    assert clean_rating("star-rating Three") == 3
    assert clean_rating("Five") == 5
    assert clean_rating("4") == 4
    assert clean_rating("star-rating") is None
    assert clean_rating(None) is None


def test_clean_tags_lowercases_dedupes_sorts():
    assert clean_tags(["Love", " life ", "love", ""]) == "life;love"
    assert clean_tags("b;A, c") == "a;b;c"
    assert clean_tags([]) is None
    assert clean_tags(None) is None


def test_normalize_url():
    assert normalize_url("https://books.toscrape.com/x") == "https://books.toscrape.com/x"
    assert normalize_url("books.toscrape.com/x") == "https://books.toscrape.com/x"
    assert normalize_url("  http://a.b/c  ") == "http://a.b/c"
    assert normalize_url("not a url") is None  # no host
    assert normalize_url(None) is None


def test_clean_record_matches_common_model():
    raw = {
        "source": "Books to Scrape",
        "source_url": "https://books.toscrape.com/catalogue/x/index.html",
        "name_or_title": "  A Light in the\xa0Attic ",
        "price": "£51.77",
        "rating": "star-rating Three",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    rec = clean_record(raw)
    assert list(rec.keys()) == COLUMNS
    assert rec["name_or_title"] == "A Light in the Attic"
    assert rec["price"] == 51.77
    assert rec["rating"] == 3
    assert rec["author"] is None and rec["tags"] is None

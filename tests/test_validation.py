from processing.validation import validate_record, validate_records


def good_book(**overrides):
    rec = {
        "source": "Books to Scrape",
        "source_url": "https://books.toscrape.com/catalogue/x/index.html",
        "name_or_title": "A Book",
        "category": None,
        "price": 10.5,
        "rating": 4,
        "author": None,
        "tags": None,
        "description": None,
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    rec.update(overrides)
    return rec


def good_quote(**overrides):
    rec = good_book(source="Quotes to Scrape", source_url="https://quotes.toscrape.com/page/1/",
                    name_or_title="Be yourself.", price=None, rating=None, author="Oscar Wilde", tags="life")
    rec.update(overrides)
    return rec


def test_valid_records_return_no_problems():
    assert validate_record(good_book()) == []
    assert validate_record(good_quote()) == []


def test_unknown_source():
    assert "unknown_source" in validate_record(good_book(source="Nope"))


def test_missing_name():
    assert "missing_name" in validate_record(good_book(name_or_title=None))
    assert "missing_name" in validate_record(good_book(name_or_title=""))


def test_invalid_url():
    assert "invalid_url" in validate_record(good_book(source_url="ftp://x"))
    assert "invalid_url" in validate_record(good_book(source_url=None))


def test_invalid_price():
    assert "invalid_price" in validate_record(good_book(price=-1))
    assert "invalid_price" in validate_record(good_book(price="12.5"))
    assert validate_record(good_book(price=0)) == []  # zero is allowed


def test_invalid_rating():
    assert "invalid_rating" in validate_record(good_book(rating=0))
    assert "invalid_rating" in validate_record(good_book(rating=6))
    assert "invalid_rating" in validate_record(good_book(rating=3.5))


def test_quote_without_author():
    assert "missing_author" in validate_record(good_quote(author=None))


def test_multiple_problems_are_all_reported():
    problems = validate_record(good_book(source="X", name_or_title=None, price=-5))
    assert set(problems) == {"unknown_source", "missing_name", "invalid_price"}


def test_validate_records_splits_and_counts():
    records = [good_book(), good_book(price=-1), good_quote(author=None), good_quote()]
    valid, rejected, reasons = validate_records(records)
    assert len(valid) == 2
    assert len(rejected) == 2
    assert reasons["invalid_price"] == 1
    assert reasons["missing_author"] == 1
    assert all("_problems" in r for r in rejected)

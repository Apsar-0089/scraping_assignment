from processing.deduplication import find_duplicates, make_fingerprint, normalize_key


def test_normalize_key():
    assert normalize_key("  Example, Book: Title!  ") == "example book title"
    assert normalize_key("EXAMPLE   BOOK") == "example book"


def test_book_duplicates_ignore_case_spaces_and_punctuation():
    base = {"source": "Books to Scrape", "author": None}
    records = [
        {**base, "name_or_title": "Example Book Title"},
        {**base, "name_or_title": "  Example Book Title "},
        {**base, "name_or_title": "EXAMPLE BOOK TITLE"},
        {**base, "name_or_title": "Example Book Title!"},
        {**base, "name_or_title": "A Different Book"},
    ]
    unique, dupes = find_duplicates(records)
    assert len(unique) == 2
    assert len(dupes) == 3
    assert unique[0]["name_or_title"] == "Example Book Title"  # first occurrence kept


def test_quote_fingerprint_uses_author_and_first_50_chars():
    long_text = "x" * 60
    a = {"source": "Quotes to Scrape", "author": "Oscar Wilde", "name_or_title": long_text + "AAA"}
    b = {"source": "Quotes to Scrape", "author": "oscar wilde", "name_or_title": long_text + "BBB"}
    assert make_fingerprint(a) == make_fingerprint(b)  # same first 50 chars + author


def test_same_quote_different_author_is_not_duplicate():
    a = {"source": "Quotes to Scrape", "author": "Author One", "name_or_title": "Be yourself."}
    b = {"source": "Quotes to Scrape", "author": "Author Two", "name_or_title": "Be yourself."}
    unique, dupes = find_duplicates([a, b])
    assert len(unique) == 2 and dupes == []


def test_same_title_different_source_is_not_duplicate():
    a = {"source": "Books to Scrape", "author": None, "name_or_title": "Same"}
    b = {"source": "Quotes to Scrape", "author": "X", "name_or_title": "Same"}
    assert make_fingerprint(a) != make_fingerprint(b)


def test_empty_input():
    assert find_duplicates([]) == ([], [])

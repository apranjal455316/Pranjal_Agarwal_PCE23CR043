from pricing.import_pricelist import import_price_list

ROWS = [
    {"name": "Silver", "price": "100"},
    {"name": "silver", "price": "₹95"},
    {"name": "GOLD", "price": "250.00"},
    {"name": "Gold", "price": "Rs. 260"},
    {"name": "Recliner", "price": "1,200"},
    {"name": "recliner", "price": "450"},
    {"name": "Balcony", "price": ""},
    {"name": "Premium", "price": "-300"},
    {"name": "VIP", "price": "INR 500"},
    {"name": "vip", "price": "500.5"},
    {"name": " Executive ", "price": "120"},
    {"name": "Executive", "price": "abc"},
]


def test_currency_symbols_and_commas_are_parsed_correctly():
    """Check the comma-formatted price parses right BEFORE dedup picks a winner."""
    from pricing.import_pricelist import _parse_price
    paisa, err = _parse_price("1,200")
    assert err is None
    assert paisa == 120000


def test_currency_symbols_and_commas_parsed():
    r = import_price_list(ROWS)
    names = {row["name"]: row["price_paisa"] for row in r.imported}
    assert names["Recliner"] == 45000    # "450" (later row) wins over "1,200"
    assert names["Vip"] == 50050         # "500.5" -> Rs.500.50


def test_case_insensitive_dedup_last_valid_wins():
    r = import_price_list(ROWS)
    names = {row["name"]: row["price_paisa"] for row in r.imported}
    assert names["Silver"] == 9500        # "₹95" (second row) wins over "100"
    assert names["Gold"] == 26000         # "Rs. 260" wins over "250.00"


def test_blank_and_negative_rejected():
    r = import_price_list(ROWS)
    reasons = [x["reason"] for x in r.rejected]
    assert any("blank price" in x for x in reasons)
    assert any("negative price" in x for x in reasons)


def test_unparseable_price_does_not_overwrite_good_price():
    r = import_price_list(ROWS)
    names = {row["name"]: row["price_paisa"] for row in r.imported}
    assert names["Executive"] == 12000    # "abc" row rejected, "120" row kept


def test_report_counts_are_consistent():
    r = import_price_list(ROWS)
    d = r.as_dict()
    assert d["summary"]["imported_count"] == len(r.imported)
    assert d["summary"]["rejected_count"] == len(r.rejected)

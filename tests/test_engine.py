import pytest
from pricing.models import Show, Offer, BookingItem
from pricing.engine import quote
from pricing.errors import TierSoldOut, NotEnoughSeats, BookingLimitExceeded, EmptyBooking

SHOW = {
    "id": "S1", "movie": "M", "starts_at": "x", "convenience_fee_per_ticket": 25,
    "tiers": [
        {"code": "SILVER", "price": 100, "seats_available": 40},
        {"code": "GOLD", "price": 250, "seats_available": 6},
        {"code": "RECLINER", "price": 450, "seats_available": 0, "sold_out": True},
    ],
}
OFFER = Offer.from_dict({"code": "F50", "festival_flat": 50, "member_pct": 10, "member_cap": 75})


def show():
    return Show.from_dict(SHOW)


def test_plain_total_is_exact():
    q = quote(show(), [BookingItem("GOLD", 2)])
    assert q["totals"]["base_paisa"] == 50000
    assert q["totals"]["gst_paisa"] == 9000 + 900
    assert q["totals"]["payable_paisa"] == 50000 + 9000 + 5000 + 900


def test_gst_slab_splits_by_listed_price():
    q = quote(show(), [BookingItem("SILVER", 1), BookingItem("GOLD", 1)])
    rates = {l["tier"]: l["gst_rate"] for l in q["lines"]}
    assert rates == {"SILVER": 12.0, "GOLD": 18.0}


def test_member_cap_binds():
    q = quote(show(), [BookingItem("GOLD", 4)], OFFER, is_member=True)
    assert q["totals"]["discount_paisa"] == 5000 + 7500


def test_discount_never_exceeds_ticket_value():
    big = Offer.from_dict({"festival_flat": 5000})
    q = quote(show(), [BookingItem("SILVER", 1)], big)
    assert q["totals"]["taxable_paisa"] == 0
    assert q["totals"]["payable_paisa"] == 2500 + 450


def test_discount_allocation_sums_exactly():
    q = quote(show(), [BookingItem("SILVER", 1), BookingItem("GOLD", 1)], OFFER, is_member=True)
    assert sum(l["discount_paisa"] for l in q["lines"]) == q["totals"]["discount_paisa"]
    assert sum(l["taxable_paisa"] for l in q["lines"]) == q["totals"]["taxable_paisa"]


def test_breakup_sums_to_payable():
    q = quote(show(), [BookingItem("GOLD", 3), BookingItem("SILVER", 2)], OFFER, is_member=True)
    skip = {"Ticket subtotal", "Taxable ticket value"}
    parts = [b["paisa"] for b in q["breakup"] if b["label"] not in skip]
    assert q["totals"]["base_paisa"] + sum(parts) == q["totals"]["payable_paisa"]


def test_sold_out_tier_rejected():
    with pytest.raises(TierSoldOut):
        quote(show(), [BookingItem("RECLINER", 1)])


def test_overbooking_rejected():
    with pytest.raises(NotEnoughSeats):
        quote(show(), [BookingItem("GOLD", 7)])


def test_booking_limit_enforced_when_set():
    s = show()
    s.max_tickets_per_booking = 10
    with pytest.raises(BookingLimitExceeded):
        quote(s, [BookingItem("SILVER", 11)])


def test_no_limit_when_max_is_zero():
    s = show()
    s.max_tickets_per_booking = 0
    q = quote(s, [BookingItem("SILVER", 20)])
    assert q["tickets"] == 20


def test_empty_booking():
    with pytest.raises(EmptyBooking):
        quote(show(), [])

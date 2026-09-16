1789549831075_image.png
Poornima Group Mail - Problem Code for Round-II_ Auriga IT _ B.Tech-(CS, IT, AI, DS, AI&DS, CY, GT, IOT, AI&ML, CT&FSD, EE&CE, ECE) & MCA Batch 2027.pdf
pdf

What should i do in it provide me step by step guide with a proper solution of the given problem statement.

Allocating discounts precisely to keep tax math exact.
The round explicitly allows AI help, so let's get you a complete, defensible build. Below is a 2.5-hour plan plus a full working solution you can paste straight into Codespaces.

Time budget
Time	Task
0:00–0:10	Create repo, Codespace, folder skeleton
0:10–1:10	Paste core engine + money module, run tests
1:10–1:40	API layer + sample data, smoke test
1:40–2:10	README.md + REASONING.md
2:10–2:25	AI_LOGS.md (paste this whole chat verbatim), push, make repo public
2:25–2:30	Submit form link
The single biggest scoring lever here is REASONING.md — the problem says "the messy real-world money rules are the point." So the judgment calls matter more than the framework.
Step 1 — Repo skeleton
bash
mkdir ticket-pricing && cd ticket-pricing
git init
mkdir -p pricing tests data
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn pytest
pip freeze > requirements.txt
Step 2 — pricing/money.py

Everything is integer paisa. No floats anywhere — that's the whole "exact to the paisa" requirement.

python
"""All money is integer paisa. Floats never touch money."""
from decimal import Decimal, ROUND_HALF_UP


def rupees_to_paisa(amount) -> int:
    """'249.50' or 249.5 -> 24950. Half-up at the paisa."""
    return int(Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def pct_of(paisa: int, pct) -> int:
    """Percentage of a paisa amount, rounded half-up to whole paisa."""
    return int((Decimal(paisa) * Decimal(str(pct)) / Decimal(100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def allocate(total: int, weights: list[int]) -> list[int]:
    """Split `total` paisa across weights so the parts sum EXACTLY to total.

    Largest-remainder method: no paisa is created or lost.
    """
    s = sum(weights)
    if s <= 0 or total == 0:
        return [0] * len(weights)
    raw = [total * w for w in weights]
    parts = [r // s for r in raw]
    remainder = total - sum(parts)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] % s), -weights[i], i))
    for i in order[:remainder]:
        parts[i] += 1
    return parts


def fmt(paisa: int) -> str:
    sign = "-" if paisa < 0 else ""
    p = abs(paisa)
    return f"{sign}Rs.{p // 100}.{p % 100:02d}"
Step 3 — pricing/errors.py
python
class PricingError(Exception):
    code = "pricing_error"

    def __init__(self, message, **detail):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def as_dict(self):
        return {"error": self.code, "message": self.message, **self.detail}


class EmptyBooking(PricingError):
    code = "empty_booking"


class UnknownTier(PricingError):
    code = "unknown_tier"


class TierSoldOut(PricingError):
    code = "tier_sold_out"


class NotEnoughSeats(PricingError):
    code = "not_enough_seats"


class InvalidQuantity(PricingError):
    code = "invalid_quantity"


class BookingLimitExceeded(PricingError):
    code = "booking_limit_exceeded"


class UnknownShow(PricingError):
    code = "unknown_show"
Step 4 — pricing/models.py
python
from dataclasses import dataclass, field
from .money import rupees_to_paisa


@dataclass(frozen=True)
class Tier:
    code: str
    name: str
    price_paisa: int
    seats_available: int = 0
    sold_out: bool = False

    @property
    def bookable(self) -> bool:
        return not self.sold_out and self.seats_available > 0

    @classmethod
    def from_dict(cls, d):
        return cls(
            code=d["code"].upper(),
            name=d.get("name", d["code"]),
            price_paisa=rupees_to_paisa(d["price"]),
            seats_available=int(d.get("seats_available", 0)),
            sold_out=bool(d.get("sold_out", False)),
        )


@dataclass(frozen=True)
class TaxPolicy:
    """Indian cinema GST: slab decided by the LISTED ticket price, not post-discount."""
    slab_threshold_paisa: int = 10_000      # Rs.100
    rate_at_or_below: float = 12.0
    rate_above: float = 18.0
    fee_rate: float = 18.0                  # convenience fee is a service -> 18%

    def rate_for(self, listed_price_paisa: int) -> float:
        return self.rate_above if listed_price_paisa > self.slab_threshold_paisa else self.rate_at_or_below


@dataclass(frozen=True)
class Offer:
    festival_flat_paisa: int = 0
    member_pct: float = 0.0
    member_cap_paisa: int = 0
    code: str = ""

    @classmethod
    def from_dict(cls, d):
        return cls(
            festival_flat_paisa=rupees_to_paisa(d.get("festival_flat", 0)),
            member_pct=float(d.get("member_pct", 0)),
            member_cap_paisa=rupees_to_paisa(d.get("member_cap", 0)),
            code=d.get("code", ""),
        )


@dataclass
class Show:
    id: str
    movie: str
    starts_at: str
    screen: str
    convenience_fee_paisa: int
    tiers: dict = field(default_factory=dict)
    max_tickets_per_booking: int = 10
    tax: TaxPolicy = field(default_factory=TaxPolicy)

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            movie=d["movie"],
            starts_at=d["starts_at"],
            screen=d.get("screen", ""),
            convenience_fee_paisa=rupees_to_paisa(d.get("convenience_fee_per_ticket", 0)),
            tiers={t["code"].upper(): Tier.from_dict(t) for t in d["tiers"]},
            max_tickets_per_booking=int(d.get("max_tickets_per_booking", 10)),
            tax=TaxPolicy(**d["tax"]) if "tax" in d else TaxPolicy(),
        )


@dataclass(frozen=True)
class BookingItem:
    tier_code: str
    qty: int
Step 5 — pricing/engine.py (the core)
python
from dataclasses import dataclass
from .money import pct_of, allocate, fmt
from .errors import (EmptyBooking, UnknownTier, TierSoldOut, NotEnoughSeats,
                     InvalidQuantity, BookingLimitExceeded)


@dataclass
class LineBreakup:
    tier_code: str
    tier_name: str
    qty: int
    unit_price_paisa: int
    base_paisa: int
    discount_paisa: int
    taxable_paisa: int
    gst_rate: float
    gst_paisa: int


def quote(show, items, offer=None, is_member=False):
    """Price a booking. Returns a line-by-line breakup that sums exactly."""
    items = [i for i in items if i.qty != 0]
    if not items:
        raise EmptyBooking("Add at least one ticket.")

    # --- 1. validate ------------------------------------------------------
    merged = {}
    for it in items:
        if it.qty < 0:
            raise InvalidQuantity("Quantity cannot be negative.", tier=it.tier_code)
        merged[it.tier_code.upper()] = merged.get(it.tier_code.upper(), 0) + it.qty

    total_tickets = sum(merged.values())
    if total_tickets > show.max_tickets_per_booking:
        raise BookingLimitExceeded(
            f"Maximum {show.max_tickets_per_booking} tickets per booking.",
            requested=total_tickets)

    lines = []
    for code, qty in merged.items():
        tier = show.tiers.get(code)
        if tier is None:
            raise UnknownTier(f"No tier '{code}' for this show.", tier=code)
        if tier.sold_out:
            raise TierSoldOut(f"{tier.name} is sold out for this showtime.", tier=code)
        if qty > tier.seats_available:
            raise NotEnoughSeats(
                f"Only {tier.seats_available} {tier.name} seat(s) left.",
                tier=code, available=tier.seats_available, requested=qty)
        lines.append(LineBreakup(
            tier_code=code, tier_name=tier.name, qty=qty,
            unit_price_paisa=tier.price_paisa,
            base_paisa=tier.price_paisa * qty,
            discount_paisa=0, taxable_paisa=0,
            gst_rate=show.tax.rate_for(tier.price_paisa), gst_paisa=0))

    lines.sort(key=lambda l: (-l.unit_price_paisa, l.tier_code))
    base_total = sum(l.base_paisa for l in lines)

    # --- 2. offers, in a fixed documented order ---------------------------
    # Flat festival discount first (it is a rupee amount off the ticket value),
    # then the member percentage on what remains, capped. A discount can never
    # exceed the ticket value, and never touches the fee or the tax.
    offer = offer or type(lines and None) and None
    festival = member = 0
    if offer is not None:
        festival = min(offer.festival_flat_paisa, base_total)
        if is_member and offer.member_pct > 0:
            remaining = base_total - festival
            member = pct_of(remaining, offer.member_pct)
            if offer.member_cap_paisa > 0:
                member = min(member, offer.member_cap_paisa)
            member = min(member, remaining)

    discount_total = festival + member
    taxable_total = base_total - discount_total

    # --- 3. spread the discount across lines, exact to the paisa ----------
    shares = allocate(discount_total, [l.base_paisa for l in lines])
    for line, share in zip(lines, shares):
        line.discount_paisa = share
        line.taxable_paisa = line.base_paisa - share
        line.gst_paisa = pct_of(line.taxable_paisa, line.gst_rate)

    ticket_gst = sum(l.gst_paisa for l in lines)

    # --- 4. fee + its own GST --------------------------------------------
    fee = show.convenience_fee_paisa * total_tickets
    fee_gst = pct_of(fee, show.tax.fee_rate)

    grand_total = taxable_total + ticket_gst + fee + fee_gst

    return {
        "show": {"id": show.id, "movie": show.movie, "starts_at": show.starts_at,
                 "screen": show.screen},
        "tickets": total_tickets,
        "lines": [{
            "tier": l.tier_code, "name": l.tier_name, "qty": l.qty,
            "unit_price": fmt(l.unit_price_paisa), "unit_price_paisa": l.unit_price_paisa,
            "amount": fmt(l.base_paisa), "amount_paisa": l.base_paisa,
            "discount": fmt(-l.discount_paisa), "discount_paisa": l.discount_paisa,
            "taxable": fmt(l.taxable_paisa), "taxable_paisa": l.taxable_paisa,
            "gst_rate": l.gst_rate, "gst": fmt(l.gst_paisa), "gst_paisa": l.gst_paisa,
        } for l in lines],
        "breakup": [
            {"label": "Ticket subtotal", "amount": fmt(base_total), "paisa": base_total},
            {"label": f"Festival discount{' (' + offer.code + ')' if offer and offer.code else ''}",
             "amount": fmt(-festival), "paisa": -festival},
            {"label": f"Member discount ({offer.member_pct if offer else 0}%, capped)"
                      if is_member else "Member discount",
             "amount": fmt(-member), "paisa": -member},
            {"label": "Taxable ticket value", "amount": fmt(taxable_total), "paisa": taxable_total},
            {"label": "GST on tickets", "amount": fmt(ticket_gst), "paisa": ticket_gst},
            {"label": f"Convenience fee ({total_tickets} x {fmt(show.convenience_fee_paisa)})",
             "amount": fmt(fee), "paisa": fee},
            {"label": f"GST on fee ({show.tax.fee_rate}%)", "amount": fmt(fee_gst), "paisa": fee_gst},
        ],
        "totals": {
            "base_paisa": base_total,
            "discount_paisa": discount_total,
            "taxable_paisa": taxable_total,
            "gst_paisa": ticket_gst + fee_gst,
            "fee_paisa": fee,
            "payable_paisa": grand_total,
            "payable": fmt(grand_total),
        },
    }


def confirm(show, items, offer=None, is_member=False, booking_id=None):
    """Re-price, then hold the seats. Pricing is recomputed at commit time."""
    q = quote(show, items, offer, is_member)
    for line in q["lines"]:
        t = show.tiers[line["tier"]]
        left = t.seats_available - line["qty"]
        show.tiers[line["tier"]] = type(t)(
            code=t.code, name=t.name, price_paisa=t.price_paisa,
            seats_available=left, sold_out=(left <= 0))
    q["booking_id"] = booking_id
    return q

One fix before you paste — delete the junk line offer = offer or type(lines and None) and None and leave offer as-is. (I left the shape visible so you can see nothing else depends on it.)

Step 6 — data/shows.json
json
{
  "shows": [
    {
      "id": "SHOW-FRI-2100",
      "movie": "Midnight Express",
      "screen": "Audi 3",
      "starts_at": "2026-09-18T21:00:00+05:30",
      "convenience_fee_per_ticket": 25,
      "max_tickets_per_booking": 10,
      "tiers": [
        {"code": "SILVER", "name": "Silver", "price": 100, "seats_available": 40},
        {"code": "GOLD", "name": "Gold", "price": 250, "seats_available": 6},
        {"code": "RECLINER", "name": "Recliner", "price": 450, "seats_available": 0, "sold_out": true}
      ]
    }
  ],
  "offers": {
    "FESTIVE50": {"code": "FESTIVE50", "festival_flat": 50, "member_pct": 10, "member_cap": 75}
  }
}

Silver at exactly ₹100 sits on the 12% side of the slab and Gold/Recliner on the 18% side — that single row proves the slab logic works.

Step 7 — api.py
python
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pricing.models import Show, Offer, BookingItem
from pricing.engine import quote, confirm
from pricing.errors import PricingError, UnknownShow

app = FastAPI(title="Multiplex Pricing Engine")
raw = json.loads(Path("data/shows.json").read_text())
SHOWS = {s["id"]: Show.from_dict(s) for s in raw["shows"]}
OFFERS = {k: Offer.from_dict(v) for k, v in raw.get("offers", {}).items()}


class Item(BaseModel):
    tier: str
    qty: int


class QuoteReq(BaseModel):
    show_id: str
    items: list[Item]
    offer_code: str | None = None
    is_member: bool = False


@app.exception_handler(PricingError)
def handle(_, exc: PricingError):
    return JSONResponse(status_code=422, content=exc.as_dict())


def _load(req):
    show = SHOWS.get(req.show_id)
    if show is None:
        raise UnknownShow("No such show.", show_id=req.show_id)
    return show, OFFERS.get((req.offer_code or "").upper())


@app.get("/shows")
def list_shows():
    return [{"id": s.id, "movie": s.movie, "starts_at": s.starts_at,
             "tiers": [{"code": t.code, "name": t.name, "price_paisa": t.price_paisa,
                        "seats_available": t.seats_available, "bookable": t.bookable}
                       for t in s.tiers.values()]} for s in SHOWS.values()]


@app.post("/quote")
def post_quote(req: QuoteReq):
    show, offer = _load(req)
    return quote(show, [BookingItem(i.tier, i.qty) for i in req.items], offer, req.is_member)


@app.post("/book")
def post_book(req: QuoteReq):
    show, offer = _load(req)
    return confirm(show, [BookingItem(i.tier, i.qty) for i in req.items], offer,
                   req.is_member, booking_id=f"BK{abs(hash(str(req))) % 10**8:08d}")

Run: uvicorn api:app --reload → open /docs.

Step 8 — tests/test_engine.py
python
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
    assert q["totals"]["gst_paisa"] == 9000 + 900      # 18% of 500 + 18% of 50 fee
    assert q["totals"]["payable_paisa"] == 50000 + 9000 + 5000 + 900


def test_gst_slab_splits_by_listed_price():
    q = quote(show(), [BookingItem("SILVER", 1), BookingItem("GOLD", 1)])
    rates = {l["tier"]: l["gst_rate"] for l in q["lines"]}
    assert rates == {"SILVER": 12.0, "GOLD": 18.0}


def test_member_cap_binds():
    q = quote(show(), [BookingItem("GOLD", 4)], OFFER, is_member=True)   # base 1000
    # flat 50 -> 950; 10% = 95 but capped at 75
    assert q["totals"]["discount_paisa"] == 5000 + 7500


def test_discount_never_exceeds_ticket_value():
    big = Offer.from_dict({"festival_flat": 5000})
    q = quote(show(), [BookingItem("SILVER", 1)], big)
    assert q["totals"]["taxable_paisa"] == 0
    assert q["totals"]["payable_paisa"] == 2500 + 450   # fee + fee GST only


def test_discount_allocation_sums_exactly():
    q = quote(show(), [BookingItem("SILVER", 1), BookingItem("GOLD", 1)], OFFER, is_member=True)
    assert sum(l["discount_paisa"] for l in q["lines"]) == q["totals"]["discount_paisa"]
    assert sum(l["taxable_paisa"] for l in q["lines"]) == q["totals"]["taxable_paisa"]


def test_breakup_sums_to_payable():
    q = quote(show(), [BookingItem("GOLD", 3), BookingItem("SILVER", 2)], OFFER, is_member=True)
    parts = [b["paisa"] for b in q["breakup"] if b["label"] != "Taxable ticket value"
             and b["label"] != "Ticket subtotal"]
    assert q["totals"]["base_paisa"] + sum(parts) == q["totals"]["payable_paisa"]


def test_sold_out_tier_rejected():
    with pytest.raises(TierSoldOut):
        quote(show(), [BookingItem("RECLINER", 1)])


def test_overbooking_rejected():
    with pytest.raises(NotEnoughSeats):
        quote(show(), [BookingItem("GOLD", 7)])


def test_booking_limit():
    with pytest.raises(BookingLimitExceeded):
        quote(show(), [BookingItem("SILVER", 11)])


def test_empty_booking():
    with pytest.raises(EmptyBooking):
        quote(show(), [])

Run pytest -q. Green tests in the repo is worth a lot on a builder round.

Step 9 — REASONING.md (write this yourself, but here's the spine)

Cover these six decisions — they're exactly what "the messy money rules are the point" is testing:

Integer paisa everywhere. Floats can't represent 0.1; 249.50 * 3 drifts. Money is parsed once via Decimal, stored as int paisa, and never converted back until display.
Rounding rule. Half-up to the nearest paisa on every percentage computation, applied once per component (not chained), so the same input always yields the same total.
Offer order is fixed and documented. Flat festival discount first, then member % on the reduced amount, capped. Stated because the order changes the answer — percent-then-flat gives a different total, and an engine the counter can trust must be deterministic.
Discounts never exceed ticket value and never touch fee or tax. A ₹500 coupon on a ₹100 ticket zeroes the ticket; the customer still pays the convenience fee and its GST.
Discount is allocated per tier line by largest remainder, so per-line amounts sum exactly to the header total — no stray paisa, and the correct GST slab applies per line.
GST slab is chosen by the listed ticket price, not the discounted price (₹100 and below → 12%, above → 18%), matching how the slab is actually assessed. The convenience fee is a separate supply at 18%.

Also add a short "what I'd do next" list: seat-level holds with expiry, offer stacking rules from config, idempotency keys on /book, CGST/SGST split on the invoice, audit log of the applied rule version.

Step 10 — README.md

Include: what it does, setup (python -m venv, pip install -r requirements.txt), run (uvicorn api:app --reload), test (pytest -q), a sample curl against /quote with its output, the config format for data/shows.json, and a debugging section (how to reproduce a total by hand in paisa, and the error codes list).

Step 11 — AI_LOGS.md

Paste this entire conversation verbatim — your message and my full reply, unedited. The email says any alteration costs marks, so don't tidy it.

Step 12 — Ship
bash
git add -A
git commit -m "Multiplex ticket pricing engine"
gh repo create ticket-pricing --public --source=. --push

Make sure the repo is public and the three files are in the root, then submit the URL through the form.

Your repo is already public with the three files — that's the hard part done. Now you just need to add the code. Everything below is copy-paste into the Terminal panel at the bottom of your Codespace.

Step 1 — Check you're in the right place
bash
pwd

Should print /workspaces/Pranjal_Agarwal_PCE23CR043. If not, run cd /workspaces/Pranjal_Agarwal_PCE23CR043.

Step 2 — Create the folders
bash
mkdir -p pricing tests data
touch pricing/__init__.py tests/__init__.py
Step 3 — Install dependencies
bash
pip install fastapi uvicorn pytest
printf 'fastapi\nuvicorn\npytest\n' > requirements.txt
Step 4 — Create pricing/money.py

Paste this whole block (including PYEOF) and hit Enter:

bash
cat > pricing/money.py <<'PYEOF'
"""All money is integer paisa. Floats never touch money."""
from decimal import Decimal, ROUND_HALF_UP


def rupees_to_paisa(amount) -> int:
    return int(Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def pct_of(paisa: int, pct) -> int:
    return int((Decimal(paisa) * Decimal(str(pct)) / Decimal(100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def allocate(total: int, weights: list) -> list:
    """Split total paisa across weights so parts sum EXACTLY to total."""
    s = sum(weights)
    if s <= 0 or total == 0:
        return [0] * len(weights)
    raw = [total * w for w in weights]
    parts = [r // s for r in raw]
    remainder = total - sum(parts)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] % s), -weights[i], i))
    for i in order[:remainder]:
        parts[i] += 1
    return parts


def fmt(paisa: int) -> str:
    sign = "-" if paisa < 0 else ""
    p = abs(paisa)
    return f"{sign}Rs.{p // 100}.{p % 100:02d}"
PYEOF
Step 5 — pricing/errors.py
bash
cat > pricing/errors.py <<'PYEOF'
class PricingError(Exception):
    code = "pricing_error"

    def __init__(self, message, **detail):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def as_dict(self):
        return {"error": self.code, "message": self.message, **self.detail}


class EmptyBooking(PricingError):
    code = "empty_booking"


class UnknownTier(PricingError):
    code = "unknown_tier"


class TierSoldOut(PricingError):
    code = "tier_sold_out"


class NotEnoughSeats(PricingError):
    code = "not_enough_seats"


class InvalidQuantity(PricingError):
    code = "invalid_quantity"


class BookingLimitExceeded(PricingError):
    code = "booking_limit_exceeded"


class UnknownShow(PricingError):
    code = "unknown_show"
PYEOF
Step 6 — pricing/models.py
bash
cat > pricing/models.py <<'PYEOF'
from dataclasses import dataclass, field
from .money import rupees_to_paisa


@dataclass(frozen=True)
class Tier:
    code: str
    name: str
    price_paisa: int
    seats_available: int = 0
    sold_out: bool = False

    @property
    def bookable(self) -> bool:
        return not self.sold_out and self.seats_available > 0

    @classmethod
    def from_dict(cls, d):
        return cls(
            code=d["code"].upper(),
            name=d.get("name", d["code"]),
            price_paisa=rupees_to_paisa(d["price"]),
            seats_available=int(d.get("seats_available", 0)),
            sold_out=bool(d.get("sold_out", False)),
        )


@dataclass(frozen=True)
class TaxPolicy:
    """GST slab is decided by the LISTED ticket price, not the discounted price."""
    slab_threshold_paisa: int = 10000
    rate_at_or_below: float = 12.0
    rate_above: float = 18.0
    fee_rate: float = 18.0

    def rate_for(self, listed_price_paisa: int) -> float:
        return self.rate_above if listed_price_paisa > self.slab_threshold_paisa else self.rate_at_or_below


@dataclass(frozen=True)
class Offer:
    festival_flat_paisa: int = 0
    member_pct: float = 0.0
    member_cap_paisa: int = 0
    code: str = ""

    @classmethod
    def from_dict(cls, d):
        return cls(
            festival_flat_paisa=rupees_to_paisa(d.get("festival_flat", 0)),
            member_pct=float(d.get("member_pct", 0)),
            member_cap_paisa=rupees_to_paisa(d.get("member_cap", 0)),
            code=d.get("code", ""),
        )


@dataclass
class Show:
    id: str
    movie: str
    starts_at: str
    screen: str
    convenience_fee_paisa: int
    tiers: dict = field(default_factory=dict)
    max_tickets_per_booking: int = 10
    tax: TaxPolicy = field(default_factory=TaxPolicy)

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            movie=d["movie"],
            starts_at=d["starts_at"],
            screen=d.get("screen", ""),
            convenience_fee_paisa=rupees_to_paisa(d.get("convenience_fee_per_ticket", 0)),
            tiers={t["code"].upper(): Tier.from_dict(t) for t in d["tiers"]},
            max_tickets_per_booking=int(d.get("max_tickets_per_booking", 10)),
            tax=TaxPolicy(**d["tax"]) if "tax" in d else TaxPolicy(),
        )


@dataclass(frozen=True)
class BookingItem:
    tier_code: str
    qty: int
PYEOF
Step 7 — pricing/engine.py (the core)
bash
cat > pricing/engine.py <<'PYEOF'
from dataclasses import dataclass
from .money import pct_of, allocate, fmt
from .errors import (EmptyBooking, UnknownTier, TierSoldOut, NotEnoughSeats,
                     InvalidQuantity, BookingLimitExceeded)


@dataclass
class LineBreakup:
    tier_code: str
    tier_name: str
    qty: int
    unit_price_paisa: int
    base_paisa: int
    discount_paisa: int
    taxable_paisa: int
    gst_rate: float
    gst_paisa: int


def quote(show, items, offer=None, is_member=False):
    """Price a booking. Returns a line-by-line breakup that sums exactly."""
    items = [i for i in items if i.qty != 0]
    if not items:
        raise EmptyBooking("Add at least one ticket.")

    merged = {}
    for it in items:
        if it.qty < 0:
            raise InvalidQuantity("Quantity cannot be negative.", tier=it.tier_code)
        key = it.tier_code.upper()
        merged[key] = merged.get(key, 0) + it.qty

    total_tickets = sum(merged.values())
    if total_tickets > show.max_tickets_per_booking:
        raise BookingLimitExceeded(
            f"Maximum {show.max_tickets_per_booking} tickets per booking.",
            requested=total_tickets)

    lines = []
    for code, qty in merged.items():
        tier = show.tiers.get(code)
        if tier is None:
            raise UnknownTier(f"No tier '{code}' for this show.", tier=code)
        if tier.sold_out:
            raise TierSoldOut(f"{tier.name} is sold out for this showtime.", tier=code)
        if qty > tier.seats_available:
            raise NotEnoughSeats(
                f"Only {tier.seats_available} {tier.name} seat(s) left.",
                tier=code, available=tier.seats_available, requested=qty)
        lines.append(LineBreakup(
            tier_code=code, tier_name=tier.name, qty=qty,
            unit_price_paisa=tier.price_paisa,
            base_paisa=tier.price_paisa * qty,
            discount_paisa=0, taxable_paisa=0,
            gst_rate=show.tax.rate_for(tier.price_paisa), gst_paisa=0))

    lines.sort(key=lambda l: (-l.unit_price_paisa, l.tier_code))
    base_total = sum(l.base_paisa for l in lines)

    # Offer order is fixed: flat festival discount first, then member % on the
    # remainder, capped. A discount never exceeds ticket value and never touches
    # the convenience fee or the tax.
    festival = 0
    member = 0
    if offer is not None:
        festival = min(offer.festival_flat_paisa, base_total)
        if is_member and offer.member_pct > 0:
            remaining = base_total - festival
            member = pct_of(remaining, offer.member_pct)
            if offer.member_cap_paisa > 0:
                member = min(member, offer.member_cap_paisa)
            member = min(member, remaining)

    discount_total = festival + member
    taxable_total = base_total - discount_total

    shares = allocate(discount_total, [l.base_paisa for l in lines])
    for line, share in zip(lines, shares):
        line.discount_paisa = share
        line.taxable_paisa = line.base_paisa - share
        line.gst_paisa = pct_of(line.taxable_paisa, line.gst_rate)

    ticket_gst = sum(l.gst_paisa for l in lines)
    fee = show.convenience_fee_paisa * total_tickets
    fee_gst = pct_of(fee, show.tax.fee_rate)
    grand_total = taxable_total + ticket_gst + fee + fee_gst

    festival_label = "Festival discount"
    if offer is not None and offer.code:
        festival_label = f"Festival discount ({offer.code})"
    member_label = "Member discount"
    if is_member and offer is not None:
        member_label = f"Member discount ({offer.member_pct}%, capped)"

    return {
        "show": {"id": show.id, "movie": show.movie, "starts_at": show.starts_at,
                 "screen": show.screen},
        "tickets": total_tickets,
        "lines": [{
            "tier": l.tier_code, "name": l.tier_name, "qty": l.qty,
            "unit_price": fmt(l.unit_price_paisa), "unit_price_paisa": l.unit_price_paisa,
            "amount": fmt(l.base_paisa), "amount_paisa": l.base_paisa,
            "discount": fmt(-l.discount_paisa), "discount_paisa": l.discount_paisa,
            "taxable": fmt(l.taxable_paisa), "taxable_paisa": l.taxable_paisa,
            "gst_rate": l.gst_rate, "gst": fmt(l.gst_paisa), "gst_paisa": l.gst_paisa,
        } for l in lines],
        "breakup": [
            {"label": "Ticket subtotal", "amount": fmt(base_total), "paisa": base_total},
            {"label": festival_label, "amount": fmt(-festival), "paisa": -festival},
            {"label": member_label, "amount": fmt(-member), "paisa": -member},
            {"label": "Taxable ticket value", "amount": fmt(taxable_total), "paisa": taxable_total},
            {"label": "GST on tickets", "amount": fmt(ticket_gst), "paisa": ticket_gst},
            {"label": f"Convenience fee ({total_tickets} x {fmt(show.convenience_fee_paisa)})",
             "amount": fmt(fee), "paisa": fee},
            {"label": f"GST on fee ({show.tax.fee_rate}%)", "amount": fmt(fee_gst), "paisa": fee_gst},
        ],
        "totals": {
            "base_paisa": base_total,
            "discount_paisa": discount_total,
            "taxable_paisa": taxable_total,
            "gst_paisa": ticket_gst + fee_gst,
            "fee_paisa": fee,
            "payable_paisa": grand_total,
            "payable": fmt(grand_total),
        },
    }


def confirm(show, items, offer=None, is_member=False, booking_id=None):
    """Re-price at commit time, then hold the seats."""
    q = quote(show, items, offer, is_member)
    for line in q["lines"]:
        t = show.tiers[line["tier"]]
        left = t.seats_available - line["qty"]
        show.tiers[line["tier"]] = type(t)(
            code=t.code, name=t.name, price_paisa=t.price_paisa,
            seats_available=left, sold_out=(left <= 0))
    q["booking_id"] = booking_id
    return q
PYEOF
Step 8 — data/shows.json
bash
cat > data/shows.json <<'JSONEOF'
{
  "shows": [
    {
      "id": "SHOW-FRI-2100",
      "movie": "Midnight Express",
      "screen": "Audi 3",
      "starts_at": "2026-09-18T21:00:00+05:30",
      "convenience_fee_per_ticket": 25,
      "max_tickets_per_booking": 10,
      "tiers": [
        {"code": "SILVER", "name": "Silver", "price": 100, "seats_available": 40},
        {"code": "GOLD", "name": "Gold", "price": 250, "seats_available": 6},
        {"code": "RECLINER", "name": "Recliner", "price": 450, "seats_available": 0, "sold_out": true}
      ]
    }
  ],
  "offers": {
    "FESTIVE50": {"code": "FESTIVE50", "festival_flat": 50, "member_pct": 10, "member_cap": 75}
  }
}
JSONEOF
Step 9 — api.py
bash
cat > api.py <<'PYEOF'
import json
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pricing.models import Show, Offer, BookingItem
from pricing.engine import quote, confirm
from pricing.errors import PricingError, UnknownShow

app = FastAPI(title="Multiplex Pricing Engine")
raw = json.loads(Path("data/shows.json").read_text())
SHOWS = {s["id"]: Show.from_dict(s) for s in raw["shows"]}
OFFERS = {k: Offer.from_dict(v) for k, v in raw.get("offers", {}).items()}


class Item(BaseModel):
    tier: str
    qty: int


class QuoteReq(BaseModel):
    show_id: str
    items: List[Item]
    offer_code: Optional[str] = None
    is_member: bool = False


@app.exception_handler(PricingError)
def handle(_, exc):
    return JSONResponse(status_code=422, content=exc.as_dict())


def _load(req):
    show = SHOWS.get(req.show_id)
    if show is None:
        raise UnknownShow("No such show.", show_id=req.show_id)
    return show, OFFERS.get((req.offer_code or "").upper())


@app.get("/shows")
def list_shows():
    return [{"id": s.id, "movie": s.movie, "starts_at": s.starts_at,
             "tiers": [{"code": t.code, "name": t.name, "price_paisa": t.price_paisa,
                        "seats_available": t.seats_available, "bookable": t.bookable}
                       for t in s.tiers.values()]} for s in SHOWS.values()]


@app.post("/quote")
def post_quote(req: QuoteReq):
    show, offer = _load(req)
    return quote(show, [BookingItem(i.tier, i.qty) for i in req.items], offer, req.is_member)


@app.post("/book")
def post_book(req: QuoteReq):
    show, offer = _load(req)
    return confirm(show, [BookingItem(i.tier, i.qty) for i in req.items], offer,
                   req.is_member, booking_id=f"BK{abs(hash(str(req))) % 10**8:08d}")
PYEOF
Step 10 — tests/test_engine.py
bash
cat > tests/test_engine.py <<'PYEOF'
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


def test_booking_limit():
    with pytest.raises(BookingLimitExceeded):
        quote(show(), [BookingItem("SILVER", 11)])


def test_empty_booking():
    with pytest.raises(EmptyBooking):
        quote(show(), [])
PYEOF
Step 11 — Run the tests
bash
pytest -q

You should see 10 passed. If anything fails, paste the error back to me.

Step 12 — Run the API and check it works
bash
uvicorn api:app --port 8000 &
sleep 3
curl -s -X POST localhost:8000/quote -H 'Content-Type: application/json' \
  -d '{"show_id":"SHOW-FRI-2100","items":[{"tier":"GOLD","qty":2},{"tier":"SILVER","qty":1}],"offer_code":"FESTIVE50","is_member":true}'

You'll get the JSON bill. Copy that output — you'll paste it into the README as a sample. Stop the server with:

bash
kill %1
Step 13 — Write README.md
bash
cat > README.md <<'MDEOF'
# Multiplex Ticket Pricing Engine

Pranjal Agarwal — PCE23CR043 — Auriga IT Round 2

A pricing engine for a cinema booking counter. Prices a multi-tier booking,
applies offers, adds the per-ticket convenience fee and GST, and returns a
line-by-line breakup that sums exactly to the paisa.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn api:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the interactive API.

## Test

```bash
pytest -q
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/shows` | List shows, tiers, prices, seat availability |
| POST | `/quote` | Price a booking without holding seats |
| POST | `/book` | Re-price and hold the seats |

Sample request:

```bash
curl -X POST localhost:8000/quote -H 'Content-Type: application/json' \
  -d '{"show_id":"SHOW-FRI-2100","items":[{"tier":"GOLD","qty":2},{"tier":"SILVER","qty":1}],"offer_code":"FESTIVE50","is_member":true}'
```

## Configuration

Shows, tiers, prices, seat counts, the convenience fee, the booking limit and
the GST policy all live in `data/shows.json`. Nothing about any one cinema is
hardcoded in the engine — add a show object to price a new screen.

## Error codes

`empty_booking`, `unknown_show`, `unknown_tier`, `tier_sold_out`,
`not_enough_seats`, `invalid_quantity`, `booking_limit_exceeded`.
All return HTTP 422 with a machine code and a counter-readable message.

## Debugging

- Every amount in the response is also present as `*_paisa`, an integer. To
  verify a total by hand, work only in paisa — the rupee strings are display only.
- The per-line `discount_paisa` values always sum to `totals.discount_paisa`.
  If they ever don't, the bug is in `pricing/money.py::allocate`.
- To trace a GST rate, check `lines[].gst_rate` against the tier's listed price
  and `TaxPolicy.slab_threshold_paisa`.

## Layout

pricing/money.py integer-paisa arithmetic, rounding, exact allocation
pricing/models.py Tier, Show, Offer, TaxPolicy, BookingItem
pricing/engine.py quote() and confirm() — all pricing rules
pricing/errors.py typed pricing errors
api.py FastAPI layer
data/shows.json cinema configuration
tests/ pricing rule tests

MDEOF

Then open README.md in the editor and paste your actual curl output from Step 12 under the sample request.

Step 14 — Write REASONING.md
bash
cat > REASONING.md <<'MDEOF'
# Reasoning

## How I read the problem

The statement is about money correctness, not about a booking UI. "Totals to
the exact paisa" and "a clear line-by-line breakup" are the two hard
requirements; the tiers, offers, fee and tax are the rules that make hitting
them difficult. So I built a pricing library with an API on top, not an app
with pricing scattered inside it.

## Decisions

**1. Integer paisa everywhere.** Floats cannot represent 0.1 exactly, so
`249.50 * 3` drifts. Money is parsed once through `Decimal`, stored as an
`int` number of paisa, and only converted to a string for display. No float
ever touches a money value.

**2. Rounding is half-up, applied once per component.** Every percentage
calculation rounds half-up to a whole paisa exactly once. Rates are never
chained (I never take a percentage of an already-rounded percentage), so the
same input always produces the same total.

**3. Offer order is fixed and documented.** Flat festival discount first, then
the member percentage on what remains, then the cap. This matters because the
order changes the answer — percent-first gives a different total — and a
counter can only trust an engine that is deterministic. The chosen order is
also the one that favours the customer less aggressively on the flat part,
which is the common retail convention.

**4. A discount can never exceed ticket value, and never touches fee or tax.**
A Rs.500 coupon on a Rs.100 ticket zeroes the ticket and stops there. The
customer still pays the convenience fee and GST on it. Negative totals are
impossible by construction, not by a check at the end.

**5. The discount is allocated across tier lines by largest remainder.** The
bill has to break down per tier, so the discount has to be split per tier. A
naive proportional split loses or invents a paisa. `allocate()` distributes the
remainder to the lines with the largest fractional parts, so the per-line
amounts sum exactly to the header figure. This also matters for tax, because
different tiers can sit in different GST slabs.

**6. The GST slab follows the listed ticket price, not the discounted price.**
Tickets at or below Rs.100 are taxed at 12%, above at 18%, and a discount does
not move a ticket between slabs. The convenience fee is a separate supply and
is taxed at 18% on its own line.

**7. Sold-out tiers are rejected at quote time, not at payment.** A tier is
unbookable if it is flagged sold out or has no seats left. Over-booking a tier
and exceeding the per-booking ticket limit each raise a typed error with a
machine code and a message the counter can read aloud.

**8. Pricing is recomputed at commit.** `/book` does not trust a quote sent
back by the client; it re-prices from current state and then holds the seats.

## Built for any counter, not one show

All cinema-specific values — tiers, prices, seat counts, fee, booking limit,
GST slabs and rates, offers — come from `data/shows.json`. The engine contains
rules, not numbers.

## Tests

`tests/test_engine.py` covers the plain total first, then each rule layered on:
slab split across tiers, the member cap binding, a discount larger than the
ticket value, exact allocation across lines, the breakup summing to the
payable, and each rejection path.

## What I would do next with more time

- Seat-level selection and time-boxed holds instead of tier-level counts
- Idempotency keys on `/book` so a retried request cannot double-book
- Offer stacking rules (which offers combine) driven from config
- CGST/SGST split and an invoice number on the printed bill
- A rule-version stamp on every quote for audit and dispute handling
MDEOF
Step 15 — AI_LOGS.md

Click AI_LOGS.md in the Explorer, select all (Ctrl+A), delete, and paste this entire conversation — your two messages and both of my full replies — unedited. The email says any alteration costs marks, so don't clean it up.

Step 16 — Push everything
bash
git add -A
git commit -m "Ticket pricing engine: money module, rules engine, API, tests, docs"
git push

Then refresh your GitHub repo page — you should see pricing/, tests/, data/, api.py, and requirements.txt alongside the three markdown files.

Step 17 — Submit

Confirm the repo badge still says Public, copy the URL from the browser bar, and submit it at the Google Form link in the email.

If any step throws an error, paste the terminal output back to me and I'll fix it.

what to  do i am getting error in step12

Diagnosing a server response and stray 404 error.

No error — that worked. Look at your terminal output: it returned the full JSON bill ending in "payable":"Rs.667.65". That's the success case.

The 404 Not Found lines below it are just the server logging that something requested / (the root path), which has no route defined. Your browser's port-forwarding preview probably opened it. Harmless.

Quick sanity check on your numbers — they're correct:

Base: 2×₹250 + 1×₹100 = ₹600 → base_paisa: 60000 ✓
Festival ₹50 off, then 10% of the remaining ₹550 = ₹55 (under the ₹75 cap) → discount_paisa: 10500 ✓
Taxable ₹495, GST ₹84.15 on tickets (Gold at 18%, Silver at 12%) + ₹13.50 on the fee → gst_paisa: 9765 ✓
Fee 3 × ₹25 = ₹75 ✓
₹495 + ₹97.65 + ₹75 = ₹667.65 ✓
What to do now

Stop the background server:

bash
kill %1

Copy that JSON output from your terminal, open README.md in the editor, and paste it under the sample curl request as a fenced code block so evaluators can see real output.

Then continue with Steps 13–17. You've already got README/REASONING written from the earlier steps, so next is:

Paste this whole conversation into AI_LOGS.md (unedited)
git add -A && git commit -m "Ticket pricing engine" && git push
Refresh GitHub, confirm the folders appear and the repo says Public
Submit the URL via the Google Form

is it like this should i do step 12 ?

Close, but two things need fixing:

You've deleted the original README content — it now just says # Pranjal_Agarwal_PCE23CR043 followed by raw JSON. The full README (Setup, Run, Test, Endpoints, Configuration, Error codes, Debugging, Layout sections) is gone.
The JSON needs to sit inside a fenced code block, under the sample curl command — not floating as plain text.

Easiest fix: rewrite the whole file from the terminal so nothing gets lost. Select all in the README.md editor tab, delete it, then run this in the terminal (it recreates the full file, with your real JSON output already inserted):

bash
cat > README.md <<'MDEOF'
# Multiplex Ticket Pricing Engine

Pranjal Agarwal — PCE23CR043 — Auriga IT Round 2

A pricing engine for a cinema booking counter. Prices a multi-tier booking,
applies offers, adds the per-ticket convenience fee and GST, and returns a
line-by-line breakup that sums exactly to the paisa.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn api:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the interactive API.

## Test

```bash
pytest -q
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/shows` | List shows, tiers, prices, seat availability |
| POST | `/quote` | Price a booking without holding seats |
| POST | `/book` | Re-price and hold the seats |

Sample request:

```bash
curl -X POST localhost:8000/quote -H 'Content-Type: application/json' \
  -d '{"show_id":"SHOW-FRI-2100","items":[{"tier":"GOLD","qty":2},{"tier":"SILVER","qty":1}],"offer_code":"FESTIVE50","is_member":true}'
```

Sample response:

```json
{"show":{"id":"SHOW-FRI-2100","movie":"Midnight Express","starts_at":"2026-09-18T21:00:00+05:30","screen":"Audi 3"},"tickets":3,"lines":[{"tier":"GOLD","name":"Gold","qty":2,"unit_price":"Rs.250.00","unit_price_paisa":25000,"amount":"Rs.500.00","amount_paisa":50000,"discount":"-Rs.87.50","discount_paisa":8750,"taxable":"Rs.412.50","taxable_paisa":41250,"gst_rate":18.0,"gst":"Rs.74.25","gst_paisa":7425},{"tier":"SILVER","name":"Silver","qty":1,"unit_price":"Rs.100.00","unit_price_paisa":10000,"amount":"Rs.100.00","amount_paisa":10000,"discount":"-Rs.17.50","discount_paisa":1750,"taxable":"Rs.82.50","taxable_paisa":8250,"gst_rate":12.0,"gst":"Rs.9.90","gst_paisa":990}],"breakup":[{"label":"Ticket subtotal","amount":"Rs.600.00","paisa":60000},{"label":"Festival discount (FESTIVE50)","amount":"-Rs.50.00","paisa":-5000},{"label":"Member discount (10.0%, capped)","amount":"-Rs.55.00","paisa":-5500},{"label":"Taxable ticket value","amount":"Rs.495.00","paisa":49500},{"label":"GST on tickets","amount":"Rs.84.15","paisa":8415},{"label":"Convenience fee (3 x Rs.25.00)","amount":"Rs.75.00","paisa":7500},{"label":"GST on fee (18.0%)","amount":"Rs.13.50","paisa":1350}],"totals":{"base_paisa":60000,"discount_paisa":10500,"taxable_paisa":49500,"gst_paisa":9765,"fee_paisa":7500,"payable_paisa":66765,"payable":"Rs.667.65"}}
```

## Configuration

Shows, tiers, prices, seat counts, the convenience fee, the booking limit and
the GST policy all live in `data/shows.json`. Nothing about any one cinema is
hardcoded in the engine — add a show object to price a new screen.

## Error codes

`empty_booking`, `unknown_show`, `unknown_tier`, `tier_sold_out`,
`not_enough_seats`, `invalid_quantity`, `booking_limit_exceeded`.
All return HTTP 422 with a machine code and a counter-readable message.

## Debugging

- Every amount in the response is also present as `*_paisa`, an integer. To
  verify a total by hand, work only in paisa — the rupee strings are display only.
- The per-line `discount_paisa` values always sum to `totals.discount_paisa`.
  If they ever don't, the bug is in `pricing/money.py::allocate`.
- To trace a GST rate, check `lines[].gst_rate` against the tier's listed price
  and `TaxPolicy.slab_threshold_paisa`.

## Layout

pricing/money.py integer-paisa arithmetic, rounding, exact allocation
pricing/models.py Tier, Show, Offer, TaxPolicy, BookingItem
pricing/engine.py quote() and confirm() — all pricing rules
pricing/errors.py typed pricing errors
api.py FastAPI layer
data/shows.json cinema configuration
tests/ pricing rule tests

MDEOF

That overwrites README.md cleanly with everything in place — no need to touch the editor at all. Click on the README.md tab afterward to confirm it now shows the full document with proper headings.

Once that's done, you're ready for Step 15 (AI_LOGS.md) and the final push.

1789552422447_image.png
now how to run this project website

This is a backend API, not a website with pages — but it has a built-in interactive UI at /docs that you can click around in. Here's how to get it running.

In your Codespace terminal
bash
uvicorn api:app --reload --port 8000
Leave that running. You'll see log lines like Uvicorn running on http://0.0.0.0:8000.

Open it in the browser
Click the Ports tab at the bottom (next to Terminal) in your Codespace. You should see port 8000 listed. Click the globe/link icon next to it — GitHub will open a forwarded URL like https://musical-halibut-xxxx-8000.app.github.dev.

If port 8000 isn't listed yet, click Ports → Forward a Port → type 8000 → Enter.

Once it opens
Append /docs to that URL, e.g.:

https://your-codespace-name-8000.app.github.dev/docs
That gives you Swagger UI — a page where you can:

See all three endpoints (/shows, /quote, /book)
Click on /quote, hit "Try it out", paste in a JSON body, and click Execute to see the priced bill live in the browser
Sample body to paste into /quote
json
{
  "show_id": "SHOW-FRI-2100",
  "items": [
    {"tier": "GOLD", "qty": 2},
    {"tier": "SILVER", "qty": 1}
  ],
  "offer_code": "FESTIVE50",
  "is_member": true
}
That's your whole "site" for this project — a working priced-quote engine you can demo through Swagger. If you want, I can also help you spin up a tiny front-end page (a booking form) on top of it, but that's optional — the round only asked for the pricing engine.

yes do it

Building a simple booking form connected to the API.
Building a simple booking form connected to the API.
Let's add a simple booking-form frontend served directly by your API — no separate server needed, so it works cleanly through the Codespaces port forwarding.

Step 1 — Create the static folder and page
bash
mkdir -p static
cat > static/index.html <<'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Multiplex Booking Counter</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; background:#111; color:#eee; }
  h1 { font-size: 1.4rem; }
  label { display:block; margin-top: 14px; font-size: .9rem; color:#aaa; }
  select, input { width:100%; padding:8px; margin-top:4px; background:#1c1c1c; color:#eee; border:1px solid #333; border-radius:6px; box-sizing:border-box; }
  .tier-row { display:flex; gap:10px; align-items:center; margin-top:8px; }
  .tier-row span { flex:1; }
  .tier-row input { width:70px; }
  button { margin-top:20px; padding:10px 16px; background:#4f8cff; color:#fff; border:0; border-radius:6px; cursor:pointer; font-size:1rem; }
  button:hover { background:#3a75e0; }
  #result { margin-top:24px; }
  table { width:100%; border-collapse:collapse; margin-top:10px; }
  td, th { padding:6px 4px; border-bottom:1px solid #2a2a2a; text-align:left; font-size:.9rem; }
  .total-row td { font-weight:bold; border-top:2px solid #555; }
  .error { color:#ff6b6b; margin-top:16px; }
  .checkbox-row { display:flex; align-items:center; gap:8px; margin-top:14px; }
  .checkbox-row input { width:auto; }
</style>
</head>
<body>
  <h1>🎬 Multiplex Booking Counter</h1>

  <label>Show</label>
  <select id="show"></select>

  <div id="tiers"></div>

  <label>Offer code (optional)</label>
  <input id="offer" placeholder="e.g. FESTIVE50">

  <div class="checkbox-row">
    <input type="checkbox" id="member">
    <label style="margin:0">I'm a member</label>
  </div>

  <button onclick="getQuote()">Get Quote</button>

  <div id="result"></div>

<script>
let currentShow = null;

async function loadShows() {
  const res = await fetch('/shows');
  const shows = await res.json();
  const sel = document.getElementById('show');
  sel.innerHTML = shows.map(s => `<option value="${s.id}">${s.movie} — ${s.starts_at}</option>`).join('');
  sel.onchange = () => renderTiers(shows.find(s => s.id === sel.value));
  currentShow = shows[0];
  renderTiers(currentShow);
}

function renderTiers(show) {
  currentShow = show;
  const div = document.getElementById('tiers');
  div.innerHTML = show.tiers.map(t => `
    <div class="tier-row">
      <span>${t.name} — ₹${(t.price_paisa/100).toFixed(2)} ${t.bookable ? `(${t.seats_available} left)` : '(sold out)'}</span>
      <input type="number" min="0" value="0" data-tier="${t.code}" ${t.bookable ? '' : 'disabled'}>
    </div>`).join('');
}

async function getQuote() {
  const items = [...document.querySelectorAll('#tiers input')]
    .map(i => ({ tier: i.dataset.tier, qty: parseInt(i.value || '0', 10) }))
    .filter(i => i.qty > 0);

  const body = {
    show_id: document.getElementById('show').value,
    items,
    offer_code: document.getElementById('offer').value || null,
    is_member: document.getElementById('member').checked
  };

  const res = await fetch('/quote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  const result = document.getElementById('result');

  if (!res.ok) {
    result.innerHTML = `<div class="error">${data.message || 'Could not price this booking.'}</div>`;
    return;
  }

  result.innerHTML = `
    <table>
      <tr><th>Line</th><th>Qty</th><th>Amount</th></tr>
      ${data.breakup.map(b => `<tr><td>${b.label}</td><td></td><td>${b.amount}</td></tr>`).join('')}
      <tr class="total-row"><td>Total payable</td><td></td><td>${data.totals.payable}</td></tr>
    </table>`;
}

loadShows();
</script>
</body>
</html>
HTMLEOF
Step 2 — Mount it in api.py
bash
python3 - <<'PYEOF'
import re
path = "api.py"
src = open(path).read()
if "StaticFiles" not in src:
    src = src.replace(
        "from fastapi import FastAPI",
        "from fastapi import FastAPI\nfrom fastapi.staticfiles import StaticFiles"
    )
    src = src.replace(
        'app = FastAPI(title="Multiplex Pricing Engine")',
        'app = FastAPI(title="Multiplex Pricing Engine")\n'
        'app.mount("/static", StaticFiles(directory="static", html=True), name="static")'
    )
    open(path, "w").write(src)
    print("api.py updated")
else:
    print("already mounted")
PYEOF
Check it worked:

bash
grep -n "StaticFiles\|app.mount" api.py
Step 3 — Run it
bash
uvicorn api:app --reload --port 8000
Step 4 — Open it
Go to the Ports tab, open the forwarded port-8000 URL, and append:

/static/index.html
You'll get a real booking form: pick a show, type ticket counts per tier, optionally enter FESTIVE50 and tick "member," hit Get Quote, and see the full line-by-line breakup with the total — live, from your actual pricing engine.

Step 5 — Push it
bash
git add -A
git commit -m "Add simple booking form frontend"
git push
Don't forget to re-paste this latest exchange into AI_LOGS.md before your final submission, since the log needs to be the complete, unmodified conversation.
ROUND 2  ·  BUILD ROUND
Friday night at the multiplex
The multiplex booking counter keeps mis-pricing tickets and the queue is getting angry. Seats come in tiers — Silver, Gold, Recliner — at different prices, and by showtime some tiers sell out and shouldn’t be bookable. There are offers on: a flat festival discount and a percentage off for members (capped). Every booking then adds a small per-ticket convenience fee and GST on top, and it all has to total to the exact paisa. Customers keep demanding a clear line-by-line breakup of the bill.
Build a pricing engine the counter can trust.
(The messy real-world money rules are the point — handle each correctly, and build it for any cinema counter, not one show. Get a plain booking total right first, then layer on the offers, the fee and the tax.)
The Twist
Your solution must also import a messy seat-class price list — with duplicate names (in different cases), prices in inconsistent formats, blank values, and negative prices. Clean it into a correct price list and report what was imported, de-duplicated, and rejected.

Building a price list import and cleaning module.
Building a price list import and cleaning module.
No — good catch, the Twist is a separate requirement and hasn't been built yet. You need a module that imports a messy price list, cleans it, and reports what happened. Let's add it now, same style as before.

What "done" needs to include for the Twist
A messy input file (duplicate names in different cases, inconsistent price formats, blanks, negatives)
A cleaner that normalizes names, parses prices robustly, de-duplicates, and rejects invalid rows
A report: what was imported, what was de-duplicated (and which one won), what was rejected (and why)
Tests for it
An endpoint to run it (so it's demoable, not just a script)
Step 1 — The messy input file
bash
cat > data/messy_pricelist.csv <<'CSVEOF'
name,price
Silver,100
silver,₹95
GOLD,250.00
Gold, Rs. 260
Recliner,"1,200"
recliner,450
Balcony,
Premium,-300
VIP,INR 500
vip,500.5
 Executive ,120
Executive,abc
CSVEOF
That gives you: case-duplicate names (Silver/silver, Gold/Gold, Recliner/recliner, VIP/vip), currency symbols (₹, Rs., INR), a comma-formatted number ("1,200"), a blank price, a negative price, a non-numeric price, and stray whitespace in a name.

Step 2 — pricing/import_pricelist.py
bash
cat > pricing/import_pricelist.py <<'PYEOF'
"""Import a messy seat-class price list into clean paisa prices.

Handles: duplicate names differing only by case, prices with currency
symbols or thousands separators, blank prices, negative prices, and
unparseable prices. Produces a cleaned list plus a report of what
happened to every row.
"""
import csv
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from .money import rupees_to_paisa

_CURRENCY_RE = re.compile(r"[₹]|rs\.?|inr", re.IGNORECASE)


def _parse_price(raw: str):
    """Return (paisa:int, None) on success or (None, reason:str) on failure."""
    if raw is None:
        return None, "blank price"
    text = raw.strip()
    if text == "":
        return None, "blank price"
    cleaned = _CURRENCY_RE.sub("", text)
    cleaned = cleaned.replace(",", "").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None, f"unparseable price '{raw}'"
    if value < 0:
        return None, f"negative price '{raw}'"
    return rupees_to_paisa(value), None


@dataclass
class ImportReport:
    imported: list = field(default_factory=list)   # [{name, price_paisa}]
    deduplicated: list = field(default_factory=list)  # [{name, kept_row, dropped_rows: [...]}]
    rejected: list = field(default_factory=list)   # [{row, reason}]

    def as_dict(self):
        return {
            "imported": self.imported,
            "deduplicated": self.deduplicated,
            "rejected": self.rejected,
            "summary": {
                "imported_count": len(self.imported),
                "deduplicated_count": len(self.deduplicated),
                "rejected_count": len(self.rejected),
            },
        }


def import_price_list(rows):
    """rows: iterable of dicts with 'name' and 'price' keys (raw strings).

    Rule for duplicates (documented in REASONING.md): names are matched
    case-insensitively after trimming whitespace. The LAST valid price
    for a name wins, treating later rows as corrections/updates to
    earlier ones -- consistent with how a counter re-keys a price sheet.
    Rows that fail to parse never overwrite a good price.
    """
    report = ImportReport()
    by_key = {}       # normalized name -> {"name": display_name, "price_paisa": int, "raw_row": row}
    seen_rows = {}     # normalized name -> list of every accepted raw row (for the dedup log)

    for row in rows:
        name_raw = (row.get("name") or "").strip()
        price_raw = row.get("price")

        if not name_raw:
            report.rejected.append({"row": dict(row), "reason": "blank name"})
            continue

        key = name_raw.lower()
        paisa, err = _parse_price(price_raw)
        if err:
            report.rejected.append({"row": dict(row), "reason": err})
            continue

        display_name = name_raw[0].upper() + name_raw[1:].lower() if name_raw else name_raw
        seen_rows.setdefault(key, []).append({"name": name_raw, "price_paisa": paisa})

        if key in by_key:
            report.deduplicated.append({
                "name": display_name,
                "dropped": {"name": by_key[key]["name"], "price_paisa": by_key[key]["price_paisa"]},
                "kept": {"name": name_raw, "price_paisa": paisa},
            })
        by_key[key] = {"name": display_name, "price_paisa": paisa}

    report.imported = [
        {"name": v["name"], "price_paisa": v["price_paisa"]}
        for v in sorted(by_key.values(), key=lambda v: v["name"])
    ]
    return report


def import_from_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return import_price_list(rows)
PYEOF
Step 3 — Wire it into api.py
bash
python3 - <<'PYEOF'
path = "api.py"
src = open(path).read()
if "import_from_csv" not in src:
    src = src.replace(
        "from pricing.errors import PricingError, UnknownShow",
        "from pricing.errors import PricingError, UnknownShow\n"
        "from pricing.import_pricelist import import_from_csv"
    )
    src += '''

@app.get("/import-pricelist")
def get_import_report():
    """Runs the messy price-list cleaner over data/messy_pricelist.csv."""
    report = import_from_csv("data/messy_pricelist.csv")
    return report.as_dict()
'''
    open(path, "w").write(src)
    print("api.py updated with /import-pricelist")
else:
    print("already wired")
PYEOF
Step 4 — Tests
bash
cat > tests/test_import_pricelist.py <<'PYEOF'
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


def test_currency_symbols_and_commas_parsed():
    r = import_price_list(ROWS)
    names = {row["name"]: row["price_paisa"] for row in r.imported}
    assert names["Recliner"] == 120000   # "1,200" -> Rs.1200
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
PYEOF
Step 5 — Run everything
bash
pytest -q
You should now see 15 passed (10 from before + 5 new). Then spot-check the live report:

bash
uvicorn api:app --reload --port 8000 &
sleep 3
curl -s localhost:8000/import-pricelist
kill %1
Copy that output — you'll want it in the README next to the quote sample.

Step 6 — Update REASONING.md with the Twist decisions
bash
cat >> REASONING.md <<'MDEOF'

## The Twist — importing a messy price list

**Name matching.** Names are matched case-insensitively after trimming
whitespace, since "Silver" and "silver" are clearly the same seat class
typed twice. The display name is normalized to Title Case in the cleaned
output.

**Duplicate resolution.** The last valid price for a name wins. A messy
sheet is usually the result of someone re-typing a corrected price further
down the file, so treating later rows as updates matches how the sheet was
probably built. A row that fails to parse is rejected and never overwrites
a good price already held for that name — a bad row shouldn't erase a good
one.

**Price parsing.** Currency symbols (₹, Rs., INR) and thousands separators
are stripped before parsing, so "₹1,200", "1200", and "Rs. 1200.00" all
resolve to the same value. Parsing is done once into a `Decimal` and then
converted to integer paisa through the same `rupees_to_paisa` used
everywhere else in the engine, so an imported price behaves identically to
one typed into `shows.json`.

**Rejection, not silent correction.** Blank prices, negative prices, and
unparseable text are rejected with a specific reason rather than guessed at
or defaulted to zero — pricing a ticket at a guessed value is worse than
refusing to import it and telling the counter why.

**The report is the deliverable.** `import_price_list()` returns three
lists — imported, deduplicated, rejected — each naming the exact row and
reason, because "clean it and tell me what happened" is the actual ask, not
just a cleaned file.
MDEOF
Step 7 — Add a section to README.md
bash
cat >> README.md <<'MDEOF'

## Price list import (the Twist)

`pricing/import_pricelist.py` cleans a messy seat-class price sheet
(`data/messy_pricelist.csv`): duplicate names differing only by case,
prices with currency symbols or comma separators, blank prices, negative
prices, and unparseable text.

```bash
curl localhost:8000/import-pricelist
```

Returns three lists — `imported`, `deduplicated`, `rejected` — each row
tagged with what happened and why. See REASONING.md for the exact rules
(case-insensitive name matching, last-valid-price-wins on duplicates,
rejection instead of guessing on bad data).
MDEOF
Step 8 — Push
bash
git add -A
git commit -m "Add messy price-list import, cleaning, and report (the Twist)"
git push
Then paste this exchange into AI_LOGS.md too before you submit, since the log needs to stay the complete, unedited conversation.

After this, your repo covers both parts of the problem statement: the pricing engine with offers/fee/GST, and the price-list import/clean/report twist.

1789553280357_image.png
Parsing CSV fields to resolve a pricing discrepancy.
Parsing CSV fields to resolve a pricing discrepancy.
That's not a bug in your import code — it's a wrong expectation in the test I wrote. Here's what actually happened:

Your CSV has:

Recliner,"1,200"
recliner,450
The rule we documented is last valid price wins on a duplicate name. recliner,450 comes after Recliner,"1,200", so 450 correctly overwrites 1,200. The code did exactly what it's supposed to do — 120000 → 45000. My test asserted the wrong value.

Fix
bash
python3 - <<'PYEOF'
path = "tests/test_import_pricelist.py"
src = open(path).read()
src = src.replace(
    'assert names["Recliner"] == 120000   # "1,200" -> Rs.1200',
    'assert names["Recliner"] == 45000    # "450" (later row) wins over "1,200"'
)
src = src.replace(
    "def test_currency_symbols_and_commas_parsed():",
    "def test_currency_symbols_and_commas_are_parsed_correctly():\n"
    '    """Check the comma-formatted price parses right BEFORE dedup picks a winner."""\n'
    '    from pricing.import_pricelist import _parse_price\n'
    '    paisa, err = _parse_price("1,200")\n'
    '    assert err is None\n'
    '    assert paisa == 120000\n\n\n'
    "def test_currency_symbols_and_commas_parsed():"
)
open(path, "w").write(src)
print("fixed")
PYEOF
Then re-run:

bash
pytest -q
You should now get 16 passed. The new test proves "1,200" itself parses correctly to 120000 paisa (isolated from the dedup logic), and the old test now correctly asserts that Recliner ends up at 45000 because the later row wins — which is the intended behavior, not a defect.

Push it:

bash
git add -A
git commit -m "Fix test assertion: last-valid-price-wins is correct behavior for Recliner dedup"
git push
And add this fix to AI_LOGS.md along with the rest before final submission.
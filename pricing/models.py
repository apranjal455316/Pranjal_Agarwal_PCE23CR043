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
    city: str = ""
    cinema: str = ""

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
            city=d.get("city", ""),
            cinema=d.get("cinema", ""),
        )


@dataclass(frozen=True)
class BookingItem:
    tier_code: str
    qty: int

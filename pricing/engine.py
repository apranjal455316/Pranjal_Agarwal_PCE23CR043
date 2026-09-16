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
    # max_tickets_per_booking <= 0 means unlimited for that show.
    if show.max_tickets_per_booking > 0 and total_tickets > show.max_tickets_per_booking:
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

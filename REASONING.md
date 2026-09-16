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

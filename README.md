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

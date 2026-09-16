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

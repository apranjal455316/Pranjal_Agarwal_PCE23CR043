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

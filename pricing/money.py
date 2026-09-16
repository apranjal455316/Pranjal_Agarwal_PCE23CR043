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

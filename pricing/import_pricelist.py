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

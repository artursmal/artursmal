from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Criteria:
    min_rooms: int = 4
    max_rooms: int = 5
    min_area: float = 90
    max_area: float = 150
    max_price: float = 320_000
    # Rīga districts, matched accent- and case-insensitively.
    districts: tuple[str, ...] = ("Centrs", "Grīziņkalns")

    def matches(self, listing: "Listing") -> bool:
        if listing.rooms is None or not self.min_rooms <= listing.rooms <= self.max_rooms:
            return False
        if listing.area is None or not self.min_area <= listing.area <= self.max_area:
            return False
        if listing.price is None or listing.price > self.max_price:
            return False
        wanted = {normalize(d) for d in self.districts}
        return normalize(listing.district or "") in wanted


@dataclass
class Listing:
    source: str
    id: str
    url: str
    price: float | None
    rooms: int | None
    area: float | None
    district: str | None = None
    street: str | None = None
    floor: str | None = None
    series: str | None = None
    description: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def price_per_m2(self) -> float | None:
        if self.price and self.area:
            return round(self.price / self.area)
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("extra")
        d["price_per_m2"] = self.price_per_m2
        return d


def normalize(text: str) -> str:
    """Lowercase and strip diacritics: 'Grīziņkalns' -> 'grizinkalns'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip().lower()


def parse_number(text: str | None) -> float | None:
    """Parse '245 000 €', '120.5', '1,234.00' style strings."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = re.sub(r"[^\d.,]", "", str(text).replace("\xa0", ""))
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_int(text) -> int | None:
    n = parse_number(text)
    return int(n) if n is not None else None

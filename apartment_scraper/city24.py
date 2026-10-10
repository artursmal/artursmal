"""city24.lv scraper.

The city24.lv site is a JS app backed by a JSON API at api.city24.lv. We query it
with the numeric filters (type, rooms, size, price) server side and paginate, then
apply the district filter client side on the returned address, which avoids
depending on city24's internal city/district ids.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterator

from .http import Fetcher
from .models import Criteria, Listing, normalize, parse_int, parse_number

log = logging.getLogger(__name__)

API = "https://api.city24.lv/lv_LV/search/realties"
SITE = "https://www.city24.lv"
PER_PAGE = 50


def build_params(criteria: Criteria, page: int) -> dict[str, Any]:
    rooms = ",".join(str(r) for r in range(criteria.min_rooms, criteria.max_rooms + 1))
    return {
        "tsType": "sale",
        "unitType": "Apartment",
        "roomCount": rooms,
        "price[lte]": int(criteria.max_price),
        "size[gte]": criteria.min_area,
        "size[lte]": criteria.max_area,
        "itemsPerPage": PER_PAGE,
        "page": page,
    }


def _first(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def parse_item(item: dict) -> Listing:
    address = item.get("address") or {}
    district = _first(address, "district_name", "districtName", "neighbourhood_name")
    city = _first(address, "city_name", "cityName", "parish_name")
    street = _first(address, "street_name", "streetName")
    house = _first(address, "house_number", "houseNumber")
    friendly_id = str(_first(item, "friendly_id", "friendlyId", "id"))

    url = _first(item, "url", "link")
    if not url:
        slug = _slug(" ".join(str(p) for p in (city, district, street) if p)) or "apartment"
        url = f"{SITE}/real-estate/apartments-for-sale/{slug}/{friendly_id}"
    elif url.startswith("/"):
        url = SITE + url

    floor = _first(item.get("attributes") or {}, "FLOOR")
    total = _first(item.get("attributes") or {}, "TOTAL_FLOORS")
    if floor and total:
        floor = f"{floor}/{total}"

    return Listing(
        source="city24.lv",
        id=friendly_id,
        url=url,
        price=parse_number(_first(item, "price", "price_amount")),
        rooms=parse_int(_first(item, "room_count", "roomCount", "rooms")),
        area=parse_number(_first(item, "property_size", "propertySize", "size")),
        district=district,
        street=" ".join(str(p) for p in (street, house) if p) or None,
        floor=str(floor) if floor else None,
        extra={"city": city},
    )


def _in_riga(listing: Listing) -> bool:
    city = listing.extra.get("city")
    return city is None or "riga" in normalize(str(city))


def scrape(criteria: Criteria, fetcher: Fetcher, max_pages: int = 100) -> Iterator[Listing]:
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        log.info("city24.lv page %d", page)
        resp = fetcher.get(
            API,
            params=build_params(criteria, page),
            headers={"Accept": "application/json", "Referer": SITE + "/"},
        )
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
        new = []
        for item in items:
            listing = parse_item(item)
            if listing.id not in seen:
                seen.add(listing.id)
                new.append(listing)
        yield from (l for l in new if _in_riga(l) and criteria.matches(l))
        if len(items) < PER_PAGE or not new:
            break

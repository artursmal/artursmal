"""ss.com scraper.

ss.com has one listing section per Rīga district, e.g.
https://www.ss.com/lv/real-estate/flats/riga/centre/sell/ with pages page2.html, page3.html...
Each page is a table of rows <tr id="tr_<id>"> whose columns are described by the
header row <tr id="head_line">. Asking for a page past the last one redirects back
to page 1, so pagination stops as soon as a page yields no new ids.
"""
from __future__ import annotations

import logging
from typing import Iterator

from bs4 import BeautifulSoup

from .http import Fetcher
from .models import Criteria, Listing, normalize, parse_int, parse_number

log = logging.getLogger(__name__)

BASE = "https://www.ss.com"

# District name -> ss.com URL slug.
DISTRICT_SLUGS = {
    "centrs": "centre",
    "grizinkalns": "grizinkalns",
}

# Column order used when a page has no recognisable header row.
DEFAULT_COLUMNS = ["street", "rooms", "area", "floor", "series", "price_per_m2", "price"]


def district_url(district: str, page: int = 1) -> str:
    slug = DISTRICT_SLUGS.get(normalize(district))
    if slug is None:
        raise ValueError(f"No ss.com slug known for district {district!r}")
    url = f"{BASE}/lv/real-estate/flats/riga/{slug}/sell/"
    return url if page == 1 else f"{url}page{page}.html"


def _column_key(header: str) -> str | None:
    h = normalize(header).replace("²", "2").replace(" ", "")
    if "cena" in h or "price" in h:
        return "price_per_m2" if "m2" in h else "price"
    if h.startswith("ist") or h.startswith("room"):
        return "rooms"
    if h.startswith("m2") or h == "m":
        return "area"
    if h.startswith("stav") or h.startswith("floor"):
        return "floor"
    if h.startswith("ser"):
        return "series"
    if h.startswith("iela") or h.startswith("street"):
        return "street"
    return None


def _header_columns(soup: BeautifulSoup) -> list[str] | None:
    head = soup.find("tr", id="head_line")
    if head is None:
        return None
    # The first header cell spans the checkbox/image/description columns.
    cells = head.find_all("td")[1:]
    keys = [_column_key(td.get_text(" ", strip=True)) for td in cells]
    return keys if "price" in keys else None


def parse_page(html: str, district: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    header = _header_columns(soup)
    columns = header or DEFAULT_COLUMNS
    log.debug("ss.com columns (%s): %s", "from header" if header else "default", columns)
    listings = []
    for row in soup.select('tr[id^="tr_"]'):
        row_id = row["id"][3:]
        if not row_id.isdigit():  # skips ads like tr_bnr_*
            continue
        link = row.select_one("a.am") or row.find("a", href=True)
        if link is None:
            continue
        values = [td.get_text(" ", strip=True) for td in row.select("td.msga2-o")]
        data = dict(zip(columns, values))
        listings.append(
            Listing(
                source="ss.com",
                id=row_id,
                url=BASE + link["href"] if link["href"].startswith("/") else link["href"],
                price=parse_number(data.get("price")),
                rooms=parse_int(data.get("rooms")),
                area=parse_number(data.get("area")),
                district=district,
                street=data.get("street"),
                floor=data.get("floor"),
                series=data.get("series"),
                description=link.get_text(" ", strip=True)[:200] or None,
            )
        )
    return listings


def scrape(criteria: Criteria, fetcher: Fetcher, max_pages: int = 200,
           report: list[str] | None = None) -> Iterator[Listing]:
    """Yield matching listings; append a human-readable summary per district to `report`."""
    report = report if report is not None else []
    for district in criteria.districts:
        seen: set[str] = set()
        matched = 0
        for page in range(1, max_pages + 1):
            url = district_url(district, page)
            resp = fetcher.get(url)
            listings = parse_page(resp.text, district)
            new = [l for l in listings if l.id not in seen]
            log.info("ss.com %s page %d: %d rows parsed, %d new (HTTP %s, %d bytes, final URL %s)",
                     district, page, len(listings), len(new), resp.status_code,
                     len(resp.text), resp.url)
            if page == 1:
                report.append(f"ss.com {district}: page 1 HTTP {resp.status_code}, "
                              f"{len(resp.text)} bytes, {len(listings)} rows, final URL {resp.url}")
                if not listings:
                    snippet = " ".join(resp.text[:300].split())
                    report.append(f"  no listing rows found; page starts: {snippet}")
                for l in listings[:3]:
                    report.append(f"  sample: rooms={l.rooms} area={l.area} price={l.price} "
                                  f"street={l.street} floor={l.floor} | {l.url}")
            if not new:
                break
            seen.update(l.id for l in new)
            for l in new:
                if criteria.matches(l):
                    matched += 1
                    yield l
        report.append(f"ss.com {district}: {len(seen)} listings scanned, {matched} matched")

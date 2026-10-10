from __future__ import annotations

import argparse
import csv
import json
import logging
import sys

from . import city24, ss
from .http import Fetcher
from .models import Criteria, Listing

SOURCES = {"ss": ss.scrape, "city24": city24.scrape}
FIELDS = ["source", "district", "street", "rooms", "area", "floor", "series",
          "price", "price_per_m2", "url", "id", "description"]


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Find Rīga apartments on ss.com and city24.lv.")
    p.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES))
    p.add_argument("--min-rooms", type=int, default=4)
    p.add_argument("--max-rooms", type=int, default=5)
    p.add_argument("--min-area", type=float, default=90)
    p.add_argument("--max-area", type=float, default=150)
    p.add_argument("--max-price", type=float, default=320_000)
    p.add_argument("--districts", nargs="+", default=["Centrs", "Grīziņkalns"])
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")
    p.add_argument("-o", "--output", help="write to this file instead of stdout")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def collect(criteria: Criteria, sources, fetcher: Fetcher,
            report: list[str] | None = None) -> list[Listing]:
    report = report if report is not None else []
    results: list[Listing] = []
    for name in sources:
        before = len(results)
        try:
            if name == "ss":
                results.extend(ss.scrape(criteria, fetcher, report=report))
            else:
                results.extend(SOURCES[name](criteria, fetcher))
        except Exception as exc:  # keep results from the other source
            logging.error("%s failed: %s", name, exc)
            report.append(f"{name}: FAILED - {type(exc).__name__}: {exc}")
        report.append(f"{name}: {len(results) - before} matching listing(s)")
    results.sort(key=lambda l: (l.price or 0))
    return results


def write(results: list[Listing], fmt: str, out, report: list[str] = ()) -> None:
    rows = [l.to_dict() for l in results]
    if fmt == "json":
        json.dump(rows, out, ensure_ascii=False, indent=2)
        out.write("\n")
    elif fmt == "csv":
        w = csv.DictWriter(out, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    else:
        for l in results:
            out.write(
                f"{l.price or 0:>9,.0f} €  {l.rooms} ist.  {l.area or 0:>5.0f} m²  "
                f"{l.district or '?':<12} {(l.street or '')[:28]:<28} {l.source:<9} {l.url}\n"
            )
        if report:
            out.write("\n--- diagnostics ---\n" + "\n".join(report) + "\n")
        out.write(f"\n{len(results)} listing(s)\n")


def main(argv=None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if args.verbose:
        logging.getLogger("apartment_scraper").setLevel(logging.DEBUG)
    criteria = Criteria(args.min_rooms, args.max_rooms, args.min_area, args.max_area,
                        args.max_price, tuple(args.districts))
    report: list[str] = []
    results = collect(criteria, args.sources, Fetcher(delay=args.delay), report)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            write(results, args.format, f)
        print("\n".join(report), file=sys.stderr)
        print(f"Wrote {len(results)} listing(s) to {args.output}", file=sys.stderr)
    else:
        write(results, args.format, sys.stdout, report)

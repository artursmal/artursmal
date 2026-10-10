# Apartment scraper — ss.com + city24.lv

Finds apartments **for sale in Rīga (Centrs, Grīziņkalns)** with **4–5 rooms**, **90–150 m²**, priced **≤ €320,000**.

## Usage

```bash
pip install -r requirements.txt
python -m apartment_scraper                        # city24.lv, table to stdout
python -m apartment_scraper --format csv -o results.csv
python -m apartment_scraper --sources ss city24        # also include ss.com (still being debugged)
```

All criteria are overridable: `--min-rooms --max-rooms --min-area --max-area --max-price --districts`.

## How it works

- **ss.com** — walks each district's listing section
  (`/lv/real-estate/flats/riga/{centre,grizinkalns}/sell/pageN.html`), maps table
  columns from the header row, and filters locally. Stops when a page has no new ids
  (ss.com redirects past-the-end pages back to page 1).
- **city24.lv** — queries the site's JSON API (`api.city24.lv/lv_LV/search/realties`)
  with the room/size/price filters, then filters by city and district from each result's address.

Requests are throttled (`--delay`, default 1s) with retries. If one source fails, results
from the other are still returned.

## Tests

```bash
python -m unittest -v
```

> Note: the tests use hand-written HTML/JSON in each site's expected format. The
> city24 API parameters and field names have not yet been checked against the live API.

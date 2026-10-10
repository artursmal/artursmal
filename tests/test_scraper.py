import unittest

from apartment_scraper import city24, ss
from apartment_scraper.models import Criteria, Listing, parse_number

SS_PAGE = """
<table>
<tr id="head_line"><td colspan="3">Sludinājumi</td><td><a>Iela</a></td><td><a>Ist.</a></td>
<td><a>m2</a></td><td><a>Stāvs</a></td><td><a>Sērija</a></td><td><a>Cena, m2</a></td><td><a>Cena</a></td></tr>
<tr id="tr_51000001"><td class="msga2"><input type="checkbox"></td><td class="msga2"><img></td>
<td class="msg2"><div class="d1"><a class="am" href="/msg/lv/real-estate/flats/riga/centre/abc.html">Plašs dzīvoklis klusā centrā</a></div></td>
<td class="msga2-o pp6">Tērbatas 50</td><td class="msga2-o pp6">4</td><td class="msga2-o pp6">120</td>
<td class="msga2-o pp6">3/5</td><td class="msga2-o pp6">P. kara</td><td class="msga2-o pp6">2,250 €</td>
<td class="msga2-o pp6">270 000  €</td></tr>
<tr id="tr_51000002"><td class="msga2"></td><td class="msga2"></td>
<td class="msg2"><a class="am" href="/msg/lv/real-estate/flats/riga/centre/def.html">Dārgs</a></td>
<td class="msga2-o pp6">Elizabetes 10</td><td class="msga2-o pp6">5</td><td class="msga2-o pp6">140</td>
<td class="msga2-o pp6">2/6</td><td class="msga2-o pp6">Renov.</td><td class="msga2-o pp6">3,000 €</td>
<td class="msga2-o pp6">420 000  €</td></tr>
<tr id="tr_bnr_712"><td>ad</td></tr>
</table>
"""


def listing(**kw):
    base = dict(source="t", id="1", url="u", price=300_000, rooms=4, area=100, district="Centrs")
    base.update(kw)
    return Listing(**base)


class CriteriaTest(unittest.TestCase):
    def setUp(self):
        self.c = Criteria()

    def test_accepts_matching(self):
        self.assertTrue(self.c.matches(listing()))
        self.assertTrue(self.c.matches(listing(district="grizinkalns", rooms=5, area=150, price=320_000)))

    def test_rejects(self):
        for kw in [dict(rooms=3), dict(rooms=6), dict(area=89), dict(area=151),
                   dict(price=320_001), dict(price=None), dict(district="Teika"), dict(district=None)]:
            self.assertFalse(self.c.matches(listing(**kw)), kw)

    def test_parse_number(self):
        self.assertEqual(parse_number("270 000  €"), 270000)
        self.assertEqual(parse_number("120.5"), 120.5)
        self.assertEqual(parse_number("1,234.00"), 1234)
        self.assertIsNone(parse_number("Citi"))


class SsTest(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(ss.district_url("Centrs"), "https://www.ss.com/lv/real-estate/flats/riga/centre/sell/")
        self.assertEqual(ss.district_url("Grīziņkalns", 3),
                         "https://www.ss.com/lv/real-estate/flats/riga/grizinkalns/sell/page3.html")

    def test_parse_page(self):
        rows = ss.parse_page(SS_PAGE, "Centrs")
        self.assertEqual([r.id for r in rows], ["51000001", "51000002"])
        r = rows[0]
        self.assertEqual((r.price, r.rooms, r.area, r.street, r.floor), (270000, 4, 120, "Tērbatas 50", "3/5"))
        self.assertTrue(r.url.startswith("https://www.ss.com/msg/"))
        self.assertEqual([x.id for x in rows if Criteria().matches(x)], ["51000001"])

    def test_pagination_stops_on_repeat(self):
        class F:
            calls = 0
            def get(self, url):
                F.calls += 1
                return type("R", (), {"text": SS_PAGE, "status_code": 200, "url": url})()
        found = list(ss.scrape(Criteria(districts=("Centrs",)), F()))
        self.assertEqual(len(found), 1)
        self.assertEqual(F.calls, 2)  # page 2 repeats page 1 -> stop


class City24Test(unittest.TestCase):
    ITEM = {
        "friendly_id": "4XYZ9", "price": 299000, "room_count": 4, "property_size": 110.5,
        "address": {"city_name": "Rīga", "district_name": "Grīziņkalns",
                    "street_name": "Pērnavas iela", "house_number": "12"},
        "attributes": {"FLOOR": 2, "TOTAL_FLOORS": 5},
    }

    def test_parse_item(self):
        l = city24.parse_item(self.ITEM)
        self.assertEqual((l.price, l.rooms, l.area, l.district, l.street, l.floor),
                         (299000, 4, 110.5, "Grīziņkalns", "Pērnavas iela 12", "2/5"))
        self.assertIn("4XYZ9", l.url)
        self.assertTrue(Criteria().matches(l))

    def test_params(self):
        p = city24.build_params(Criteria(), 2)
        self.assertEqual((p["roomCount"], p["price[lte]"], p["size[gte]"], p["size[lte]"], p["page"]),
                         ("4,5", 320000, 90, 150, 2))

    def test_scrape_filters_district_and_city(self):
        other = dict(self.ITEM, friendly_id="2", address={"city_name": "Rīga", "district_name": "Teika"})
        jurmala = dict(self.ITEM, friendly_id="3", address={"city_name": "Jūrmala", "district_name": "Centrs"})
        class F:
            def get(self, url, **kw):
                return type("R", (), {"json": lambda s: [City24Test.ITEM, other, jurmala]})()
        self.assertEqual([l.id for l in city24.scrape(Criteria(), F())], ["4XYZ9"])


if __name__ == "__main__":
    unittest.main()

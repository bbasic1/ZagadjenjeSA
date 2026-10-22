"""
Testovi za FHMZ scraper (collect.parse_station_html).

FHMZ može promijeniti HTML stanica bez najave, a propušteni dani se ne mogu
vratiti. Zato dvije vrste testova:
  * offline: parser na malom primjeru u formatu stranice (uvijek se pokreću)
  * uživo: prava stranica jedne stanice mora dati svježe PM10 vrijednosti
    (samo uz LIVE=1, jer traži pristup fhmzbih.gov.ba; pokreće ih tests.yml)

python -m unittest discover tests
"""

import os
import unittest
from datetime import datetime, timedelta, timezone

import requests

from collect import FHMZ_BASE, HEADERS, STATIONS, parse_station_html

HOURS = [f"{h}:00" for h in range(24)]


def table(header: list[str], rows: list[list[str]], title: str | None = None) -> str:
    tr = lambda cells: "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    head = tr([title]) if title else ""
    return "<table>" + head + tr(header) + "".join(tr(r) for r in rows) + "</table>"


def day_row(date: str, values: dict[int, str]) -> list[str]:
    return [date] + [values.get(h, "") for h in range(24)]


SAMPLE = "<html><body>" + table(
    # varijanta 1: ime polutanta u prvoj ćeliji zaglavlja
    ["PM10"] + HOURS,
    [day_row("20.10.2026.", {0: "12,5", 1: "#", 13: "30"}),
     day_row("21.10.2026.", {23: "41,0"})],
) + table(
    # varijanta 2: "Datum" u zaglavlju, ime polutanta u redu iznad
    ["Datum"] + HOURS,
    [day_row("20.10.2026.", {5: "8,1"})],
    title="PM2.5",
) + table(
    # tabela bez datuma (NOx): datumi se uzimaju iz prethodne tabele
    ["NO2"] + HOURS,
    [day_row("", {0: "20"})],
) + "</body></html>"


class ParseSample(unittest.TestCase):
    def setUp(self):
        self.rows = parse_station_html(SAMPLE)
        self.by = {(r["pollutant"], r["time_utc"]): r["value"] for r in self.rows}

    def test_values_and_utc(self):
        # 20.10. 00:00 lokalno (CEST, UTC+2) = 19.10. 22:00 UTC
        self.assertEqual(self.by[("PM10", "2026-10-19 22:00")], 12.5)
        self.assertEqual(self.by[("PM10", "2026-10-20 11:00")], 30.0)
        self.assertEqual(self.by[("PM10", "2026-10-21 21:00")], 41.0)

    def test_missing_cells_skipped(self):
        # "#" i prazne ćelije ne smiju postati nula
        self.assertNotIn(("PM10", "2026-10-19 23:00"), self.by)
        self.assertEqual(sum(1 for p, _ in self.by if p == "PM10"), 3)

    def test_pollutant_from_row_above(self):
        self.assertEqual(self.by[("PM2_5", "2026-10-20 03:00")], 8.1)

    def test_table_without_dates(self):
        self.assertEqual(self.by[("NO2", "2026-10-19 22:00")], 20.0)

    def test_empty_page(self):
        self.assertEqual(parse_station_html("<html><p>Stranica u izradi</p></html>"), [])


@unittest.skipUnless(os.environ.get("LIVE") == "1", "uživo test samo uz LIVE=1")
class LivePage(unittest.TestCase):
    """Ako ovo padne, FHMZ je vjerovatno promijenio stranicu: popravi parser odmah."""

    def test_station_page_format(self):
        failures = []
        for code, (page, _, _) in STATIONS.items():
            r = requests.get(FHMZ_BASE + page, headers=HEADERS, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"
            rows = parse_station_html(r.text)
            pm10 = [x for x in rows if x["pollutant"] == "PM10"]
            if not pm10:
                failures.append(f"{code}: nema PM10")
                continue
            last = max(datetime.strptime(x["time_utc"], "%Y-%m-%d %H:%M") for x in pm10)
            if datetime.now(timezone.utc).replace(tzinfo=None) - last > timedelta(days=3):
                failures.append(f"{code}: zadnji PM10 {last} UTC")
        # pojedinačna stanica može ne raditi; ako ne radi većina, problem je u formatu
        self.assertLess(len(failures), len(STATIONS) // 2, "; ".join(failures))


if __name__ == "__main__":
    unittest.main()

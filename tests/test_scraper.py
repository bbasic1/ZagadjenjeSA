"""
Testovi za FHMZ prikupljanje (collect.parse_portal_json).

FHMZ može promijeniti portal bez najave (26.11.2026. je ugasio stare stranice
stanica), a propušteni dani se ne mogu vratiti. Zato dvije vrste testova:
  * offline: parser na malom primjeru u formatu odgovora portala (uvijek)
  * uživo: portal mora dati svježe PM10 vrijednosti za većinu stanica
    (samo uz LIVE=1, jer traži pristup zrak.fhmzbih.gov.ba; pokreće ih tests.yml)

python -m unittest discover tests
"""

import os
import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from ingest.collect import STATIONS, fetch_pollutant, is_stale, parse_portal_json

IDS = {s[0]: code for code, s in STATIONS.items()}


def item(station_id: int, date: str, value):
    # skraćen red iz /rest/pubrep/data/last_week/{polutant}
    return {"canton": "Kanton Sarajevo", "date": date, "id": station_id,
            "name": "x", "stationId": "STA-x", "value": value}


SAMPLE = [
    item(17, "2026-11-21T23:00:00", 15.9254),   # Vijećnica, zima (UTC+1)
    item(17, "2026-11-22T00:00:00", 14.7027),   # ponoć lokalno = 23:00 UTC prethodnog dana
    item(3,  "2026-10-20T00:00:00", 12.5),      # Bjelave, ljetno vrijeme (UTC+2)
    item(3,  "2026-11-21T10:00:00", None),      # nema mjerenja
    item(999, "2026-11-21T10:00:00", 50.0),     # stanica koju ne pratimo
]


class ParseSample(unittest.TestCase):
    def setUp(self):
        self.rows, self.missing = parse_portal_json(SAMPLE, IDS, "PM10")
        self.by = {(r["station"], r["time_utc"]): r["value"] for r in self.rows}

    def test_values_and_utc(self):
        # provjereno naspram starih stranica: lokalno 23:00 = 22:00 UTC zimi
        self.assertEqual(self.by[("vijecnica", "2026-11-21 22:00")], 15.93)
        self.assertEqual(self.by[("vijecnica", "2026-11-21 23:00")], 14.7)
        self.assertEqual(self.by[("bjelave", "2026-10-19 22:00")], 12.5)

    def test_missing_values_skipped(self):
        # null ne smije postati nula, ali se broji
        self.assertEqual(self.missing, 1)
        self.assertNotIn(("bjelave", "2026-11-21 09:00"), self.by)

    def test_unknown_station_ignored(self):
        self.assertEqual(len(self.rows), 3)
        self.assertTrue(all(r["pollutant"] == "PM10" for r in self.rows))

    def test_empty_response(self):
        self.assertEqual(parse_portal_json([], IDS, "PM10"), ([], 0))


class Stale(unittest.TestCase):
    def test_stale(self):
        now = datetime(2026, 11, 27, 21, 0, tzinfo=timezone.utc)
        fresh = pd.DataFrame([{"pollutant": "PM10", "time_utc": "2026-11-27 19:00"}])
        old = pd.DataFrame([{"pollutant": "PM10", "time_utc": "2026-11-22 14:00"}])
        self.assertFalse(is_stale(fresh, now))
        self.assertTrue(is_stale(old, now))
        self.assertTrue(is_stale(pd.DataFrame(), now))


@unittest.skipUnless(os.environ.get("LIVE") == "1", "uživo test samo uz LIVE=1")
class LivePortal(unittest.TestCase):
    """Ako ovo padne, FHMZ je vjerovatno promijenio portal: popravi prikupljanje odmah."""

    def test_pm10_fresh(self):
        rows, _ = parse_portal_json(fetch_pollutant(287), IDS, "PM10")
        failures = []
        for code in STATIONS:
            times = [r["time_utc"] for r in rows if r["station"] == code]
            if not times:
                failures.append(f"{code}: nema PM10")
                continue
            last = datetime.strptime(max(times), "%Y-%m-%d %H:%M")
            if datetime.now(timezone.utc).replace(tzinfo=None) - last > timedelta(days=1):
                failures.append(f"{code}: zadnji PM10 {last} UTC")
        # pojedinačna stanica može ne raditi; ako ne radi većina, problem je u formatu
        self.assertLess(len(failures), len(STATIONS) // 2, "; ".join(failures))


if __name__ == "__main__":
    unittest.main()

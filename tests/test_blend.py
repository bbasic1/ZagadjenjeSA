"""Mješavina model + stanica: medijan, raspon i da nema curenja."""

import unittest

import numpy as np
import pandas as pd

from ingest.collect import LOCAL_TZ
from model.blend import blend, residuals


def fhmz_const(days: int, value: float, start: str = "2026-11-01") -> pd.DataFrame:
    t = pd.date_range(start, periods=24 * days, freq="h", tz=LOCAL_TZ)
    return pd.DataFrame({"station": "bjelave", "time": t, "PM10": value})


def pred(q50: float, issue: str, h: int = 1) -> pd.DataFrame:
    issue = pd.Timestamp(issue)
    return pd.DataFrame({"station": ["bjelave"], "pollutant": ["pm10"], "horizon": [h],
                         "issue_day": [issue], "target_day": [issue + pd.Timedelta(days=h)],
                         "q10": [q50 * 0.8], "q50": [q50], "q90": [q50 * 1.25]})


class BlendTest(unittest.TestCase):
    def test_median_is_half_model_half_station(self):
        today = pd.Timestamp("2026-11-10")
        cutoff = pd.Timestamp("2026-11-10 17:00", tz=LOCAL_TZ)
        out = blend(pred(20, "2026-11-10"), pred(20, "2026-11-01").iloc[:0],
                    fhmz_const(10, 60), today, cutoff, {"pm10": "PM10"})
        r = out.iloc[0]
        self.assertAlmostEqual(r.q50, 40)  # premalo parova: bez pomaka, raspon iz modela raširen
        self.assertAlmostEqual(r.q50_model, 20)
        self.assertAlmostEqual(r.perz_fhmz, 60)
        self.assertLess(r.q10, r.q50)
        self.assertGreater(r.q90, r.q50)

    def test_residuals_only_use_finished_days(self):
        today = pd.Timestamp("2026-11-10")
        hist = pd.concat([pred(20, f"2026-11-{d:02d}") for d in range(2, 10)])
        res = residuals(hist, fhmz_const(12, 60), today, {"pm10": "PM10"})
        # ciljni dan 10.11. (izdato 9.11.) još nije završio i ne smije ući
        self.assertEqual(len(res), 7)
        self.assertTrue(np.allclose(res.r, np.log1p(60) - np.log1p(40)))


if __name__ == "__main__":
    unittest.main()

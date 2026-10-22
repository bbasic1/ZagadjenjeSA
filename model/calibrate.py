"""
Jednostavna kalibracija CAMS-skale prognoze na FHMZ stanice (MOS v0).

Model predviđa CAMS dnevni prosjek, a CAMS sistematski griješi po stanici
(u oktobru 2026 precjenjuje kotlinu za ~9 µg/m³, Ilijaš potcjenjuje).
Zato prognozu množimo faktorom po stanici:

    faktor = zbir mjerenja / zbir CAMS-a   (zadnjih 14 dana, satni parovi)

Koriste se samo sati koji su već izmjereni prije izdavanja, pa nema curenja.
Faktor se skuplja prema mrežnom medijanu dok stanica nema dovoljno sati
(shrinkage), da jedna rupava stanica ne dobije divlji faktor.
"""

import pandas as pd

WINDOW_DAYS = 14
SHRINK_HOURS = 72     # s ovoliko parova faktor je pola stanica, pola mreža
CLIP = (0.4, 2.5)


def station_factors(fhmz: pd.DataFrame, cams: pd.DataFrame, pollutant: str,
                    cams_col: str, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Faktor po stanici iz satnih parova (mjerenje, CAMS) prije cutoff-a."""
    start = cutoff - pd.Timedelta(days=WINDOW_DAYS)
    obs = fhmz[(fhmz.time > start) & (fhmz.time <= cutoff)][["station", "time", pollutant]]
    mod = cams[(cams.time > start) & (cams.time <= cutoff)][["station", "time", cams_col]]
    pairs = obs.merge(mod, on=["station", "time"]).dropna()
    g = pairs.groupby("station")
    raw = pd.DataFrame({"n_sati": g.size(),
                        "faktor_sirovi": g[pollutant].sum() / g[cams_col].sum()})
    network = raw.faktor_sirovi.median() if len(raw) else 1.0
    w = raw.n_sati / (raw.n_sati + SHRINK_HOURS)
    raw["faktor"] = (w * raw.faktor_sirovi + (1 - w) * network).clip(*CLIP)
    raw.attrs["network"] = network
    return raw


def factor_for(factors: pd.DataFrame, station: str) -> float:
    if station in factors.index:
        return float(factors.loc[station, "faktor"])
    return float(min(max(factors.attrs.get("network", 1.0), CLIP[0]), CLIP[1]))

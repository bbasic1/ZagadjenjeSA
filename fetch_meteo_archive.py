"""
Povlači historijske meteo PROGNOZE (ne mjerenja) za sve stanice.

Izvor je Open-Meteo Previous Runs API: za svaki sat daje vrijednost iz
modelskog runa pokrenutog N dana ranije (varijabla_previous_dayN). To je
tačno ono što bismo imali u trenutku izdavanja prognoze, pa nema curenja.

Uzimamo lead 2 i 3 dana, namjerno konzervativno: prognoza se izdaje u 18:00
dana D, a run od "1 dan ranije" za kasne sate dana D+1 bio bi pokrenut tek
poslije 18:00 dana D. Za D+1 koristimo zato _previous_day2, a za D+2 _previous_day3.

Temperatura na 850 hPa u ovoj arhivi ne postoji, pa inverziju mjerimo
temperaturom na vrhu Bjelašnice (tačka "bjelasnica_vrh") minus temperatura
na stanici u kotlini.

Sve varijable idu u jedan zahtjev po periodu: Open-Meteo limit broji
lokacije × dane × (varijable / 10), pa je jedan zahtjev s 14 varijabli
mnogo jeftiniji od 7 zahtjeva s po 2.

Rezultat: data/meteo/previous_runs.csv.gz (station, time_utc, var_previous_dayN...).
Pokreće se iz GitHub Actions (.github/workflows/meteo_archive.yml).
"""

import sys
import time
from datetime import date, timedelta

import pandas as pd
import requests

from collect import DATA, HEADERS, STATIONS

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
LEADS = [2, 3]
VARIABLES = ["temperature_2m", "relative_humidity_2m", "precipitation", "pressure_msl",
             "wind_speed_10m", "wind_direction_10m", "boundary_layer_height"]
# vrh Bjelašnice, za mjeru inverzije (temperatura gore minus dolje)
UPPER = ("bjelasnica_vrh", 43.7156, 18.2564)
FIRST_YEAR = 2023
OUT = DATA / "meteo" / "previous_runs.csv.gz"


def locations() -> list[tuple[str, float, float]]:
    return [(code, s[1], s[2]) for code, s in STATIONS.items()] + [UPPER]


def fetch(variables: list[str], start: date, end: date) -> pd.DataFrame | None:
    """Sve varijable i leadovi, sve lokacije, jedan period; None ako period nije u arhivi."""
    cols = [f"{v}_previous_day{n}" for v in variables for n in LEADS]
    locs = locations()
    params = {
        "latitude": ",".join(str(l[1]) for l in locs),
        "longitude": ",".join(str(l[2]) for l in locs),
        "hourly": ",".join(cols),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "GMT",
    }
    for attempt in range(6):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=180)
        except requests.Timeout:
            print(f"  {start}: timeout, pokušaj {attempt + 1}", flush=True)
            time.sleep(20 * (attempt + 1))
            continue
        if r.status_code == 429:  # limit zahtjeva: čekaj da se oslobodi
            print(f"  {start}: limit (429), čekam, pokušaj {attempt + 1}", flush=True)
            time.sleep(60 * (attempt + 1))
            continue
        break
    else:
        raise RuntimeError("svi pokušaji neuspješni")
    if r.status_code == 400:
        print(f"  {start}: nije dostupno ({r.json().get('reason', '')[:120]})", flush=True)
        return None
    r.raise_for_status()
    data = r.json()
    data = [data] if isinstance(data, dict) else data
    frames = [pd.DataFrame(loc["hourly"]).assign(station=code)
              for (code, _, _), loc in zip(locs, data)]
    out = pd.concat(frames, ignore_index=True).rename(columns={"time": "time_utc"})
    out = out.dropna(subset=cols, how="all")
    print(f"  {start} do {end}: {len(out)} redova", flush=True)
    return out if not out.empty else None


def main() -> int:
    yesterday = date.today() - timedelta(days=1)
    periods = [(date(y, m, 1), date(y, m + 5, 30 if m == 1 else 31))
               for y in range(FIRST_YEAR, yesterday.year + 1) for m in (1, 7)]
    parts, failed = [], []
    for start, end in periods:
        if start > yesterday:
            continue
        try:
            df = fetch(VARIABLES, start, min(end, yesterday))
        except Exception as e:
            print(f"  ! {start}: {e}", flush=True)
            failed.append(start.isoformat())
            continue
        if df is not None:
            parts.append(df)
        time.sleep(5)
    if failed or not parts:
        print(f"GREŠKA: neuspjeli periodi {failed}")
        return 1
    df = pd.concat(parts, ignore_index=True)
    df["time_utc"] = pd.to_datetime(df.time_utc).dt.strftime("%Y-%m-%d %H:00")
    df = df.drop_duplicates(["station", "time_utc"]).sort_values(["station", "time_utc"])
    first = df.station.ne("bjelasnica_vrh")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, float_format="%.2f")
    print(f"Snimljeno {len(df)} redova, {df[first].time_utc.min()} do {df.time_utc.max()} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Povlači historijske meteo PROGNOZE (ne mjerenja) za sve stanice.

Izvor je Open-Meteo Previous Runs API: za svaki sat daje vrijednost iz
modelskog runa pokrenutog N dana ranije (varijabla_previous_dayN). To je
tačno ono što bismo imali u trenutku izdavanja prognoze, pa nema curenja.

Uzimamo lead 2 i 3 dana, namjerno konzervativno: prognoza se izdaje u 18:00
dana D, a run od "1 dan ranije" za kasne sate dana D+1 bio bi pokrenut tek
poslije 18:00 dana D. Za D+1 koristimo zato _previous_day2, a za D+2 _previous_day3.

Rezultat: data/meteo/previous_runs.csv.gz (station, time_utc, var_previous_dayN...).
Pokreće se iz GitHub Actions (.github/workflows/meteo_archive.yml).
"""

import sys
import time
from datetime import date, timedelta

import pandas as pd
import requests

from collect import DATA, HEADERS, METEO_VARS, STATIONS

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
LEADS = [2, 3]
FIRST_YEAR = 2022  # Previous Runs arhiva za većinu varijabli počinje 2022-2024
OUT = DATA / "meteo" / "previous_runs.csv.gz"


def fetch(variable: str, start: date, end: date) -> pd.DataFrame | None:
    """Jedna varijabla, svi leadovi, sve stanice; None ako API ne nudi period/varijablu."""
    cols = [f"{variable}_previous_day{n}" for n in LEADS]
    params = {
        "latitude": ",".join(str(s[1]) for s in STATIONS.values()),
        "longitude": ",".join(str(s[2]) for s in STATIONS.values()),
        "hourly": ",".join(cols),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "GMT",
    }
    for attempt in range(5):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=180)
        except requests.Timeout:
            print(f"  {variable} {start}: timeout, pokušaj {attempt + 1}")
            time.sleep(20 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(30 * (attempt + 1))
            continue
        break
    else:
        raise RuntimeError("svi pokušaji neuspješni")
    if r.status_code == 400:
        print(f"  {variable} {start}: nije dostupno ({r.json().get('reason', '')[:100]})")
        return None
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        data = [data]
    frames = []
    for code, loc in zip(STATIONS, data):
        df = pd.DataFrame(loc["hourly"])
        df.insert(0, "station", code)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True).rename(columns={"time": "time_utc"})
    out = out.dropna(subset=cols, how="all")
    print(f"  {variable} {start} do {end}: {len(out)} redova")
    return out if not out.empty else None


def main() -> int:
    yesterday = date.today() - timedelta(days=1)
    per_var, failed = [], []
    for variable in METEO_VARS:
        parts = []
        # pola godine po zahtjevu: manji zahtjevi i manje izgubljeno ako početak arhive pada usred godine
        periods = [(date(y, m, 1), date(y, m + 5, 30 if m == 1 else 31))
                   for y in range(FIRST_YEAR, yesterday.year + 1) for m in (1, 7)]
        for start, end in periods:
            if start > yesterday:
                continue
            end = min(end, yesterday)
            try:
                df = fetch(variable, start, end)
            except Exception as e:
                print(f"  ! {variable} {start}: {e}")
                failed.append((variable, start.isoformat()))
                continue
            if df is not None:
                parts.append(df)
            time.sleep(2)
        if parts:
            per_var.append(pd.concat(parts).set_index(["station", "time_utc"]))
    if failed or not per_var:
        print(f"GREŠKA: neuspjeli zahtjevi {failed}")
        return 1
    df = pd.concat(per_var, axis=1).reset_index()
    df["time_utc"] = pd.to_datetime(df.time_utc).dt.strftime("%Y-%m-%d %H:00")
    df = df.sort_values(["station", "time_utc"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, float_format="%.2f")
    print(f"Snimljeno {len(df)} redova, {df.time_utc.min()} do {df.time_utc.max()}, "
          f"kolone: {', '.join(c for c in df.columns if c not in ('station', 'time_utc'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

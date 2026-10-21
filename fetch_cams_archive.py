"""
Povlači CAMS arhivu (Open-Meteo Air Quality, domena cams_europe) za sve stanice.

Rezultat: data/cams/archive.csv.gz, long format po satu:
    station, time_utc, cams_pm10, cams_pm2_5

Ovo je CAMS analiza (svaki sat iz najsvježijeg runa), a ne arhiva prognoza
24-48 h unaprijed. Za baseline "sirovi CAMS" je zato optimistična procjena;
prave prognoze skupljamo sami u data/forecast/.

Pokreće se ručno ili iz GitHub Actions (.github/workflows/cams_archive.yml).
"""

import sys
import time
from datetime import date

import pandas as pd
import requests

from collect import DATA, HEADERS, STATIONS

URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
FIRST_YEAR = 2013  # najranije što cams_europe na Open-Meteo može imati
OUT = DATA / "cams" / "archive.csv.gz"


def fetch_year(year: int) -> pd.DataFrame:
    """Jedan zahtjev za sve stanice i jednu godinu; prazno ako godina nije dostupna."""
    end = min(date(year, 12, 31), date.today())
    params = {
        "latitude": ",".join(str(s[1]) for s in STATIONS.values()),
        "longitude": ",".join(str(s[2]) for s in STATIONS.values()),
        "hourly": "pm10,pm2_5",
        "domains": "cams_europe",
        "start_date": f"{year}-01-01",
        "end_date": end.isoformat(),
        "timezone": "GMT",
    }
    for attempt in range(4):
        r = requests.get(URL, params=params, headers=HEADERS, timeout=120)
        if r.status_code == 429:  # ograničenje zahtjeva, sačekaj pa ponovi
            time.sleep(30 * (attempt + 1))
            continue
        break
    if r.status_code == 400:  # godina van raspona arhive
        print(f"  {year}: nije dostupno ({r.json().get('reason', r.text)[:80]})")
        return pd.DataFrame()
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        data = [data]
    frames = []
    for code, loc in zip(STATIONS, data):
        df = pd.DataFrame(loc["hourly"])
        df.insert(0, "station", code)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(columns={"time": "time_utc", "pm10": "cams_pm10", "pm2_5": "cams_pm2_5"})
    out = out.dropna(subset=["cams_pm10", "cams_pm2_5"], how="all")
    print(f"  {year}: {len(out)} redova")
    return out


def main() -> int:
    frames = []
    for year in range(FIRST_YEAR, date.today().year + 1):
        try:
            frames.append(fetch_year(year))
        except Exception as e:
            print(f"  ! {year}: {e}")
        time.sleep(2)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        print("GREŠKA: arhiva prazna")
        return 1
    df["time_utc"] = pd.to_datetime(df.time_utc).dt.strftime("%Y-%m-%d %H:00")
    df = df.drop_duplicates(["station", "time_utc"]).sort_values(["station", "time_utc"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, float_format="%.1f")
    print(f"Snimljeno {len(df)} redova, {df.time_utc.min()} do {df.time_utc.max()} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

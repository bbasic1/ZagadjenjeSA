"""
Prikupljanje podataka za prognozu zagađenja zraka u Sarajevu.

Svako pokretanje radi dvije stvari:
  1. FHMZ mjerenja: stranice stanica daju satne vrijednosti za zadnjih ~7 dana.
     Spajaju se u mjesečne fajlove data/fhmz/YYYY-MM.csv (bez duplikata),
     pa propušteno pokretanje ništa ne kvari.
  2. Open-Meteo prognoze (meteo + CAMS): snimak se čuva dvaput dnevno
     u data/forecast/. Ovo je arhiva prognoza koju niko drugi ne čuva
     umjesto tebe, a treba ti za trening bez curenja podataka.

Sva vremena se čuvaju u UTC.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

LOCAL_TZ = ZoneInfo("Europe/Sarajevo")
DATA = Path(__file__).parent / "data"
HEADERS = {"User-Agent": "sarajevo-air-forecast (studentski projekat)"}
FHMZ_BASE = "https://www.fhmzbih.gov.ba/latinica/ZRAK/"

# kod stanice: (stranica na FHMZ, lat, lon) — koordinate su približne
STATIONS = {
    "vijecnica":  ("amsVijecnica.php", 43.8590, 18.4340),
    "bjelave":    ("amsBjelave.php",   43.8670, 18.4230),
    "otoka":      ("amsOtoka.php",     43.8480, 18.3620),
    "saraj_polje":("amsSPolje.php",    43.8440, 18.3410),
    "ilidza":     ("amsIlidza.php",    43.8300, 18.3100),
    "vogosca":    ("amsVogosca.php",   43.9030, 18.3440),
    "hadzici":    ("amsHadzici.php",   43.8220, 18.2010),
    "ilijas":     ("amsIlijas.php",    43.9510, 18.2710),
    "ivan_sedlo": ("amsISedlo.php",    43.7560, 18.0350),  # planinska, iznad kotline
}

METEO_VARS = [
    "temperature_2m", "temperature_850hPa", "relative_humidity_2m",
    "precipitation", "pressure_msl", "wind_speed_10m",
    "wind_direction_10m", "boundary_layer_height",
]
CAMS_VARS = ["pm10", "pm2_5"]


# ---------------------------------------------------------------- FHMZ

def parse_station_html(html: str) -> list[dict]:
    """Iz HTML-a stranice stanice izvuče redove (polutant, vrijeme_utc, vrijednost)."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    last_dates: list[str] = []

    for table in soup.find_all("table"):
        rows = [[c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                for tr in table.find_all("tr")]
        # tražimo red zaglavlja koji počinje s "datum" (ili prazan pa satima)
        header_idx = next((i for i, r in enumerate(rows)
                           if len(r) >= 25 and r[1] == "0:00"), None)
        if header_idx is None:
            continue

        pollutant = rows[header_idx][0] if rows[header_idx][0].lower() != "datum" else ""
        if not pollutant and header_idx > 0 and rows[header_idx - 1]:
            pollutant = rows[header_idx - 1][0]
        if not pollutant:
            continue
        hours = [int(h.split(":")[0]) for h in rows[header_idx][1:25]]

        dates_here = []
        for k, r in enumerate(rows[header_idx + 1:]):
            if len(r) < 25:
                continue
            date_str = r[0].rstrip(".")
            if not date_str and k < len(last_dates):  # neke tabele (NOx) nemaju datume
                date_str = last_dates[k]
            try:
                day = datetime.strptime(date_str, "%d.%m.%Y")
            except ValueError:
                continue
            dates_here.append(date_str)
            for h, cell in zip(hours, r[1:25]):
                cell = cell.replace(",", ".")
                if not cell or cell == "#":
                    continue
                try:
                    value = float(cell)
                except ValueError:
                    continue
                local = day.replace(hour=h, tzinfo=LOCAL_TZ)
                out.append({
                    "pollutant": pollutant.upper().replace("PM2.5", "PM2_5"),
                    "time_utc": local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:00"),
                    "value": value,
                })
        if dates_here:
            last_dates = dates_here
    return out


def collect_fhmz(fetched_at: str) -> pd.DataFrame:
    frames = []
    for code, (page, _, _) in STATIONS.items():
        try:
            r = requests.get(FHMZ_BASE + page, headers=HEADERS, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"
            rows = parse_station_html(r.text)
        except Exception as e:  # jedna stanica ne smije srušiti ostale
            print(f"  ! {code}: {e}")
            continue
        df = pd.DataFrame(rows)
        if df.empty:
            print(f"  ! {code}: nema vrijednosti (stanica možda ne radi)")
            continue
        df["station"] = code
        df["fetched_at"] = fetched_at
        frames.append(df)
        pm = df[df.pollutant == "PM2_5"]
        last = pm.sort_values("time_utc").iloc[-1] if not pm.empty else None
        info = f"zadnji PM2.5 {last.value} u {last.time_utc} UTC" if last is not None else "bez PM2.5"
        print(f"  {code:12s} {len(df):5d} vrijednosti, {info}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def save_fhmz(new: pd.DataFrame) -> None:
    """Spaja nova mjerenja u mjesečne fajlove; novije preuzimanje pobjeđuje."""
    if new.empty:
        return
    folder = DATA / "fhmz"
    folder.mkdir(parents=True, exist_ok=True)
    cols = ["station", "pollutant", "time_utc", "value", "fetched_at"]
    new = new[cols]
    for month, part in new.groupby(new.time_utc.str[:7]):
        path = folder / f"{month}.csv"
        if path.exists():
            part = pd.concat([pd.read_csv(path), part], ignore_index=True)
        part = (part.drop_duplicates(["station", "pollutant", "time_utc"], keep="last")
                    .sort_values(["station", "pollutant", "time_utc"]))
        part.to_csv(path, index=False)


# ---------------------------------------------------------- Open-Meteo

def fetch_open_meteo(url: str, variables: list[str]) -> pd.DataFrame:
    params = {
        "latitude": ",".join(str(s[1]) for s in STATIONS.values()),
        "longitude": ",".join(str(s[2]) for s in STATIONS.values()),
        "hourly": ",".join(variables),
        "forecast_days": 3,
        "timezone": "GMT",
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):  # jedna lokacija vraća objekat, više njih listu
        data = [data]
    frames = []
    for code, loc in zip(STATIONS, data):
        df = pd.DataFrame(loc["hourly"])
        df.insert(0, "station", code)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    return out.rename(columns={"time": "valid_utc"})


def collect_forecasts(now: datetime) -> None:
    """Snimak prognoze dvaput dnevno (blok 00 i 12 UTC); ponovljeno pokretanje se preskače."""
    block = "00" if now.hour < 12 else "12"
    path = DATA / "forecast" / f"{now:%Y-%m-%d}_{block}.csv"
    if path.exists():
        print(f"  prognoza za blok {block} UTC već snimljena, preskačem")
        return
    meteo = fetch_open_meteo("https://api.open-meteo.com/v1/forecast", METEO_VARS)
    cams = fetch_open_meteo("https://air-quality-api.open-meteo.com/v1/air-quality", CAMS_VARS)
    cams = cams.rename(columns={v: f"cams_{v}" for v in CAMS_VARS})
    df = meteo.merge(cams, on=["station", "valid_utc"], how="outer")
    df.insert(0, "issued_utc", now.strftime("%Y-%m-%d %H:%M"))
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  snimljeno {len(df)} redova prognoze -> {path.name}")


# ---------------------------------------------------------------- main

def main() -> int:
    now = datetime.now(timezone.utc)
    fetched_at = now.strftime("%Y-%m-%d %H:%M")
    print(f"Pokretanje {fetched_at} UTC")

    print("FHMZ mjerenja:")
    obs = collect_fhmz(fetched_at)
    save_fhmz(obs)

    print("Open-Meteo prognoze:")
    forecast_ok = True
    try:
        collect_forecasts(now)
    except Exception as e:
        print(f"  ! prognoza nije snimljena: {e}")
        forecast_ok = False

    # neuspjeh vraća kod 1, pa GitHub Actions pokaže crveno i pošalje ti mail
    if obs.empty or not forecast_ok:
        print("GREŠKA: dio podataka nije prikupljen")
        return 1
    print("Gotovo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

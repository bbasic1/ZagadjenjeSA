"""
Prikupljanje podataka za prognozu zagađenja zraka u Sarajevu.

Svako pokretanje radi dvije stvari:
  1. FHMZ mjerenja: portal zrak.fhmzbih.gov.ba daje satne vrijednosti za zadnjih ~7 dana.
     Spajaju se u mjesečne fajlove data/fhmz/YYYY-MM.csv (bez duplikata),
     pa propušteno pokretanje ništa ne kvari.
  2. Open-Meteo prognoze (meteo + CAMS): snimak se čuva dvaput dnevno
     u data/forecast/. Ovo je arhiva prognoza koju niko drugi ne čuva
     umjesto tebe, a treba ti za trening bez curenja podataka.

Sva vremena se čuvaju u UTC.
"""

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

LOCAL_TZ = ZoneInfo("Europe/Sarajevo")
DATA = Path(__file__).resolve().parents[1] / "data"
HEADERS = {"User-Agent": "sarajevo-air-forecast (studentski projekat)"}
# Od 26.11.2026. FHMZ podatke objavljuje samo na portalu zrak.fhmzbih.gov.ba
# (stare stranice amsXxx.php vraćaju 404). Ovo je JSON iza izvještaja
# "Sedmodnevni pregled": satne vrijednosti jednog polutanta za odabrane
# stanice, zadnjih ~7 dana. Uslovi: navesti izvor (FHMZ), najviše 1 zahtjev / 0,5 s.
FHMZ_API = "https://zrak.fhmzbih.gov.ba/rest/pubrep/data/last_week/{pid}"
REQUEST_GAP = 0.6   # sekunde između zahtjeva
STALE_HOURS = 12    # starije od ovoga znači da FHMZ ne osvježava podatke
EMPTY_RETRIES = (20,)  # sekunde čekanja prije ponovnog pokušaja

# id polutanta na portalu -> naziv u našim CSV fajlovima (isti kao ranije)
POLLUTANTS = {
    287: "PM10", 379: "PM2_5", 1: "SO2", 657: "NO2", 148: "NO",
    662: "NOX", 499: "O3", 2: "CO", 21: "H2S",
}

# kod stanice: (id stanice na portalu, lat, lon) — koordinate su približne
STATIONS = {
    "vijecnica":  (17, 43.8590, 18.4340),
    "bjelave":    (3,  43.8670, 18.4230),
    "otoka":      (12, 43.8480, 18.3620),
    "saraj_polje":(34, 43.8440, 18.3410),
    "ilidza":     (13, 43.8300, 18.3100),
    "vogosca":    (27, 43.9030, 18.3440),
    "hadzici":    (26, 43.8220, 18.2010),
    "ilijas":     (18, 43.9510, 18.2710),
    "ivan_sedlo": (1,  43.7560, 18.0350),  # planinska, iznad kotline
}

METEO_VARS = [
    "temperature_2m", "temperature_850hPa", "relative_humidity_2m",
    "precipitation", "pressure_msl", "wind_speed_10m",
    "wind_direction_10m", "boundary_layer_height",
]
CAMS_VARS = ["pm10", "pm2_5"]


# ---------------------------------------------------------------- FHMZ

def parse_portal_json(items: list, ids: dict[int, str], pollutant: str) -> tuple[list[dict], int]:
    """Iz odgovora portala izvuče redove (stanica, polutant, vrijeme_utc, vrijednost).

    Portal daje `date` u lokalnom vremenu (Europe/Sarajevo), bez oznake zone,
    i to kao kraj sata, isto kao stara stranica (sat "23:00" lokalno = 22:00 UTC
    zimi). Prazne vrijednosti (null) se preskaču i broje, nikad ne postaju nula.
    Vraća (redovi, broj praznih).
    """
    out, missing = [], 0
    for it in items:
        code = ids.get(it.get("id"))
        if code is None:
            continue  # stanica koju ne pratimo
        if it.get("value") is None:
            missing += 1
            continue
        local = datetime.fromisoformat(it["date"]).replace(tzinfo=LOCAL_TZ)
        out.append({
            "station": code,
            "pollutant": pollutant,
            "time_utc": local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:00"),
            "value": round(float(it["value"]), 2),  # kao na starim stranicama
        })
    return out, missing


def fetch_pollutant(pid: int) -> list:
    """Zadnjih ~7 dana satnih vrijednosti jednog polutanta za sve naše stanice.

    Ako odgovor nije JSON lista (npr. stranica "One moment, please..."), pokuša
    još jednom, pa u grešci opiše šta je portal poslao.
    """
    params = [("stations", s[0]) for s in STATIONS.values()]
    for wait in (0, *EMPTY_RETRIES):
        if wait:
            time.sleep(wait)
        r = requests.get(FHMZ_API.format(pid=pid), params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError:
            continue
        if isinstance(data, list):
            return data
    title = re.search(r"<title>([^<]*)", r.text)
    raise RuntimeError(f"odgovor nije JSON lista (HTTP {r.status_code}, {len(r.text)} B, "
                       f"naslov: {title.group(1).strip() if title else '-'!r})")


def collect_fhmz(fetched_at: str) -> pd.DataFrame:
    ids = {s[0]: code for code, s in STATIONS.items()}
    rows = []
    for i, (pid, pollutant) in enumerate(POLLUTANTS.items()):
        if i:
            time.sleep(REQUEST_GAP)  # uslovi portala: najviše jedan zahtjev u pola sekunde
        try:
            got, missing = parse_portal_json(fetch_pollutant(pid), ids, pollutant)
        except Exception as e:  # jedan polutant ne smije srušiti ostale
            print(f"  ! {pollutant}: {e}")
            continue
        print(f"  {pollutant:6s} {len(got):5d} vrijednosti, {missing} praznih")
        rows += got
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["fetched_at"] = fetched_at
    for code in STATIONS:
        pm = df[(df.station == code) & (df.pollutant == "PM10")]
        if pm.empty:
            print(f"  ! {code}: nema PM10 (stanica možda ne radi)")
        else:
            print(f"  {code:12s} zadnji PM10 {pm.time_utc.max()} UTC")
    return df


def is_stale(obs: pd.DataFrame, now: datetime) -> bool:
    """True ako je najnovije PM10 mjerenje (bilo koje stanice) starije od STALE_HOURS.

    Stara stranica je 22.11.2026. prestala da se osvježava, a prikupljanje je
    danima "uspijevalo" bez novih podataka. Ovo to čini vidljivim.
    """
    pm = obs[obs.pollutant == "PM10"] if not obs.empty else obs
    if pm.empty:
        return True
    newest = datetime.strptime(pm.time_utc.max(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    age = (now - newest).total_seconds() / 3600
    if age > STALE_HOURS:
        print(f"  ! najnovije PM10 mjerenje je od {newest:%Y-%m-%d %H:%M} UTC ({age:.0f} h staro)")
        return True
    return False


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
    stale = is_stale(obs, now)

    print("Open-Meteo prognoze:")
    forecast_ok = True
    try:
        collect_forecasts(now)
    except Exception as e:
        print(f"  ! prognoza nije snimljena: {e}")
        forecast_ok = False

    # neuspjeh vraća kod 1, pa GitHub Actions pokaže crveno i pošalje ti mail
    if obs.empty or stale or not forecast_ok:
        print("GREŠKA: dio podataka nije prikupljen")
        return 1
    print("Gotovo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

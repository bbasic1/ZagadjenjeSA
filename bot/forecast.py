"""
Večernja prognoza: zadnji podaci -> LightGBM modeli -> poruka u Telegram kanal.

Pokreće se iz GitHub Actions (.github/workflows/forecast.yml) poslije 18:00
po lokalnom vremenu. Koristi iste features kao train_v1.py:
  * CAMS satne vrijednosti zaključno sa 17:00 danas (ništa poslije izdavanja)
  * meteo prognoza za sutra i prekosutra (najsvježiji run)

Model predviđa CAMS dnevni prosjek po CAMS ćeliji; calibrate.py ga zatim
prevodi na skalu svake FHMZ stanice (faktor iz zadnjih 14 dana mjerenja).

Svaka prognoza se snima u data/predictions/YYYY-MM-DD.csv, da je kasnije
uporedimo sa stvarnim mjerenjem (javna tačnost).

python -m bot.forecast --dry   samo ispiše poruku, ne šalje i ne snima
"""

import sys
from datetime import datetime

import lightgbm as lgb
import numpy as np
import pandas as pd
import requests

from model.baseline import load_fhmz
from bot.categories import ADVICE_SENSITIVE, category
from model.calibrate import WINDOW_DAYS, factor_for, station_factors
from model.conformal import load_config as load_conformal, widen
from ingest.collect import DATA, HEADERS, LOCAL_TZ, STATIONS
from ingest.fetch_meteo_archive import VARIABLES, locations
from bot.send_telegram import check_config, send
from model.train_v1 import HORIZONS, ISSUE_HOUR, MODELS, QUANTILES, attach_upper, build_dataset

# CAMS ćelije za koje imamo modele; stanice u istoj ćeliji dijele sirovu prognozu
CELLS = ["bjelave", "hadzici", "ilidza", "ilijas", "ivan_sedlo", "otoka", "vogosca"]
CELL_OF = {"vijecnica": "bjelave", "saraj_polje": "ilidza"}
DISPLAY = {
    "bjelave": "Bjelave", "vijecnica": "Vijećnica", "otoka": "Otoka", "ilidza": "Ilidža",
    "saraj_polje": "Saraj Polje", "vogosca": "Vogošća", "hadzici": "Hadžići",
    "ilijas": "Ilijaš", "ivan_sedlo": "Ivan Sedlo",
}
POLLUTANTS = [("pm10", "cams_pm10", "PM10"), ("pm2_5", "cams_pm2_5", "PM2_5")]
DAYS = ["ponedjeljak", "utorak", "srijeda", "četvrtak", "petak", "subota", "nedjelja"]
DAYS_ACC = ["ponedjeljak", "utorak", "srijedu", "četvrtak", "petak", "subotu", "nedjelju"]
TREND_UG = 5  # promjena medijana stanica (µg/m³) koju vrijedi spomenuti u uvodu


def fetch(url: str, variables: list[str], past_days: int, forecast_days: int,
          locs: list[tuple[str, float, float]] | None = None) -> pd.DataFrame:
    locs = locs or [(code, s[1], s[2]) for code, s in STATIONS.items()]
    params = {
        "latitude": ",".join(str(l[1]) for l in locs),
        "longitude": ",".join(str(l[2]) for l in locs),
        "hourly": ",".join(variables), "past_days": past_days,
        "forecast_days": forecast_days, "timezone": "GMT",
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    data = [data] if isinstance(data, dict) else data
    frames = [pd.DataFrame(loc["hourly"]).assign(station=code)
              for (code, _, _), loc in zip(locs, data)]
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df.pop("time")).dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
    return df


def live_inputs(now: datetime) -> tuple[pd.DataFrame, pd.DataFrame]:
    cams = fetch("https://air-quality-api.open-meteo.com/v1/air-quality",
                 ["pm10", "pm2_5"], past_days=WINDOW_DAYS + 1, forecast_days=1)
    cams = cams.rename(columns={"pm10": "cams_pm10", "pm2_5": "cams_pm2_5"})
    cutoff = now.replace(hour=ISSUE_HOUR - 1, minute=0, second=0, microsecond=0)
    cams = cams[cams.time <= cutoff]  # samo ono što je poznato u trenutku izdavanja
    met = fetch("https://api.open-meteo.com/v1/forecast", VARIABLES, past_days=1,
                forecast_days=4, locs=locations())
    # modeli su trenirani na kolonama iz arhive prognoza; live run je najsvježija prognoza
    for v in VARIABLES:
        for lead in (2, 3):
            met[f"{v}_previous_day{lead}"] = met[v]
    return cams, attach_upper(met)


def predict(cams: pd.DataFrame, met: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    rows = []
    conformal = load_conformal()
    for pol, col, _ in POLLUTANTS:
        for h in HORIZONS:
            df = build_dataset(cams, met, col, h, stations=CELLS)
            df = df[df.issue_day == today]
            out = df[["station", "issue_day", "target_day"]].copy()
            for q in QUANTILES:
                model = lgb.Booster(model_file=str(MODELS / f"{pol}_h{h}_q{int(q * 100)}.txt"))
                out[f"q{int(q * 100)}"] = np.expm1(model.predict(df.reindex(columns=model.feature_name())))
            qs = [f"q{int(q * 100)}" for q in QUANTILES]
            out[qs] = np.sort(out[qs].values, axis=1)
            # raspon 10–90 % raširen po CQR korekciji (conformal.py), jer je sirov preuzak
            c = (conformal or {}).get(f"{pol}_h{h}")
            if c:
                out["q10"], out["q90"] = widen(out.q10, out.q90, c)
            else:
                print(f"UPOZORENJE: nema CQR korekcije za {pol} D+{h}, raspon je sirov (preuzak)")
            rows.append(out.assign(pollutant=pol, horizon=h))
    return pd.concat(rows, ignore_index=True)


def calibrate(pred: pd.DataFrame, cams: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Raširi prognozu ćelija na svih 9 stanica i pomnoži faktorom stanice.

    Faktor koristi samo mjerenja do cutoff-a (17:00 danas). Ako mjerenja nisu
    dostupna, ide sirova CAMS-skala uz vidljivo upozorenje (faktor 1).
    """
    try:
        fhmz = load_fhmz()
        factors = {pol: station_factors(fhmz, cams, fcol, col, cutoff)
                   for pol, col, fcol in POLLUTANTS}
    except Exception as e:  # noqa: BLE001 - prognoza ide i bez kalibracije
        print(f"UPOZORENJE: kalibracija nije uspjela ({e!r}), šaljem sirovu prognozu")
        factors = None
    qs = [f"q{int(q * 100)}" for q in QUANTILES]
    rows = []
    for station in DISPLAY:
        part = pred[pred.station == CELL_OF.get(station, station)].copy()
        part["cell"] = part.pop("station")
        part["station"] = station
        part = part.rename(columns={q: f"{q}_cams" for q in qs})
        part["faktor"] = [factor_for(factors[p], station) if factors else 1.0
                          for p in part.pollutant]
        for q in qs:
            part[q] = part[f"{q}_cams"] * part.faktor
        rows.append(part)
    out = pd.concat(rows, ignore_index=True)
    if factors:
        for pol, f in factors.items():
            print(f"Faktori {pol} (mreža {f.attrs['network']:.2f}): "
                  + ", ".join(f"{s} {v:.2f} ({n} h)" for s, v, n in zip(f.index, f.faktor, f.n_sati)))
    return out


def intro(pm: pd.DataFrame) -> list[str]:
    """Pozdrav, dani i kratak trend; sve izvedeno iz same prognoze."""
    d1, d2 = (pm[pm.horizon == h].target_day.iloc[0] for h in HORIZONS)
    lines = ["🌆 <b>Dobro veče, Sarajevo!</b>",
             f"Evo kakav nas zrak čeka sutra, u {DAYS_ACC[d1.dayofweek]} {d1:%d.%m.}, "
             f"i prekosutra, u {DAYS_ACC[d2.dayofweek]} {d2:%d.%m.} 👇"]
    m1, m2 = (pm[pm.horizon == h].q50.median() for h in HORIZONS)
    if m2 - m1 >= TREND_UG:
        lines.append(f"Pažnja: u {DAYS_ACC[d2.dayofweek]} se zagađenje penje 📈")
    elif m1 - m2 >= TREND_UG:
        lines.append(f"Dobre vijesti: u {DAYS_ACC[d2.dayofweek]} zrak postaje čišći 📉")
    return lines + [""]


FALLBACK_MIN_HOURS = 12  # perzistencija samo za stanice s bar ovoliko sati u zadnja 24 h


def persistence(today: pd.Timestamp, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Rezervna prognoza "sutra kao danas": prosjek FHMZ mjerenja zadnja 24 h do 17:00.

    Koristi se samo kad model ili njegovi ulazi zakažu. Isti oblik kao calibrate().
    """
    fhmz = load_fhmz()
    window = fhmz[(fhmz.time > cutoff - pd.Timedelta(hours=24)) & (fhmz.time <= cutoff)]
    rows = []
    for pol, _, fcol in POLLUTANTS:
        g = window.groupby("station")[fcol]
        mean = g.mean()[g.count() >= FALLBACK_MIN_HOURS]
        for station, v in mean.items():
            for h in HORIZONS:
                rows.append({"station": station, "issue_day": today,
                             "target_day": today + pd.Timedelta(days=h), "pollutant": pol,
                             "horizon": h, "q10": np.nan, "q50": v, "q90": np.nan})
    out = pd.DataFrame(rows)
    if out.empty or not (out.pollutant == "pm10").any():
        raise RuntimeError("ni perzistencija nije moguća: nema dovoljno FHMZ mjerenja PM10")
    missing = sorted(set(DISPLAY) - set(out[out.pollutant == "pm10"].station))
    if missing:
        print(f"UPOZORENJE: perzistencija bez stanica {missing} (premalo mjerenja)")
    return out.assign(model="perzistencija")


def message(pred: pd.DataFrame) -> str:
    pm = pred[pred.pollutant == "pm10"]
    fallback = "model" in pm and (pm.model == "perzistencija").any()
    lines = intro(pm)
    if fallback:
        lines += ["⚠️ Model danas nije dostupan, pa je prognoza jednostavna: "
                  "sutra i prekosutra kao zadnja 24 h mjerenja.", ""]
    for h in HORIZONS:
        part = pm[pm.horizon == h].sort_values("q50", ascending=False)
        day = part.target_day.iloc[0]
        label = "Sutra" if h == 1 else "Prekosutra"
        lines.append(f"📅 <b>{label}, {DAYS[day.dayofweek]} {day:%d.%m.}</b> (PM10, dnevni prosjek)")
        for _, r in part.iterrows():
            _, emoji, name = category(r.q50, "pm10")
            spread = "" if pd.isna(r.q10) else f" ({r.q10:.0f}–{r.q90:.0f})"
            lines.append(f"{emoji} {DISPLAY[r.station]}: {name}, ~{r.q50:.0f} µg/m³{spread}")
        lines.append("")
    # preporuka FHMZ po najgoroj stanici za sutra
    tomorrow = pm[pm.horizon == HORIZONS[0]]
    worst = max(category(v, "pm10") for v in tomorrow.q50)
    if worst[2] in ADVICE_SENSITIVE:
        lines.append(f"Savjet FHMZ za kategoriju „{worst[2]}“ (sutra): {ADVICE_SENSITIVE[worst[2]]}.")
        lines.append("")
    if not fallback:
        lines.append("U zagradi je raspon u koji očekujemo stvarni prosjek.")
    lines.append("Lijepo veče i čujemo se sutra! 💚")
    lines.append("")
    source = ("Rezervna prognoza iz mjerenja FHMZ" if fallback
              else "Eksperimentalni model korigovan na mjerenja stanica")
    lines.append(f"<i>{source}, nije zvanični izvor. "
                 "Kategorije po skali indeksa FHMZ. Mjerenja uživo: fhmzbih.gov.ba</i>")
    return "\n".join(lines)


def main() -> int:
    dry = "--dry" in sys.argv
    now = datetime.now(LOCAL_TZ)
    today = pd.Timestamp(now.date())
    path = DATA / "predictions" / f"{today:%Y-%m-%d}.csv"
    if not dry:
        if now.hour < ISSUE_HOUR:
            print(f"Još nije {ISSUE_HOUR}:00 po lokalnom vremenu, preskačem")
            return 0
        if path.exists():
            print("Današnja prognoza je već poslana, preskačem")
            return 0
        problems = check_config()
        if problems:
            print("GREŠKA:", "; ".join(problems))
            return 1
    cutoff = pd.Timestamp(now.replace(hour=ISSUE_HOUR - 1, minute=0, second=0, microsecond=0))
    failed = False
    try:
        cams, met = live_inputs(now)
        pred = calibrate(predict(cams, met, today), cams, cutoff).assign(model="lightgbm")
    except Exception as e:  # noqa: BLE001 - umjesto tišine šaljemo perzistenciju, run ipak pada
        print(f"GREŠKA: model nije uspio ({e!r}), šaljem perzistenciju")
        pred, failed = persistence(today, cutoff), True
    text = message(pred)
    print(text)
    if dry:
        return 1 if failed else 0
    send(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    pred.assign(issued_local=now.strftime("%Y-%m-%d %H:%M")).to_csv(path, index=False, float_format="%.1f")
    print(f"Poslano i snimljeno -> {path}")
    return 1 if failed else 0  # crven run, da se kvar modela vidi


if __name__ == "__main__":
    sys.exit(main())

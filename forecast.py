"""
Večernja prognoza: zadnji podaci -> LightGBM modeli -> poruka u Telegram kanal.

Pokreće se iz GitHub Actions (.github/workflows/forecast.yml) poslije 18:00
po lokalnom vremenu. Koristi iste features kao train_v1.py:
  * CAMS satne vrijednosti zaključno sa 17:00 danas (ništa poslije izdavanja)
  * meteo prognoza za sutra i prekosutra (najsvježiji run)

Svaka prognoza se snima u data/predictions/YYYY-MM-DD.csv, da je kasnije
uporedimo sa stvarnim mjerenjem (javna tačnost).

python forecast.py --dry   samo ispiše poruku, ne šalje i ne snima
"""

import sys
from datetime import datetime

import lightgbm as lgb
import numpy as np
import pandas as pd
import requests

from collect import DATA, HEADERS, LOCAL_TZ, STATIONS
from fetch_meteo_archive import VARIABLES, locations
from send_telegram import check_config, send
from train_v1 import HORIZONS, ISSUE_HOUR, MODELS, QUANTILES, attach_upper, build_dataset

# prikaz: stanice u istoj CAMS ćeliji dijele prognozu
DISPLAY = {
    "bjelave": "Bjelave / Vijećnica", "otoka": "Otoka", "ilidza": "Ilidža / Saraj Polje",
    "vogosca": "Vogošća", "hadzici": "Hadžići", "ilijas": "Ilijaš", "ivan_sedlo": "Ivan Sedlo",
}
# EEA skala za dnevni PM10 (µg/m³); uskladiti sa skalom Zavoda kad je potvrdimo
CATEGORIES = [(20, "🟢", "dobar"), (40, "🟡", "prihvatljiv"), (50, "🟠", "umjeren"),
              (100, "🔴", "loš"), (150, "🟣", "vrlo loš"), (np.inf, "⚫", "izuzetno loš")]
DAYS = ["pon", "uto", "sri", "čet", "pet", "sub", "ned"]


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
                 ["pm10", "pm2_5"], past_days=5, forecast_days=1)
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
    for pol, col in [("pm10", "cams_pm10"), ("pm2_5", "cams_pm2_5")]:
        for h in HORIZONS:
            df = build_dataset(cams, met, col, h, stations=sorted(DISPLAY))
            df = df[df.issue_day == today]
            out = df[["station", "issue_day", "target_day"]].copy()
            for q in QUANTILES:
                model = lgb.Booster(model_file=str(MODELS / f"{pol}_h{h}_q{int(q * 100)}.txt"))
                out[f"q{int(q * 100)}"] = np.expm1(model.predict(df[model.feature_name()]))
            qs = [f"q{int(q * 100)}" for q in QUANTILES]
            out[qs] = np.sort(out[qs].values, axis=1)
            rows.append(out.assign(pollutant=pol, horizon=h))
    return pd.concat(rows, ignore_index=True)


def category(x: float) -> tuple[str, str]:
    return next((e, n) for limit, e, n in CATEGORIES if x <= limit)


def message(pred: pd.DataFrame) -> str:
    pm = pred[pred.pollutant == "pm10"]
    lines = []
    for h in HORIZONS:
        part = pm[pm.horizon == h].sort_values("q50", ascending=False)
        day = part.target_day.iloc[0]
        label = "Sutra" if h == 1 else "Prekosutra"
        lines.append(f"<b>{label}, {DAYS[day.dayofweek]} {day:%d.%m.}</b> (PM10, dnevni prosjek)")
        for _, r in part.iterrows():
            emoji, name = category(r.q50)
            lines.append(f"{emoji} {DISPLAY[r.station]}: {name}, ~{r.q50:.0f} µg/m³ "
                         f"({r.q10:.0f}–{r.q90:.0f})")
        lines.append("")
    lines.append("<i>Eksperimentalni model, nije zvanični izvor. "
                 "Mjerenja uživo: fhmzbih.gov.ba</i>")
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
    cams, met = live_inputs(now)
    pred = predict(cams, met, today)
    text = message(pred)
    print(text)
    if dry:
        return 0
    send(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    pred.assign(issued_local=now.strftime("%Y-%m-%d %H:%M")).to_csv(path, index=False, float_format="%.1f")
    print(f"Poslano i snimljeno -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

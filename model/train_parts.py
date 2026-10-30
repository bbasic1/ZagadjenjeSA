"""
Prognoza PM10 posebno za dan (07–17 h) i veče (18–23 h), D+1 i D+2.

Dnevni prosjek skriva večernji vrh: zimi je veče u CAMS-u oko 1,6× dnevni
prosjek, a popodne oko 0,65×. Ovdje je target prosjek jednog dijela dana,
a ostalo je kao u train_v1 (LightGBM, kvantili 0.1/0.5/0.9, log skala).

Pravila protiv curenja ista kao u train_v1:
  * PM do 17:00 dana izdavanja; dan D (07–17) je u 18:00 poznat, veče D-1 također
  * meteo samo iz arhive PROGNOZA, lead = horizont + 1 dan (veče je u istom
    kalendarskom danu, pa ne treba duži lead)
  * validacija klizeća po zimama

Izlaz: reports/model_dan_vece.md; --final snima models/pm10_{dan,vece}_h{h}_q*.txt
"""

import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

from bot.categories import category
from model.baseline import load_cams
from model.train_v1 import (HEATING, HORIZONS, MODELS, N_ROUNDS, PARAMS, QUANTILES,
                            REPORT, evaluate, fit_predict, load_meteo, meteo_features,
                            pm_features, unique_cells)

PARTS = {"dan": range(7, 18), "vece": range(18, 24)}
PART_MIN_HOURS = {"dan": 8, "vece": 5, "dnevni": 18}
LABEL = {"dan": "danju (07–17 h)", "vece": "navečer (18–24 h)"}
REPORT = REPORT.with_name("model_dan_vece.md")
POLLUTANT = ("pm10", "cams_pm10")


def part_mean(hourly: pd.Series, part: str) -> pd.Series:
    """Prosjek dijela dana po kalendarskom danu; None ako fali previše sati."""
    s = hourly.dropna()
    if part != "dnevni":
        s = s[s.index.hour.isin(PARTS[part])]
    g = s.groupby(pd.to_datetime(s.index.date))
    return g.mean().where(g.size() >= PART_MIN_HOURS[part])


def evening_meteo(met: pd.DataFrame, lead: int) -> pd.DataFrame:
    """Meteo prognoza samo za večernje sate ciljnog dana."""
    m = met.set_index("time")
    ev = m.index.hour.isin(PARTS["vece"])
    day = pd.to_datetime(m.index.date)[ev]
    t = m[f"temperature_2m_previous_day{lead}"][ev]
    out = pd.DataFrame({"t2m_eve": t.groupby(day).mean(),
                        "wind_eve": m[f"wind_speed_10m_previous_day{lead}"][ev].groupby(day).mean()})
    if f"t_upper_previous_day{lead}" in m:
        out["inv_eve"] = (m[f"t_upper_previous_day{lead}"][ev] - t).groupby(day).mean()
    return out


def build_dataset(cams: pd.DataFrame, met: pd.DataFrame, part: str, h: int,
                  stations: list[str] | None = None) -> pd.DataFrame:
    rows = []
    stations = stations or unique_cells(cams)
    for station in stations:
        c = cams[cams.station == station].set_index("time").sort_index()[POLLUTANT[1]]
        X = pm_features(c, "pm")
        X["issue_day"] = X.index
        X["target_day"] = X.index + pd.Timedelta(days=h)
        X["dan_D"] = part_mean(c, "dan").reindex(X.index).values
        X["vece_Dm1"] = part_mean(c, "vece").reindex(X.index - pd.Timedelta(days=1)).values
        # perzistencija dijela dana: zadnji poznati isti dio dana
        X["persistence"] = X["dan_D"] if part == "dan" else X["vece_Dm1"]
        y = part_mean(c, part)
        X["y"] = y.reindex(X.target_day).values
        X["y_issue_day"] = X["persistence"]
        ms = met[met.station == station]
        mf = meteo_features(ms, lead=h + 1).join(evening_meteo(ms, lead=h + 1))
        X = X.join(mf.reindex(X.target_day).set_index(X.index))
        X["station"] = station
        rows.append(X)
    df = pd.concat(rows, ignore_index=True)
    doy = df.target_day.dt.dayofyear
    df["doy_sin"], df["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    df["dow"] = df.target_day.dt.dayofweek
    df["station"] = pd.Categorical(df.station, categories=sorted(stations))
    return df


def in_meteo_range(df: pd.DataFrame, met: pd.DataFrame) -> pd.DataFrame:
    return df[df.target_day >= met.time.min().tz_localize(None).normalize()]


def compare(cams: pd.DataFrame, met: pd.DataFrame, h: int) -> pd.DataFrame:
    """Poseban model za dio dana naspram dnevnog modela i perzistencije, iste test zime."""
    import model.train_v1 as v1
    daily = in_meteo_range(v1.build_dataset(cams, met, POLLUTANT[1], h), met)
    daily_res, _ = evaluate(daily)
    daily_res = daily_res[["station", "target_day", "q50"]].rename(columns={"q50": "q50_dnevni"})
    rows = []
    for part in PARTS:
        df = in_meteo_range(build_dataset(cams, met, part, h), met)
        res, imp = evaluate(df)
        res = res.merge(daily_res, on=["station", "target_day"])
        cat = lambda col: (res[col].map(lambda v: category(v)[0])  # noqa: E731
                           == res.y.map(lambda v: category(v)[0])).mean() * 100
        rows.append({
            "dio": LABEL[part], "n": len(res), "prosjek": res.y.mean(),
            "MAE_model": (res.q50 - res.y).abs().mean(),
            "MAE_dnevna_prognoza": (res.q50_dnevni - res.y).abs().mean(),
            "MAE_perzist": (res.persistence - res.y).abs().mean(),
            "kategorija_model_%": cat("q50"), "kategorija_dnevna_%": cat("q50_dnevni"),
            "pokrivenost_10_90_%": 100 * ((res.y >= res.q10) & (res.y <= res.q90)).mean(),
            "features": ", ".join(f"{k} {v:.0%}" for k, v in imp.head(5).items()),
        })
    return pd.DataFrame(rows)


def train_final(cams: pd.DataFrame, met: pd.DataFrame) -> None:
    MODELS.mkdir(exist_ok=True)
    pol = POLLUTANT[0]
    for part in PARTS:
        for h in HORIZONS:
            df = in_meteo_range(build_dataset(cams, met, part, h), met)
            df = df.dropna(subset=["y", "persistence"])
            feats = feature_cols(df)
            for q in QUANTILES:
                data = lgb.Dataset(df[feats], np.log1p(df.y))
                model = lgb.train({**PARAMS, "objective": "quantile", "alpha": q}, data, N_ROUNDS)
                model.save_model(MODELS / f"{pol}_{part}_h{h}_q{int(q * 100)}.txt")
    print(f"Modeli za dan i veče snimljeni u {MODELS}")


def feature_cols(df: pd.DataFrame) -> list[str]:
    skip = {"y", "y_issue_day", "issue_day", "target_day"}
    return [c for c in df.columns if c not in skip]


def main() -> None:
    cams, met = load_cams(), load_meteo()
    if "--final" in sys.argv:
        train_final(cams, met)
        return
    parts = ["# PM10 posebno za dan i veče\n\n",
             "Target: CAMS prosjek dijela dana po ćeliji (07–17 h i 18–24 h lokalno). "
             "Test: zime (okt–mar, mjeseci grijanja), model treniran samo na prošlosti. "
             "„Dnevna prognoza“ je medijan modela v1 za cijeli dan, korišten kao prognoza "
             "dijela dana: to je ono što bot danas zapravo kaže. Perzistencija je zadnji "
             "poznati isti dio dana (dan D, veče D-1).\n\n"
             "Ograda: CAMS ima jači dnevni ciklus od stanica (u oktobru 2026 CAMS precjenjuje "
             "veče, faktor ~0,67, a potcjenjuje dan, ~1,39), pa kalibracija na stanice mora "
             "ići posebno za svaki dio dana.\n"]
    for h in HORIZONS:
        t = compare(cams, met, h)
        parts.append(f"\n## D+{h}\n\n")
        parts.append(t.drop(columns="features").to_markdown(index=False, floatfmt=".1f"))
        parts.append("\n\nNajvažniji features: "
                     + "; ".join(f"{r.dio}: {r.features}" for r in t.itertuples()) + "\n")
    REPORT.write_text("".join(parts), encoding="utf-8")
    print("".join(parts))


if __name__ == "__main__":
    main()

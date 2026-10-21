"""
Faza 4: prvi LightGBM model za dnevni prosjek PM10 (i PM2.5), D+1 i D+2.

Target je zasad CAMS dnevni prosjek po ćeliji stanice (pretrening iz plana);
kalibracija na FHMZ mjerenjima dolazi kad se skupi sezona.

Pravila protiv curenja:
  * prošle vrijednosti PM-a samo do 17:00 dana izdavanja (izdaje se u 18:00)
  * meteo samo iz arhive PROGNOZA (Previous Runs), lead = horizont + 1 dan
  * CAMS za ciljni dan se NE koristi kao feature, jer je CAMS ovdje target
  * validacija klizeća po zimama: model uvijek trenira samo na prošlosti

Izlaz: reports/model_v1.md
"""

import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from baseline import CHANGE_THRESHOLD, ISSUE_HOUR, MIN_HOURS, load_cams
from collect import DATA, LOCAL_TZ
from fetch_meteo_archive import UPPER

QUANTILES = [0.1, 0.5, 0.9]
HORIZONS = [1, 2]
HEATING = [10, 11, 12, 1, 2, 3]
# zime na kojima testiramo; trening je sve prije početka zime
TEST_SEASONS = [("2024-10-01", "2025-04-01"), ("2025-10-01", "2026-04-01")]
REPORT = Path(__file__).parent / "reports" / "model_v1.md"
MODELS = Path(__file__).parent / "models"
UPPER_POINT = UPPER[0]
N_ROUNDS = 400
PARAMS = dict(learning_rate=0.03, num_leaves=15, min_data_in_leaf=30,
              bagging_fraction=0.8, bagging_freq=1, feature_fraction=0.8,
              verbose=-1, seed=0)


# ------------------------------------------------------------ podaci

def unique_cells(cams: pd.DataFrame) -> list[str]:
    """Stanice u istoj CAMS ćeliji imaju isti niz; zadržimo po jednu."""
    wide = cams.pivot_table(index="time", columns="station", values="cams_pm10")
    keep = []
    for s in wide:
        if not any(wide[s].equals(wide[k]) for k in keep):
            keep.append(s)
    return keep


def attach_upper(met: pd.DataFrame) -> pd.DataFrame:
    """Temperatura s vrha Bjelašnice kao kolona t_upper_* uz svaku stanicu."""
    cols = [c for c in met.columns if c.startswith("temperature_2m_previous_day")]
    upper = met[met.station == UPPER_POINT].set_index("time")[cols]
    upper.columns = [c.replace("temperature_2m", "t_upper") for c in cols]
    return met[met.station != UPPER_POINT].join(upper, on="time")


def load_meteo() -> pd.DataFrame:
    df = pd.read_csv(DATA / "meteo" / "previous_runs.csv.gz")
    df["time"] = (pd.to_datetime(df.pop("time_utc")).dt.tz_localize("UTC")
                  .dt.tz_convert(LOCAL_TZ))
    return attach_upper(df)


# ------------------------------------------------------------ features

def pm_features(hourly: pd.Series, prefix: str) -> pd.DataFrame:
    """Features iz prošlih vrijednosti, indeks = dan izdavanja D.

    Pomak od (24 - ISSUE_HOUR) sati stavlja sat 17:00 dana D kao zadnji sat
    "dana" D, pa ništa poslije izdavanja ne ulazi.
    """
    s = hourly.dropna().copy()
    s.index = s.index + pd.Timedelta(hours=24 - ISSUE_HOUR)
    day = pd.to_datetime(s.index.date)
    g = s.groupby(day)
    mean24 = g.mean().where(g.size() >= MIN_HOURS)
    out = pd.DataFrame({
        f"{prefix}_mean24": mean24,
        f"{prefix}_max24": g.max(),
        f"{prefix}_last6": g.apply(lambda x: x.iloc[-6:].mean()),
        f"{prefix}_last": g.last(),
    })
    out[f"{prefix}_mean24_prev"] = mean24.shift(1)
    out[f"{prefix}_trend24"] = mean24 - mean24.shift(1)
    out[f"{prefix}_mean72"] = mean24.rolling(3, min_periods=2).mean()
    out[f"{prefix}_max72"] = out[f"{prefix}_max24"].rolling(3, min_periods=2).max()
    out.index = pd.to_datetime(out.index)
    return out


def meteo_features(met: pd.DataFrame, lead: int) -> pd.DataFrame:
    """Dnevni agregati meteo prognoze za kalendarski dan (indeks = ciljni dan)."""
    def col(v):
        return f"{v}_previous_day{lead}"

    m = met.set_index("time")
    day = pd.to_datetime(m.index.date)
    night = (m.index.hour < 7)
    out = pd.DataFrame(index=pd.to_datetime(sorted(set(day))))
    if col("temperature_2m") in m:
        t = m[col("temperature_2m")].groupby(day)
        out["t2m_mean"], out["t2m_min"], out["t2m_max"] = t.mean(), t.min(), t.max()
        out["hdd"] = (15 - out.t2m_mean).clip(lower=0)
    if col("t_upper") in m and col("temperature_2m") in m:
        # vrh Bjelašnice (~2000 m) minus kotlina; normalno je oko -10 °C,
        # a što je bliže nuli ili pozitivno, to je inverzija jača
        inv = m[col("t_upper")] - m[col("temperature_2m")]
        out["inv_mean"] = inv.groupby(day).mean()
        out["inv_max"] = inv.groupby(day).max()
        out["inv_night"] = inv[night].groupby(day[night]).mean()
    if col("wind_speed_10m") in m:
        w = m[col("wind_speed_10m")].groupby(day)
        out["wind_mean"], out["wind_max"] = w.mean(), w.max()
    if col("precipitation") in m:
        out["precip_sum"] = m[col("precipitation")].groupby(day).sum(min_count=1)
    if col("boundary_layer_height") in m:
        b = m[col("boundary_layer_height")].groupby(day)
        out["blh_mean"], out["blh_min"] = b.mean(), b.min()
    if col("relative_humidity_2m") in m:
        out["rh_mean"] = m[col("relative_humidity_2m")].groupby(day).mean()
    if col("pressure_msl") in m:
        p = m[col("pressure_msl")].groupby(day).mean()
        out["pressure_mean"] = p
    return out


def daily_target(hourly: pd.Series) -> pd.Series:
    s = hourly.dropna()
    g = s.groupby(pd.to_datetime(s.index.date))
    return g.mean().where(g.size() >= MIN_HOURS)


def build_dataset(cams: pd.DataFrame, met: pd.DataFrame, pol_col: str, h: int,
                  stations: list[str] | None = None) -> pd.DataFrame:
    rows = []
    stations = stations or unique_cells(cams)
    for station in stations:
        c = cams[cams.station == station].set_index("time").sort_index()
        X = pm_features(c[pol_col], "pm")
        X["persistence"] = X["pm_mean24"]
        X["issue_day"] = X.index
        X["target_day"] = X.index + pd.Timedelta(days=h)
        y = daily_target(c[pol_col])
        X["y"] = y.reindex(X.target_day).values
        X["y_issue_day"] = y.reindex(X.index).values
        mf = meteo_features(met[met.station == station], lead=h + 1)
        X = X.join(mf.reindex(X.target_day).set_index(X.index))
        X["station"] = station
        rows.append(X)
    df = pd.concat(rows, ignore_index=True)
    doy = df.target_day.dt.dayofyear
    df["doy_sin"], df["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    df["dow"] = df.target_day.dt.dayofweek
    df["station"] = pd.Categorical(df.station, categories=sorted(stations))
    return df


# ------------------------------------------------------------ trening i evaluacija

def feature_cols(df: pd.DataFrame) -> list[str]:
    skip = {"y", "y_issue_day", "issue_day", "target_day"}
    return [c for c in df.columns if c not in skip]


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    """Kvantilni modeli na log skali; vraća predikcije za test."""
    out = pd.DataFrame(index=test.index)
    for q in QUANTILES:
        data = lgb.Dataset(train[feats], np.log1p(train.y))
        model = lgb.train({**PARAMS, "objective": "quantile", "alpha": q}, data, N_ROUNDS)
        out[f"q{int(q * 100)}"] = np.expm1(model.predict(test[feats]))
        if q == 0.5:
            out.attrs["importance"] = pd.Series(model.feature_importance("gain"), index=feats)
    # kvantili ne smiju preći jedan preko drugog
    qs = np.sort(out[[f"q{int(q * 100)}" for q in QUANTILES]].values, axis=1)
    out[[f"q{int(q * 100)}" for q in QUANTILES]] = qs
    return out


def evaluate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = df.dropna(subset=["y", "persistence"])
    feats = feature_cols(df)
    preds, imps = [], []
    for start, end in TEST_SEASONS:
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        train = df[df.target_day < start]           # samo prošlost
        test = df[(df.issue_day >= start) & (df.target_day < end)]
        test = test[test.target_day.dt.month.isin(HEATING)]
        if len(train) < 200 or test.empty:
            continue
        p = fit_predict(train, test, feats)
        imps.append(p.attrs["importance"])
        preds.append(test[["station", "issue_day", "target_day", "y", "y_issue_day",
                           "persistence"]].join(p).assign(sezona=f"{start:%Y}/{end:%y}"))
    res = pd.concat(preds)
    imp = pd.concat(imps, axis=1).mean(axis=1).sort_values(ascending=False)
    return res, imp / imp.sum()


def summarize(res: pd.DataFrame) -> pd.DataFrame:
    def one(g):
        change = (g.y - g.y_issue_day).abs() >= CHANGE_THRESHOLD
        mae_m = (g.q50 - g.y).abs().mean()
        mae_p = (g.persistence - g.y).abs().mean()
        return pd.Series({
            "n": len(g), "n_promjena": int(change.sum()),
            "MAE_model": mae_m, "MAE_perzist": mae_p,
            "skill_%": 100 * (1 - mae_m / mae_p),
            "MAE_model_promjena": (g.q50 - g.y)[change].abs().mean(),
            "MAE_perzist_promjena": (g.persistence - g.y)[change].abs().mean(),
            "pokrivenost_10_90_%": 100 * ((g.y >= g.q10) & (g.y <= g.q90)).mean(),
        })
    by_season = res.groupby("sezona").apply(one, include_groups=False)
    total = one(res).to_frame("SVE").T
    return pd.concat([by_season, total])


def train_final(cams: pd.DataFrame, met: pd.DataFrame) -> None:
    """Modeli na svim podacima za operativnu prognozu (models/*.txt)."""
    MODELS.mkdir(exist_ok=True)
    for pol, col in [("pm10", "cams_pm10"), ("pm2_5", "cams_pm2_5")]:
        for h in HORIZONS:
            df = build_dataset(cams, met, col, h).dropna(subset=["y", "persistence"])
            df = df[df.target_day >= met.time.min().tz_localize(None).normalize()]
            feats = feature_cols(df)
            for q in QUANTILES:
                data = lgb.Dataset(df[feats], np.log1p(df.y))
                model = lgb.train({**PARAMS, "objective": "quantile", "alpha": q}, data, N_ROUNDS)
                model.save_model(MODELS / f"{pol}_h{h}_q{int(q * 100)}.txt")
    print(f"Modeli snimljeni u {MODELS}")


def main() -> None:
    if "--final" in sys.argv:
        train_final(load_cams(), load_meteo())
        return
    cams = load_cams()
    met = load_meteo()
    parts = ["# Faza 4: LightGBM v1\n",
             "Target: CAMS dnevni prosjek po ćeliji stanice (pretrening). Izdavanje u "
             f"{ISSUE_HOUR}:00 lokalno. Meteo iz arhive prognoza (lead = horizont + 1 dan). "
             "Test: zime (okt–mar), model treniran samo na podacima prije te zime. "
             "Perzistencija je računata na istim test danima.\n",
             f"\nMeteo arhiva: {met.time.min():%d.%m.%Y} do {met.time.max():%d.%m.%Y}.\n"]
    for pol, col in [("PM10", "cams_pm10"), ("PM2_5", "cams_pm2_5")]:
        for h in HORIZONS:
            df = build_dataset(cams, met, col, h)
            df = df[df.target_day >= met.time.min().tz_localize(None).normalize()]
            res, imp = evaluate(df)
            s = summarize(res)
            parts.append(f"\n## {pol}, D+{h}\n\n")
            parts.append(s.to_markdown(floatfmt=".1f"))
            parts.append("\n\nNajvažniji features (udio gain-a): "
                         + ", ".join(f"{k} {v:.0%}" for k, v in imp.head(8).items()) + "\n")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("".join(parts), encoding="utf-8")
    print("".join(parts))


if __name__ == "__main__":
    main()

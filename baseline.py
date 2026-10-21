"""
Faza 3: greška baselineova za dnevni prosjek PM10 i PM2.5 po stanici.

Postavka oponaša stvarnu upotrebu: prognoza se izdaje u 18:00 po lokalnom
vremenu dana D, za dnevni prosjek dana D+1 (24 h) i D+2 (48 h).
U trenutku izdavanja znamo samo mjerenja do 18:00 dana D, pa:

  perzistencija  = prosjek zadnja 24 h prije izdavanja (D-1 18:00 do D 17:00)
  sirovi CAMS    = dnevni prosjek CAMS-a za dan D+h (iz arhive analiza, pa je
                   ovo optimistično za CAMS; prava prognoza CAMS-a je lošija)

Ništa iz budućnosti ne ulazi u perzistenciju. Dan se računa samo ako ima
barem 18 od 24 satne vrijednosti.

Izlaz: reports/baseline.md
"""

from pathlib import Path

import numpy as np
import pandas as pd

from collect import DATA, LOCAL_TZ

ISSUE_HOUR = 18          # lokalno vrijeme izdavanja prognoze
MIN_HOURS = 18           # minimalno sati za valjan dnevni prosjek
CHANGE_THRESHOLD = 10.0  # µg/m³: "dan promjene" ako se dnevni prosjek pomjeri bar ovoliko
HORIZONS = [1, 2]
POLLUTANTS = {"PM10": "cams_pm10", "PM2_5": "cams_pm2_5"}
REPORT = Path(__file__).parent / "reports" / "baseline.md"


# ------------------------------------------------------------ učitavanje

def load_fhmz() -> pd.DataFrame:
    """Satna mjerenja, wide po polutantu: station, time (lokalno), PM10, PM2_5."""
    files = sorted((DATA / "fhmz").glob("*.csv"))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df[df.pollutant.isin(POLLUTANTS)]
    df = df.pivot_table(index=["station", "time_utc"], columns="pollutant",
                        values="value").reset_index()
    return _to_local(df)


def load_cams() -> pd.DataFrame:
    df = pd.read_csv(DATA / "cams" / "archive.csv.gz")
    return _to_local(df)


def _to_local(df: pd.DataFrame) -> pd.DataFrame:
    df["time"] = (pd.to_datetime(df.pop("time_utc")).dt.tz_localize("UTC")
                  .dt.tz_convert(LOCAL_TZ))
    return df


# ------------------------------------------------------------- baseline

def daily_mean(hourly: pd.Series) -> pd.Series:
    """Dnevni prosjek po lokalnom kalendarskom danu; NaN ako fali previše sati."""
    g = hourly.dropna().groupby(hourly.dropna().index.date)
    out = g.mean().where(g.size() >= MIN_HOURS)
    out.index = pd.to_datetime(out.index)
    return out


def persistence(hourly: pd.Series) -> pd.Series:
    """Za svaki dan D: prosjek zadnja 24 h zaključno sa satom prije izdavanja.

    Sat označen s 17:00 je zadnji poznat u 18:00, pa prozor ide od
    D-1 18:00 do D 17:00. Indeks rezultata je dan izdavanja D.
    """
    s = hourly.dropna()
    shifted = s.copy()
    # pomak od 6 h stavlja prozor (D-1 18:00, D 17:00) u kalendarski dan D
    shifted.index = shifted.index + pd.Timedelta(hours=24 - ISSUE_HOUR)
    g = shifted.groupby(shifted.index.date)
    out = g.mean().where(g.size() >= MIN_HOURS)
    out.index = pd.to_datetime(out.index)
    return out


def build_pairs(obs: pd.DataFrame, col: str, cams: pd.DataFrame | None,
                cams_col: str | None) -> pd.DataFrame:
    """Tabela (stanica, dan izdavanja, horizont, stvarno, perzistencija, cams)."""
    rows = []
    for station, g in obs.groupby("station"):
        hourly = g.set_index("time")[col].sort_index()
        if hourly.dropna().empty:
            continue
        truth = daily_mean(hourly)
        pers = persistence(hourly)
        today = daily_mean(hourly)  # samo za definiciju dana promjene
        cams_daily = None
        if cams is not None:
            c = cams[cams.station == station].set_index("time")[cams_col].sort_index()
            cams_daily = daily_mean(c)
        for h in HORIZONS:
            target_day = pers.index + pd.Timedelta(days=h)
            df = pd.DataFrame({
                "station": station, "issue_day": pers.index, "horizon": h,
                "persistence": pers.values,
                "truth": truth.reindex(target_day).values,
                "truth_issue_day": today.reindex(pers.index).values,
            })
            if cams_daily is not None:
                df["cams"] = cams_daily.reindex(target_day).values
            rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    return out.dropna(subset=["truth", "persistence"])


def scores(pairs: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    def one(g: pd.DataFrame) -> pd.Series:
        res = {"n": len(g)}
        change = (g.truth - g.truth_issue_day).abs() >= CHANGE_THRESHOLD
        res["n_promjena"] = int(change.sum())
        for m in models:
            ok = g[m].notna()
            err = g.loc[ok, m] - g.loc[ok, "truth"]
            res[f"MAE_{m}"] = err.abs().mean()
            res[f"RMSE_{m}"] = np.sqrt((err ** 2).mean())
            res[f"bias_{m}"] = err.mean()
            res[f"MAE_{m}_promjena"] = err[change[ok]].abs().mean()
        return pd.Series(res)

    per_station = pairs.groupby(["horizon", "station"]).apply(one, include_groups=False)
    total = pairs.groupby("horizon").apply(one, include_groups=False)
    total["station"] = "SVE"
    total = total.set_index("station", append=True)
    return pd.concat([per_station, total]).sort_index()


# ---------------------------------------------------------------- izvještaj

def fmt(df: pd.DataFrame) -> str:
    df = df.reset_index()
    df["n"] = df["n"].astype(int)
    df["n_promjena"] = df["n_promjena"].astype(int)
    return df.to_markdown(index=False, floatfmt=".1f")


def main() -> None:
    parts = ["# Faza 3: baseline greška\n",
             f"Izdavanje u {ISSUE_HOUR}:00 lokalno, target je dnevni prosjek "
             f"za D+1 i D+2. Dan valjan uz ≥{MIN_HOURS} sati. Dan promjene: "
             f"dnevni prosjek se pomjeri ≥{CHANGE_THRESHOLD:.0f} µg/m³ u odnosu na dan izdavanja. "
             "Sve greške u µg/m³.\n"]

    cams = load_cams() if (DATA / "cams" / "archive.csv.gz").exists() else None
    fhmz = load_fhmz()

    for pol, cams_col in POLLUTANTS.items():
        pairs = build_pairs(fhmz, pol, cams, cams_col if cams is not None else None)
        models = ["persistence"] + (["cams"] if cams is not None else [])
        days = f"{pairs.issue_day.min():%d.%m.%Y} do {pairs.issue_day.max():%d.%m.%Y}" if len(pairs) else "nema"
        parts.append(f"\n## {pol}: FHMZ mjerenja (dani izdavanja {days})\n")
        parts.append("Malo dana, brojke su orijentacione dok se ne skupi sezona.\n\n")
        parts.append(fmt(scores(pairs, models)) if len(pairs) else "Nema dovoljno podataka.")
        parts.append("\n")

    if cams is not None:
        # dugi niz: perzistencija na CAMS-u kao zamjena za mjerenja, samo sezona grijanja
        parts.append("\n## Perzistencija na CAMS arhivi (sezona grijanja, okt–mar)\n")
        parts.append(f"CAMS od {cams.time.min():%d.%m.%Y} do {cams.time.max():%d.%m.%Y}. "
                     "CAMS je izglađen i ne vidi vrhove u kotlini, pa je ovo mjera "
                     "dinamike, ne prave greške na stanici.\n")
        # stanice u istoj CAMS ćeliji imaju identičan niz, pa nisu nezavisne
        wide = cams.pivot_table(index="time", columns="station", values="cams_pm10")
        same = [f"{a} = {b}" for i, a in enumerate(wide) for b in list(wide)[i + 1:]
                if wide[a].equals(wide[b])]
        if same:
            parts.append("Iste CAMS ćelije (identičan niz): " + ", ".join(same) + ".\n")
        season = cams[cams.time.dt.month.isin([10, 11, 12, 1, 2, 3])]
        for pol, cams_col in POLLUTANTS.items():
            pairs = build_pairs(season.rename(columns={cams_col: pol}), pol, None, None)
            pairs = pairs[pairs.issue_day.dt.month.isin([10, 11, 12, 1, 2, 3])]
            parts.append(f"\n### {pol}\n\n")
            parts.append(fmt(scores(pairs, ["persistence"])))
            parts.append("\n")

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("".join(parts), encoding="utf-8")
    print("".join(parts))


if __name__ == "__main__":
    main()

"""
Mješavina modela i mjerenja stanica (od 15.11.2026).

U prvom smogu (8.–11.11.2026) model je predviđao ~30 µg/m³, a izmjereno je
66–76: lagovi modela su CAMS, pa kad CAMS promaši epizodu, promaši i model.
Zato je poslana prognoza pola model, pola perzistencija sa stanica:

    medijan = 0,5 · model + 0,5 · FHMZ prosjek zadnja 24 h do 17:00

Raspon 10–90 % (i mali pomak medijana) dolazi iz grešaka te mješavine na
prošlim poslanim prognozama, zadnjih 28 dana, na log skali. Koriste se samo
ciljni dani koji su završili prije dana izdavanja, pa nema curenja.

Ograda: težina 0,5 je izabrana na 30.10.–13.11.2026, dakle na sezoni uživo;
ti dani su za mješavinu optimistični, pošten test počinje 15.11.2026.
"""

import numpy as np
import pandas as pd

BLEND_WEIGHT = 0.5      # udio modela; ostatak je perzistencija sa stanice
PERSIST_MIN_HOURS = 12  # sati u zadnja 24 h za perzistenciju stanice
DAILY_MIN_HOURS = 18    # sati za valjan dnevni prosjek mjerenja
WINDOW_DAYS = 28        # prozor grešaka za raspon
MIN_PAIRS = 40          # manje parova: raspon iz modela, raširen
FALLBACK_WIDEN = 2.5    # koliko puta se raširi log-raspon modela bez dovoljno parova
QS = ["q10", "q50", "q90"]


def station_persistence(fhmz: pd.DataFrame, cutoff: pd.Timestamp, col: str) -> pd.Series:
    """FHMZ prosjek zadnja 24 h do cutoff-a po stanici; bez stanica s premalo sati."""
    w = fhmz[(fhmz.time > cutoff - pd.Timedelta(hours=24)) & (fhmz.time <= cutoff)]
    g = w.groupby("station")[col]
    return g.mean()[g.count() >= PERSIST_MIN_HOURS]


def daily_obs(fhmz: pd.DataFrame, col: str) -> pd.Series:
    s = fhmz.dropna(subset=[col])
    day = pd.to_datetime(s.time.dt.date)
    g = s.groupby([s.station, day])[col]
    return g.mean()[g.count() >= DAILY_MIN_HOURS]


def residuals(history: pd.DataFrame, fhmz: pd.DataFrame, today: pd.Timestamp,
              columns: dict[str, str]) -> pd.DataFrame:
    """Log-greške mješavine na prošlim prognozama čiji je ciljni dan završio."""
    h = history.copy()
    for c in ("issue_day", "target_day"):
        h[c] = pd.to_datetime(h[c]).dt.normalize()
    h = h[(h.target_day < today) & (h.issue_day >= today - pd.Timedelta(days=WINDOW_DAYS))]
    # poslije uvođenja je q50 već mješavina; model je u q50_model
    model = h["q50_model"].fillna(h.q50) if "q50_model" in h else h.q50
    h = h.assign(model_q50=model)
    rows = []
    for pol, col in columns.items():
        part = h[h.pollutant == pol]
        obs = daily_obs(fhmz, col)
        tz = fhmz.time.dt.tz
        pers = {d: station_persistence(fhmz, (pd.Timestamp(d) + pd.Timedelta(hours=17)).tz_localize(tz), col)
                for d in part.issue_day.unique()}
        for r in part.itertuples():
            o = obs.get((r.station, r.target_day))
            p = pers[r.issue_day].get(r.station)
            if o is None or p is None or pd.isna(r.model_q50):
                continue
            b = BLEND_WEIGHT * r.model_q50 + (1 - BLEND_WEIGHT) * p
            rows.append({"pollutant": pol, "horizon": r.horizon,
                         "r": np.log1p(o) - np.log1p(b)})
    return pd.DataFrame(rows, columns=["pollutant", "horizon", "r"])


def blend(pred: pd.DataFrame, history: pd.DataFrame, fhmz: pd.DataFrame,
          today: pd.Timestamp, cutoff: pd.Timestamp, columns: dict[str, str]) -> pd.DataFrame:
    """Medijan i raspon poslane prognoze; stari medijan modela ostaje u q50_model."""
    out = pred.copy()
    out["q50_model"] = out.q50
    out["perz_fhmz"] = np.nan
    res = residuals(history, fhmz, today, columns)
    for pol, col in columns.items():
        pers = station_persistence(fhmz, cutoff, col)
        for h in sorted(out.horizon.unique()):
            idx = (out.pollutant == pol) & (out.horizon == h)
            p = out.loc[idx, "station"].map(pers)
            out.loc[idx, "perz_fhmz"] = p
            missing = sorted(out.loc[idx & p.isna().reindex(out.index, fill_value=False), "station"])
            measured = set(fhmz.dropna(subset=[col]).station)
            missing = [s for s in missing if s in measured]  # stanice bez tog polutanta ne javljamo
            if missing:
                print(f"UPOZORENJE: {pol} D+{h} bez perzistencije za {missing}, ostaje samo model")
            m = out.loc[idx]
            b = np.where(p.isna(), m.q50_model, BLEND_WEIGHT * m.q50_model + (1 - BLEND_WEIGHT) * p)
            r = res[(res.pollutant == pol) & (res.horizon == h)].r
            if len(r) >= MIN_PAIRS:
                lo, mid, hi = np.quantile(r, [0.1, 0.5, 0.9])
                q = {"q10": np.expm1(np.log1p(b) + lo), "q50": np.expm1(np.log1p(b) + mid),
                     "q90": np.expm1(np.log1p(b) + hi)}
                print(f"Raspon {pol} D+{h} iz {len(r)} parova: log-greška {lo:+.2f} / {mid:+.2f} / {hi:+.2f}")
            else:
                print(f"UPOZORENJE: {pol} D+{h} ima samo {len(r)} parova, raspon iz modela "
                      f"raširen {FALLBACK_WIDEN}×")
                q = {"q10": b * (m.q10 / m.q50_model) ** FALLBACK_WIDEN, "q50": b,
                     "q90": b * (m.q90 / m.q50_model) ** FALLBACK_WIDEN}
            for k, v in q.items():
                out.loc[idx, k] = np.clip(v, 0, None)
    out[QS] = np.sort(out[QS].values, axis=1)
    return out

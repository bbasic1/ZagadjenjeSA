"""
Tiha prognoza PM10 za dan (07–17 h) i veče (18–24 h), uz večernju poruku.

Ne ide u poruku: snima se u data/predictions_dan_vece/YYYY-MM-DD.csv da se
nakon dvije sedmice provjeri na stanicama prije nego što je ljudi vide.
Kalibracija ide posebno po dijelu dana, jer CAMS veče precjenjuje, a dan
potcjenjuje (faktor iz istih sati zadnjih 14 dana).
"""

import lightgbm as lgb
import numpy as np
import pandas as pd

from bot.categories import category
from model.baseline import load_fhmz
from model.calibrate import factor_for, station_factors
from model.train_parts import LABEL, PARTS, POLLUTANT, build_dataset
from model.train_v1 import HORIZONS, MODELS, QUANTILES
from ingest.collect import DATA

FOLDER = DATA / "predictions_dan_vece"
QS = [f"q{int(q * 100)}" for q in QUANTILES]


def predict_parts(cams: pd.DataFrame, met: pd.DataFrame, today: pd.Timestamp,
                  cutoff: pd.Timestamp, cells: list[str], cell_of: dict[str, str],
                  stations: list[str]) -> pd.DataFrame:
    """Prognoza po ćeliji, pa po stanici s faktorom za taj dio dana.

    Raspon je sirov (bez CQR korekcije), pa je vjerovatno preuzak, kao u v1.
    """
    pol, col = POLLUTANT
    fhmz = load_fhmz()
    rows = []
    for part, hours in PARTS.items():
        factors = station_factors(fhmz, cams, "PM10", col, cutoff, hours=hours)
        print(f"Faktori PM10 {part} (mreža {factors.attrs['network']:.2f}): "
              + ", ".join(f"{s} {v:.2f}" for s, v in zip(factors.index, factors.faktor)))
        for h in HORIZONS:
            df = build_dataset(cams, met, part, h, stations=cells)
            df = df[df.issue_day == today]
            cell_pred = df[["station", "issue_day", "target_day"]].copy()
            for q in QUANTILES:
                model = lgb.Booster(model_file=str(MODELS / f"{pol}_{part}_h{h}_q{int(q * 100)}.txt"))
                cell_pred[f"q{int(q * 100)}"] = np.expm1(
                    model.predict(df.reindex(columns=model.feature_name())))
            cell_pred[QS] = np.sort(cell_pred[QS].values, axis=1)
            for station in stations:
                p = cell_pred[cell_pred.station == cell_of.get(station, station)].copy()
                p["cell"] = p.pop("station")
                p["station"] = station
                p = p.rename(columns={q: f"{q}_cams" for q in QS})
                p["faktor"] = factor_for(factors, station)
                for q in QS:
                    p[q] = p[f"{q}_cams"] * p.faktor
                rows.append(p.assign(pollutant=pol, horizon=h, dio=part))
    return pd.concat(rows, ignore_index=True)


def preview(pred: pd.DataFrame, display: dict[str, str]) -> str:
    """Kako bi izgledao dio poruke za sutra (samo za --dry i log)."""
    tomorrow = pred[pred.horizon == HORIZONS[0]]
    lines = ["Probno, ne šalje se: sutra " + " i ".join(LABEL.values())]
    for station in display:
        s = tomorrow[tomorrow.station == station].set_index("dio").q50
        if s.empty:
            continue
        parts = [f"{icon} {s[part]:.0f} {category(s[part], 'pm10')[2]}"
                 for part, icon in (("dan", "☀️"), ("vece", "🌙")) if part in s]
        lines.append(f"{display[station]}: " + " · ".join(parts))
    return "\n".join(lines)


def save(pred: pd.DataFrame, today: pd.Timestamp, issued: str) -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / f"{today:%Y-%m-%d}.csv"
    pred.assign(issued_local=issued).to_csv(path, index=False, float_format="%.1f")
    print(f"Probna prognoza za dan i veče snimljena -> {path}")

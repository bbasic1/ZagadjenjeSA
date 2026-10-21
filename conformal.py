"""
Kalibracija raspona 10–90 % (conformalized quantile regression, CQR).

Kvantilni modeli daju preuzak raspon (~65 % pogodaka umjesto 80 %). CQR
mjeri koliko su kvantili promašivali na podacima koje model NIJE vidio i
pomjeri donju i gornju granicu za toliko (na log skali, posebno za svaku
stranu):

    s_lo = log(q10) - log(y)     koliko je y ispod q10
    s_hi = log(y) - log(q90)     koliko je y iznad q90
    c_lo, c_hi = kvantil (1 - 0.1)(1 + 1/n) od s_lo, s_hi
    raspon = [q10 * e^-c_lo, q90 * e^c_hi]

Bez curenja: korekcija za zimu Z dolazi samo iz prognoza za prethodnu zimu,
koje je napravio model treniran prije nje (klizeće, kao train_v1). Samo
prethodna zima, jer starije zime imaju slabije modele (manje podataka za
trening) i previše rašire raspon. Za operativnu prognozu (zima 2026/27)
korekcija je iz zime 2025/26.

Granica: model predviđa CAMS, a poruka stanicu. Greška CAMS -> stanica nije
u ovoj korekciji, pa će pokrivenost na stanicama biti niža; to mjeri dashboard,
a kad se skupi dovoljno parova, istu korekciju treba računati na stanicama.

python conformal.py           izvještaj reports/conformal.md
python conformal.py --final   + models/conformal.json (čita forecast.py)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from baseline import load_cams
from train_v1 import (HEATING, HORIZONS, MODELS, TEST_SEASONS, build_dataset, feature_cols,
                      fit_predict, load_meteo)

ALPHA = 0.1                                    # po strani, ukupno 80 %
CAL_WINTERS = 1                                # koliko prethodnih zima ulazi u korekciju
# zime za koje pravimo prognoze van uzorka; prva služi samo kao kalibracija
SEASONS = [("2023-10-01", "2024-04-01")] + TEST_SEASONS
CONFIG = MODELS / "conformal.json"
REPORT = Path(__file__).parent / "reports" / "conformal.md"
POLS = [("pm10", "cams_pm10", "PM10"), ("pm2_5", "cams_pm2_5", "PM2.5")]


def out_of_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Prognoze za svaku zimu iz modela treniranog samo na ranijim podacima."""
    df = df.dropna(subset=["y", "persistence"])
    feats = feature_cols(df)
    parts = []
    for start, end in SEASONS:
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        train = df[df.target_day < start]
        test = df[(df.issue_day >= start) & (df.target_day < end)]
        test = test[test.target_day.dt.month.isin(HEATING)]
        if len(train) < 200 or test.empty:
            print(f"  preskačem {start:%Y}: trening {len(train)} redova")
            continue
        p = fit_predict(train, test, feats)
        parts.append(test[["station", "target_day", "y"]].join(p)
                     .assign(sezona=f"{start:%Y}/{end:%y}", n_train=len(train)))
    return pd.concat(parts)


def corrections(cal: pd.DataFrame) -> dict:
    y = np.log1p(cal.y)
    s_lo = np.log1p(cal.q10) - y
    s_hi = y - np.log1p(cal.q90)
    n = len(cal)
    level = min(1.0, (1 - ALPHA) * (1 + 1 / n))
    # raspon se samo širi, nikad ne sužava: na stanicama je greška veća nego na CAMS-u
    return {"c_lo": max(0.0, float(np.quantile(s_lo, level, method="higher"))),
            "c_hi": max(0.0, float(np.quantile(s_hi, level, method="higher"))), "n": n}


def load_config() -> dict | None:
    if not CONFIG.exists():
        return None
    return json.loads(CONFIG.read_text(encoding="utf-8"))["korekcije"]


def widen(q10, q90, c: dict):
    """Primijeni korekciju; radi i na skalarima i na nizovima."""
    lo = np.expm1(np.log1p(q10) - c["c_lo"])
    hi = np.expm1(np.log1p(q90) + c["c_hi"])
    return np.clip(lo, 0, None), hi


def interval_stats(y, lo, hi) -> dict:
    a = 2 * ALPHA
    inside = (y >= lo) & (y <= hi)
    # interval score (Gneiting & Raftery): širina + kazna za promašaj; manje je bolje
    score = (hi - lo) + (2 / a) * (lo - y).clip(lower=0) + (2 / a) * (y - hi).clip(lower=0)
    return {"pokr_%": 100 * inside.mean(), "ispod_%": 100 * (y < lo).mean(),
            "iznad_%": 100 * (y > hi).mean(), "sirina": (hi - lo).mean(),
            "int_score": score.mean()}


def evaluate(oos: pd.DataFrame) -> pd.DataFrame:
    """Za svaku test zimu: korekcija samo iz prethodne zime (ili CAL_WINTERS zima)."""
    seasons = list(dict.fromkeys(oos.sezona))
    rows = []
    for i, s in enumerate(seasons[1:], start=1):
        prev = seasons[max(0, i - CAL_WINTERS):i]
        cal = oos[oos.sezona.isin(prev)]
        test = oos[oos.sezona == s]
        c = corrections(cal)
        lo, hi = widen(test.q10, test.q90, c)
        raw = interval_stats(test.y, test.q10, test.q90)
        new = interval_stats(test.y, lo, hi)
        rows.append({"test": s, "kalibracija": "+".join(prev), "n": len(test),
                     "c_lo": c["c_lo"], "c_hi": c["c_hi"],
                     **{f"{k}_prije": v for k, v in raw.items() if k in ("pokr_%", "sirina", "int_score")},
                     **{f"{k}_poslije": v for k, v in new.items()}})
    return pd.DataFrame(rows).set_index("test")


def main() -> None:
    final = "--final" in sys.argv
    cams, met = load_cams(), load_meteo()
    parts = ["# Kalibracija raspona 10–90 % (CQR)\n\n",
             "Korekcija za svaku test zimu je izračunata samo iz prognoza za prethodnu zimu, "
             "koje je napravio model treniran prije nje. Zima 2023/24 ima model treniran na "
             "samo 9 mjeseci (meteo arhiva počinje 2023), pa njena korekcija za 2024/25 "
             "previše raširi raspon; mjerodavan je red 2025/26. Cilj pokrivenosti 80 %, "
             "po 10 % sa svake strane. Target je CAMS dnevni prosjek (kao u model_v1), "
             "pa pokrivenost na FHMZ stanicama treba mjeriti posebno (dashboard).\n\n"
             "`c_lo`, `c_hi` su pomaci na log skali: 0.10 znači da se granica pomjeri ~10 % prema van; negativni pomaci (suženje) se postavljaju na 0. "
             "Interval score = širina + 10 × promašaj; manje je bolje.\n"]
    config = {"alpha_po_strani": ALPHA, "metoda": "CQR na log skali", "korekcije": {}}
    for pol, col, name in POLS:
        for h in HORIZONS:
            print(f"{name} D+{h}")
            df = build_dataset(cams, met, col, h)
            df = df[df.target_day >= met.time.min().tz_localize(None).normalize()]
            oos = out_of_sample(df)
            ev = evaluate(oos)
            parts.append(f"\n## {name}, D+{h}\n\n" + ev.to_markdown(floatfmt=".2f") + "\n")
            # operativno: zadnja zima(e), isto pravilo kao u evaluaciji
            recent = oos[oos.sezona.isin(list(dict.fromkeys(oos.sezona))[-CAL_WINTERS:])]
            c = corrections(recent)
            c["kalibracija"] = sorted(recent.sezona.unique())
            config["korekcije"][f"{pol}_h{h}"] = c
            parts.append(f"\nOperativna korekcija (iz {', '.join(c['kalibracija'])}, n = {c['n']}): "
                         f"c_lo {c['c_lo']:.3f}, c_hi {c['c_hi']:.3f}\n")
    REPORT.write_text("".join(parts), encoding="utf-8")
    print("".join(parts))
    if final:
        CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Korekcije snimljene u {CONFIG}")


if __name__ == "__main__":
    main()

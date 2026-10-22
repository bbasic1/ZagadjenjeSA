"""
Javni dashboard tačnosti: svaka poslana prognoza naspram FHMZ mjerenja.

Čita data/predictions/*.csv (snimljeno u trenutku slanja, prije mjerenja)
i data/fhmz/*.csv, pa pravi statičnu stranicu site/index.html i
site/parovi.csv sa svim parovima prognoza-mjerenje.

Poređenje je pošteno prema perzistenciji: ona koristi ista FHMZ mjerenja
koja su bila poznata u 18:00 dana izdavanja (zadnja 24 h do 17:00).
Uz male uzorke prikazuje interval nesigurnosti (bootstrap po danima) i
jasno piše kad razlika još ništa ne znači.

python dashboard.py                      # data/predictions -> site/
python dashboard.py --predictions DIR --out DIR
"""

import argparse
import html
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from baseline import CHANGE_THRESHOLD, daily_mean, load_fhmz, persistence
from categories import SOURCE as SCALE_SOURCE, category
from collect import DATA, LOCAL_TZ

DISPLAY = {
    "bjelave": "Bjelave", "vijecnica": "Vijećnica", "otoka": "Otoka", "ilidza": "Ilidža",
    "saraj_polje": "Saraj Polje", "vogosca": "Vogošća", "hadzici": "Hadžići",
    "ilijas": "Ilijaš", "ivan_sedlo": "Ivan Sedlo",
}
POLLUTANTS = {"pm10": ("PM10", "PM10"), "pm2_5": ("PM2_5", "PM2.5")}  # kod -> (FHMZ kolona, naziv)
SMALL_SAMPLE = 30      # ispod ovoliko parova rezultat je samo orijentacija
BOOT = 2000
REPO = "https://github.com/bbasic1/ZagadjenjeSA"


# ------------------------------------------------------------ podaci

def load_predictions(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.csv"))
    if not files:
        return pd.DataFrame(columns=["station", "pollutant", "horizon", "issue_day",
                                     "target_day", "model", "q10", "q50", "q90"])
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    need = {"station", "pollutant", "horizon", "issue_day", "target_day", "q10", "q50", "q90"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"predictions nemaju kolone {sorted(missing)}")
    for c in ("issue_day", "target_day"):
        df[c] = pd.to_datetime(df[c]).dt.normalize()
    # stariji snimci nemaju kolonu model; tada je to uvijek bio LightGBM.
    # Kad forecast.py padne na perzistenciju (fallback), q10 i q90 su prazni.
    df["model"] = df["model"].fillna("lightgbm") if "model" in df else "lightgbm"
    # ako je isti dan slučajno snimljen dvaput, vrijedi prva (poslana) prognoza
    return df.drop_duplicates(["station", "pollutant", "horizon", "target_day"], keep="first")


def observations(fhmz: pd.DataFrame) -> pd.DataFrame:
    """Po stanici i polutantu: dnevni prosjek (istina) i perzistencija po danu izdavanja."""
    rows = []
    for pol, (col, _) in POLLUTANTS.items():
        if col not in fhmz:
            continue
        for station, g in fhmz.groupby("station"):
            hourly = g.set_index("time")[col].sort_index()
            if hourly.dropna().empty:
                continue
            day = pd.DataFrame({"truth": daily_mean(hourly),
                                "persistence": persistence(hourly)})
            rows.append(day.rename_axis("day").reset_index().assign(station=station, pollutant=pol))
    return pd.concat(rows, ignore_index=True)


def pair(pred: pd.DataFrame, obs: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    truth = obs[["station", "pollutant", "day", "truth"]]
    p = pred.merge(truth.rename(columns={"day": "target_day"}),
                   on=["station", "pollutant", "target_day"], how="left")
    p = p.merge(obs.rename(columns={"day": "issue_day", "truth": "truth_issue_day"}),
                on=["station", "pollutant", "issue_day"], how="left")
    p["status"] = np.select(
        [p.target_day >= today, p.truth.isna(), p.persistence.isna()],
        ["čeka mjerenje", "nema mjerenja", "nema perzistencije"], "ok")
    return p


# ------------------------------------------------------------ metrike

def cat_hits(pred: pd.Series, truth: pd.Series, pollutant: pd.Series) -> pd.Series:
    return pd.Series([category(a, p)[0] == category(b, p)[0]
                      for a, b, p in zip(pred, truth, pollutant)], index=pred.index, dtype=bool)


def skill_ci(g: pd.DataFrame, rng: np.random.Generator) -> tuple[float, float] | None:
    """90 % bootstrap interval za skill, uzorkuje cijele ciljne dane (stanice
    istog dana nisu nezavisne)."""
    days = g.target_day.unique()
    if len(days) < 5:
        return None
    by_day = g.groupby("target_day")
    em = by_day.apply(lambda d: (d.q50 - d.truth).abs().sum(), include_groups=False).values
    ep = by_day.apply(lambda d: (d.persistence - d.truth).abs().sum(), include_groups=False).values
    idx = rng.integers(0, len(days), size=(BOOT, len(days)))
    s = 100 * (1 - em[idx].sum(1) / ep[idx].sum(1))
    return float(np.percentile(s, 5)), float(np.percentile(s, 95))


def wilson(k: int, n: int, z: float = 1.645) -> tuple[float, float]:
    if n == 0:
        return math.nan, math.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def has_range(g: pd.DataFrame) -> pd.Series:
    return g.q10.notna() & g.q90.notna()


def score(g: pd.DataFrame, rng: np.random.Generator) -> dict:
    n = len(g)
    if n == 0:
        return {"n": 0}
    em, ep = (g.q50 - g.truth).abs(), (g.persistence - g.truth).abs()
    change = (g.truth - g.truth_issue_day).abs() >= CHANGE_THRESHOLD
    # MAE broji svaku poslanu prognozu (i fallback); raspon samo gdje ga je bilo
    rg = g[has_range(g)]
    inside = (rg.truth >= rg.q10) & (rg.truth <= rg.q90)
    return {
        "n": n, "dana": g.target_day.nunique(),
        "mae_m": em.mean(), "mae_p": ep.mean(),
        "skill": 100 * (1 - em.sum() / ep.sum()) if ep.sum() > 0 else math.nan,
        "skill_ci": skill_ci(g, rng),
        "n_fallback": int((g.model != "lightgbm").sum()), "n_raspon": len(rg),
        "pokr": 100 * inside.mean() if len(rg) else math.nan,
        "pokr_ci": wilson(int(inside.sum()), len(rg)),
        "kat_m": 100 * cat_hits(g.q50, g.truth, g.pollutant).mean(),
        "kat_p": 100 * cat_hits(g.persistence, g.truth, g.pollutant).mean(),
        "n_prom": int(change.sum()),
        "mae_m_prom": em[change].mean() if change.any() else math.nan,
        "mae_p_prom": ep[change].mean() if change.any() else math.nan,
    }


# ------------------------------------------------------------ HTML

def f(x, d=1, suf=""):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}{suf}"


def verdict(s: dict) -> str:
    if s["n"] == 0:
        return "Još nema provjerenih prognoza."
    ci = s["skill_ci"]
    if ci is None:
        return f"Samo {s['dana']} dan(a) s mjerenjem: prerano za bilo kakav zaključak."
    lo, hi = ci
    if lo > 0:
        return f"Model je bolji od perzistencije (90 % interval skill-a {lo:.0f} do {hi:.0f} %)."
    if hi < 0:
        return f"Model je zasad lošiji od perzistencije (90 % interval {lo:.0f} do {hi:.0f} %)."
    return (f"Razlika još nije pouzdana: 90 % interval skill-a je {lo:.0f} do {hi:.0f} %, "
            "uključuje nulu.")


def tiles(s: dict) -> str:
    if s["n"] == 0:
        return '<p class="muted">Još nema parova prognoza–mjerenje.</p>'
    lo, hi = s["pokr_ci"]
    cov = (f"cilj 80 %, 90 % interval {lo:.0f}–{hi:.0f} %" if s["n_raspon"] else "nema prognoza s rasponom")
    if s["n_fallback"]:
        cov += f"; {s['n_fallback']} fallback bez raspona nije uračunato"
    items = [
        ("MAE modela", f(s["mae_m"]) + " µg/m³", f"perzistencija {f(s['mae_p'])} µg/m³"),
        ("Skill prema perzistenciji", f(s["skill"], 0, " %"), "više je bolje, 0 = isto"),
        ("Pogođen raspon 10–90 %", f(s["pokr"], 0, " %"), cov),
        ("Tačna kategorija", f(s["kat_m"], 0, " %"), f"perzistencija {f(s['kat_p'], 0, ' %')}"),
        ("Dani promjene (≥10 µg/m³)", f(s["mae_m_prom"]) + " µg/m³" if s["n_prom"] else "–",
         f"perzistencija {f(s['mae_p_prom'])}, n = {s['n_prom']}"),
    ]
    cells = "".join(f'<div class="tile"><div class="tl">{a}</div><div class="tv">{b}</div>'
                    f'<div class="ts">{c}</div></div>' for a, b, c in items)
    return f'<div class="tiles">{cells}</div>'


def station_table(ok: pd.DataFrame, rng) -> str:
    rows = []
    for st, name in DISPLAY.items():
        s = score(ok[ok.station == st], rng)
        if s["n"] == 0:
            rows.append(f"<tr><td>{name}</td><td>0</td>" + "<td>–</td>" * 5 + "</tr>")
            continue
        rows.append(f"<tr><td>{name}</td><td>{s['n']}</td><td>{f(s['mae_m'])}</td>"
                    f"<td>{f(s['mae_p'])}</td><td>{f(s['skill'], 0)}</td>"
                    f"<td>{f(s['pokr'], 0)}</td><td>{f(s['kat_m'], 0)}</td></tr>")
    return ("<table><thead><tr><th>Stanica</th><th>n</th><th>MAE model</th>"
            "<th>MAE perzist.</th><th>skill %</th><th>raspon %</th><th>kategorija %</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def range_text(r) -> str:
    if math.isnan(r.q10) or math.isnan(r.q90):
        return "perzistencija, bez raspona"
    return f"{r.q10:.0f}–{r.q90:.0f}"


def chart(g: pd.DataFrame, ymax: float, days: pd.DatetimeIndex) -> str:
    """Mala slika jedne stanice: raspon 10–90, medijan, mjerenje, perzistencija."""
    W, H, L, R, T, B = 300, 150, 30, 8, 8, 20
    if len(days) < 2:
        days = pd.date_range(days[0] - pd.Timedelta(days=1), periods=2) if len(days) else days
    x0, x1 = days.min(), days.max()
    span = max((x1 - x0).days, 1)
    X = lambda d: L + (W - L - R) * (d - x0).days / span
    Y = lambda v: T + (H - T - B) * (1 - min(v, ymax) / ymax)
    g = g.sort_values("target_day")
    out = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    for t in np.linspace(0, ymax, 4)[1:]:
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>'
                   f'<text class="ax" x="{L - 4}" y="{Y(t) + 3:.1f}" text-anchor="end">{t:.0f}</text>')
    out.append(f'<line class="base" x1="{L}" x2="{W - R}" y1="{Y(0)}" y2="{Y(0)}"/>')
    for d in (x0, x1):
        out.append(f'<text class="ax" x="{X(d):.1f}" y="{H - 5}" text-anchor="middle">{d:%d.%m.}</text>')
    if len(g):
        # raspon crta samo neprekinute dijelove; fallback dani (bez raspona) prekidaju traku
        seg_id = (~has_range(g)).cumsum()
        for _, seg in g[has_range(g)].groupby(seg_id[has_range(g)]):
            top = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in zip(seg.target_day, seg.q90))
            bot = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in zip(seg.target_day[::-1], seg.q10[::-1]))
            out.append(f'<polygon class="band" points="{top} {bot}"/>')
        out.append('<polyline class="med" points="'
                   + " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in zip(g.target_day, g.q50)) + '"/>')
        pe = g.dropna(subset=["persistence"])
        if len(pe):
            out.append('<polyline class="pers" points="'
                       + " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in zip(pe.target_day, pe.persistence))
                       + '"/>')
        for _, r in g.iterrows():
            tip = (f"{r.target_day:%d.%m.}: prognoza {r.q50:.0f} ({range_text(r)}), "
                   f"mjereno {f(r.truth, 0)}, perzistencija {f(r.persistence, 0)}")
            cx = f"{X(r.target_day):.1f}"
            out.append(f'<g class="hit"><title>{html.escape(tip)}</title>'
                       f'<rect x="{float(cx) - 8:.1f}" y="{T}" width="16" height="{H - T - B}"/>')
            if not math.isnan(r.truth):
                out.append(f'<circle class="obs" cx="{cx}" cy="{Y(r.truth):.1f}" r="4"/>')
            out.append("</g>")
    out.append("</svg>")
    return "".join(out)


def charts(sub: pd.DataFrame) -> str:
    if sub.empty:
        return '<p class="muted">Nema prognoza za prikaz.</p>'
    days = pd.DatetimeIndex(sorted(sub.target_day.unique()))
    ymax = max(20.0, np.nanmax(sub[["q90", "truth", "persistence"]].to_numpy(dtype=float)))
    ymax = math.ceil(ymax * 1.1 / 10) * 10
    cards = "".join(f'<figure><figcaption>{name}</figcaption>'
                    f'{chart(sub[sub.station == st], ymax, days)}</figure>'
                    for st, name in DISPLAY.items())
    return f'<div class="grid9">{cards}</div>'


def recent_table(p: pd.DataFrame, pol: str, h: int) -> str:
    sub = p[(p.pollutant == pol) & (p.horizon == h)].sort_values(["target_day", "station"],
                                                                 ascending=[False, True])
    last = sorted(sub.target_day.unique())[-3:]
    sub = sub[sub.target_day.isin(last)]
    if sub.empty:
        return '<p class="muted">Još nema poslanih prognoza.</p>'
    rows = []
    for _, r in sub.iterrows():
        _, emo, name = category(r.q50, pol)
        if r.status == "ok":
            _, emo_t, name_t = category(r.truth, pol)
            hit = (abs(r.q50 - r.truth) <= abs(r.persistence - r.truth))
            inside = ("–" if math.isnan(r.q10) or math.isnan(r.q90)
                      else "da" if r.q10 <= r.truth <= r.q90 else "ne")
            res = (f"<td>{r.truth:.0f}</td><td>{r.persistence:.0f}</td>"
                   f"<td>{inside}</td><td>{emo_t} {name_t}"
                   f"{'' if name == name_t else ' ✗'}</td><td>{'model' if hit else 'perzistencija'}</td>")
        else:
            res = f'<td colspan="5" class="muted">{r.status}</td>'
        rows.append(f"<tr><td>{r.target_day:%d.%m.}</td><td>{DISPLAY.get(r.station, r.station)}</td>"
                    f"<td>{emo} {r.q50:.0f} ({range_text(r)})</td>{res}</tr>")
    return ("<table><thead><tr><th>Dan</th><th>Stanica</th><th>Prognoza</th><th>Mjereno</th>"
            "<th>Perzist.</th><th>U rasponu</th><th>Kategorija (mjereno)</th><th>Bliže</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


CSS = """
:root{--bg:#fcfcfb;--card:#f3f2ee;--ink:#0b0b0b;--ink2:#52514e;--mut:#7a7975;--line:#dddcd6;
--s1:#2a78d6;--band:rgba(42,120,214,.18);--s2:#eb6834;--warn-bg:#fff4d6;--warn:#6b4a00}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a19;--card:#242422;
--ink:#f0efec;--ink2:#c3c2b7;--mut:#8f8e87;--line:#3a3a37;--s1:#3987e5;--band:rgba(57,135,229,.25);
--s2:#d95926;--warn-bg:#3a3020;--warn:#f2d58a}}
:root[data-theme="dark"]{--bg:#1a1a19;--card:#242422;--ink:#f0efec;--ink2:#c3c2b7;--mut:#8f8e87;
--line:#3a3a37;--s1:#3987e5;--band:rgba(57,135,229,.25);--s2:#d95926;--warn-bg:#3a3020;--warn:#f2d58a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1060px;margin:0 auto;padding:24px 16px 48px}h1{font-size:26px;margin:0 0 4px}
h2{font-size:19px;margin:32px 0 8px}h3{font-size:16px;margin:20px 0 6px}.muted,.ts{color:var(--mut)}
.lead{color:var(--ink2);margin:0 0 16px}.warn{background:var(--warn-bg);color:var(--warn);
padding:10px 14px;border-radius:8px;margin:12px 0}.verdict{font-weight:600;margin:8px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.tile{background:var(--card);border-radius:8px;padding:10px 12px}.tl{font-size:13px;color:var(--ink2)}
.tv{font-size:24px;font-weight:650;font-variant-numeric:tabular-nums}.ts{font-size:12px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.tabs button{font:inherit;border:1px solid var(--line);
background:var(--bg);color:var(--ink);border-radius:6px;padding:4px 10px;cursor:pointer}
.tabs button[aria-pressed="true"]{background:var(--ink);color:var(--bg)}
.grid9{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}
figure{margin:0;background:var(--card);border-radius:8px;padding:8px}figcaption{font-size:13px;font-weight:600}
svg{width:100%;height:auto;display:block}.grid{stroke:var(--line);stroke-width:1}.base{stroke:var(--mut)}
.ax{fill:var(--mut);font-size:10px}.band{fill:var(--band)}.med{fill:none;stroke:var(--s1);stroke-width:2}
.pers{fill:none;stroke:var(--s2);stroke-width:2;stroke-dasharray:4 3}
.obs{fill:var(--ink);stroke:var(--card);stroke-width:2}.hit rect{fill:transparent}
.hit:hover rect{fill:var(--line);opacity:.5}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--ink2);margin:6px 0}
.legend i{display:inline-block;width:18px;height:10px;margin-right:5px;vertical-align:middle}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--ink2);font-weight:600}a{color:var(--s1)}
"""

JS = """
document.querySelectorAll('.tabs').forEach(t=>t.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 t.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));
 document.querySelectorAll('[data-view]').forEach(v=>v.hidden=v.dataset.view!==b.dataset.view);}));
"""


def view(p: pd.DataFrame, pol: str, h: int, rng) -> str:
    sub = p[(p.pollutant == pol) & (p.horizon == h)]
    ok = sub[sub.status == "ok"]
    s = score(ok, rng)
    label = "sutra (D+1)" if h == 1 else "prekosutra (D+2)"
    warn = ""
    if s["n"] < SMALL_SAMPLE:
        warn = (f'<div class="warn">Mali uzorak: {s["n"]} parova iz {s.get("dana", 0)} dana. '
                "Brojke ispod su orijentacija, ne rezultat. Stanice istog dana nisu nezavisne, "
                "pa je stvarni uzorak bliži broju dana nego broju parova.</div>")
    counts = sub.status.value_counts()
    status = ", ".join(f"{k}: {v}" for k, v in counts.items() if k != "ok")
    return (f"<h2>{POLLUTANTS[pol][1]}, {label}</h2>{warn}"
            f'<p class="verdict">{verdict(s)}</p>{tiles(s)}'
            + (f'<p class="muted">Bez para: {status}. Nedostajuća mjerenja se ne popunjavaju, '
               "takve prognoze ne ulaze u brojke.</p>" if status else "")
            + '<h3>Po danima</h3><div class="legend"><span><i style="background:var(--band)"></i>'
            'raspon 10–90 %</span><span><i style="border-top:2px solid var(--s1);height:0"></i>prognoza '
            '(medijan)</span><span><i style="border-top:2px dashed var(--s2);height:0"></i>perzistencija'
            '</span><span><i style="background:var(--ink);border-radius:5px;width:10px"></i>mjereno '
            "(FHMZ)</span></div>" + charts(sub)
            + f"<h3>Po stanicama</h3><div class='scroll'>{station_table(ok, rng)}</div>"
            + f"<h3>Zadnja 3 dana</h3><div class='scroll'>{recent_table(p, pol, h)}</div>")


def render(p: pd.DataFrame, now: datetime) -> str:
    rng = np.random.default_rng(0)
    first = p.issue_day.min()
    sent = p.issue_day.nunique()
    views, buttons = [], []
    for i, (pol, h) in enumerate([("pm10", 1), ("pm10", 2), ("pm2_5", 1), ("pm2_5", 2)]):
        key = f"{pol}-{h}"
        buttons.append(f'<button data-view="{key}" aria-pressed="{str(i == 0).lower()}">'
                       f'{POLLUTANTS[pol][1]} D+{h}</button>')
        views.append(f'<section data-view="{key}"{"" if i == 0 else " hidden"}>{view(p, pol, h, rng)}</section>')
    since = f"od {first:%d.%m.%Y}, {sent} večeri" if sent else "još nijedna"
    return f"""<!doctype html><html lang="bs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tačnost prognoze zagađenja</title><style>{CSS}</style></head><body><main>
<h1>Koliko je prognoza bila tačna</h1>
<p class="lead">Svaka prognoza ZagađenkoBota za Sarajevo, poslana u 18:00 i snimljena prije nego što
je mjerenje poznato, upoređena sa dnevnim prosjekom FHMZ stanice. Poslane prognoze: {since}.
Ažurirano {now:%d.%m.%Y. u %H:%M}.</p>
<div class="tabs" role="group">{''.join(buttons)}</div>
{''.join(views)}
<h2>Kako se računa</h2>
<ul>
<li><b>Mjereno</b>: dnevni prosjek FHMZ stanice (lokalni dan), samo ako ima bar 18 satnih
vrijednosti. Podaci su automatski i nevalidirani. Dan bez dovoljno mjerenja se preskače, ne popunjava.</li>
<li><b>Perzistencija</b> (»sutra kao danas«): prosjek zadnja 24 h zaključno sa 17:00 na dan
izdavanja, iz istih FHMZ mjerenja. To je ono što je bilo poznato kad je prognoza poslana.</li>
<li><b>Skill</b> = 1 − MAE modela / MAE perzistencije. Interval je 90 % bootstrap po danima.</li>
<li><b>Raspon</b>: 10. i 90. percentil prognoze; ako je dobro kalibriran, mjerenje upada u njega u
oko 80 % slučajeva.</li>
<li><b>Kategorija</b>: <a href="{SCALE_SOURCE}">skala indeksa kvaliteta zraka FHMZ</a>. FHMZ je
primjenjuje na satne vrijednosti; ovdje se primjenjuje na dnevni prosjek.</li>
<li><b>Fallback</b>: kad model ili podaci zakažu, bot šalje perzistenciju bez raspona. Takve prognoze ulaze u MAE i kategoriju (to je bilo poslano), ali ne u pokrivenost raspona.</li>
<li><b>Dan promjene</b>: dnevni prosjek se u odnosu na dan izdavanja pomjerio bar 10 µg/m³.</li>
<li>Prognoze se commituju u repo u trenutku slanja (<a href="{REPO}/commits/main/data/predictions">historija
</a>), pa se ne mogu naknadno popraviti. Svi parovi: <a href="parovi.csv">parovi.csv</a>.</li>
</ul>
<p class="muted">Eksperimentalni projekat, nije zvanični izvor. Mjerenja: FHMZ (fhmzbih.gov.ba).
Prognoze vremena i CAMS: Open-Meteo, CC BY 4.0. <a href="{REPO}">Kod</a>.</p>
</main><script>{JS}</script></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path, default=DATA / "predictions")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "site")
    args = ap.parse_args()
    now = datetime.now(LOCAL_TZ)
    pred = load_predictions(args.predictions)
    obs = observations(load_fhmz())
    p = pair(pred, obs, pd.Timestamp(now.date()))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(render(p, now), encoding="utf-8")
    cols = ["issue_day", "target_day", "horizon", "pollutant", "station", "model", "q10", "q50",
            "q90", "truth", "persistence", "status"]
    p.reindex(columns=cols).sort_values(cols[:5]).to_csv(
        args.out / "parovi.csv", index=False, float_format="%.1f", date_format="%Y-%m-%d")
    ok = p[p.status == "ok"]
    print(f"{len(pred)} prognoza, {len(ok)} s mjerenjem -> {args.out / 'index.html'}")
    for k, v in p.status.value_counts().items():
        if k != "ok":
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ZagadjenjeSA

Prognoza zagađenja zraka u Sarajevu za sutra (D+1) i prekosutra (D+2), po mjernoj stanici. Svako veče poslije 18:00 Telegram bot **ZagađenkoBot** objavi prognozu u kanalu, a javni dashboard prati koliko su prognoze bile tačne:

**Dashboard tačnosti:** https://bbasic1.github.io/ZagadjenjeSA/

> **Ograda.** Ovo je eksperimentalni, nezavisni projekat. Nije zvanični izvor informacija o kvalitetu zraka. Zvanični podaci su na stranici [Federalnog hidrometeorološkog zavoda (FHMZ)](https://www.fhmzbih.gov.ba/).

## Šta se prognozira

- **PM10**, dnevni prosjek, za sve stanice (glavni target)
- **PM2.5**, dnevni prosjek, za stanice koje ga mjere (Bjelave, Otoka, Ilidža, Vogošća, Hadžići)

Uz srednju vrijednost prognoza daje i raspon (10–90 %) i kategoriju po skali indeksa kvaliteta zraka FHMZ.

Cilj je pobijediti perzistenciju, tj. pretpostavku "sutra će biti kao danas". Na razvojnom testu (zime 2024/25 i 2025/26, cilj CAMS) model ima MAE za PM10 od 8.3 µg/m³ za sutra, naspram 11.9 za perzistenciju (prekosutra 9.2 naspram 13.8). Detalji su u [`reports/`](reports/). Pravi završni test je sezona 2026/27 uživo: svaka prognoza se snimi prije nego što je mjerenje poznato.

## Kako radi

1. **Prikupljanje** (`ingest/collect.py`, svaki sat preko GitHub Actions): satna mjerenja sa stranica FHMZ stanica i snimci Open-Meteo prognoze (meteo varijable i CAMS PM).
2. **Model** (`model/train_v1.py`): LightGBM s kvantilnom regresijom (0.1, 0.5, 0.9), poseban model za D+1 i D+2. Pretreniran je na CAMS arhivi od 2013. Varijable su perzistencija zadnjih sati i dana, inverzija (temperatura Bjelašnice minus kotlina), vjetar, padavine, vlažnost, pritisak, stepen grijanja i sezonalnost.
3. **Kalibracija** (`model/calibrate.py`, `model/conformal.py`): faktor po stanici iz zadnjih 14 dana mjerenja i CQR korekcija koja širi raspon do ciljane pokrivenosti od 80 %.
4. **Večernja prognoza** (`bot/forecast.py`, 18:00 po lokalnom vremenu): poruka u Telegram kanal i snimak u `data/predictions/`. Ako model ili podaci zakažu, šalje se perzistencija.
5. **Dashboard** (`dashboard/dashboard.py`): poređenje poslanih prognoza s mjerenjima, objavljeno na GitHub Pages.

### Bez curenja podataka

Vremenske varijable za buduće dane (vjetar, padavine, temperatura) dolaze **samo iz prognoze** koja je bila dostupna u trenutku izdavanja, nikad iz kasnijih mjerenja. Za trening se koriste historijske prognoze iz Open-Meteo Previous Runs arhive. Mjerenja PM-a se koriste samo do 17:00 dana izdavanja, a validacija je isključivo klizeća po vremenu.

## Struktura repoa

| Putanja | Šta je |
| --- | --- |
| `ingest/` | Prikupljanje: FHMZ mjerenja i snimci Open-Meteo prognoze (`collect.py`), arhiva CAMS-a i historijskih meteo prognoza (`fetch_cams_archive.py`, `fetch_meteo_archive.py`) |
| `model/` | Perzistencija i sirovi CAMS (`baseline.py`), validacija i trening (`train_v1.py`), kalibracija po stanici (`calibrate.py`), korekcija raspona 10–90 % (`conformal.py`) |
| `bot/` | Večernja prognoza (`forecast.py`), slanje u Telegram (`send_telegram.py`), skala kategorija FHMZ (`categories.py`) |
| `dashboard/` | Dashboard tačnosti → `site/` |
| `data/fhmz/` | Satna mjerenja po mjesecima (UTC) |
| `data/forecast/` | Snimci prognoze dvaput dnevno |
| `data/predictions/` | Svaka poslana prognoza |
| `models/` | Istrenirani modeli i korekcija raspona |
| `reports/` | Izvještaji o evaluaciji |
| `tests/` | Testovi formata FHMZ stranica |
| `.github/workflows/` | Raspored prikupljanja, prognoze, dashboarda i testova |

Sva vremena u fajlovima su UTC.

## Pokretanje lokalno

Potreban je Python 3. Skripte se pokreću kao moduli iz root foldera repoa (`python -m folder.skripta`).

```bash
pip install -r requirements.txt
python -m ingest.collect          # prikupi mjerenja i prognozu
python -m bot.forecast --dry      # ispiši večernju prognozu bez slanja
python -m dashboard.dashboard     # napravi dashboard u site/
python -m unittest discover tests
```

Ponovni trening modela: `python -m model.train_v1 --final`, pa `python -m model.conformal --final`.

Slanje u Telegram traži varijable okruženja `TELEGRAM_TOKEN` i `TELEGRAM_CHAT_ID`. U repou su postavljene kao GitHub Actions secreti i nikad se ne commituju.

## Izvori podataka

- Mjerenja: [FHMZ BiH](https://www.fhmzbih.gov.ba/)
- Meteo prognoze i CAMS: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0), CAMS je servis programa Copernicus

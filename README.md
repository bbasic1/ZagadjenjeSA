# ZagadjenjeSA

**English** · [Bosanski](README.bs.md)

Air pollution forecasts for Sarajevo, Bosnia and Herzegovina, for tomorrow (D+1) and the day after (D+2), per monitoring station. Every evening after 18:00 local time the Telegram bot **ZagađenkoBot** posts the forecast to a public channel, and a public dashboard tracks how accurate past forecasts were:

**Accuracy dashboard:** https://bbasic1.github.io/ZagadjenjeSA/

> **Disclaimer.** This is an experimental, independent project and not an official source of air quality information. Official data is published by the [Federal Hydrometeorological Institute (FHMZ)](https://www.fhmzbih.gov.ba/).

## What is forecast

- **PM10** daily mean at every station (main target)
- **PM2.5** daily mean at the stations that measure it (Bjelave, Otoka, Ilidža, Vogošća, Hadžići)

Each forecast includes a median, a 10–90 % range, and a category on the FHMZ air quality index scale.

The goal is to beat persistence, the assumption that tomorrow will be like today. On the development test (winters 2024/25 and 2025/26, with CAMS as the target), the PM10 model has a MAE of 8.3 µg/m³ for tomorrow, against 11.9 for persistence (9.2 against 13.8 for the day after). Details are in [`reports/`](reports/). The real final test is the 2026/27 season, live: every forecast is saved before the measurement is known.

## How it works

1. **Collection** (`ingest/collect.py`, hourly via GitHub Actions): hourly measurements from the FHMZ station pages, plus snapshots of the Open-Meteo forecast (weather variables and CAMS PM).
2. **Model** (`model/train_v1.py`): LightGBM quantile regression (0.1, 0.5, 0.9), with a separate model for D+1 and D+2. It is pre-trained on the CAMS archive since 2013. Features are recent PM persistence, inversion strength (forecast temperature on Bjelašnica minus the valley), wind, precipitation, humidity, pressure, heating degrees and seasonality.
3. **Calibration** (`model/calibrate.py`, `model/conformal.py`): a per-station factor from the last 14 days of measurements, and a CQR correction that widens the range towards 80 % coverage.
4. **Evening forecast** (`bot/forecast.py`, 18:00 local time): a message to the Telegram channel and a snapshot in `data/predictions/`. If the model or the data fail, a persistence forecast is sent instead.
5. **Dashboard** (`dashboard/dashboard.py`): compares the sent forecasts with measurements and publishes the result on GitHub Pages.

### No data leakage

Weather variables for future days (wind, precipitation, temperature) come **only from forecasts** that were available at issue time, never from later measurements. Training uses historical forecasts from the Open-Meteo Previous Runs archive. PM measurements are used only up to 17:00 on the issue day, and validation is strictly time-based (rolling, training always before testing).

## Repository layout

| Path | Contents |
| --- | --- |
| `ingest/` | Data collection: FHMZ measurements and Open-Meteo forecast snapshots (`collect.py`), CAMS archive and historical weather forecasts (`fetch_cams_archive.py`, `fetch_meteo_archive.py`) |
| `model/` | Persistence and raw CAMS error (`baseline.py`), validation and training (`train_v1.py`), per-station calibration (`calibrate.py`), 10–90 % range correction (`conformal.py`) |
| `bot/` | Evening forecast (`forecast.py`), Telegram sending (`send_telegram.py`), FHMZ index categories (`categories.py`) |
| `dashboard/` | Accuracy dashboard → `site/` |
| `data/fhmz/` | Hourly measurements by month (UTC) |
| `data/forecast/` | Forecast snapshots, twice a day |
| `data/predictions/` | Every forecast that was sent |
| `models/` | Trained models and range correction |
| `reports/` | Evaluation reports (in Bosnian) |
| `tests/` | Tests for the FHMZ page format |
| `.github/workflows/` | Schedules for collection, forecast, dashboard and tests |

All times in data files are UTC.

## Running locally

Requires Python 3. Scripts run as modules from the repository root (`python -m folder.script`).

```bash
pip install -r requirements.txt
python -m ingest.collect          # collect measurements and forecasts
python -m bot.forecast --dry      # print the evening forecast without sending it
python -m dashboard.dashboard     # build the dashboard into site/
python -m unittest discover tests
```

To retrain the models: `python -m model.train_v1 --final`, then `python -m model.conformal --final`.

Sending to Telegram needs the `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` environment variables. In this repo they are GitHub Actions secrets and are never committed.

## Data sources

- Measurements: [FHMZ BiH](https://www.fhmzbih.gov.ba/)
- Weather forecasts and CAMS: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0); CAMS is a Copernicus service

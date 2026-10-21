# Faza 4: LightGBM v1
Target: CAMS dnevni prosjek po ćeliji stanice (pretrening). Izdavanje u 18:00 lokalno. Meteo iz arhive prognoza (lead = horizont + 1 dan). Test: zime (okt–mar), model treniran samo na podacima prije te zime. Perzistencija je računata na istim test danima.

Meteo arhiva: 01.01.2023 do 21.10.2026.

## PM10, D+1

|         |      n |   n_promjena |   MAE_model |   MAE_perzist |   skill_% |   MAE_model_promjena |   MAE_perzist_promjena |   pokrivenost_10_90_% |
|:--------|-------:|-------------:|------------:|--------------:|----------:|---------------------:|-----------------------:|----------------------:|
| 2024/25 | 1267.0 |        476.0 |         8.5 |          12.2 |      29.8 |                 12.3 |                   22.7 |                  66.5 |
| 2025/26 | 1267.0 |        457.0 |         8.0 |          11.5 |      30.9 |                 11.8 |                   20.9 |                  66.3 |
| SVE     | 2534.0 |        933.0 |         8.3 |          11.9 |      30.4 |                 12.0 |                   21.8 |                  66.4 |

Najvažniji features (udio gain-a): pm_last 34%, doy_sin 6%, doy_cos 5%, pm_mean24 5%, pressure_mean 4%, pm_max72 4%, t2m_max 4%, wind_mean 4%

## PM10, D+2

|         |      n |   n_promjena |   MAE_model |   MAE_perzist |   skill_% |   MAE_model_promjena |   MAE_perzist_promjena |   pokrivenost_10_90_% |
|:--------|-------:|-------------:|------------:|--------------:|----------:|---------------------:|-----------------------:|----------------------:|
| 2024/25 | 1260.0 |        577.0 |         9.0 |          14.3 |      37.2 |                 12.1 |                   24.3 |                  65.4 |
| 2025/26 | 1260.0 |        624.0 |         9.4 |          13.2 |      28.9 |                 12.6 |                   20.6 |                  61.3 |
| SVE     | 2520.0 |       1201.0 |         9.2 |          13.8 |      33.2 |                 12.4 |                   22.4 |                  63.4 |

Najvažniji features (udio gain-a): pm_last 19%, doy_cos 10%, doy_sin 9%, pm_max72 7%, pressure_mean 7%, t2m_max 4%, station 4%, wind_mean 4%

## PM2_5, D+1

|         |      n |   n_promjena |   MAE_model |   MAE_perzist |   skill_% |   MAE_model_promjena |   MAE_perzist_promjena |   pokrivenost_10_90_% |
|:--------|-------:|-------------:|------------:|--------------:|----------:|---------------------:|-----------------------:|----------------------:|
| 2024/25 | 1267.0 |        435.0 |         7.9 |          11.5 |      31.6 |                 11.8 |                   22.5 |                  69.9 |
| 2025/26 | 1267.0 |        429.0 |         7.0 |          11.1 |      36.6 |                 10.9 |                   20.6 |                  68.7 |
| SVE     | 2534.0 |        864.0 |         7.4 |          11.3 |      34.1 |                 11.4 |                   21.6 |                  69.3 |

Najvažniji features (udio gain-a): pm_last 29%, pm_mean24 9%, doy_sin 6%, doy_cos 5%, pressure_mean 5%, wind_mean 4%, pm_mean72 4%, station 3%

## PM2_5, D+2

|         |      n |   n_promjena |   MAE_model |   MAE_perzist |   skill_% |   MAE_model_promjena |   MAE_perzist_promjena |   pokrivenost_10_90_% |
|:--------|-------:|-------------:|------------:|--------------:|----------:|---------------------:|-----------------------:|----------------------:|
| 2024/25 | 1260.0 |        560.0 |         8.8 |          13.5 |      34.9 |                 12.1 |                   23.4 |                  62.0 |
| 2025/26 | 1260.0 |        594.0 |         8.4 |          12.7 |      34.0 |                 11.6 |                   20.3 |                  62.8 |
| SVE     | 2520.0 |       1154.0 |         8.6 |          13.1 |      34.5 |                 11.9 |                   21.8 |                  62.4 |

Najvažniji features (udio gain-a): pm_max72 10%, pm_mean72 10%, pm_last 10%, doy_cos 9%, doy_sin 9%, pressure_mean 6%, wind_mean 5%, station 4%

# PM10 posebno za dan i veče

Target: CAMS prosjek dijela dana po ćeliji (07–17 h i 18–24 h lokalno). Test: zime (okt–mar, mjeseci grijanja), model treniran samo na prošlosti. „Dnevna prognoza“ je medijan modela v1 za cijeli dan, korišten kao prognoza dijela dana: to je ono što bot danas zapravo kaže. Perzistencija je zadnji poznati isti dio dana (dan D, veče D-1).

Ograda: CAMS ima jači dnevni ciklus od stanica (u oktobru 2026 CAMS precjenjuje veče, faktor ~0,67, a potcjenjuje dan, ~1,39), pa kalibracija na stanice mora ići posebno za svaki dio dana.

## D+1

| dio               |    n |   prosjek |   MAE_model |   MAE_dnevna_prognoza |   MAE_perzist |   kategorija_model_% |   kategorija_dnevna_% |   pokrivenost_10_90_% |
|:------------------|-----:|----------:|------------:|----------------------:|--------------:|---------------------:|----------------------:|----------------------:|
| danju (07–17 h)   | 2534 |      22.5 |         6.2 |                  10.6 |           7.9 |                 76.6 |                  65.2 |                  64.2 |
| navečer (18–24 h) | 2534 |      60.1 |        16.4 |                  29.4 |          24.3 |                 72.1 |                  42.6 |                  66.9 |

Najvažniji features: danju (07–17 h): pm_last 30%, pm_last6 9%, doy_sin 6%, pressure_mean 5%, doy_cos 4%; navečer (18–24 h): pm_max72 15%, pm_last 13%, doy_cos 11%, doy_sin 6%, pm_max24 5%

## D+2

| dio               |    n |   prosjek |   MAE_model |   MAE_dnevna_prognoza |   MAE_perzist |   kategorija_model_% |   kategorija_dnevna_% |   pokrivenost_10_90_% |
|:------------------|-----:|----------:|------------:|----------------------:|--------------:|---------------------:|----------------------:|----------------------:|
| danju (07–17 h)   | 2520 |      22.6 |         6.9 |                  10.5 |           9.4 |                 73.3 |                  64.6 |                  64.6 |
| navečer (18–24 h) | 2520 |      60.4 |        17.2 |                  30.6 |          25.2 |                 71.5 |                  40.6 |                  65.5 |

Najvažniji features: danju (07–17 h): pressure_mean 16%, pm_last 11%, doy_sin 9%, doy_cos 7%, wind_max 4%; navečer (18–24 h): pm_max72 17%, doy_cos 15%, doy_sin 8%, station 5%, pressure_mean 5%
